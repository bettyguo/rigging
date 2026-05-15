"""Example 01 — Two-agent handoff.

A planner delegates one execution step to a worker. The smallest
useful rig.
"""

from __future__ import annotations

import anyio
from rich.console import Console

from rigging.adapters import LocalPythonAdapter
from rigging.identity import KeyPair
from rigging.runtime import Rig

from examples._shared import build_card, usd_capability

console = Console()


async def _plan(input: dict) -> dict:
    return {"step": f"echo {input.get('q', '?')}"}


async def _execute(input: dict) -> dict:
    text = input.get("step", "")
    suffix = text.removeprefix("echo ").strip()
    return {"result": suffix or "<empty>"}


async def _run() -> None:
    planner_key = KeyPair.generate()
    worker_key = KeyPair.generate()

    planner_card = build_card(
        planner_key,
        operator_name="Planner Inc.",
        capabilities=[usd_capability("plan", description="Make a one-step plan.")],
    )
    worker_card = build_card(
        worker_key,
        operator_name="Worker Inc.",
        capabilities=[usd_capability("execute", description="Execute a single step.")],
    )

    planner = LocalPythonAdapter(card=planner_card, keypair=planner_key, handlers={"plan": _plan})
    worker = LocalPythonAdapter(
        card=worker_card, keypair=worker_key, handlers={"execute": _execute}
    )

    rig = Rig(name="example-01")
    rig.register(planner, keypair=planner_key)
    rig.register(worker, keypair=worker_key)

    console.rule("[bold cyan]Example 01 — Two-agent handoff")
    console.print(f"Planner: {planner.did}")
    console.print(f"Worker:  {worker.did}")

    plan = await rig.call(
        caller=planner,
        callee_did=planner.did,
        capability="plan",
        input={"q": "say hello"},
        cost_budget=("usd", "0.05"),
    ) if False else None  # the planner step would be local to its harness
    del plan

    result = await rig.call(
        caller=planner,
        callee_did=worker.did,
        capability="execute",
        input={"step": "echo say hello"},
        cost_budget=("usd", "0.05"),
    )

    console.print(f"\n[bold]Worker output:[/bold] {result.output}")
    console.print(f"[bold]Cost:[/bold]          ${result.cost}")

    trace = rig.finish()
    console.print(f"\n[bold]Trace[/bold] {trace.trace_id}  ({len(trace.spans)} spans)")
    for span in trace.spans:
        console.print(f"  · {span.kind.value}  contract={span.contract_id[:8] if span.contract_id else '-'}")


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
