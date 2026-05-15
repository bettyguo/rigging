"""Centralised rig policy knobs.

The runtime's behaviour is *mostly* fixed by the spec — that's the
point. The few values that genuinely vary per deployment (default
contract lifetime, recursion caps, default verifier budget) live here
so they can be supplied at ``Rig`` construction time without scattering
constants across modules.

Implementations MAY add fields; the runtime treats unknown fields on
this model as a programmer error (extras are forbidden) to keep the
configuration surface honest.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class RigConfig(BaseModel):
    """Policy knobs that bound the rig's runtime behaviour."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    default_contract_lifetime: timedelta = timedelta(minutes=5)
    """Default lifetime stamped on contracts when the caller does not
    set ``expires`` explicitly. The spec recommends ≤ 1 hour; we ship a
    much tighter default so honest callers feel friction *before*
    misconfiguration."""

    max_contract_depth: Annotated[int, Field(ge=1, le=32)] = 8
    """Hard cap on contract nesting depth. Protects against runaway
    delegation. Distinct from :attr:`verification_recursion_cap`."""

    verification_recursion_cap: Annotated[int, Field(ge=1, le=8)] = 3
    """Per ``rig-contract-v0.md`` §3, the maximum depth of a
    verification chain. The leaf contract MUST carry
    ``trust_propagation: "sealed"``."""

    default_verifier_budget: Decimal = Decimal("0.05")
    """Budget allocated to a verifier sub-contract when the caller does
    not specify one explicitly. The unit is taken from the verifier's
    declared cost model."""

    enforce_execute_timeout: bool = True
    """If True, ``Rig.call`` wraps each callee's ``execute`` in an
    ``anyio.move_on_after`` scope whose deadline is the contract's
    ``expires``. Off only for tests that simulate a stalled callee."""
