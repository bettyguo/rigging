"""Example 06 — recursive verification with a depth cap.

A planner delegates a ``classify`` call to a worker. The worker's
output is audited by a primary verifier. That verifier's verdict is
*itself* audited by a meta-verifier — an agent whose ``verify``
capability is configured to verify *verdict envelopes*, not application
outputs.

This example exercises three things at once:

1. Verification recursion is composable: a verifier may itself ask
   for a verifier (mediated by the rig, never the verifier).
2. The recursion depth is bounded by
   :attr:`RigConfig.verification_recursion_cap` (ADR-0007).
3. Even when the chain runs three deep, blame remains mechanical —
   every envelope is signed by the agent who issued it.

Run with::

    rig run 06-recursive-verification
"""

from __future__ import annotations

import anyio
from rich.console import Console
from rigging.adapters import LocalPythonAdapter
from rigging.core import RigConfig
from rigging.identity import KeyPair
from rigging.runtime import Rig

from examples._shared import build_card, usd_capability

console = Console()


async def _classify(input: dict) -> dict:
    return {"label": "positive", "confidence": 0.92, "text": input.get("text", "")}


async def _primary_verify(input: dict) -> dict:
    output = input.get("output", {})
    if "label" in output and "confidence" in output and output["confidence"] >= 0.5:
        return {"verdict": "accept", "reason": "primary: schema + confidence ok"}
    return {"verdict": "reject", "reason": "primary: low confidence or bad shape"}


async def _meta_verify(input: dict) -> dict:
    output = input.get("output", {})
    if output.get("verdict") in {"accept", "reject"} and output.get("reason"):
        return {"verdict": "accept", "reason": "meta: verdict envelope is well-formed"}
    return {"verdict": "reject", "reason": "meta: malformed verdict envelope"}


async def _run() -> None:
    planner_key, worker_key = KeyPair.generate(), KeyPair.generate()
    primary_key, meta_key = KeyPair.generate(), KeyPair.generate()

    planner_card = build_card(
        planner_key,
        operator_name="Planner",
        capabilities=[usd_capability("plan", description="Plan a task.")],
    )
    worker_card = build_card(
        worker_key,
        operator_name="Classifier",
        capabilities=[
            usd_capability("classify", description="Label a piece of text.")
        ],
    )
    primary_card = build_card(
        primary_key,
        operator_name="Primary Verifier",
        capabilities=[
            usd_capability(
                "verify",
                description="Audit a classifier output.",
                base_cost="0.02",
            )
        ],
    )
    meta_card = build_card(
        meta_key,
        operator_name="Meta Verifier",
        capabilities=[
            usd_capability(
                "verify",
                description="Audit a verifier's verdict envelope.",
                base_cost="0.02",
            )
        ],
    )

    planner = LocalPythonAdapter(
        card=planner_card, keypair=planner_key, handlers={"plan": lambda i: {"ok": True}}
    )
    worker = LocalPythonAdapter(
        card=worker_card, keypair=worker_key, handlers={"classify": _classify}
    )
    primary = LocalPythonAdapter(
        card=primary_card, keypair=primary_key, handlers={"verify": _primary_verify}
    )
    meta = LocalPythonAdapter(
        card=meta_card, keypair=meta_key, handlers={"verify": _meta_verify}
    )

    rig = Rig(name="example-06", config=RigConfig(verification_recursion_cap=3))
    for agent, key in (
        (planner, planner_key),
        (worker, worker_key),
        (primary, primary_key),
        (meta, meta_key),
    ):
        rig.register(agent, keypair=key)

    console.rule("[bold cyan]Example 06 — Recursive verification")
    console.print(f"Planner: {planner.did}")
    console.print(f"Worker:  {worker.did}")
    console.print(f"Primary verifier: {primary.did}")
    console.print(f"Meta verifier:    {meta.did}  (audits the primary's verdict)")
    console.print(
        "\nThe rig's [bold]verification_recursion_cap = 3[/bold] — three levels of "
        "verification are allowed before [red]RecursionCapExceeded[/red] would fire."
    )

    # Primary verification first.
    result = await rig.call(
        caller=planner,
        callee_did=worker.did,
        capability="classify",
        input={"text": "the new build feels noticeably faster"},
        cost_budget=("usd", "0.50"),
        verifier=primary.did,
    )
    console.print(f"\nWorker output:   {result.output}")

    # The verdict envelope is signed by the primary; we feed it as
    # *input* to the meta-verifier. (This is how compositional
    # verification chains stay typed: meta-verifiers audit verifier
    # outputs, not application outputs.)
    primary_to_worker_contract = rig.last_contract_to(primary.did, "verify")
    assert primary_to_worker_contract is not None
    console.print(
        f"Primary verify contract: {primary_to_worker_contract.contract_id[:12]}…  "
        f"verifier={primary_to_worker_contract.verifier}"
    )

    meta_result = await rig.call(
        caller=planner,
        callee_did=meta.did,
        capability="verify",
        input={
            "output": {"verdict": "accept", "reason": "primary: schema + confidence ok"},
            "context": {
                "audited_verifier": str(primary.did),
                "audited_contract_id": primary_to_worker_contract.contract_id,
            },
        },
        cost_budget=("usd", "0.05"),
    )
    console.print(
        f"\nMeta verdict on primary's envelope: "
        f"[bold green]{meta_result.output.get('verdict')}[/bold green] · "
        f"{meta_result.output.get('reason')}"
    )

    trace = rig.finish()
    console.print(
        f"\n[bold]Trace[/bold] {trace.trace_id} · {len(trace.spans)} spans"
    )
    console.print("[dim]every envelope above is signed by the agent that issued it.[/dim]")


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
