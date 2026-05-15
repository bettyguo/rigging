# ADR-0002 — Pydantic v2 over dataclasses + jsonschema

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

The rig's external surfaces — agent cards, contracts, traces — are
JSON documents with strict invariants (signatures verify, expiry is in
the future, units match capability cost models). The rig's internal
representation needs to (a) parse those JSON documents safely, (b) emit
them deterministically, (c) carry the invariants as types so they cannot
be silently violated by adapter code, and (d) participate in static type
checking under `mypy --strict` and `pyright` strict mode.

The Python ecosystem offers two serious choices: dataclasses (or
`attrs`) plus a JSON Schema validator like `jsonschema`, or Pydantic v2,
which co-locates schema, validation, and type at the cost of a runtime
dependency on the Pydantic engine.

## Decision

We use Pydantic v2 for every external surface and every internal model
that crosses a module boundary. We do not use bare dataclasses or
`attrs` for these surfaces. We do not separately maintain JSON Schema
documents — Pydantic emits them when needed.

## Consequences

- *Pro:* One source of truth per model: the Python class is the schema,
  the validator, and the type. There is no possibility of drift between
  a hand-written `jsonschema` file and the runtime validator.
- *Pro:* Pydantic v2's discriminator unions handle the
  `verifier: "self" | <DID>` and `trust_propagation: "verified" |
  "sealed"` patterns with no custom code.
- *Pro:* The `model_validator` decorator is the cleanest place to put
  cross-field invariants (e.g., `expires > issued`, `cost_budget.unit`
  matches capability cost model).
- *Pro:* Pydantic's JSON Schema export is good enough to embed in the
  capability `input_schema` / `output_schema` slots of agent cards.
- *Con:* Pydantic is a heavy dependency for a *runtime* library. We
  accept this for v0; it is the price of having model-as-validator.
- *Con:* The Pydantic v2 → v3 transition is a future risk. We mitigate
  by pinning to `>=2.6,<3` and reviewing each minor release.

## Alternatives considered

### Alternative A — `attrs` + `jsonschema`
Lighter dependency footprint; validation library is mature. Lost on
drift: keeping the Python type in sync with the schema is a manual
discipline that fails under time pressure.

### Alternative B — `msgspec`
Faster than Pydantic; smaller. Lost on ecosystem: less mainstream, less
familiar to readers, more friction for adapter authors who want to add
their own models.

### Alternative C — Hand-rolled validators
Lost on every dimension. Mentioned only to be dismissed: rigs deal with
adversarial inputs (forged signatures, capability spoofing), and
hand-rolled validators have a perfect record of missing edge cases.

## References

- Pydantic v2 docs, [Model validators](https://docs.pydantic.dev/2.6/concepts/validators/).
- `docs/spec/agent-card-v0.md`, §3 for the canonicalisation rules that
  Pydantic must respect.
