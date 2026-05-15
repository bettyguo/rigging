# Phase 2 Review

> Written immediately after closing Phase 2. Read this before opening Phase 3.

## 1. What I produced

- **Four versioned specifications** under [`docs/spec/`](../spec/):
  `identity-v0.md`, `agent-card-v0.md`, `rig-contract-v0.md`,
  `trace-v0.md`. Each has a normative section using RFC 2119 keywords,
  a worked example, a rationale, and a "future versions" section.
- **Ten ADRs** under [`docs/adr/`](../adr/), exceeding the §5.2 minimum
  of eight: Python-only, Pydantic v2, anyio, OpenTelemetry, Ed25519,
  explicit budget propagation, verifier-as-agent, agent-card vs MCP,
  no silent retries, ULID for contract IDs. The template lives at
  `0000-template.md`.
- **Interface stubs** in
  [`packages/rigging-core/src/rigging/core/`](../../packages/rigging-core/src/rigging/core/):
  `identity.py`, `agent_card.py`, `contract.py`, `trace.py`,
  `protocols.py`, `errors.py`, plus a curated `__init__.py`. The
  pydantic models are mostly complete (their type *is* the interface);
  the `Rig` and `Agent` protocols have `...` bodies awaiting Phase 3.
- **`docs/architecture.md`** with two Mermaid diagrams (package graph
  and per-call sequence), the state machine, and module-by-module
  responsibilities.

## 2. Decisions made; ADR coverage

The Phase-1 review listed five decisions that needed ADRs in Phase 2.
Status:

- *Cost propagation* → ADR-0006. ✓
- *Verifier-as-agent* → ADR-0007. ✓
- *Card vs MCP* → ADR-0008. ✓
- *No silent retries* → ADR-0009. ✓ (Was provisionally numbered;
  promoted to its own ADR.)
- *Seven contract fields* — captured in `rig-contract-v0.md`, not an
  ADR. Rationale: it is a spec detail, not a foundational decision
  needing the ADR ceremony. The ADR I *did* add (0010, ULID) covers
  the only contract-field choice that warranted independent
  justification.

## 3. What I learned that contradicts earlier assumptions

Phase 1 left the riskiest unknown as "fan-out and load-bearing
outputs". Writing `trace-v0.md` §3.4 forced a concrete answer: the
`rig.consumed` event lists the contract IDs whose outputs were
consumed, and the extractor falls back to the *over-approximation* (all
sub-contracts are load-bearing) when the event is absent. This is the
correct conservative default: it means an adapter that forgets to emit
`rig.consumed` produces over-wide blame chains rather than dishonest
narrow ones.

The other surprise was the **`callee_card_hash` field** in the contract
schema. Phase 1's Q3 made the card vs descriptor distinction crisp, but
I had not realised until writing `rig-contract-v0.md` §9 that without a
card-hash binding, a callee could swap its card between fetch and
contract-issuance to widen its accepted contracts. The hash closes that
gap. This is a Phase-2 addition that wasn't in the master prompt's
example contract; it is essential.

A smaller revision: the master prompt's example contract had
`preconditions` and `postconditions` arrays. Working through the spec
made it clear these are a DSL hazard (we would end up reimplementing
Cedar or Rego badly). They are deferred to v1; the v0 contract has no
predicate fields.

## 4. Interface review (figurative "show to a skeptical reader")

The interface acceptance test was: *can a competent engineer predict
what each method does without reading the docstring?*

Walking the public surface in `packages/rigging-core/src/rigging/core/`:

- `DID.from_string`, `derive_did` — obvious.
- `AgentCard.has_capability`, `AgentCard.capability` — obvious.
- `Contract` is a pydantic model; the fields self-explain.
- `RigError` and subclasses — names map directly to reason codes.
- `Agent.accept`, `Agent.execute` — obvious from the names.
- `Verifier.verify` — obvious.
- `Rig.register`, `Rig.call`, `Rig.trace` — `call` is the only one that
  needs documentation. Its kwargs-only design forces every caller to
  name the budget explicitly, which is the desired ergonomics.

One concern: `Rig.call` takes a `cost_budget` as a tuple `(unit, max)`.
A future reader might wonder why we use a tuple instead of constructing
a `CostBudget` model directly. The answer is that the caller-side
typing is more forgiving (no model construction needed for the common
case); the runtime constructs the proper `CostBudget` inside. I'll
include this in a docstring or possibly accept either form in the
implementation phase.

## 5. Riskiest unknown going into Phase 3

The riskiest unknown is **JCS canonicalization correctness**. The
contract and card formats both hash and sign over JCS-canonical JSON
(RFC 8785), and a single off-by-one in canonicalisation (e.g., wrong
number-formatting, wrong handling of duplicate keys) invalidates every
signature in the system in a way that is hard to debug.

Mitigation plan for Phase 3:
- Use a vetted JCS library (`rfc8785` on PyPI) rather than rolling our
  own.
- Write Hypothesis property tests that round-trip random JSON through
  the canonicaliser and check byte-for-byte stability.
- Hash the same payload from two different processes and confirm
  agreement.

## 6. Acceptance: proceeding to Phase 3

The four specs are coherent. The ADRs cover every decision worth
defending. The interfaces are tight enough to implement against. The
architecture document gives a reader the package graph and the per-call
flow in one place.

Phase 3 is now unblocked. The implementation order will follow the
master prompt's Milestone 3.1 → 3.7 sequence; I expect to take some
liberty in the *internal* organisation of `rigging-runtime` (the
master-prompt list of files is a starting point, not a contract).
