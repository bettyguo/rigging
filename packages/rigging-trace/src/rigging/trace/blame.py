"""Blame-chain extraction.

Given a finished :class:`TraceRecord`, the extractor walks the rig-level
spans to produce a :class:`BlameChain`: the ordered sequence of contract
IDs whose outputs the failure depended on. The extractor is
deterministic and pure — same trace in, same chain out — which is what
makes it useful as evidence.

v0.1 adds *mid-chain attribution*: when a parent contract's verifier
rejects but all the parent's sub-contracts succeeded, blame lands on
the *parent* (the routing decision) rather than the leaves (which did
their declared jobs correctly). See :func:`extract_blame_chain` for the
exact rule. The postmortem from v0.0 flagged this as the single most
important v1 improvement; we ship it here.
"""

from __future__ import annotations

from collections.abc import Iterable

from rigging.core.errors import BlameAttributionError
from rigging.core.trace import BlameChain, RigSpanKind, SpanRecord, TraceRecord


class BlameExtractionError(BlameAttributionError):
    """Raised when the trace is too inconsistent to extract a chain."""


_TERMINAL_FAILURE_CODES = frozenset(
    {
        "verifier_rejected",
        "budget_overrun",
        "callee_unreachable",
        "verifier_unreachable",
        "signature_invalid",
        "schema_invalid",
        "output_schema_invalid",
        "policy_rejected",
        "capability_mismatch",
        "capability_unknown",
        "parent_budget_exhausted",
        "recursion_cap_exceeded",
        "expired",
        "unhandled_exception",
    }
)


def _find_failure(spans: Iterable[SpanRecord]) -> SpanRecord | None:
    """Return the earliest span that carries a terminal failure code."""
    earliest: SpanRecord | None = None
    for span in spans:
        if span.reason_code in _TERMINAL_FAILURE_CODES:
            if earliest is None or span.start < earliest.start:
                earliest = span
    return earliest


def _executes_by_contract(spans: Iterable[SpanRecord]) -> dict[str, SpanRecord]:
    """Index ``rig.execute`` spans by their contract id."""
    index: dict[str, SpanRecord] = {}
    for span in spans:
        if span.kind is RigSpanKind.EXECUTE and span.contract_id is not None:
            index[span.contract_id] = span
    return index


def _children_by_parent(
    executes: dict[str, SpanRecord],
) -> dict[str, list[SpanRecord]]:
    """Group execute spans by their parent contract id."""
    out: dict[str, list[SpanRecord]] = {}
    for span in executes.values():
        if span.parent_contract_id:
            out.setdefault(span.parent_contract_id, []).append(span)
    return out


def _real_subcontracts(
    parent_contract_id: str,
    children_by_parent: dict[str, list[SpanRecord]],
) -> list[SpanRecord]:
    """Return *delegation* sub-contracts (not the rig's own verify call).

    A verifier sub-contract is rig machinery — it doesn't represent a
    delegation decision the parent agent made. Mid-chain blame should
    only consider real delegations.
    """
    children = children_by_parent.get(parent_contract_id, [])
    return [c for c in children if c.capability != "verify"]


def _all_children_clean(
    parent_contract_id: str,
    children_by_parent: dict[str, list[SpanRecord]],
) -> bool:
    """Recursive: did every descendant complete without a failure reason?"""
    children = children_by_parent.get(parent_contract_id, [])
    for child in children:
        if child.reason_code in _TERMINAL_FAILURE_CODES:
            return False
        if not _all_children_clean(
            child.contract_id or "", children_by_parent
        ):
            return False
    return True


def extract_blame_chain(trace: TraceRecord) -> BlameChain | None:
    """Compute the blame chain for a finished trace, or ``None`` on success.

    The proximate-cause attribution uses two rules:

    - **Leaf rule.** If the failing span is a contract's own execute /
      cost-debit / void, the contract's callee is the proximate cause.
    - **Mid-chain rule.** If the failing span is a ``rig.verify`` with
      ``verdict=reject`` and the verified contract had *only* successful
      sub-contracts, the proximate cause is the *issuer* of the
      verified contract (the parent agent), not the executing callee.
      Rationale: the executing agent did its declared job; the routing
      decision (or the wrapping logic) is what failed.

    The chain itself is always built by walking parent-contract pointers
    upward from the failing contract to the root.

    Raises:
        BlameExtractionError: When the trace is internally inconsistent.
    """
    failure = _find_failure(trace.spans)
    if failure is None:
        return None

    executes = _executes_by_contract(trace.spans)
    children = _children_by_parent(executes)

    if failure.contract_id is None:
        raise BlameExtractionError("failing span has no contract_id")

    proximate_contract_id: str = failure.contract_id
    chain_apply_midchain = False

    if (
        failure.kind is RigSpanKind.VERIFY
        and failure.verifier_verdict == "reject"
        and failure.contract_id is not None
    ):
        # Mid-chain rule fires only when the verified contract had at
        # least one *delegation* sub-contract (real composition, not
        # just the rig's verify call) AND all such delegations
        # succeeded. Then the executing agent's composition logic — not
        # the leaf callees — is the proximate cause.
        delegations = _real_subcontracts(failure.contract_id, children)
        if delegations and _all_children_clean(failure.contract_id, children):
            chain_apply_midchain = True

    chain: list[str] = []
    current_id: str | None = proximate_contract_id
    proximate_agent: str | None = None
    visited: set[str] = set()
    while current_id is not None and current_id != "":
        if current_id in visited:
            raise BlameExtractionError(
                f"contract chain contains a cycle at {current_id!r}"
            )
        visited.add(current_id)
        chain.append(current_id)
        execute_span = executes.get(current_id)
        if execute_span is None:
            break
        if proximate_agent is None and execute_span.callee is not None:
            proximate_agent = str(execute_span.callee)
        current_id = execute_span.parent_contract_id

    chain.reverse()  # root-first

    if proximate_agent is None:
        if failure.callee is not None:
            proximate_agent = str(failure.callee)
        else:
            raise BlameExtractionError(
                "cannot identify the proximate-cause agent for the failure"
            )

    # Mid-chain promotion: the executing agent of the verified
    # contract is to blame — they delegated and their composition of
    # the (successful) sub-results was rejected. The leaf callees are
    # exonerated because they did exactly what their cards declared.
    if chain_apply_midchain:
        rejected_execute = executes.get(failure.contract_id or "")
        if rejected_execute is not None and rejected_execute.callee is not None:
            proximate_agent = str(rejected_execute.callee)

    return BlameChain(
        contract_ids=chain,
        proximate_cause=proximate_agent,
        reason_code=failure.reason_code,
    )
