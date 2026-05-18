"""Unit tests for the ``rig doctor`` diagnostic module."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rigging.diagnostics import CheckResult, collect_checks, render


def test_collect_checks_returns_non_empty_list() -> None:
    checks = collect_checks()
    assert len(checks) >= 5
    assert all(isinstance(c, CheckResult) for c in checks)


def test_collect_checks_in_workspace_finds_repo_files(tmp_path: Path) -> None:
    """Workspace checks fail outside the repo and pass inside."""
    outside = collect_checks(cwd=tmp_path)
    names = {c.name: c for c in outside}
    # The repo-relative checks should all be missing in a tmp dir.
    assert names["repo · CONCEPT.md"].ok is False
    assert names["repo · README.md"].ok is False

    repo_root = Path(__file__).resolve().parents[2]
    inside = collect_checks(cwd=repo_root)
    names = {c.name: c for c in inside}
    assert names["repo · CONCEPT.md"].ok is True
    assert names["repo · README.md"].ok is True


def test_python_check_passes_under_3_12_or_later() -> None:
    """We require 3.12+; the runner is 3.12+ in CI, so this must pass."""
    checks = collect_checks()
    python_check = next(c for c in checks if c.name == "python >= 3.12")
    assert python_check.ok is True


def test_rigging_packages_all_importable() -> None:
    """Every rig package must be importable in a healthy install."""
    checks = collect_checks()
    import_checks = [c for c in checks if c.name.startswith("import · rigging.")]
    assert len(import_checks) == 5
    assert all(c.ok for c in import_checks)


def test_render_returns_failure_count(capsys: object) -> None:
    """``render`` returns the number of failed checks for the CLI exit code."""
    # capsys is unused — Console writes directly to stdout — but the
    # signature documents that the function takes a fixture in pytest.
    del capsys
    ok = [CheckResult("ok1", True, ""), CheckResult("ok2", True, "")]
    bad = [CheckResult("ok1", True, ""), CheckResult("bad1", False, "boom")]

    console = Console(record=True, width=80)
    assert render(ok, console=console) == 0
    assert render(bad, console=console) == 1


def test_dep_check_handles_unknown_package(monkeypatch: object) -> None:
    """``_check_dep`` returns ok=False for a missing package."""
    from rigging.diagnostics import _check_dep

    result = _check_dep("definitely-not-installed-xyz-9999")
    assert result.ok is False
    assert "missing" in result.notes
