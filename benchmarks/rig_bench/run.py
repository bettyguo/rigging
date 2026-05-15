"""Rigging-Bench v0 — entry point and reporter."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from benchmarks.rig_bench.axes import blame, cost, expressiveness, fidelity, identity

console = Console()

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"


def run_suite(*, full: bool = False) -> int:
    """Run the benchmark and write reports. Returns shell exit code."""
    axes = [
        ("fidelity", "Capability-advertisement fidelity", fidelity.run),
        ("expressiveness", "Delegation-contract expressiveness", expressiveness.run),
        ("identity", "Identity propagation", identity.run),
        ("cost", "Cost-attribution accuracy", cost.run),
        ("blame", "Blame-resolution correctness", blame.run),
    ]
    started = time.time()
    results: dict[str, Any] = {}
    for key, label, fn in axes:
        t = time.time()
        try:
            result = fn(full=full)
        except Exception as exc:  # noqa: BLE001
            result = {"score": 0.0, "error": repr(exc)}
        result["duration_s"] = round(time.time() - t, 3)
        result["label"] = label
        results[key] = result

    elapsed = round(time.time() - started, 3)
    write_reports(results, full=full, elapsed=elapsed)
    print_summary(results, elapsed=elapsed)
    return 0


def print_summary(results: dict[str, Any], *, elapsed: float) -> None:
    table = Table(title=f"Rigging-Bench v0 (elapsed {elapsed}s)")
    table.add_column("Axis")
    table.add_column("Score", justify="right")
    table.add_column("Duration", justify="right")
    for key, info in results.items():
        score = info.get("score", 0)
        table.add_row(info.get("label", key), f"{score:.3f}", f"{info['duration_s']}s")
    console.print(table)


def write_reports(results: dict[str, Any], *, full: bool, elapsed: float) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "full" if full else "smoke"
    json_path = RESULTS_DIR / f"v0-reference-{suffix}.json"
    md_path = RESULTS_DIR / f"v0-reference-{suffix}.md"

    json_path.write_text(
        json.dumps(
            {
                "suite_version": "rigging-bench/v0",
                "implementation": "rigging-reference",
                "mode": suffix,
                "elapsed_s": elapsed,
                "axes": results,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    overall = sum(info.get("score", 0) for info in results.values()) / len(results)
    md_lines: list[str] = [
        "# Rigging-Bench v0 — reference results",
        "",
        f"Implementation: **rigging-reference** ({suffix} mode)\n",
        f"Elapsed: {elapsed}s\n",
        f"Overall: **{overall:.3f}**\n",
        "| Axis | Score | Duration |",
        "| --- | ---: | ---: |",
    ]
    for key, info in results.items():
        md_lines.append(
            f"| {info.get('label', key)} | {info.get('score', 0):.3f} | {info['duration_s']}s |"
        )
    md_lines.append("")
    md_lines.append(
        "Honesty: the v0 reference is not expected to score 1.0 across the board. "
        "Where weakness exists it is documented per-axis in the JSON output."
    )
    md_path.write_text("\n".join(md_lines), encoding="utf-8")


if __name__ == "__main__":
    run_suite(full=False)
