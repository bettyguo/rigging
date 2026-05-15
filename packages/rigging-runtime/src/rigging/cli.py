"""``rig`` — the unified rig CLI entry point.

Mounts the identity, trace, run, bench, and spec subcommand groups.
The packages themselves own most of the CLI surface; this module is
the assembly layer.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from rigging.core.agent_card import AgentCard
from rigging.core.contract import Contract
from rigging.core.errors import RigError
from rigging.identity.cli import app as identity_app
from rigging.trace.inspect import app as trace_app

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="rig — the typed, trust-bearing coupling layer for harnessed agents.",
)
app.add_typer(identity_app, name="identity")
app.add_typer(trace_app, name="trace")

console = Console()

KNOWN_EXAMPLES: dict[str, str] = {
    "01-two-agent-handoff": "examples.01_two_agent_handoff.run",
    "02-three-vendor-rig": "examples.02_three_vendor_rig.run",
    "03-adversarial-subagent": "examples.03_adversarial_subagent.run",
    "04-cost-attribution": "examples.04_cost_attribution.run",
    "05-vote-ensemble": "examples.05_vote_ensemble.run",
}


@app.command("run")
def run_example(
    example: Annotated[str, typer.Argument(help="Example name (e.g. 03-adversarial-subagent).")],
) -> None:
    """Run a built-in example end-to-end."""
    target = KNOWN_EXAMPLES.get(example)
    if target is None:
        console.print(f"[red]unknown example:[/red] {example}")
        console.print(f"  known: {', '.join(sorted(KNOWN_EXAMPLES))}")
        raise typer.Exit(code=2)
    try:
        module = importlib.import_module(target)
    except ImportError as exc:
        console.print(f"[red]could not import {target}:[/red] {exc}")
        raise typer.Exit(code=3) from exc
    main_fn = getattr(module, "main", None)
    if main_fn is None or not callable(main_fn):
        console.print(f"[red]{target} has no main() entry point[/red]")
        raise typer.Exit(code=3)
    try:
        main_fn()
    except RigError as exc:
        console.print(f"[red]rig error:[/red] {exc.message}")
        if exc.contract_id:
            console.print(f"  contract: {exc.contract_id}")
        raise typer.Exit(code=4) from exc


@app.command("bench")
def bench(
    full: Annotated[bool, typer.Option("--full", help="Run the full suite (slower).")] = False,
) -> None:
    """Run Rigging-Bench v0 against the reference implementation."""
    try:
        bench_module = importlib.import_module("benchmarks.rig_bench.run")
    except ImportError as exc:
        console.print(f"[red]benchmarks not available:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    run_suite = getattr(bench_module, "run_suite", None)
    if run_suite is None or not callable(run_suite):
        console.print("[red]bench module missing run_suite entry point[/red]")
        raise typer.Exit(code=3)
    exit_code = run_suite(full=full)
    raise typer.Exit(code=exit_code)


@app.command("spec")
def spec_validate(
    document: Annotated[Path, typer.Argument(help="Path to a card or contract JSON file.")],
    kind: Annotated[
        str,
        typer.Option("--kind", help="One of 'card' or 'contract'. Inferred if omitted."),
    ] = "auto",
) -> None:
    """Validate a JSON document against the spec models."""
    raw = json.loads(document.read_text(encoding="utf-8"))
    resolved_kind = kind
    if kind == "auto":
        version = raw.get("card_version") or raw.get("contract_version")
        if not isinstance(version, str):
            console.print("[red]could not infer kind: missing version field[/red]")
            raise typer.Exit(code=2)
        resolved_kind = "card" if "agent-card" in version else "contract"
    if resolved_kind == "card":
        AgentCard.model_validate(raw)
        console.print("[green]valid agent card[/green]")
    elif resolved_kind == "contract":
        Contract.model_validate(raw)
        console.print("[green]valid contract[/green]")
    else:
        console.print(f"[red]unknown kind:[/red] {resolved_kind}")
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
