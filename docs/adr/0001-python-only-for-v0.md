# ADR-0001 — Python-only for v0

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

A reference implementation of a cross-agent layer is inherently
heterogeneous: real rigs in production will mix Python, TypeScript, Go,
Rust, and probably JVM participants. The v0 implementation must
nonetheless be in some specific language. Splitting v0 across languages
would multiply the surface area without strengthening the underlying
ideas.

The agent ecosystem in 2026 has Python as its centre of gravity. The
canonical implementations of MCP servers, the most-cited research code,
the dominant supervisor frameworks (LangGraph, CrewAI, AutoGen), and the
academic substrate readers (NeurIPS / ICLR) all sit in Python. The
Hashimoto-tier infrastructure crowd reads Go and Rust more comfortably,
but they read Python too; the inverse is not true.

## Decision

The v0 reference implementation is Python 3.12+ only. No JavaScript, no
Go, no Rust, no second language *anywhere* in the reference repo —
including examples, benchmarks, and tooling.

Future versions MAY add second-language adapters that participate in a
Python-orchestrated rig over the wire (this is on the v1 roadmap), but
the *runtime, core, identity, trace, and adapter scaffolding* are
Python-only.

## Consequences

- *Pro:* One toolchain, one type-checker, one test runner, one CI
  configuration. Contributor onboarding is friction-free.
- *Pro:* Examples are runnable on any modern laptop without installing a
  second runtime.
- *Pro:* Pydantic v2 + anyio + cryptography + OpenTelemetry SDK is a
  well-trodden stack with mature tooling.
- *Con:* Pure-Python signing and JCS canonicalisation are slower than
  comparable Go or Rust code. For v0 the throughput targets are
  modest (single-digit hundreds of contracts/second per process); when
  this becomes a bottleneck, the offending modules can be ported.
- *Con:* Some readers will assume rigs are a Python-specific idea. The
  CONCEPT.md essay and the agent-card / contract / trace specs are
  written language-agnostically to head this off.

## Alternatives considered

### Alternative A — Python + TypeScript dual implementation
A small TypeScript participant in `examples/05-typescript-participant/`
would have made the cross-language story concrete. It lost on cost: we
would have spent at least 30% of the budget maintaining a parallel
implementation of identity and contract validation in TypeScript with
nothing conceptually new to show.

### Alternative B — Go for the runtime, Python adapters only
Tempting from a performance and deployment standpoint. Lost on audience:
the readers who will most carefully evaluate the design are not Go-first.
A Python runtime is more accessible for the readership that matters in
v0.

### Alternative C — Rust core with PyO3 bindings
Hypothetically the most defensible long-term choice. Lost on velocity:
v0 needs to ship and be readable; the Rust-PyO3 dance would slow design
iteration without changing any conceptual outcome.

## References

- Phase-1 review, "What I produced" section.
- `CONCEPT.md` — emphasises that rigging is a layer of *discipline*,
  which is best demonstrated in a language readers can audit quickly.
