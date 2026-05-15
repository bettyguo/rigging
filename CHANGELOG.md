# Changelog

All notable changes to `rigging` will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — Unreleased — post-v0 audit cycle

### Fixed
- **A1 — Verifier output signatures are now verified.** `Rig._run_verifier`
  re-derives the verifier's public key from its registered card and
  validates the JWS envelope against the canonicalised verdict payload
  before trusting the verdict. Previously the verdict was read without
  re-checking the signature.
- **A2/A3 — Contract expiry is enforced at execute.** The rig now refuses
  to invoke an already-expired contract (emits `rig.contract.void`,
  raises `ContractExpired`) and wraps every `Agent.execute` in an
  `anyio.move_on_after` scope bounded by `contract.expires`. A new
  `ContractExpired` error type lives in `rigging.core.errors`.
- **A4 — Runtime-side terminations emit `rig.contract.void` spans.**
  Reject (callee declined) and void (runtime voided) are now distinct
  span kinds in the trace, matching `trace-v0.md`.
- **A5 — Span hierarchy is parent-child, not flat.** `Rig.call` threads
  an explicit `parent_span` argument; sub-contract spans correctly
  nest under their parent's `rig.execute` / `rig.verify` span.
- **A6 — Example 04 demonstrates true hierarchical budgets.** B issues
  C's sub-contract with `parent_contract=A→B`. The overrun is local to
  C's contract; A's budget is structurally protected.

### Added
- **`RigConfig` for policy knobs.** Centralised `default_contract_lifetime`,
  `max_contract_depth`, `verification_recursion_cap`,
  `default_verifier_budget`, and `enforce_execute_timeout`. Pass to
  `Rig(config=...)`.
- **`Rig.export_trace(path)` / `Rig.import_trace(path)`.** JSON
  round-trip via Pydantic; `rig trace inspect` now consumes the same
  format the runtime writes.
- **`ExecuteResult.consumed_contract_ids`.** Adapters can declare which
  sub-contracts they used as load-bearing. The runtime records the list
  on the parent execute span; the blame extractor uses it to prune
  speculative fan-out (`trace-v0.md` §3.4).
- **`Rig.contract(id)`, `Rig.issued_contracts()`, `Rig.last_contract_to(...)`.**
  Public lookup of issued contracts; needed by adapters that issue
  sub-contracts (e.g., the new vote ensemble) and by examples that
  demonstrate hierarchical budgets.
- **`VoteEnsembleVerifier` adapter.** A coordinator agent whose
  `verify` capability fans out to N constituent verifiers and reports
  the majority verdict. The runtime needed no changes — pure
  composition. Example 05 uses it.
- **Sync handler support in `LocalPythonAdapter`.** Handlers may be
  `async def` or plain `def`; sync handlers run on a worker thread via
  `anyio.to_thread.run_sync`.
- **Mid-chain blame attribution** in the blame extractor. When a
  verifier rejects a contract whose real (non-verify) sub-contracts all
  succeeded, blame is promoted from the leaf callees to the executing
  agent — the composition decision is what failed, not the leaf.
- **Example 05 — vote-ensemble verifier.** New runnable example
  demonstrating composable verification.

### Internal
- `py.typed` markers on every package; mypy `--strict` clean across all
  28 source files.
- Stale `type: ignore` comments removed.
- New test suites: `tests/integration/test_runtime_features.py` (9
  tests covering A1-A5, D1-D5, accessors), `tests/property/test_budget_properties.py`
  (4 property tests for ledger invariants),
  `tests/property/test_contract_roundtrip.py` (2 property tests for
  contract signing + replay).
- Test count: 61 → 76.

## [0.1.0] — Unreleased

The v0 reference implementation. This release establishes the conceptual
substrate; APIs are deliberately small and the on-disk formats are explicitly
marked `v0` so that v1 can break them without ceremony.

### Added
- **Concept and specs.** `CONCEPT.md` essay plus four versioned specifications:
  delegation contracts (`rig-contract-v0`), agent capability advertisements
  (`agent-card-v0`), cross-agent trace format (`trace-v0`), and agent identity
  (`identity-v0`).
- **`rigging-identity`** — Ed25519 key generation, agent card signing/verification,
  `did:rig:<pubkey-hash>` derivation, and a small CLI surface.
- **`rigging-core`** — Pydantic v2 data models for contracts, agent cards, and
  traces, with validators that enforce the spec invariants.
- **`rigging-trace`** — OpenTelemetry span processor for rig-level semantics
  plus a blame-chain extractor that yields a machine-checkable DAG.
- **`rigging-adapters`** — `LiteLLMAdapter`, `MCPAdapter`, `LocalPythonAdapter`.
  Each adapter wraps an existing harnessed agent so it can speak rig.
- **`rigging-runtime`** — the `Rig` orchestrator: contract negotiation, routing,
  cost-budget enforcement, verifier invocation, blame-chain construction, and
  structured failures.
- **CLI.** A unified `rig` entrypoint (`rig identity ...`, `rig run ...`,
  `rig trace inspect ...`, `rig bench run`, `rig spec validate`).
- **Examples.** Four runnable scenarios covering the minimum-viable rig,
  heterogeneous composition, adversarial sub-agents, and cost attribution.
- **Rigging-Bench v0.** Benchmark suite scoring rig implementations on the five
  axes of the *Rigging Completeness Matrix*.

### Notes
- The rig layer itself remains LLM-provider-agnostic; provider-specific code
  lives only under `rigging-adapters`.
- All on-disk formats are explicitly versioned. Breakage between v0 and v1 is
  expected and will be tracked here.
