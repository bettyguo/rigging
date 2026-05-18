"""``rig`` — the unified rig CLI entry point.

Mounts the identity, trace, run, bench, spec, card, contract, and doctor
subcommand groups. The packages themselves own most of the CLI surface;
this module is the assembly layer.
"""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rigging.core.agent_card import AgentCard
from rigging.core.contract import Contract, ContractState
from rigging.core.errors import RigError
from rigging.diagnostics import collect_checks, render
from rigging.identity.cards import card_hash, verify_card
from rigging.identity.cli import app as identity_app
from rigging.trace.inspect import app as trace_app

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="rig — the typed, trust-bearing coupling layer for harnessed agents.",
)
app.add_typer(identity_app, name="identity")
app.add_typer(trace_app, name="trace")

card_app = typer.Typer(
    no_args_is_help=True, add_completion=False, help="Inspect signed agent cards."
)
contract_app = typer.Typer(
    no_args_is_help=True, add_completion=False, help="Inspect signed delegation contracts."
)
app.add_typer(card_app, name="card")
app.add_typer(contract_app, name="contract")

console = Console()

KNOWN_EXAMPLES: dict[str, str] = {
    "01-two-agent-handoff": "examples.01_two_agent_handoff.run",
    "02-three-vendor-rig": "examples.02_three_vendor_rig.run",
    "03-adversarial-subagent": "examples.03_adversarial_subagent.run",
    "04-cost-attribution": "examples.04_cost_attribution.run",
    "05-vote-ensemble": "examples.05_vote_ensemble.run",
    "06-recursive-verification": "examples.06_recursive_verification.run",
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


@app.command("examples")
def list_examples() -> None:
    """List every built-in example."""
    table = Table(title="Built-in examples", show_lines=False)
    table.add_column("name", style="bold cyan")
    table.add_column("module", style="dim")
    for name, target in sorted(KNOWN_EXAMPLES.items()):
        table.add_row(name, target)
    console.print(table)
    console.print(f"\nRun with: [bold]rig run <name>[/bold]   ({len(KNOWN_EXAMPLES)} total)")


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


@app.command("doctor")
def doctor() -> None:
    """Audit the local environment for rigging compatibility."""
    failed = render(collect_checks())
    if failed:
        raise typer.Exit(code=1)


@app.command("version")
def version() -> None:
    """Print the installed ``rigging`` package version."""
    try:
        import importlib.metadata as _md

        v = _md.version("rigging")
    except _md.PackageNotFoundError:
        v = "unknown (editable install? check pyproject.toml)"
    console.print(f"rigging {v}")


@card_app.command("show")
def card_show(
    card_file: Annotated[Path, typer.Argument(help="Path to a JSON agent card.")],
    verify: Annotated[
        bool,
        typer.Option("--verify/--no-verify", help="Verify the JWS signature."),
    ] = True,
) -> None:
    """Pretty-print an agent card; verify its signature by default."""
    raw = json.loads(card_file.read_text(encoding="utf-8"))
    card = AgentCard.model_validate(raw)
    if verify:
        verify_card(card)
    header = (
        f"[bold]{card.operator.name}[/bold]\n"
        f"agent_id : {card.agent_id}\n"
        f"hash     : {card_hash(card)}\n"
        f"issued   : {card.issued.isoformat()}\n"
        f"expires  : {card.expires.isoformat()}"
    )
    console.print(Panel.fit(header, border_style="cyan", title="agent card"))
    table = Table(title=f"capabilities ({len(card.capabilities)})", show_lines=False)
    table.add_column("name", style="bold")
    table.add_column("cost / call")
    table.add_column("verifier kinds", style="dim")
    table.add_column("description", overflow="fold")
    for cap in card.capabilities:
        table.add_row(
            cap.name,
            f"{cap.cost_model.base} {cap.cost_model.unit}",
            ", ".join(cap.verifier_kinds),
            cap.description,
        )
    console.print(table)
    if verify:
        console.print("[green]signature ✓[/green]")


@contract_app.command("show")
def contract_show(
    contract_file: Annotated[Path, typer.Argument(help="Path to a JSON contract.")],
) -> None:
    """Pretty-print a delegation contract."""
    raw = json.loads(contract_file.read_text(encoding="utf-8"))
    contract = Contract.model_validate(raw)
    now = datetime.now(tz=UTC)
    if now >= contract.expires:
        state = ContractState.VOIDED.value
        state_style = "red"
        state_note = "expired"
    else:
        state = ContractState.PROPOSED.value
        state_style = "yellow"
        state_note = "not yet observed"
    header = (
        f"[bold]contract[/bold] {contract.contract_id}\n"
        f"caller   : {contract.caller}\n"
        f"callee   : {contract.callee}\n"
        f"capability: {contract.capability}\n"
        f"budget   : {contract.cost_budget.max} {contract.cost_budget.unit}\n"
        f"verifier : {contract.verifier}\n"
        f"trust    : {contract.trust_propagation}\n"
        f"issued   : {contract.issued.isoformat()}\n"
        f"expires  : {contract.expires.isoformat()}\n"
        f"state    : [{state_style}]{state}[/] ({state_note})"
    )
    console.print(Panel.fit(header, border_style="cyan", title="delegation contract"))
    if contract.parent_id:
        console.print(f"  parent contract: [dim]{contract.parent_id}[/dim]")
    if contract.signature:
        console.print(
            f"  signature: [green]present[/green] ({len(contract.signature)} chars)"
        )
    else:
        console.print("  signature: [red]missing[/red]")


if __name__ == "__main__":
    app()
