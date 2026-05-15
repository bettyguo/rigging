# ADR-0009 — No silent retries inside the rig

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

The most useful instinct in distributed systems engineering is *retry on
transient failure*. The most dangerous instinct in rig design is the
same instinct, inherited unexamined. A silent retry violates the chain
of custody between the contract a caller signed and the output the
callee delivered: if the rig quietly retried on a different instance,
the signature on the output no longer corresponds to the participant the
caller addressed.

This question came up in Phase 1 (Q6: graceful failure) and recurred
during the trace-spec design. It needs an ADR because the temptation to
add transparent retries appears every time someone tries to make a rig
"more friendly".

## Decision

The rig runtime MUST NOT silently retry a contract. When a callee fails
(unreachable, returns an error, exceeds budget, fails verification), the
rig:

1. Marks the contract terminal (`rejected` or `voided`) with a reason
   code from `rig-contract-v0.md` §6.
2. Surfaces a typed `RigError` to the caller.
3. Records the failure in the trace.

If the caller wants retry behaviour, the caller's harness issues a *new*
contract with a new `contract_id`. The two attempts appear as separate
contracts in the trace, linked (if the caller chooses) via a
`rig.causal_link` attribute or via the harness's own correlation.

## Consequences

- *Pro:* Every output that crosses an agent boundary corresponds to
  exactly one contract. Blame attribution is straightforward: walk to
  the contract, find the signing key.
- *Pro:* Retry behaviour is policy, not protocol. Different harnesses
  can implement different retry strategies without cross-rig coupling.
- *Pro:* Cost attribution is honest. A retried call is a new debit
  against a new contract; the trace shows the operator that retries
  happened and at what cost.
- *Con:* Naïve callers who do not implement retry will see more failures
  than they would under an autoretry rig. We consider this a feature:
  the failures were always happening; the rig now makes them visible.
- *Con:* Some retries are functionally idempotent and the redundant
  contract is logistical overhead. We accept the overhead; the
  alternative (implicit idempotency tracking) is exactly the kind of
  feature whose edge cases produce silent partial failure.

## Alternatives considered

### Alternative A — Configurable retry policy at the rig layer
A `retry_policy` field on contracts. Lost: it lets the rig synthesize
output the callee never produced, which makes blame attribution
unsound.

### Alternative B — Best-effort retry inside the runtime
Try the call; if it fails, try once more silently. Lost on the same
ground as A, and additionally because "once more silently" creates a
race between observed-success and observed-failure that the trace cannot
fully describe.

## References

- `docs/phase-reviews/think.md` Q6.
- `CONCEPT.md` — section on "the most important discipline a rig
  enforces is refusing to silently fix things".
- Lamport, *Time, Clocks, and the Ordering of Events* (CACM 21:7, 1978).
