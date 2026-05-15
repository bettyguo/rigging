# ADR-0008 — Agent cards and MCP server descriptors are dual

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

The MCP specification's *server descriptor* and the rig's *agent card*
look superficially similar: both name capabilities, both describe typed
inputs and outputs. A naïve implementation would treat them as
interchangeable, or build the agent card by inheriting from the MCP
descriptor with a few extra fields. This conflation has appeared in at
least one community draft.

The two documents serve dual roles. Treating them as the same thing
quietly destroys the trust model.

## Decision

Agent cards and MCP server descriptors are *separate kinds of object*
and the rig refuses to conflate them. The runtime never reads an MCP
descriptor; the runtime always reads an agent card. Adapters that wrap
MCP servers as rig participants explicitly *translate* between the two,
producing a signed agent card from the (unsigned) MCP descriptor and an
operator's intent.

## Consequences

- *Pro:* The trust boundary is unambiguous. An MCP descriptor describes
  what tools an agent uses; an agent card describes what an agent
  produces. Conflating them would let unsigned tool descriptors leak
  into the rig's trust calculus.
- *Pro:* Operators retain the freedom to expose a *subset* of an MCP
  server's tools as rig capabilities, or to wrap several MCP tools
  behind a single rig capability. The translation is policy.
- *Pro:* Versioning of the two surfaces is independent. MCP's server
  capability spec can evolve without forcing changes to the rig agent-
  card spec.
- *Con:* Adapter authors must write the translation explicitly. We
  provide a `MCPAdapter.from_descriptor()` helper for the common case
  (one MCP tool ↔ one rig capability), but it is not automatic.
- *Con:* Some readers will look for an obvious mapping between MCP and
  rig surfaces and not find one. The CONCEPT.md essay calls this out;
  the spec rationale section repeats it.

## Alternatives considered

### Alternative A — Treat MCP descriptor as a subset of agent card
An MCP server's tool list could *be* the agent's capability list, with
the operator signing the union. Lost: this glues the rig's trust model
to MCP's, and any MCP-side breaking change becomes a rig-side breaking
change.

### Alternative B — Generate the agent card from MCP descriptor
automatically. Lost: the operator must consciously choose what to expose
and at what cost. Auto-generation hides this choice.

## References

- Anthropic, *Model Context Protocol Specification* (2024-11), §3.2.
- `docs/related-work.md`, MCP section.
- `docs/spec/agent-card-v0.md`, §1.
- `docs/phase-reviews/think.md`, Q3.
