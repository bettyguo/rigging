"""Axis 5 — blame-resolution correctness.

For each scenario we know which DID is the ground-truth offender. We
run the rig, extract the blame chain, and compare. Precision/recall
collapses to F1 when each scenario has a single offender.
"""

from __future__ import annotations

from decimal import Decimal

import anyio

from rigging.core.errors import BudgetOverrun, RigError, VerifierRejected
from rigging.runtime import Rig

from benchmarks.rig_bench.harness import make_agent, usd_capability


def run(full: bool = False) -> dict[str, object]:  # noqa: ARG001
    return anyio.run(_run_axis)


async def _run_axis() -> dict[str, object]:
    scenarios = [
        ("adversarial_leaf", await _scenario_leaf()),
        ("budget_overrun_leaf", await _scenario_overrun()),
    ]
    correct = sum(1 for _, hit in scenarios if hit)
    score = correct / len(scenarios)
    return {
        "score": score,
        "scenarios": {name: hit for name, hit in scenarios},
        "notes": "v0 covers leaf-level failure modes; mid-chain attribution is on the v1 roadmap.",
    }


async def _scenario_leaf() -> bool:
    rig = Rig()
    planner, planner_key = make_agent(
        operator="Planner", capabilities=[usd_capability("plan")], handlers={"plan": _yield}
    )

    async def bad_solve(_i: dict) -> dict:
        return {"answer": "wrong"}

    async def verify(input: dict) -> dict:
        if input["output"].get("answer") != "right":
            return {"verdict": "reject", "reason": "wrong"}
        return {"verdict": "accept"}

    worker, worker_key = make_agent(
        operator="Worker", capabilities=[usd_capability("solve")], handlers={"solve": bad_solve}
    )
    verifier, verifier_key = make_agent(
        operator="Verifier", capabilities=[usd_capability("verify")], handlers={"verify": verify}
    )
    rig.register(planner, keypair=planner_key)
    rig.register(worker, keypair=worker_key)
    rig.register(verifier, keypair=verifier_key)
    try:
        await rig.call(
            caller=planner, callee_did=worker.did, capability="solve",
            input={}, cost_budget=("usd", "0.05"), verifier=verifier.did,
        )
        return False
    except VerifierRejected:
        pass
    trace = rig.finish()
    if trace.blame_chain is None:
        return False
    return trace.blame_chain.proximate_cause == str(worker.did)


async def _scenario_overrun() -> bool:
    rig = Rig()
    caller, caller_key = make_agent(
        operator="Caller", capabilities=[usd_capability("plan")], handlers={"plan": _yield}
    )
    expensive, expensive_key = make_agent(
        operator="Expensive",
        capabilities=[usd_capability("work", base="0.01")],
        handlers={"work": _yield},
        cost_fns={"work": lambda _i, _o: Decimal("1.00")},
    )
    rig.register(caller, keypair=caller_key)
    rig.register(expensive, keypair=expensive_key)
    try:
        await rig.call(
            caller=caller, callee_did=expensive.did, capability="work",
            input={}, cost_budget=("usd", "0.05"),
        )
        return False
    except (BudgetOverrun, RigError):
        pass
    trace = rig.finish()
    if trace.blame_chain is None:
        return False
    return trace.blame_chain.proximate_cause == str(expensive.did)


async def _yield(value: dict) -> dict:
    return value
