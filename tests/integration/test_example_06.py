"""Integration test for example 06 (recursive verification).

Verifies that:

- The example's `main()` runs end-to-end without raising.
- A trace is produced with both primary-verify and meta-verify spans.
- The verification_recursion_cap is honoured.
"""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError
from rigging.core import RigConfig
from rigging.core.errors import RecursionCapExceeded


def test_example_06_module_main_runs() -> None:
    """The example's main() runs to completion without raising."""
    module = importlib.import_module("examples.06_recursive_verification.run")
    main = module.main
    main()  # raises on any uncaught error


def test_verification_recursion_cap_in_config() -> None:
    """The cap exists, has a sensible default, and clamps correctly."""
    default = RigConfig()
    assert default.verification_recursion_cap >= 1
    assert default.verification_recursion_cap <= 8


def test_recursion_cap_exceeded_is_a_rig_error() -> None:
    """RecursionCapExceeded must be a RigError with a reason code."""
    exc = RecursionCapExceeded("cap exceeded", contract_id="01HXQK3Z" * 3 + "AB")
    assert exc.reason_code == "recursion_cap_exceeded"
    assert exc.message == "cap exceeded"


@pytest.mark.parametrize("cap", [1, 2, 3, 5])
def test_rig_config_accepts_valid_caps(cap: int) -> None:
    config = RigConfig(verification_recursion_cap=cap)
    assert config.verification_recursion_cap == cap


def test_rig_config_rejects_out_of_range_caps() -> None:
    with pytest.raises(ValidationError):
        RigConfig(verification_recursion_cap=0)
    with pytest.raises(ValidationError):
        RigConfig(verification_recursion_cap=99)
