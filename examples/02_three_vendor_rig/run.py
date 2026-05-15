"""Example 02 — three-vendor rig.

Three independently-operated agents collaborate on one task. The
example uses :class:`LocalPythonAdapter` for determinism; in a real
deployment each agent would be backed by a different harness/model.
"""

from __future__ import annotations

import anyio
from rich.console import Console

from rigging.adapters import LocalPythonAdapter
from rigging.identity import KeyPair
from rigging.runtime import Rig

from examples._shared import build_card, usd_capability

console = Console()


async def _make_plan(input: dict) -> dict:
    task = input.get("task", "")
    return {
        "subtasks": [
            f"draft a {task} implementation",
            f"review the {task} implementation",
        ]
    }


async def _write_code(input: dict) -> dict:
    spec = input.get("spec", "")
    return {
        "code": (
            "def hello(name):\n"
            "    return f'hello, {name}'  # impl spec: " + spec
        )
    }


async def _review(input: dict) -> dict:
    code = input.get("code", "")
    return {
        "comments": [
            "naming is clear",
            "consider docstring" if '"""' not in code else "docstring present",
        ],
        "approved": True,
    }


async def _run() -> None:
    planner_key, coder_key, reviewer_key = (KeyPair.generate() for _ in range(3))

    planner_card = build_card(
        planner_key,
        operator_name="Anthropic-shaped Planner",
        capabilities=[usd_capability("make_plan", description="Plan a coding task.")],
    )
    coder_card = build_card(
        coder_key,
        operator_name="OpenAI-shaped Coder",
        capabilities=[
            usd_capability(
                "write_code",
                description="Write Python code from a brief spec.",
                base_cost="0.02",
            )
        ],
    )
    reviewer_card = build_card(
        reviewer_key,
        operator_name="Local-Ollama Reviewer",
        capabilities=[
            usd_capability(
                "review_code",
                description="Review a code snippet and produce comments.",
            )
        ],
    )

    planner = LocalPythonAdapter(
        card=planner_card, keypair=planner_key, handlers={"make_plan": _make_plan}
    )
    coder = LocalPythonAdapter(
        card=coder_card, keypair=coder_key, handlers={"write_code": _write_code}
    )
    reviewer = LocalPythonAdapter(
        card=reviewer_card, keypair=reviewer_key, handlers={"review_code": _review}
    )

    rig = Rig(name="example-02")
    for agent, key in (
        (planner, planner_key),
        (coder, coder_key),
        (reviewer, reviewer_key),
    ):
        rig.register(agent, keypair=key)

    console.rule("[bold cyan]Example 02 — Three-vendor rig")
    code_result = await rig.call(
        caller=planner,
        callee_did=coder.did,
        capability="write_code",
        input={"spec": "greet a user by name"},
        cost_budget=("usd", "0.10"),
    )
    review_result = await rig.call(
        caller=planner,
        callee_did=reviewer.did,
        capability="review_code",
        input={"code": code_result.output["code"]},
        cost_budget=("usd", "0.05"),
    )

    console.print("[bold]Code:[/bold]")
    console.print(code_result.output["code"])
    console.print(f"[bold]Review:[/bold] {review_result.output}")
    console.print(
        f"\n[bold]Costs:[/bold] coder=${code_result.cost}  reviewer=${review_result.cost}"
    )

    trace = rig.finish()
    console.print(
        f"\n[bold]Trace[/bold] {trace.trace_id} ({len(trace.spans)} spans)"
    )


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
