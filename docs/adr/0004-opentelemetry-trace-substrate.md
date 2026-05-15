# ADR-0004 — OpenTelemetry as the trace substrate

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

Traces are a first-class artifact of a rig. They are the evidence a
blame-chain extractor walks, the substrate a cost-attribution report is
built on, and the medium through which the rig's operations remain
auditable. The format and emission mechanism for these traces is one of
the most consequential v0 decisions.

The alternatives are: invent a rig-native trace format; reuse
OpenTelemetry and extend it with rig-specific attributes; reuse a
narrower SDK (Sentry, Honeycomb's `libhoney`, OpenLLMetry); or rely on
free-text logs and synthesise traces at analysis time.

## Decision

We use OpenTelemetry SDK as the trace substrate. Rig-specific semantics
are conveyed via attributes namespaced under `rig.` and a small set of
named span kinds (see `docs/spec/trace-v0.md`). We do not invent a
parallel trace format.

## Consequences

- *Pro:* Any OpenTelemetry-compatible backend can ingest rig traces:
  Tempo, Honeycomb, Lightstep, Datadog, Jaeger, the OTLP collector. No
  one needs to install rig-specific viewing infrastructure to use a rig.
- *Pro:* OpenTelemetry's span model is a good fit for rig semantics:
  contracts produce span trees, sub-contracts produce child spans,
  fan-out produces siblings.
- *Pro:* The `rig.blame.chain` attribute is structurally a JSON-encoded
  list, which OpenTelemetry attributes support natively.
- *Pro:* Existing OpenTelemetry instrumentation in adapter libraries
  (Anthropic SDK, OpenAI SDK, LiteLLM) flows through without
  modification — adapter authors do not need to learn a new trace API.
- *Con:* OpenTelemetry attribute namespacing is permissive; nothing
  stops a misbehaving adapter from polluting the rig namespace. We
  mitigate by having the rig-trace package own all `rig.*` attribute
  setting; adapters call rig-trace's typed API.
- *Con:* OpenTelemetry's sampling model is geared toward observability,
  not auditing. We disable sampling at the rig layer (100% retention)
  and let backends sample at export.

## Alternatives considered

### Alternative A — Invent a rig-native trace format
Maximally clean. Lost on adoption: nobody wants to learn a fourth trace
format, and we would have to reinvent collector, exporter, and viewer
infrastructure.

### Alternative B — Reuse OpenLLMetry
OpenLLMetry is itself an OpenTelemetry extension for LLM-shaped data.
Compatible with this ADR. We don't conflict with OpenLLMetry; rigs that
also produce OpenLLMetry semantic convention spans get them for free.

### Alternative C — Logs only, no traces
Lost on blame attribution. Free-text logs cannot be programmatically
walked to produce a DAG of agent dependencies.

## References

- OpenTelemetry [Specification](https://opentelemetry.io/docs/specs/).
- `docs/spec/trace-v0.md` for the rig attribute schema.
