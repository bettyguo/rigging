"""Axis 4 — cost-attribution accuracy.

Sets up a chain A → B → C with synthetic cost functions that produce
known totals, runs the rig, then compares the rig's ledger to ground
truth. The score is ``1 - L1_error / total_ground_truth``.
"""

from __future__ import annotations

from decimal import Decimal

import anyio

from rigging.runtime import Rig

from benchmarks.rig_bench.harness import make_agent, usd_capability


def run(full: bool = False) -> dict[str, object]:  # noqa: ARG001
    return anyio.run(_run_axis)


async def _run_axis() -> dict[str, object]:
    ground_truth = {
        "a_b": Decimal("0.10"),
        "b_c": Decimal("0.20"),
    }

    a, a_key = make_agent(operator="A", capabilities=[usd_capability("step")], handlers={"step": _yield})
    b, b_key = make_agent(
        operator="B",
        capabilities=[usd_capability("step", base="0.10")],
        handlers={"step": _yield},
        cost_fns={"step": lambda _i, _o: ground_truth["a_b"]},
    )
    c, c_key = make_agent(
        operator="C",
        capabilities=[usd_capability("step", base="0.20")],
        handlers={"step": _yield},
        cost_fns={"step": lambda _i, _o: ground_truth["b_c"]},
    )

    rig = Rig()
    rig.register(a, keypair=a_key)
    rig.register(b, keypair=b_key)
    rig.register(c, keypair=c_key)

    a_to_b = await rig.call(
        caller=a, callee_did=b.did, capability="step",
        input={}, cost_budget=("usd", "0.50"),
    )
    b_to_c = await rig.call(
        caller=b, callee_did=c.did, capability="step",
        input={}, cost_budget=("usd", "0.30"),
    )

    measured = {
        "a_b": a_to_b.cost,
        "b_c": b_to_c.cost,
    }
    error = sum(abs(measured[k] - ground_truth[k]) for k in ground_truth)
    total = sum(ground_truth.values())
    score = float(max(Decimal("0"), Decimal("1") - error / total))
    return {
        "score": score,
        "ground_truth": {k: str(v) for k, v in ground_truth.items()},
        "measured": {k: str(v) for k, v in measured.items()},
        "l1_error": str(error),
    }


async def _yield(value: dict) -> dict:
    return value
