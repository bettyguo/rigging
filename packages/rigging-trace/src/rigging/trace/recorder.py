"""In-process trace recorder used by the runtime.

The recorder owns a list of :class:`SpanRecord` objects accumulated
during a rig run. The runtime creates child :class:`SpanBuilder`
instances around each significant action; closing a builder appends a
``SpanRecord`` to the recorder and (if configured) emits an OTel span.
"""

from __future__ import annotations

import secrets
import threading
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any, Self

from rigging.core.identity import DID
from rigging.core.trace import (
    BlameChain,
    RigSpanKind,
    SpanRecord,
    TraceRecord,
)


def _span_id() -> str:
    return secrets.token_hex(8)


def _trace_id() -> str:
    return secrets.token_hex(16)


class SpanBuilder:
    """Mutable, in-progress span. Use as a context manager.

    Example::

        with recorder.span(RigSpanKind.EXECUTE) as span:
            span.set_contract(contract)
            span.set_cost(Decimal("0.05"))

    The span is committed to the recorder on ``__exit__``. If the body
    raised, the span still commits but ``reason_code`` is set to
    ``"unhandled_exception"`` and ``output_hash`` is left null.
    """

    def __init__(
        self,
        recorder: "TraceRecorder",
        kind: RigSpanKind,
        parent: "SpanBuilder | None",
    ) -> None:
        self._recorder = recorder
        self._kind = kind
        self._parent = parent
        self._span_id = _span_id()
        self._start = datetime.now(tz=UTC)
        self._end: datetime | None = None
        self._fields: dict[str, Any] = {}
        self._committed = False

    # --- typed setters ---------------------------------------------------

    @property
    def span_id(self) -> str:
        return self._span_id

    @property
    def parent_span_id(self) -> str | None:
        return self._parent.span_id if self._parent is not None else None

    def set_contract(
        self,
        *,
        contract_id: str,
        parent_contract_id: str | None,
        caller: DID,
        callee: DID,
        capability: str,
    ) -> None:
        self._fields.update(
            contract_id=contract_id,
            parent_contract_id=parent_contract_id,
            caller=caller,
            callee=callee,
            capability=capability,
        )

    def set_cost(self, value: Decimal, *, unit: str, budget_max: Decimal) -> None:
        self._fields.update(
            cost_unit=unit,
            cost_value=value,
            cost_budget_max=budget_max,
        )

    def set_verifier(
        self,
        *,
        agent_id: str,
        verdict: str | None,
        reason: str | None,
    ) -> None:
        self._fields.update(
            verifier=agent_id,
            verifier_verdict=verdict,
            verifier_reason=reason,
        )

    def set_envelope(self, jws: str) -> None:
        self._fields["signature_envelope"] = jws

    def set_reason(self, code: str) -> None:
        self._fields["reason_code"] = code

    def set_hashes(self, *, input_hash: str | None, output_hash: str | None) -> None:
        if input_hash is not None:
            self._fields["input_hash"] = input_hash
        if output_hash is not None:
            self._fields["output_hash"] = output_hash

    def set_consumed(self, contract_ids: list[str]) -> None:
        self._fields["consumed_contract_ids"] = list(contract_ids)

    def set_blame_chain(self, contract_ids: list[str]) -> None:
        self._fields["blame_chain"] = list(contract_ids)

    # --- lifecycle -------------------------------------------------------

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._end = datetime.now(tz=UTC)
        if exc is not None and "reason_code" not in self._fields:
            self._fields["reason_code"] = "unhandled_exception"
        record = SpanRecord(
            span_id=self._span_id,
            parent_span_id=self.parent_span_id,
            kind=self._kind,
            start=self._start,
            end=self._end,
            **self._fields,
        )
        self._recorder._commit(record, self)  # noqa: SLF001
        self._committed = True


class TraceRecorder:
    """Thread-safe collector of :class:`SpanRecord` instances.

    One instance per rig run. The recorder can be snapshotted into a
    :class:`TraceRecord` at any time via :meth:`snapshot`; the snapshot
    is immutable. Subsequent spans continue to accumulate.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._trace_id = _trace_id()
        self._spans: list[SpanRecord] = []
        self._root_span_id: str | None = None
        self._started = datetime.now(tz=UTC)
        self._ended: datetime | None = None
        self._listeners: list[Any] = []

    # --- API for the runtime --------------------------------------------

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def root_span_id(self) -> str | None:
        return self._root_span_id

    def add_listener(self, listener: Any) -> None:
        """Register a listener that is notified of each committed span.

        The OTel bridge uses this to mirror spans into an OTel tracer.
        """
        self._listeners.append(listener)

    def span(
        self,
        kind: RigSpanKind,
        *,
        parent: SpanBuilder | None = None,
    ) -> SpanBuilder:
        """Open a new :class:`SpanBuilder` rooted at ``parent`` (or the run)."""
        return SpanBuilder(self, kind, parent)

    def finish(self) -> None:
        """Mark the trace as complete. Subsequent ``snapshot`` calls
        will include the end timestamp."""
        with self._lock:
            self._ended = datetime.now(tz=UTC)

    def snapshot(self, *, blame_chain: BlameChain | None = None) -> TraceRecord:
        """Return an immutable :class:`TraceRecord` of the current state."""
        with self._lock:
            return TraceRecord(
                trace_id=self._trace_id,
                root_span_id=self._root_span_id or "",
                started=self._started,
                ended=self._ended,
                spans=list(self._spans),
                blame_chain=blame_chain,
            )

    # --- internal -------------------------------------------------------

    def _commit(self, record: SpanRecord, builder: SpanBuilder) -> None:
        with self._lock:
            if self._root_span_id is None:
                self._root_span_id = record.span_id
            self._spans.append(record)
        for listener in self._listeners:
            try:
                listener(record)
            except Exception:  # noqa: BLE001 - listeners must not break the run
                continue
