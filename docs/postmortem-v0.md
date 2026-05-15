# Postmortem — v0 reference implementation

> Written immediately after closing Phase 4. The discipline of this
> document is to be **honest** about what worked, what didn't, and what
> the next person to look at this codebase should know.

---

## 1. What surprised me

Three things, in order of magnitude:

**The card-hash binding.** Phase 1 left me confident the contract
schema was straightforward; Phase 2 surfaced an attack that hadn't
appeared in Phase 1 — a callee could swap its card between contract
fetch and issuance, widening its accepted contracts. The
`callee_card_hash` field in the contract is the fix, but I didn't
anticipate it and would not have caught it without writing the spec.
This argues for the phase-gated discipline: writing specs forced a
class of attack into the open that a fast-shipping prototype would have
deferred to a CVE.

**JCS canonicalisation is less scary than expected.** I budgeted JCS
correctness as the riskiest Phase-3 unknown. In practice, our surface
is narrow (we sign over dicts whose values are strings, ints, lists,
and other dicts) and a small custom implementation passes a 200-example
Hypothesis property suite without trouble. We would still want
`rfc8785` from PyPI for any input we don't control.

**The verifier-as-agent decision pays off immediately.** I expected the
verifier-as-special-role alternative would have been simpler in v0 and
the verifier-as-agent decision would only pay off later. Wrong. The
runtime stayed small *immediately* — there is exactly one call path
(``Rig.call``) for both the primary delegation and the verifier
sub-contract, and the trace's structure tells the same story whether or
not a verifier was involved. If I'd taken the other path I'd have
spent the second half of Phase 3 unwinding it.

## 2. What I got wrong and had to revisit

- I started Phase 3 with `DID` as a frozen dataclass. The first smoke
  test exposed that pydantic v2's `model_dump(mode="json")` round-trip
  collapses dataclasses into dicts, breaking re-validation. I rewrote
  `DID` as a `str` subclass with a `__get_pydantic_core_schema__` hook.
  Lesson: when a type will round-trip through pydantic and JSON, *be*
  the JSON-shaped type, don't wrap one.
- The master prompt's example contract included `preconditions` and
  `postconditions` arrays. I included them in the first draft of
  `rig-contract-v0.md`. Working through the spec rationale (§9) showed
  they are a DSL hazard — we would inevitably end up implementing a
  half-baked Rego/Cedar clone. They are deferred to v1.
- The first cut of the blame-chain extractor over-relied on
  `rig.consumed` events to prune speculative branches. Writing the
  trace spec showed that adapters in the wild will frequently omit the
  event. I made the extractor over-approximate (treat all
  sub-contracts as load-bearing if `rig.consumed` is absent) — the
  conservative direction. Wider blame is debuggable; narrower blame is
  dishonest.

## 3. The single most important thing v1 must address

**Mid-chain blame attribution.**

The v0 extractor finds the *leaf* of a failure: the contract whose
output was directly rejected. It does not yet handle the case where the
*planner* was the proximate cause (because it routed a question to an
agent unsuited for it; the verifier correctly rejects the agent's
output, but the agent didn't fail — the planner did). The benchmark's
"blame" axis discount of 0.70 reflects this.

The fix has two parts. First, the extractor needs to distinguish
*output-was-wrong* failures from *routing-was-wrong* failures. Second,
the rig needs to carry forward a notion of *why this contract was
issued*, so the extractor can attribute blame to the issuance decision
rather than the executor. Both are tractable; both deferred to v1.

## 4. What I would emphasise in the seminal essay

If I were rewriting `CONCEPT.md` tomorrow, knowing what I know now:

- I would lean *harder* on the *refuse to silently fix things* close.
  This is the single most counterintuitive principle in the rig
  design, and the one that practitioners will push back on first. The
  argument needs to land before the cost-attribution argument
  (currently a few paragraphs earlier), because cost attribution
  *depends on* the no-silent-retry discipline.
- I would include a worked example of a *failed* multi-agent run earlier
  in the essay. Showing the blame chain producing a specific
  participant's DID is the most visceral way to communicate what a
  rig is *for*; today the essay only references the example.
- I would name the maritime metaphor in the *first sentence*, not in
  §1. The fraud connotation of "rigging" is the easiest first-pass
  objection; defuse it before anything else.

The conceptual frame holds. The three primitives (cards, contracts,
blame) are the right primitives. The three refusals (no unsigned
cards, no undeclared capabilities, no silent retries) are the right
refusals. The v0 implementation is small enough to read end-to-end and
honest enough about its gaps that future contributors can extend it
without first having to undo something. That is the bar I wanted to
clear.

## Reviewer-facing addendum

What a 30-minute reviewer should look at, in order:

1. [`CONCEPT.md`](../CONCEPT.md) — the essay.
2. [`docs/spec/rig-contract-v0.md`](./spec/rig-contract-v0.md) — the
   spec that does the most load-bearing work.
3. [`packages/rigging-runtime/src/rigging/runtime/rig.py`](../packages/rigging-runtime/src/rigging/runtime/rig.py)
   — the orchestrator. One file. Read it.
4. [`examples/03_adversarial_subagent/run.py`](../examples/03_adversarial_subagent/run.py)
   — the example that justifies the whole project.
5. [`benchmarks/results/v0-reference.md`](../benchmarks/results/v0-reference.md)
   — the honest scores, with discounts.

If a reviewer leaves with a different mental model than "rigs make
cards, contracts, and blame chains explicit and mechanically
checkable," the documentation has failed.
