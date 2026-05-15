# Phase 1 Review

> Written immediately after closing Phase 1. Read this before opening Phase 2.

## 1. What I produced

- [`docs/phase-reviews/think.md`](./think.md) — six open questions answered, each with at least
  one cited source, with cross-cutting notes at the end.
- [`docs/related-work.md`](../related-work.md) — survey of ten adjacent systems (A2A, MCP, ACP,
  OASF, KYA, OpenHarness, LangGraph, CrewAI, `loom-agent`, Teradata `loom`),
  each ~200 words, each answering *what does Rigging add?*.
- [`CONCEPT.md`](../../CONCEPT.md) — the long-form essay (~2,400 words). The voice
  target was Hashimoto/Spolsky; the structure is metaphor → gap → primitives
  → discipline → close. No bullet-pointed marketing.

## 2. Decisions made; ADR coverage

The Phase-1 work locked in several decisions that need to be captured as
ADRs in Phase 2. Listing them here so they cannot be quietly forgotten:

- **Cost propagation: explicit budget propagation, not caller-pays.** Justified
  in Q4 of `think.md` against the alternatives. → ADR-0006.
- **Verifier-as-agent, not verifier-as-privileged-role.** Justified in Q5. The
  argument turns on uniformity of runtime invariants. → ADR-0007.
- **Agent cards and MCP server descriptors are *dual*, not the same thing.**
  The card is the *producer-side* surface; the MCP descriptor is the
  *consumer-side* surface. → ADR-0008.
- **The rig must never silently retry.** Retries are first-class contracts.
  Encoded in the failure-semantics design (Q6) and called out explicitly in
  `CONCEPT.md`. This will appear in the rig-runtime contract negotiation
  ADR (provisionally ADR-0009).
- **Seven fields earn a place in the contract.** `contract_id`, `caller`,
  `callee`, `capability`, `cost_budget`, `verifier`, `expiry`, `signature`.
  Everything else deferred. → spec `rig-contract-v0.md`.

## 3. What I learned that contradicts earlier assumptions

The master prompt suggested the verifier's relationship to the rig was a
free design choice. Working through Q5 made me realize it is *not* free:
treating the verifier as a privileged role outside the rig produces a
cascading set of special cases that contaminate the runtime. The
verifier-as-agent choice was forced by the discipline of "every special
case is a future bug", not chosen freely. This is worth flagging — I went
into Phase 1 believing both options were viable; I left believing only one
is.

A second update: I expected `trust_propagation` to be a v0 must-have based
on the master prompt's sketch. Writing the contract spec made it clear that
v0 only needs two values: `sealed` (terminate recursive verification here)
and `verified` (continue). The third value mentioned in the prompt
(`transparent`) is a future extension and would let an intermediate agent
pass through without re-signing. We can ship without it.

## 4. Riskiest unknown going into Phase 2

The riskiest unknown is the **interaction between blame chains and async
fan-out**. If agent A delegates the same capability to B *and* C in
parallel and only one of them is correct, the blame chain construction
needs to identify the bad span without naïvely blaming both contributors.
The Phase-2 trace spec will need a precise definition of which spans count
as *load-bearing* for a given output and which were merely speculatively
executed. I have a rough idea (the verifier's acceptance of a specific
output makes that output's chain load-bearing; the others become orphaned)
but I have not pressure-tested it against more than two adversarial
sketches.

Phase 2 plan: write the trace spec *last* of the four, after the contract
and agent-card specs are solid, so I can think through fan-out with the
contract semantics already fixed.

## Bedrock-check (figurative re-read of CONCEPT.md)

Does the essay sound like a Hashimoto-tier post or like generic AI
marketing? My honest read: the metaphor section and the *refuses* close
both work. The middle section ("you can tell the layer is real because it
is already being open-coded everywhere") needed two rewrites to lose the
demo-deck rhythm. The cost-attribution and verifier sections are the most
opinionated; I think they read well, and they are the parts most likely to
get cited or argued with. If a reviewer disagrees with those, I want them
to disagree *specifically*, which they will be able to do.

Proceed to Phase 2.
