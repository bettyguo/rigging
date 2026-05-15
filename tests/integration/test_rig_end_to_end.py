"""End-to-end rig tests with :class:`LocalPythonAdapter`."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from rigging.adapters import LocalPythonAdapter
from rigging.core import AgentCard, Capability, CostModel, OperatorInfo
from rigging.core.errors import (
    BudgetOverrun,
    CapabilityMismatch,
    VerifierRejected,
)
from rigging.identity import KeyPair, sign_card
from rigging.runtime import Rig


def _cap(name: str) -> Capability:
    return Capability(
        name=name,
        description=f"cap {name}",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        cost_model=CostModel(
            unit="usd",
            base=Decimal("0.01"),
            per_input_unit=Decimal("0"),
            per_output_unit=Decimal("0"),
            input_unit="call",
            output_unit="call",
        ),
        verifier_kinds=["self"],
    )


def _build_card(keypair: KeyPair, *, capabilities: list[Capability]) -> AgentCard:
    now = datetime.now(tz=UTC)
    return sign_card(
        AgentCard(
            agent_id=keypair.did,
            public_key=base64.b64encode(keypair.public_bytes).decode("ascii"),
            operator=OperatorInfo(name="Test"),
            capabilities=capabilities,
            issued=now,
            expires=now + timedelta(hours=1),
        ),
        key=keypair,
    )


@pytest.mark.anyio
async def test_two_agent_call_succeeds() -> None:
    caller_key, callee_key = KeyPair.generate(), KeyPair.generate()
    caller_card = _build_card(caller_key, capabilities=[_cap("plan")])
    callee_card = _build_card(callee_key, capabilities=[_cap("echo")])

    async def echo(input: dict) -> dict:
        return {"echoed": input["text"]}

    caller = LocalPythonAdapter(
        card=caller_card, keypair=caller_key, handlers={"plan": lambda i: _yield({})}
    )
    callee = LocalPythonAdapter(
        card=callee_card, keypair=callee_key, handlers={"echo": echo}
    )

    rig = Rig()
    rig.register(caller, keypair=caller_key)
    rig.register(callee, keypair=callee_key)

    result = await rig.call(
        caller=caller,
        callee_did=callee.did,
        capability="echo",
        input={"text": "hi"},
        cost_budget=("usd", "0.05"),
    )
    assert result.output == {"echoed": "hi"}
    assert result.cost == Decimal("0.01")
    trace = rig.finish()
    assert trace.blame_chain is None
    assert any(s.kind.value == "rig.execute" for s in trace.spans)


async def _yield(value: dict) -> dict:
    return value


@pytest.mark.anyio
async def test_callee_missing_capability_raises() -> None:
    a_key, b_key = KeyPair.generate(), KeyPair.generate()
    a_card = _build_card(a_key, capabilities=[_cap("plan")])
    b_card = _build_card(b_key, capabilities=[_cap("echo")])

    a = LocalPythonAdapter(card=a_card, keypair=a_key, handlers={"plan": _yield})
    b = LocalPythonAdapter(card=b_card, keypair=b_key, handlers={"echo": _yield})

    rig = Rig()
    rig.register(a, keypair=a_key)
    rig.register(b, keypair=b_key)

    with pytest.raises(CapabilityMismatch):
        await rig.call(
            caller=a,
            callee_did=b.did,
            capability="something_else",
            input={},
            cost_budget=("usd", "0.05"),
        )


@pytest.mark.anyio
async def test_budget_overrun_localised_to_offender() -> None:
    a_key, b_key = KeyPair.generate(), KeyPair.generate()
    a_card = _build_card(a_key, capabilities=[_cap("plan")])
    b_card = _build_card(b_key, capabilities=[_cap("expensive")])

    a = LocalPythonAdapter(card=a_card, keypair=a_key, handlers={"plan": _yield})
    b = LocalPythonAdapter(
        card=b_card,
        keypair=b_key,
        handlers={"expensive": _yield},
        cost_fns={"expensive": lambda _i, _o: Decimal("1.00")},
    )

    rig = Rig()
    rig.register(a, keypair=a_key)
    rig.register(b, keypair=b_key)

    with pytest.raises(BudgetOverrun) as ei:
        await rig.call(
            caller=a,
            callee_did=b.did,
            capability="expensive",
            input={},
            cost_budget=("usd", "0.10"),
        )
    assert ei.value.contract_id is not None
    trace = rig.finish()
    # The trace should record the failure with reason=budget_overrun
    assert any(s.reason_code == "budget_overrun" for s in trace.spans)


@pytest.mark.anyio
async def test_verifier_rejection_produces_blame_chain() -> None:
    planner_key, worker_key, verifier_key = (
        KeyPair.generate() for _ in range(3)
    )
    planner_card = _build_card(planner_key, capabilities=[_cap("plan")])
    worker_card = _build_card(worker_key, capabilities=[_cap("solve")])
    verifier_card = _build_card(verifier_key, capabilities=[_cap("verify")])

    async def adversarial(input: dict) -> dict:
        del input
        return {"answer": "wrong"}

    async def verify(input: dict) -> dict:
        if input["output"].get("answer") != "right":
            return {"verdict": "reject", "reason": "wrong answer"}
        return {"verdict": "accept", "reason": "ok"}

    planner = LocalPythonAdapter(
        card=planner_card, keypair=planner_key, handlers={"plan": _yield}
    )
    worker = LocalPythonAdapter(
        card=worker_card, keypair=worker_key, handlers={"solve": adversarial}
    )
    verifier = LocalPythonAdapter(
        card=verifier_card, keypair=verifier_key, handlers={"verify": verify}
    )

    rig = Rig()
    for agent, key in (
        (planner, planner_key),
        (worker, worker_key),
        (verifier, verifier_key),
    ):
        rig.register(agent, keypair=key)

    with pytest.raises(VerifierRejected):
        await rig.call(
            caller=planner,
            callee_did=worker.did,
            capability="solve",
            input={},
            cost_budget=("usd", "0.05"),
            verifier=verifier.did,
        )
    trace = rig.finish()
    assert trace.blame_chain is not None
    assert trace.blame_chain.proximate_cause == str(worker.did)
    assert trace.blame_chain.reason_code == "verifier_rejected"
