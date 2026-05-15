# Rigging Trace Specification — v0

> Status: **DRAFT** · Version: `v0` · Last updated: 2026-05-15
>
> This specification uses RFC 2119 / RFC 8174 normative keywords.
> Companion specifications: `identity-v0.md`, `agent-card-v0.md`,
> `rig-contract-v0.md`.

---

## 1. Purpose

Cross-agent traces are the artifact a rig produces while it runs. They MUST
be sufficient — without consulting any other source — to answer:

- *Which contracts were issued during this run?*
- *Which agent produced which output, and when?*
- *Was each output verified, and by whom?*
- *Where did money go, broken down by agent?*
- *When the final output is wrong, **which agent is to blame**?*

The trace format is an extension of OpenTelemetry, not a replacement. It
adds a small, opinionated set of attributes that lift opaque span trees
into rig-aware artifacts. Any OpenTelemetry-compatible backend can ingest
the traces; the rig-specific tooling (e.g., the blame-chain extractor)
runs against the same spans.

## 2. Span schema

### 2.1 Span kinds

A v0 trace consists of spans of the following kinds. Implementations MUST
set the OpenTelemetry span name to one of these strings.

| Span name             | Emitted by    | Represents                                            |
|-----------------------|---------------|-------------------------------------------------------|
| `rig.run`             | Rig runtime   | The top-level run kicked off by an operator.          |
| `rig.contract.propose`| Rig runtime   | Caller proposed a contract.                           |
| `rig.contract.accept` | Rig runtime   | Callee accepted a contract.                           |
| `rig.contract.reject` | Rig runtime   | Callee rejected a contract.                           |
| `rig.execute`         | Adapter       | Callee performing the work.                           |
| `rig.verify`          | Rig runtime   | Verifier checking an output.                          |
| `rig.cost.debit`      | Rig runtime   | Cost recorded against a contract.                     |
| `rig.contract.void`   | Rig runtime   | Contract voided (unreachable, budget overrun, etc.).  |
| `rig.error`           | Rig runtime   | Out-of-band error not otherwise captured by a span.   |

All other spans (e.g., spans emitted by an agent's harness for tool calls
or model completions) are passed through verbatim — they are part of the
overall trace but are not rig-level events.

### 2.2 Rig-level span attributes

Every rig-level span MUST carry these attributes (when applicable to the
kind). All attribute keys are namespaced under `rig.`.

| Attribute                  | Type    | Description                                                       |
|----------------------------|---------|-------------------------------------------------------------------|
| `rig.contract.id`          | string  | The contract this span is associated with.                        |
| `rig.contract.parent_id`   | string  | Parent contract ID, or empty string if root.                      |
| `rig.contract.version`     | string  | The contract version (e.g., `"rigging/contract/v0"`).             |
| `rig.caller.agent_id`      | string  | Caller DID.                                                       |
| `rig.callee.agent_id`      | string  | Callee DID.                                                       |
| `rig.capability`           | string  | The capability name.                                              |
| `rig.cost.unit`            | string  | `tokens`, `usd`, or `wall_seconds`.                               |
| `rig.cost.value`           | string  | Decimal-as-string. Only present on `rig.cost.debit` and the closing `rig.execute`. |
| `rig.cost.budget_max`      | string  | The contract's budget ceiling.                                    |
| `rig.verifier.agent_id`    | string  | The verifier's DID (or `"self"` if self-verification).            |
| `rig.verifier.verdict`     | string  | One of `accept`, `reject`, `abstain`. Only on `rig.verify`.       |
| `rig.verifier.reason`      | string  | Free-text reason from the verifier; optional.                     |
| `rig.blame.chain`          | string  | JSON-array of contract IDs in load-bearing order. See §3.         |
| `rig.signature.envelope`   | string  | Base64 of the JWS over the span's output. Required on `rig.execute` and `rig.verify`. |
| `rig.reason_code`          | string  | One of the rejection/void codes from `rig-contract-v0.md` §6.     |

Additional advisory attributes (OPTIONAL):

| Attribute                  | Type    | Description                                                |
|----------------------------|---------|------------------------------------------------------------|
| `rig.agent.harness`        | string  | Free-form harness identifier (`langgraph/0.2`, `claude-code/2.0`, etc.). |
| `rig.agent.model`          | string  | Underlying model id if known (`anthropic/claude-opus-4-7`). |
| `rig.input.hash`           | string  | `sha256:<hex>` of the canonicalised input.                 |
| `rig.output.hash`          | string  | `sha256:<hex>` of the canonicalised output.                |

### 2.3 Span relationships

- A `rig.run` is the root span of a rig invocation.
- Each contract produces a `rig.contract.propose` and either a
  `rig.contract.accept` or `rig.contract.reject`. These are children of
  the span representing the *issuing* call (typically a `rig.execute`).
- An accepted contract produces exactly one `rig.execute` span as the
  child of the `rig.contract.accept`. Sub-contracts produced during that
  execute appear as descendants.
- A `rig.verify` is a child of the `rig.execute` it verifies. Its
  `rig.contract.id` refers to the contract whose output is being verified.

## 3. The blame chain

### 3.1 Definition

For any span `s` with output `o`, the **blame chain of `s`** is the ordered
sequence of contract IDs `[c1, c2, ..., cn]` such that:

- `cn` is `s`'s contract,
- each `c_i` is the contract whose output `c_{i+1}`'s execute span consumed
  as load-bearing input,
- the sequence terminates at `c1`, the root contract whose caller is the
  external operator.

A contract's output is *load-bearing* for the consuming contract if any of
the consuming contract's input fields are derived from it. The rig assumes
all sub-contract outputs are load-bearing unless the parent's adapter
explicitly marks them otherwise via the `rig.consumed` event (see §4).

### 3.2 Encoding

The blame chain is serialized as a JSON array of contract IDs in
load-bearing order (root first, leaf last), placed in the
`rig.blame.chain` attribute as a JSON string. Example:

```
rig.blame.chain = "[\"01HW8E1AAA0000000000000000\", \"01HW8E4QV3X8N2W3F1A0X5KQAB\"]"
```

### 3.3 Extracting the chain from a trace

The extractor walks span ancestors:

1. Start at the failing span `s`.
2. Find the ancestor `rig.execute` span — this is `s`'s contract.
3. Find that contract's parent contract (via `rig.contract.parent_id`).
4. Repeat until `parent_id` is empty.

A reference implementation lives in
[`packages/rigging-trace/src/rigging/trace/blame.py`](../../packages/rigging-trace/src/rigging/trace/blame.py).
The extractor MUST be deterministic: given the same trace input, it MUST
produce the same chain.

### 3.4 Fan-out

When a parent contract issues *N* sub-contracts in parallel and only one of
them is consumed (e.g., a vote ensemble where the majority wins, a
speculative race), the rig MUST emit a `rig.consumed` event on the parent
`rig.execute` span listing the contract IDs whose outputs were used. The
extractor uses this to prune speculative branches.

If `rig.consumed` is absent (legacy or simple adapters), the extractor
assumes *all* sub-contracts are load-bearing. This is the safe over-
approximation: too-wide blame is debuggable; too-narrow blame is dishonest.

## 4. Events

OpenTelemetry events (timestamped points within a span) used by the rig:

| Event name           | Attributes                                                                                  |
|----------------------|---------------------------------------------------------------------------------------------|
| `rig.consumed`       | `rig.consumed.contract_ids` — JSON array of contract IDs consumed as load-bearing.         |
| `rig.budget.warning` | `rig.cost.value` (current), `rig.cost.budget_max`. Emitted at 80% of budget.               |
| `rig.signature.fail` | `rig.signature.kind` (`caller` / `callee` / `verifier`).                                    |
| `rig.policy.deny`    | `rig.policy.rule` — string naming the rule that denied.                                     |

## 5. Sampling and retention

A rig in v0 MUST sample 100% of trace data. Sampling is a v1 concern.
Implementations MAY apply downstream sampling at the export stage, but
the in-process trace MUST be complete to allow blame extraction.

## 6. Worked example

A trace from `examples/03-adversarial-subagent/` (simplified):

```
rig.run [operator → planner]
└── rig.contract.propose                 [contract C1: operator → planner / generate_plan]
    └── rig.contract.accept              [C1]
        └── rig.execute                  [C1: planner produces plan]
            ├── rig.contract.propose     [contract C2: planner → worker / execute_step]
            │   └── rig.contract.accept  [C2]
            │       └── rig.execute      [C2: worker emits adversarial output]
            ├── rig.contract.propose     [contract C3: planner → verifier / check]
            │   └── rig.contract.accept  [C3]
            │       └── rig.verify       [C3: verifier rejects worker output]
            └── rig.cost.debit           [C2: $0.05]
                                          rig.blame.chain = ["C1", "C2"]
                                          rig.reason_code = "verifier_rejected"
```

A `rig trace inspect <trace-id>` against this trace would print:

```
Run: c0ffee... (failed)
Reason: verifier_rejected (C2 output rejected by C3)
Blame chain:
  C1  did:rig:operator → did:rig:planner   generate_plan
  C2  did:rig:planner  → did:rig:worker    execute_step    ← responsible
Cost: $0.05 attributed to planner (C2)
```

## 7. Rationale (non-normative)

- **OpenTelemetry as the substrate.** Reusing existing tracing
  infrastructure (collectors, backends, viewers) is worth a small amount
  of attribute-naming friction. Inventing a parallel trace format would
  isolate rig traces from the broader observability stack.
- **Mandatory `rig.signature.envelope`.** It is the receipt that makes
  blame attribution defensible. A trace without signatures on execute
  outputs would let an adversarial implementation claim "we never said
  that".
- **`rig.consumed` defaults to *all*.** When the adapter is honest about
  what was consumed, the blame chain is precise; when the adapter is
  silent, the chain is over-approximated. We err on the side of including
  a participant in the chain rather than letting them slip out silently.
- **No standardized log format.** Logs are out of scope; the trace is the
  only contract. Adapters MAY emit logs alongside, but the rig makes no
  guarantees about them.

## 8. Future versions

- A `rig.causal_link` attribute for explicit causality across span trees
  (today causality is structural — ancestor-of).
- Sampling guidance (which spans MUST always be kept; which may be
  dropped).
- A trace-redaction profile for outputs containing PII.
- A signed-trace format (today, signatures are at the envelope level; v1
  could sign whole traces for downstream tamper-evidence).
