# ADR-0003 — anyio over bare asyncio

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

A rig executes contracts concurrently: parallel sub-contracts, parallel
verifications in a vote ensemble, interleaved I/O against agent
adapters. The runtime is unavoidably async.

Python offers two async ecosystems: the stdlib `asyncio` and the `trio`
library. They are mostly compatible but differ on cancellation, task
groups, and structured concurrency. The `anyio` library provides a
common API that runs on either loop and offers task groups, cancellation
scopes, and stream primitives that are saner than bare `asyncio`'s.

## Decision

Every `async def` and `await` in the rig codebase uses `anyio`
primitives. We do not import `asyncio` directly in library code; we use
`anyio.run`, `anyio.create_task_group`, `anyio.move_on_after`,
`anyio.from_thread.run_sync`, and friends.

## Consequences

- *Pro:* Structured concurrency by default. `anyio.create_task_group`
  guarantees that exceptions propagate cleanly and that no child task
  outlives the scope. This is the correct semantics for a rig: a sub-
  contract that orphans itself is a leak.
- *Pro:* Cancellation works correctly across the runtime. Budget-overrun
  detection cancels an in-flight execute via a cancellation scope; no
  futures-zombies.
- *Pro:* Users can run the rig under `asyncio.run` *or* `trio.run`. This
  matters for adopters who have already invested in trio.
- *Con:* `anyio` is one more dependency, and a non-trivial one. We
  accept the cost.
- *Con:* Some libraries (notably `litellm`) are asyncio-native. We bridge
  them via `anyio.from_thread.run_sync` and `anyio.to_thread.run_sync`;
  this works but adds a layer.

## Alternatives considered

### Alternative A — Bare asyncio
Stdlib, no extra dependency, familiar. Lost on cancellation: asyncio's
default semantics around cancellation are easy to get subtly wrong, and
in a rig those bugs are the worst kind (silent partial failure).

### Alternative B — Trio only
The cleanest semantics in the Python async world. Lost on ecosystem: too
many third-party libraries are asyncio-only.

## References

- Nathaniel J. Smith, *Notes on structured concurrency, or: Go statement
  considered harmful* (2018). The argument that justifies anyio's
  defaults.
- `anyio` documentation,
  [structured concurrency](https://anyio.readthedocs.io/en/stable/tasks.html).
