# ADR-0007 — Verifier-as-agent, not verifier-as-privileged-role

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

A rig contract names a *verifier*. The verifier either accepts or
rejects the callee's output. The design question is whether the verifier
is a privileged role baked into the runtime (a special slot the rig
invokes at a specific phase) or just another rig participant whose
agent card advertises a `verify_*` capability and that receives
contracts like anyone else.

This is a structural choice. Once made, undoing it later means rewriting
the runtime's state machine and every adapter's verifier integration.

## Decision

The verifier is a normal rig participant. Verifying is just another
capability; verifiers receive contracts; their decisions appear in the
trace as `rig.verify` spans. The runtime has no special-case code for
verifiers other than the trust-propagation field on the parent contract
naming the verifier to be invoked.

The single concession: contracts may name `verifier: "self"`, meaning
the callee verifies its own output. This is treated as a degenerate
case in which the `rig.verify` span and the `rig.execute` span coincide.

## Consequences

- *Pro:* Runtime stays small. There is no second invocation path, no
  second cost-attribution rule, no second failure semantics.
- *Pro:* Verifiers are composable. A "vote of three verifiers" is just
  three sibling sub-contracts whose acceptances are tallied by a rig-
  level aggregator capability; nothing in the runtime needs to know
  about voting.
- *Pro:* Verifiers are auditable like any other agent. Their outputs
  are signed, their costs are attributed, their decisions appear in the
  blame chain.
- *Pro:* The verifier itself can have a verifier. This is the right
  semantics: "who verifies the verifier?" is a real question, and the
  rig answers it by recursing.
- *Con:* Recursion can run away. The v0 recursion cap is 3 (see
  `rig-contract-v0.md` §3), and `trust_propagation: "sealed"` provides
  an explicit termination point.
- *Con:* `verifier: "self"` is tempting and easy to misuse. We accept
  this; the alternative — making self-verification impossible — would
  make legitimate uses (deterministic capabilities verifying their own
  output) needlessly hard.

## Alternatives considered

### Alternative A — Verifier-as-privileged-role
The runtime owns a "verifier registry" and contracts name verifiers by
ID. The runtime has special code paths for invoking verifiers, billing
verifier cost, and handling verifier failure. Lost on uniformity: every
special case is a future bug, and verifier composition (vote
ensembles, recursive auditing) becomes a runtime-level concern instead
of a rig-level composition.

### Alternative B — No verifier at all
The callee's output is trusted; downstream consumers handle their own
verification. Lost: this is the *current* state of multi-agent systems,
and it is the gap rigs are meant to close.

## References

- `docs/phase-reviews/think.md` Q5.
- `CONCEPT.md` — section on "The verifier deserves its own paragraph".
- Russell & Wefald, *Do the Right Thing* (1991), Ch. 3 on metareasoning
  termination.
