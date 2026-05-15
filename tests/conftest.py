"""Pytest configuration shared by all test packages."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for sub in (
    "packages/rigging-core/src",
    "packages/rigging-identity/src",
    "packages/rigging-trace/src",
    "packages/rigging-adapters/src",
    "packages/rigging-runtime/src",
):
    sys.path.insert(0, str(ROOT / sub))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
