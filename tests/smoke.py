"""Quick smoke test — exercises the rig end-to-end with two local agents.

Not part of the formal test suite; this is a sanity check we can run by
hand during early Phase 3 to make sure imports, signing, and the
contract state machine all work.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import anyio

from rigging.core import AgentCard, Capability, CostModel, OperatorInfo
from rigging.adapters import LocalPythonAdapter
from rigging.identity import KeyPair, sign_card
from rigging.runtime import Rig


def make_card(keypair: KeyPair, *, name: str, capability_name: str) -> AgentCard:
    now = datetime.now(tz=UTC)
    unsigned = AgentCard(
        agent_id=keypair.did,
        public_key=base64.b64encode(keypair.public_bytes).decode("ascii"),
        operator=OperatorInfo(name=name),
        capabilities=[
            Capability(
                name=capability_name,
                description=f"Smoke-test capability {capability_name}",
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
            ),
        ],
        issued=now,
        expires=now + timedelta(hours=1),
    )
    return sign_card(unsigned, key=keypair)


async def main() -> None:
    planner_key = KeyPair.generate()
    worker_key = KeyPair.generate()

    planner_card = make_card(planner_key, name="Planner Inc.", capability_name="plan")
    worker_card = make_card(worker_key, name="Worker Inc.", capability_name="echo")

    async def echo(input: dict) -> dict:
        return {"echoed": input.get("text", "")}

    async def plan(input: dict) -> dict:
        return {"plan": f"echo {input.get('q', '?')}"}

    planner = LocalPythonAdapter(
        card=planner_card,
        keypair=planner_key,
        handlers={"plan": plan},
    )
    worker = LocalPythonAdapter(
        card=worker_card,
        keypair=worker_key,
        handlers={"echo": echo},
    )

    rig = Rig(name="smoke")
    rig.register(planner, keypair=planner_key)
    rig.register(worker, keypair=worker_key)

    result = await rig.call(
        caller=planner,
        callee_did=worker.did,
        capability="echo",
        input={"text": "hello rigging"},
        cost_budget=("usd", "0.05"),
        verifier="self",
    )
    print("OUTPUT:", result.output)
    print("COST:  ", result.cost)
    print("SIG:   ", result.signature[:40], "...")

    trace = rig.finish()
    print(f"\nTrace {trace.trace_id} produced {len(trace.spans)} spans:")
    for span in trace.spans:
        bits = [span.kind.value]
        if span.contract_id:
            bits.append(f"contract={span.contract_id[:8]}")
        if span.reason_code:
            bits.append(f"reason={span.reason_code}")
        print(" ", " ".join(bits))
    print("Blame chain:", trace.blame_chain)


if __name__ == "__main__":
    anyio.run(main)
