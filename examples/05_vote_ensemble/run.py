"""Example 05 — vote-ensemble verifier.

Demonstrates compositional verification: a coordinator agent fans a
verify call out to three constituent verifiers, tallies, and returns
the majority verdict. The runtime knows nothing about voting — it sees
the ensemble as just another verifier.
"""

from __future__ import annotations

import anyio
from rich.console import Console

from rigging.adapters import LocalPythonAdapter, VoteEnsembleVerifier
from rigging.core.errors import VerifierRejected
from rigging.identity import KeyPair
from rigging.runtime import Rig

from examples._shared import build_card, usd_capability

console = Console()


async def _solve_wrong(input: dict) -> dict:
    del input
    return {"answer": "42"}


def _make_verifier(label: str, *, accept: bool) -> tuple[LocalPythonAdapter, KeyPair]:
    """A verifier whose verdict is hard-coded for clarity in the demo."""
    def verify(input: dict) -> dict:
        if accept:
            return {"verdict": "accept", "reason": f"{label} accepts"}
        return {"verdict": "reject", "reason": f"{label} rejects: bad answer"}
    key = KeyPair.generate()
    card = build_card(
        key,
        operator_name=f"Verifier-{label}",
        capabilities=[usd_capability("verify", description=f"{label} verifier.")],
    )
    return LocalPythonAdapter(card=card, keypair=key, handlers={"verify": verify}), key


async def _run() -> None:
    planner_key = KeyPair.generate()
    worker_key = KeyPair.generate()
    coord_key = KeyPair.generate()

    planner_card = build_card(
        planner_key,
        operator_name="Planner",
        capabilities=[usd_capability("plan", description="Plan a task.")],
    )
    worker_card = build_card(
        worker_key,
        operator_name="Adversarial Worker",
        capabilities=[
            usd_capability(
                "solve",
                description="Solve a question (always returns 42).",
            )
        ],
    )
    coordinator_card = build_card(
        coord_key,
        operator_name="Vote Coordinator",
        capabilities=[
            usd_capability(
                "verify",
                description="Majority vote across constituent verifiers.",
                # The ensemble's base cost covers the three constituents'
                # base costs (3 × $0.01) plus a small coordination fee.
                base_cost="0.10",
            )
        ],
    )

    planner = LocalPythonAdapter(
        card=planner_card, keypair=planner_key, handlers={"plan": lambda i: {"step": "x"}}
    )
    worker = LocalPythonAdapter(
        card=worker_card, keypair=worker_key, handlers={"solve": _solve_wrong}
    )
    v_a, ka = _make_verifier("A", accept=False)
    v_b, kb = _make_verifier("B", accept=False)
    v_c, kc = _make_verifier("C", accept=True)

    rig = Rig(name="example-05")
    for agent, key in (
        (planner, planner_key),
        (worker, worker_key),
        (v_a, ka),
        (v_b, kb),
        (v_c, kc),
    ):
        rig.register(agent, keypair=key)

    coordinator = VoteEnsembleVerifier(
        card=coordinator_card,
        keypair=coord_key,
        rig=rig,
        constituents=[v_a.did, v_b.did, v_c.did],
    )
    rig.register(coordinator, keypair=coord_key)

    console.rule("[bold cyan]Example 05 — Vote ensemble")
    console.print(f"Planner:     {planner.did}")
    console.print(f"Worker:      {worker.did} (adversarial)")
    console.print(f"Coordinator: {coordinator.did} (votes across A,B,C)")
    console.print(f"  Verifier A: {v_a.did} (rejects)")
    console.print(f"  Verifier B: {v_b.did} (rejects)")
    console.print(f"  Verifier C: {v_c.did} (accepts)")

    try:
        await rig.call(
            caller=planner,
            callee_did=worker.did,
            capability="solve",
            input={"question": "anything"},
            # Budget covers worker cost + ensemble verification (which
            # internally pays for 3 constituent verifiers).
            cost_budget=("usd", "0.50"),
            verifier=coordinator.did,
        )
        console.print("\n[bold green]unexpectedly accepted[/bold green]")
    except VerifierRejected as exc:
        console.print(f"\n[bold red]ensemble rejected:[/bold red] {exc.message}")

    trace = rig.finish()
    console.print(
        f"\n[bold]Trace[/bold] {trace.trace_id} ({len(trace.spans)} spans)"
    )
    if trace.blame_chain:
        console.print(
            f"[bold red]Proximate cause:[/bold red] {trace.blame_chain.proximate_cause}"
        )
        console.print(
            f"[bold red]Reason:[/bold red] {trace.blame_chain.reason_code}"
        )


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
