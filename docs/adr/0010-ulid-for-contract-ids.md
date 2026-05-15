# ADR-0010 — ULID for contract IDs

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

Every contract has a `contract_id`. The ID needs to be globally unique
without coordination, lexicographically sortable by issuance time
(so that traces remain readable when grouped by ID prefix), and short
enough to print in CLI output without wrapping.

Practical options: UUIDv4 (random), UUIDv7 (time-ordered), KSUID, ULID,
Snowflake-style. The trace spec already names ULID in its worked
example, but no ADR previously justified the choice.

## Decision

Contract IDs are ULIDs (Crockford-base32-encoded 128-bit values, with a
48-bit Unix-time-ms prefix and an 80-bit random suffix). They are
generated locally by the issuing agent's harness; no central allocator.

## Consequences

- *Pro:* 26-character canonical form. Comfortable in log lines, slack
  pastes, and CLI grids. Easier to type from a screenshot than a UUID.
- *Pro:* Lexicographically sortable. A directory of contracts on disk
  reads in time order. A `grep ^01HW8 traces.log` selects a slice of
  time.
- *Pro:* No coordination. Two rig instances generate non-colliding IDs
  without talking to each other; collision probability with 80 random
  bits at 1000 contracts/second is negligible over the universe's
  lifetime.
- *Pro:* The timestamp prefix is informative — if a contract appears
  with an ID from 2025, it is suspect.
- *Con:* ULIDs are not a stdlib type. We adopt the `python-ulid`
  package or a small inlined implementation. The risk surface is small.
- *Con:* ULIDs reveal issuance time. We consider this acceptable for v0
  (the same information is on every span anyway); operators concerned
  about timing-side-channels in shared environments can substitute
  UUIDv4 in a future profile.

## Alternatives considered

### Alternative A — UUIDv4
Stdlib; familiar. Lost on sort order: random UUIDs scatter in any
time-ordered index.

### Alternative B — UUIDv7
Time-ordered, stdlib in 3.11+. A strong candidate. Lost on character
count (36 chars including hyphens vs. 26 for ULID) and on the slight
ergonomics edge ULID has at the CLI.

### Alternative C — Snowflake-style
Requires a machine-ID allocation scheme. Lost on coordination cost: rig
participants live in independent trust domains; a global Snowflake
allocator is a bridge too far for v0.

## References

- A. Feerasta, *ULID Specification* (2016),
  https://github.com/ulid/spec.
- `docs/spec/rig-contract-v0.md` §2.
