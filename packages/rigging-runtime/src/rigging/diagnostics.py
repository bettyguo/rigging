"""``rig doctor`` — environment + repo health check.

A read-only diagnostic. Surfaces three things, fast:

- Python / cryptography / pydantic / opentelemetry versions.
- Whether each rig package is importable, and from where.
- Whether the workspace looks like a rigging checkout (CONCEPT.md / specs / examples present).

No I/O beyond reading the local repo. No network. Exit code is the
number of failed checks.
"""

from __future__ import annotations

import importlib
import importlib.metadata as _md
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

_PACKAGES = (
    "rigging.core",
    "rigging.identity",
    "rigging.trace",
    "rigging.adapters",
    "rigging.runtime",
)
_DEPS = ("pydantic", "anyio", "cryptography", "opentelemetry-api", "typer", "rich")


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single doctor check.

    ``ok`` means the check passed. ``notes`` is one short string for
    the table — use the empty string when there is nothing to say.
    """

    name: str
    ok: bool
    notes: str = ""


def _check_python() -> CheckResult:
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 12)
    detail = f"{major}.{minor}.{sys.version_info[2]} on {platform.system()}"
    return CheckResult("python >= 3.12", ok, detail)


def _check_dep(name: str) -> CheckResult:
    try:
        version = _md.version(name)
    except _md.PackageNotFoundError:
        return CheckResult(f"dep · {name}", False, "missing")
    return CheckResult(f"dep · {name}", True, version)


def _check_package(name: str) -> CheckResult:
    try:
        mod = importlib.import_module(name)
    except ImportError as exc:
        return CheckResult(f"import · {name}", False, str(exc))
    where = getattr(mod, "__file__", None) or "<namespace>"
    return CheckResult(f"import · {name}", True, str(Path(where).parent.name))


def _check_workspace(root: Path) -> list[CheckResult]:
    must = ("CONCEPT.md", "README.md", "docs/spec", "examples", "packages")
    out: list[CheckResult] = []
    for rel in must:
        path = root / rel
        out.append(CheckResult(f"repo · {rel}", path.exists(), str(path)))
    return out


def collect_checks(cwd: Path | None = None) -> list[CheckResult]:
    """Run every diagnostic check. Pure; returns a list."""
    results: list[CheckResult] = [_check_python()]
    results.extend(_check_dep(dep) for dep in _DEPS)
    results.extend(_check_package(pkg) for pkg in _PACKAGES)
    results.extend(_check_workspace(Path(cwd or os.getcwd())))
    return results


def render(checks: list[CheckResult], *, console: Console | None = None) -> int:
    """Pretty-print ``checks`` to the console. Returns the number that failed."""
    console = console or Console()
    table = Table(title="rig doctor", show_lines=False)
    table.add_column("check", style="bold")
    table.add_column("status")
    table.add_column("notes", overflow="fold")
    failed = 0
    for c in checks:
        status = "[green]✓[/green]" if c.ok else "[red]✗[/red]"
        if not c.ok:
            failed += 1
        table.add_row(c.name, status, c.notes)
    console.print(table)
    if failed:
        console.print(f"[red]{failed} check(s) failed[/red]")
    else:
        console.print("[green]all checks passed.[/green]")
    return failed
