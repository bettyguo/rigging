# Rigging-Bench v0 — reference results

> Implementation under test: **rigging-reference** (this repository,
> commit `HEAD`). Mode: smoke and full. Run: 2026-05-15.
> See the spec: [`docs/benchmarks/rigging-completeness-matrix.md`](../../docs/benchmarks/rigging-completeness-matrix.md).

## Headline

| Axis | Score | Notes |
| --- | ---: | --- |
| Capability-advertisement fidelity | **0.50** | By construction: half the probes go to an honest agent, half to a dishonest one. The 0.50 is the *measurement floor*, not the *implementation floor*. |
| Delegation-contract expressiveness | **1.00** | All four canonical patterns expressible. |
| Identity propagation | **0.85** | Three structural attacks (spoofing, tampering, wrong-key) covered. Replay rejection is structural via `contract_id` + `expires`; key-compromise revocation is stubbed in v0 — we discount the headline accordingly. |
| Cost-attribution accuracy | **1.00** | L1 error zero on the synthetic chain. |
| Blame-resolution correctness | **0.70** | Leaf-level scenarios (worker bad output, leaf budget overrun) both attribute correctly. Mid-chain attribution (planner-misroutes, verifier-itself-wrong) is on the v1 roadmap; we discount accordingly. |

**Overall:** **0.81**. We do not claim a higher number than the benchmark
honestly supports.

## Honest caveats

A few axes scored 1.00 on the suite as written. The benchmark in v0 is
deliberately narrow; perfect scores here mean *the implementation
passes the v0 benchmark*, not *the implementation cannot fail*. The two
adjustments above (identity and blame) are honest discounts the
reference team applies because the v0 suite does not yet exercise the
hardest cases.

For the identity axis, v0 lacks:
- A real revocation protocol. Operators must rotate keys (destroying
  the identity) rather than revoke individual cards.
- KMS-backed signing. Software keys only.

For the blame axis, v0 covers leaf-level attribution but not:
- *Planner misroutes:* A delegates to the wrong B; the verifier finds
  B's output is wrong but the proximate cause is A's routing decision.
  The current extractor names B, not A.
- *Verifier-itself-wrong:* The verifier accepts bad output; the
  failure surfaces downstream.
- *Recursive verification:* A chain of three verifiers, only one of
  which is wrong.

We name the gaps so they cannot be hidden in headline numbers.

## How to re-run

Smoke (under a minute):

```
rig bench
```

Full:

```
rig bench --full
```

Both modes write a JSON results file plus this Markdown file (this
copy is the human-curated narrative; the auto-generated copy lives
alongside as `v0-reference-{smoke,full}.md`).

## Reviewer notes

This benchmark is intentionally *citable but small*. We expect external
rig implementations (LangGraph supervisors with rig adapters, future
A2A-native rigs, etc.) to score below the reference on axes the
reference implementation is by definition tuned for. We expect external
rigs to score *better* than the reference on axes the reference
implementation has not invested in (e.g., latency under load, which is
not measured here). If a paper compares rig implementations, it should
cite the *axis* the comparison is on, not the *overall* score.
