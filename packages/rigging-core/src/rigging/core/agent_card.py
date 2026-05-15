"""Agent card model — the producer-side advertisement of an agent.

Mirrors ``docs/spec/agent-card-v0.md``. Cross-field invariants (DID
matches public key hash, expires > issued, capability names unique) are
enforced via Pydantic ``model_validator`` decorators.

The signature itself is *not* verified here — that requires the
``rigging-identity`` package's cryptographic engine. ``AgentCard``
guarantees structural validity; an unsigned card may still pass through
this layer. The runtime calls ``rigging.identity.verify_card`` before
trusting it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from rigging.core.identity import DID

CAPABILITY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

CardVersion = Literal["rigging/agent-card/v0"]
CostUnit = Literal["tokens", "usd", "wall_seconds"]
VerifierKind = Annotated[str, StringConstraints(min_length=1, max_length=128)]


def _decimal_string(value: str | Decimal) -> Decimal:
    """Parse a decimal-as-string; reject floats.

    Costs are intentionally encoded as strings so that float drift cannot
    creep into cost-attribution arithmetic.
    """
    if isinstance(value, float):
        raise ValueError("cost values must be decimal-encoded strings, not floats")
    return Decimal(str(value))


class OperatorInfo(BaseModel):
    """Identifies the legal/responsible party behind an agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, Field(min_length=1, max_length=256)]
    """A human-readable name for the operator."""
    uri: str | None = None
    """Optional URI where the operator's authoritative card list lives."""
    contact: str | None = None
    """Optional contact (email, URL)."""


class CostModel(BaseModel):
    """How a capability's invocation price is computed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit: CostUnit
    """The single cost dimension. v0 forces operators to pick one."""
    base: Decimal
    """Fixed cost per invocation."""
    per_input_unit: Decimal
    """Cost added per ``input_unit`` of input."""
    per_output_unit: Decimal
    """Cost added per ``output_unit`` of output."""
    input_unit: Annotated[str, Field(min_length=1, max_length=32)]
    """Free-form name of the input unit (``page``, ``token``, ``char``)."""
    output_unit: Annotated[str, Field(min_length=1, max_length=32)]
    """Free-form name of the output unit."""

    @field_validator("base", "per_input_unit", "per_output_unit", mode="before")
    @classmethod
    def _decimal_from_string(cls, value: Any) -> Decimal:
        return _decimal_string(value)


class Capability(BaseModel):
    """A single named capability the agent will accept delegation for."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    """Capability name. Must match ``^[a-z][a-z0-9_]{0,63}$``."""
    description: Annotated[str, Field(min_length=1, max_length=500)]
    input_schema: dict[str, Any]
    """JSON Schema (Draft 2020-12) for accepted input."""
    output_schema: dict[str, Any]
    """JSON Schema (Draft 2020-12) for produced output."""
    cost_model: CostModel
    verifier_kinds: list[VerifierKind] = Field(default_factory=list)
    """Names of verifier kinds compatible with this capability's output.

    Use ``"self"`` for deterministic capabilities that can self-verify.
    """

    @field_validator("name")
    @classmethod
    def _capability_name_valid(cls, value: str) -> str:
        if not CAPABILITY_NAME_RE.match(value):
            raise ValueError(
                "capability name must match ^[a-z][a-z0-9_]{0,63}$, "
                f"got {value!r}"
            )
        return value


class TrustAssertion(BaseModel):
    """A signed claim about the agent or its operator.

    The rig does not interpret ``value``; higher layers (policy engines,
    compliance UIs) read it. The ``signature`` is verified using the
    issuer's public key (resolved out-of-band).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Annotated[str, Field(min_length=1, max_length=64)]
    value: dict[str, Any]
    issuer: str
    """DID or URI naming the issuer."""
    issued: datetime
    expires: datetime
    signature: str
    """JWS Compact Serialization, signed by the issuer."""


class AgentCard(BaseModel):
    """The externally-visible advertisement of an agent.

    This model is the *only* artifact the rig consults when deciding
    whether to issue a contract to a given agent. See
    ``docs/spec/agent-card-v0.md`` for the normative definition.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    card_version: CardVersion = "rigging/agent-card/v0"
    agent_id: DID
    """The agent's stable identity (DID).

    Pydantic will validate the DID grammar on construction.
    """
    public_key: str
    """Base64-encoded raw Ed25519 public key (32 bytes pre-encoding)."""
    operator: OperatorInfo
    capabilities: list[Capability]
    trust_assertions: list[TrustAssertion] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    issued: datetime
    expires: datetime
    signature: str = ""
    """JWS over the canonicalized card with this field blank.

    Empty string indicates an unsigned card; such cards MUST NOT be
    accepted by the runtime.
    """

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.expires <= self.issued:
            raise ValueError("expires must be after issued")
        if not self.capabilities:
            raise ValueError("an agent card must declare at least one capability")
        names = [c.name for c in self.capabilities]
        if len(names) != len(set(names)):
            raise ValueError("capability names must be unique within a card")
        return self

    def has_capability(self, name: str) -> bool:
        """Return ``True`` if ``name`` is declared on this card."""
        return any(c.name == name for c in self.capabilities)

    def capability(self, name: str) -> Capability:
        """Return the named capability.

        Raises:
            KeyError: If the capability is not declared.
        """
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        raise KeyError(f"capability {name!r} not declared on card {self.agent_id}")

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return ``True`` if this card has expired relative to ``now``."""
        moment = now if now is not None else datetime.now(tz=UTC)
        return moment >= self.expires
