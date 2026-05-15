"""Delegation contract model — the bill of lading between two agents.

Mirrors ``docs/spec/rig-contract-v0.md``. As with :mod:`agent_card`, the
signature is *not* verified at the type layer; that is the runtime's
job. The model enforces the structural invariants (expiry, budget unit,
parent linkage shape).
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from rigging.core.identity import DID, parse_did

ContractVersion = Literal["rigging/contract/v0"]
CostUnit = Literal["tokens", "usd", "wall_seconds"]
TrustPropagation = Literal["verified", "sealed"]

ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
CARD_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
"""Hashes embedded in contracts use the ``sha256:<hex>`` prefix form."""


class ReasonCode(str, Enum):
    """Reason codes for contract rejection or voiding.

    Mirrors the table in ``docs/spec/rig-contract-v0.md`` §6.
    """

    CAPABILITY_UNKNOWN = "capability_unknown"
    CAPABILITY_MISMATCH = "capability_mismatch"
    SCHEMA_INVALID = "schema_invalid"
    BUDGET_UNIT_MISMATCH = "budget_unit_mismatch"
    BUDGET_TOO_LOW = "budget_too_low"
    BUDGET_OVERRUN = "budget_overrun"
    EXPIRED = "expired"
    RECURSION_CAP_EXCEEDED = "recursion_cap_exceeded"
    CALLEE_UNREACHABLE = "callee_unreachable"
    VERIFIER_UNREACHABLE = "verifier_unreachable"
    VERIFIER_REJECTED = "verifier_rejected"
    OUTPUT_SCHEMA_INVALID = "output_schema_invalid"
    SIGNATURE_INVALID = "signature_invalid"
    PARENT_BUDGET_EXHAUSTED = "parent_budget_exhausted"
    POLICY_REJECTED = "policy_rejected"


class ContractState(str, Enum):
    """The lifecycle states of a contract.

    Transitions are defined in ``docs/spec/rig-contract-v0.md`` §5.
    """

    PROPOSED = "proposed"
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
    VOIDED = "voided"


class CostBudget(BaseModel):
    """A single-dimensional spending ceiling.

    Multi-dimensional budgets are explicitly deferred to v1; an operator
    needing both token and dollar limits must pick one for v0.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit: CostUnit
    max: Decimal

    @field_validator("max", mode="before")
    @classmethod
    def _decimal_from_string(cls, value: Any) -> Decimal:
        if isinstance(value, float):
            raise ValueError("budget values must be decimal-encoded strings, not floats")
        return Decimal(str(value))

    @model_validator(mode="after")
    def _non_negative(self) -> Self:
        if self.max < 0:
            raise ValueError("budget max must be non-negative")
        return self


class Contract(BaseModel):
    """A delegation contract.

    See ``docs/spec/rig-contract-v0.md`` for the normative semantics.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: ContractVersion = "rigging/contract/v0"
    contract_id: str
    """ULID. Lexicographically sortable by issuance time."""
    parent_id: str | None = None
    """Parent contract's ID if this is a sub-contract, else ``None``."""
    caller: DID
    callee: DID
    callee_card_hash: str
    """``sha256:<hex>`` of the JCS-canonical callee card at issuance."""
    capability: str
    input: dict[str, Any]
    """The input payload. Must validate against the capability's schema."""
    cost_budget: CostBudget
    verifier: str
    """Either ``"self"`` or a DID of a verifier agent."""
    trust_propagation: TrustPropagation = "verified"
    issued: datetime
    expires: datetime
    signature: str = ""
    """JWS by the caller. Empty until signed."""

    @field_validator("contract_id", "parent_id")
    @classmethod
    def _ulid_grammar(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ULID_RE.match(value):
            raise ValueError(f"contract_id must be a ULID, got {value!r}")
        return value

    @field_validator("callee_card_hash")
    @classmethod
    def _card_hash_grammar(cls, value: str) -> str:
        if not CARD_HASH_RE.match(value):
            raise ValueError(
                "callee_card_hash must look like 'sha256:<64-hex-chars>', "
                f"got {value!r}"
            )
        return value

    @field_validator("verifier")
    @classmethod
    def _verifier_form(cls, value: str) -> str:
        if value == "self":
            return value
        parse_did(value)  # validates grammar; raises on bad input
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.expires <= self.issued:
            raise ValueError("contract expires must be after issued")
        if self.caller == self.callee:
            raise ValueError("a contract's caller and callee must differ")
        return self
