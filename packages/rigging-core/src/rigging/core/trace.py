"""Trace data model — the structured representation of a rig run.

This is the in-memory record type used by the blame-chain extractor and
by ``rig trace inspect``. The :mod:`rigging.trace` package converts
OpenTelemetry spans into ``SpanRecord`` instances and vice versa.

The data model intentionally mirrors the OpenTelemetry span tree, with
the rig-specific attributes (``rig.*``) hoisted into typed fields.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rigging.core.identity import DID


class RigSpanKind(str, Enum):
    """The named rig span kinds defined in ``trace-v0.md`` §2.1."""

    RUN = "rig.run"
    CONTRACT_PROPOSE = "rig.contract.propose"
    CONTRACT_ACCEPT = "rig.contract.accept"
    CONTRACT_REJECT = "rig.contract.reject"
    EXECUTE = "rig.execute"
    VERIFY = "rig.verify"
    COST_DEBIT = "rig.cost.debit"
    CONTRACT_VOID = "rig.contract.void"
    ERROR = "rig.error"


class SpanRecord(BaseModel):
    """A single rig-level span.

    Non-rig spans (harness tool calls, model completions) are preserved
    on the underlying OpenTelemetry trace but are not represented here:
    this type is for the rig-level view.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str
    parent_span_id: str | None
    kind: RigSpanKind
    start: datetime
    end: datetime | None = None

    contract_id: str | None = None
    parent_contract_id: str | None = None
    caller: DID | None = None
    callee: DID | None = None
    capability: str | None = None
    cost_unit: str | None = None
    cost_value: Decimal | None = None
    cost_budget_max: Decimal | None = None
    verifier: str | None = None
    verifier_verdict: str | None = None
    verifier_reason: str | None = None
    blame_chain: list[str] | None = None
    signature_envelope: str | None = None
    reason_code: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    consumed_contract_ids: list[str] | None = None
    """Populated from the ``rig.consumed`` event when present."""

    extra: dict[str, Any] = Field(default_factory=dict)
    """Pass-through for non-canonical attributes; not load-bearing."""

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.end is not None and self.end < self.start:
            raise ValueError("span end must not precede span start")
        return self


class BlameChain(BaseModel):
    """An ordered chain of contracts leading to a failure.

    The chain is *root-first*: ``contract_ids[0]`` is the root contract
    issued by the operator; ``contract_ids[-1]`` is the contract whose
    output is the proximate cause of the failure.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_ids: Annotated[list[str], Field(min_length=1)]
    proximate_cause: str
    """The agent DID at the leaf of the chain — the proximate cause."""
    reason_code: str | None = None

    def root(self) -> str:
        return self.contract_ids[0]

    def leaf(self) -> str:
        return self.contract_ids[-1]


class TraceRecord(BaseModel):
    """A complete trace: the run-level rollup of all rig spans."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str
    root_span_id: str
    started: datetime
    ended: datetime | None = None
    spans: list[SpanRecord]
    blame_chain: BlameChain | None = None
    """Populated by the extractor when a terminal failure is present."""
