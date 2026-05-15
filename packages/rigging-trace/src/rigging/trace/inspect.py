"""``rig trace inspect`` — pretty-print a trace and its blame chain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rigging.core.trace import RigSpanKind, TraceRecord
from rigging.trace.blame import extract_blame_chain

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Inspect rig traces.")


def _load_trace(path: Path) -> TraceRecord:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return TraceRecord.model_validate(raw)


@app.command("inspect")
def inspect_trace(
    trace_file: Annotated[Path, typer.Argument(help="Path to a JSON-serialised TraceRecord.")],
) -> None:
    """Pretty-print a trace and its blame chain."""
    console = Console()
    trace = _load_trace(trace_file)
    blame = extract_blame_chain(trace)

    console.print(
        Panel.fit(
            f"[bold]trace[/bold] {trace.trace_id}\n"
            f"started {trace.started.isoformat()} · {len(trace.spans)} spans",
            border_style="cyan",
        )
    )

    span_table = Table(title="Spans", show_lines=False)
    span_table.add_column("kind", style="bold")
    span_table.add_column("contract")
    span_table.add_column("caller → callee")
    span_table.add_column("capability")
    span_table.add_column("reason", style="red")
    span_table.add_column("verdict")

    for span in trace.spans:
        caller_callee = ""
        if span.caller and span.callee:
            caller_callee = f"{span.caller} → {span.callee}"
        elif span.caller:
            caller_callee = f"{span.caller} → ?"
        span_table.add_row(
            span.kind.value,
            (span.contract_id or "")[:12],
            caller_callee,
            span.capability or "",
            span.reason_code or "",
            span.verifier_verdict or "",
        )
    console.print(span_table)

    if blame is None:
        console.print("\n[green]no failure recorded.[/green]")
        return

    blame_table = Table(title="Blame chain (root → leaf)")
    blame_table.add_column("#", style="dim")
    blame_table.add_column("contract")
    blame_table.add_column("agent")
    for i, contract_id in enumerate(blame.contract_ids):
        agent = (
            blame.proximate_cause if i == len(blame.contract_ids) - 1 else ""
        )
        blame_table.add_row(str(i + 1), contract_id, agent)
    console.print(blame_table)

    console.print(
        f"\n[bold red]reason:[/bold red] {blame.reason_code}\n"
        f"[bold red]proximate cause:[/bold red] {blame.proximate_cause}"
    )


def _used() -> None:
    """Silence the ``RigSpanKind`` unused-import warning; we import it for
    side-effect on documented exports."""
    _ = RigSpanKind
