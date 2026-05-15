"""Property tests for the blame-chain extractor.

The extractor is the rig's most consequential pure function: a bug here
silently produces dishonest blame attribution. We pin its behaviour by
generating synthetic linear contract trees of various depths and
verifying that a failure injected at depth ``d`` produces a chain of
length ``d``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from rigging.core.identity import DID, derive_did
from rigging.core.trace import (
    BlameChain,
    RigSpanKind,
    SpanRecord,
    TraceRecord,
)
from rigging.runtime.ulid import new_ulid
from rigging.trace.blame import extract_blame_chain


def _build_linear_trace(depth: int) -> TraceRecord:
    """A trace whose contracts form a linear chain root → leaf."""
    contracts: list[str] = []
    spans: list[SpanRecord] = []
    parent_contract: str | None = None
    last_callee: DID | None = None
    now = datetime.now(tz=UTC)
    for i in range(depth):
        cid = new_ulid()
        contracts.append(cid)
        # Deterministic synthetic key bytes; just need a valid DID.
        caller_bytes = (b"\x01" * 32 if i == 0 else (i).to_bytes(32, "big"))
        callee_bytes = (i + 100).to_bytes(32, "big")
        caller = derive_did(caller_bytes)
        callee = derive_did(callee_bytes)
        last_callee = callee
        span = SpanRecord(
            span_id=new_ulid(),
            parent_span_id=None,
            kind=RigSpanKind.EXECUTE,
            start=now,
            end=now,
            contract_id=cid,
            parent_contract_id=parent_contract,
            caller=caller,
            callee=callee,
            capability=f"step_{i}",
            cost_unit="usd",
            cost_value=Decimal("0"),
            cost_budget_max=Decimal("1"),
        )
        spans.append(span)
        parent_contract = cid

    # Inject a failure on the deepest span.
    failed = spans[-1].model_copy(update={"reason_code": "budget_overrun"})
    spans[-1] = failed

    return TraceRecord(
        trace_id=new_ulid(),
        root_span_id=spans[0].span_id,
        started=now,
        ended=now,
        spans=spans,
    )


@given(st.integers(min_value=1, max_value=8))
@settings(max_examples=50, deadline=None)
def test_chain_length_matches_depth(depth: int) -> None:
    trace = _build_linear_trace(depth)
    chain = extract_blame_chain(trace)
    assert chain is not None
    assert isinstance(chain, BlameChain)
    assert len(chain.contract_ids) == depth
    # Root-first ordering: contract_ids[0] is the outermost contract.
    assert chain.contract_ids[-1] == trace.spans[-1].contract_id


@given(st.integers(min_value=1, max_value=8))
@settings(max_examples=20, deadline=None)
def test_chain_terminates_at_actual_failure(depth: int) -> None:
    trace = _build_linear_trace(depth)
    chain = extract_blame_chain(trace)
    assert chain is not None
    failure_span = trace.spans[-1]
    assert chain.proximate_cause == str(failure_span.callee)
    assert chain.reason_code == failure_span.reason_code


def test_no_failure_returns_none() -> None:
    trace = _build_linear_trace(3)
    cleaned = [s.model_copy(update={"reason_code": None}) for s in trace.spans]
    clean_trace = trace.model_copy(update={"spans": cleaned})
    assert extract_blame_chain(clean_trace) is None
