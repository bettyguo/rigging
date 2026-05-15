"""Example 04 — cost attribution under budget overrun.

Three-agent chain A → B → C, each with its own carved-out budget. C
deliberately overruns its $0.20 budget by reporting a $0.30 cost. The
overrun:

- raises ``BudgetOverrun`` against C's contract,
- emits a ``rig.contract.void`` span with ``reason_code=budget_overrun``,
- leaves A's parent budget untouched.

This is what makes ADR-0006 ("explicit budget propagation") concrete.

The example uses :meth:`Rig.last_contract_to` to look up the A->B
contract so it can be passed as ``parent_contract`` when B issues its
own sub-contract to C.
"""

from __future__ import annotations

from decimal import Decimal

import anyio
from rich.console import Console

from rigging.adapters import LocalPythonAdapter
from rigging.core.errors import BudgetOverrun
from rigging.identity import KeyPair
from rigging.runtime import Rig

from examples._shared import build_card, usd_capability

console = Console()


async def _b_step(input: dict) -> dict:
    return {"forwarded": input}


async def _c_overrun(input: dict) -> dict:
    return {"answer": input.get("q", "?")}


async def _run() -> None:
    a_key, b_key, c_key = (KeyPair.generate() for _ in range(3))
    a_card = build_card(
        a_key,
        operator_name="A Inc.",
        capabilities=[usd_capability("a_step", description="A's step.")],
    )
    b_card = build_card(
        b_key,
        operator_name="B Inc.",
        capabilities=[usd_capability("b_step", description="B's step.")],
    )
    c_card = build_card(
        c_key,
        operator_name="C Inc.",
        capabilities=[
            usd_capability(
                "c_step",
                description="C's step (will overspend).",
                base_cost="0.01",
            )
        ],
    )

    c = LocalPythonAdapter(
        card=c_card,
        keypair=c_key,
        handlers={"c_step": _c_overrun},
        cost_fns={"c_step": lambda _i, _o: Decimal("0.30")},
    )
    b = LocalPythonAdapter(card=b_card, keypair=b_key, handlers={"b_step": _b_step})
    a = LocalPythonAdapter(
        card=a_card,
        keypair=a_key,
        handlers={"a_step": lambda _i: {"ok": True}},
    )

    rig = Rig(name="example-04")
    rig.register(a, keypair=a_key)
    rig.register(b, keypair=b_key)
    rig.register(c, keypair=c_key)

    console.rule("[bold cyan]Example 04 — Cost attribution")

    # Step 1: A → B with $0.50.
    await rig.call(
        caller=a,
        callee_did=b.did,
        capability="b_step",
        input={"task": "delegate to c"},
        cost_budget=("usd", "0.50"),
    )
    a_to_b = rig.last_contract_to(b.did, "b_step")
    assert a_to_b is not None
    console.print(f"A->B contract:    {a_to_b.contract_id}  budget=${a_to_b.cost_budget.max}")

    # Step 2: B → C with $0.20 carved from A->B's $0.50 (minus $0.01 spent).
    try:
        await rig.call(
            caller=b,
            callee_did=c.did,
            capability="c_step",
            input={"q": "hello"},
            cost_budget=("usd", "0.20"),
            parent_contract=a_to_b,
        )
    except BudgetOverrun as exc:
        console.print(
            f"\n[bold red]budget overrun:[/bold red] {exc.message}\n"
            f"[bold]contract:[/bold] {exc.contract_id}"
        )

    console.print(
        "\nA->B's budget is unaffected: only B's own spending counts against it.\n"
        "C's overrun is local — B sees it; A doesn't pay for it."
    )

    trace = rig.finish()
    console.print(
        f"\n[bold]Trace[/bold] {trace.trace_id} ({len(trace.spans)} spans)"
    )
    for span in trace.spans:
        bits = [span.kind.value]
        if span.contract_id:
            bits.append(f"contract={span.contract_id[:8]}")
        if span.cost_value is not None:
            bits.append(f"cost=${span.cost_value}")
        if span.reason_code:
            bits.append(f"[red]reason={span.reason_code}[/red]")
        console.print(" · " + " ".join(bits))


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
