"""Example 03 — adversarial subagent.

A worker agent has been configured to return obviously-wrong output.
The verifier catches it; the blame chain points at the worker.
"""

from __future__ import annotations

import anyio
from rich.console import Console

from rigging.adapters import LocalPythonAdapter
from rigging.core.errors import VerifierRejected
from rigging.identity import KeyPair
from rigging.runtime import Rig

from examples._shared import build_card, usd_capability

console = Console()


async def _adversarial_solve(input: dict) -> dict:
    # Returns the same answer regardless of the question. A naive
    # planner would happily accept this and move on.
    del input
    return {"answer": "42"}


async def _verify(input: dict) -> dict:
    output = input.get("output", {})
    answer = output.get("answer", "")
    # Ground-truth oracle for this example: the question's expected
    # answer is carried out-of-band via a synthetic check.
    expected = "hello, world"
    if answer != expected:
        return {
            "verdict": "reject",
            "reason": f"answer {answer!r} did not match expected {expected!r}",
        }
    return {"verdict": "accept", "reason": "ok"}


async def _run() -> None:
    planner_key, worker_key, verifier_key = (KeyPair.generate() for _ in range(3))

    planner_card = build_card(
        planner_key,
        operator_name="Planner Co.",
        capabilities=[usd_capability("plan", description="Plan a task.")],
    )
    worker_card = build_card(
        worker_key,
        operator_name="Adversarial Worker Inc.",
        capabilities=[
            usd_capability(
                "solve",
                description="Solve a question.",
                verifier_kinds=["ground_truth_v1"],
            )
        ],
    )
    verifier_card = build_card(
        verifier_key,
        operator_name="Verifier-A",
        capabilities=[
            usd_capability(
                "verify",
                description="Verify a callee output against ground truth.",
            )
        ],
    )

    planner = LocalPythonAdapter(
        card=planner_card,
        keypair=planner_key,
        handlers={"plan": lambda _input: _yield({"step": "solve"})},
    )
    worker = LocalPythonAdapter(
        card=worker_card,
        keypair=worker_key,
        handlers={"solve": _adversarial_solve},
    )
    verifier = LocalPythonAdapter(
        card=verifier_card,
        keypair=verifier_key,
        handlers={"verify": _verify},
    )

    rig = Rig(name="example-03")
    rig.register(planner, keypair=planner_key)
    rig.register(worker, keypair=worker_key)
    rig.register(verifier, keypair=verifier_key)

    console.rule("[bold cyan]Example 03 — Adversarial subagent")
    console.print(f"Planner:  {planner.did}")
    console.print(f"Worker:   {worker.did} (adversarial)")
    console.print(f"Verifier: {verifier.did}")

    try:
        await rig.call(
            caller=planner,
            callee_did=worker.did,
            capability="solve",
            input={"question": "greeting"},
            cost_budget=("usd", "0.05"),
            verifier=verifier.did,
        )
    except VerifierRejected as exc:
        console.print(f"\n[bold red]rejected:[/bold red] {exc.message}")

    trace = rig.finish()
    console.print(
        f"\n[bold]Trace[/bold] {trace.trace_id} ({len(trace.spans)} spans)"
    )
    for span in trace.spans:
        bits = [span.kind.value]
        if span.contract_id:
            bits.append(f"contract={span.contract_id[:8]}")
        if span.reason_code:
            bits.append(f"[red]reason={span.reason_code}[/red]")
        if span.verifier_verdict:
            bits.append(f"verdict={span.verifier_verdict}")
        console.print(" · " + " ".join(bits))

    if trace.blame_chain:
        console.print(
            f"\n[bold red]Blame chain:[/bold red] {' → '.join(trace.blame_chain.contract_ids)}"
        )
        console.print(
            f"[bold red]Proximate cause:[/bold red] {trace.blame_chain.proximate_cause}"
        )
        console.print(
            f"[bold red]Reason:[/bold red] {trace.blame_chain.reason_code}"
        )


async def _yield(value: dict) -> dict:
    return value


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
