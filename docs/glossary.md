# Glossary

> The vocabulary of rigging. Where a term is ambiguous in the broader
> ecosystem, this page pins what *this project* means by it.

---

### A2A
**Agent-to-agent** wire protocol. A peer protocol for agents to talk to
other agents. Rigging *uses* A2A as one possible envelope format for
contracts; it does not redefine it. See
[`docs/related-work.md`](./related-work.md).

### Adapter
A small module that bridges an existing harness or runtime into the rig,
implementing the [`Agent`](./spec/agent-card-v0.md) protocol. See
[`packages/rigging-adapters/`](../packages/rigging-adapters/). Reference
adapters: `LocalPythonAdapter`, `LiteLLMAdapter`, `MCPAdapter`.

### ADR
**Architecture Decision Record.** A short document recording a load-bearing
decision, its context, alternatives, and consequences. Stored under
[`docs/adr/`](./adr/). v0 has 10 ADRs.

### Agent
A participant in a rig. Every agent has a long-lived identity key, a
signed [agent card](#agent-card), and one or more declared capabilities.
The runtime's view of an agent is exactly its card; everything else is
the agent's own internal business.

### Agent card
A signed JSON document advertising an agent's identity, capabilities,
input/output schemas, cost model, verifier compatibility, and trust
assertions. Spec: [`docs/spec/agent-card-v0.md`](./spec/agent-card-v0.md).

### Blame chain
The ordered DAG of signed envelopes recovered from a trace, walked
backwards from a failure to find the proximate cause. Spec:
[`docs/spec/trace-v0.md`](./spec/trace-v0.md) §3.

### Capability
A named operation an agent claims it can perform, with typed input and
output schemas. A contract is always *for a capability*; calls against
undeclared capabilities are refused at the rig boundary.

### Contract (delegation contract)
A signed document of the form *"I, A, ask you, B, to perform capability
C with budget D under verifier V before time T."* Spec:
[`docs/spec/rig-contract-v0.md`](./spec/rig-contract-v0.md).

### Cost budget
A bounded allocation, expressed as `(unit, max)`, attached to a contract.
v0 supports `tokens`, `usd`, and `wall_seconds`. Sub-contracts must
*carve* their budget from the parent's allocation. See
[ADR-0006](./adr/0006-explicit-budget-propagation.md).

### Cost ledger
The runtime's per-contract record of debits. Maintains the invariant
that no contract's debits exceed its budget and no sub-contract's debit
can be attributed to a contract other than its parent.

### DID (decentralized identifier)
The string form of an agent's identity. v0 uses `did:rig:<pubkey-hash>`
derived deterministically from the agent's Ed25519 public key. Spec:
[`docs/spec/identity-v0.md`](./spec/identity-v0.md).

### Ed25519
The signature scheme used by rigging-identity. Fast, deterministic,
small keys, no parameter choices. See
[ADR-0005](./adr/0005-ed25519-over-ecdsa-rsa.md).

### Envelope
A signed JSON object — either a contract, an output, or a verifier
verdict — produced by some agent under some contract. Envelopes are the
atomic unit of accountability in a rig run.

### Harness
The OS-layer abstraction wrapping a single agent (memory, tools, control
loop, observability, evals). A rig *composes* harnesses; it does not
replace them.

### JCS
**JSON Canonicalisation Scheme** (RFC 8785). Used to produce a unique
byte serialisation of any JSON document so it can be signed. See
[`packages/rigging-identity/`](../packages/rigging-identity/).

### JWS
**JSON Web Signature.** The signed-envelope format used throughout
rigging. We use the compact serialisation (`base64url.base64url.base64url`)
with the `EdDSA` algorithm.

### MCP
**Model Context Protocol** (Anthropic). The wire format between an agent
and its tools. Rigging *uses* MCP — every MCP server can be exposed as a
rig participant via `MCPAdapter` — but does not redefine it. See
[`docs/related-work.md`](./related-work.md).

### Proximate cause
The first envelope walked backwards from a failure whose contents, if
replaced with ground truth, would have prevented the failure. The blame
chain terminates here. The rig does not adjudicate fault; it makes the
question of fault *mechanically answerable*.

### Rig
The orchestrator. The object you `register()` agents with and `call()`
through. The only place that constructs contracts, mediates negotiation,
invokes verifiers, debits cost, and emits traces. Implemented by the
`Rig` class in [`packages/rigging-runtime/`](../packages/rigging-runtime/).

### Span
A unit in the trace — propose, accept, reject, void, execute, verify,
cost.debit. Spans carry `rig.*` attributes (contract id, caller, callee,
capability, cost, verdict, blame chain). Compatible with OpenTelemetry.

### Sub-budget
A budget carved from a parent contract's allocation, attached to a
sub-contract. The sub-contract cannot exceed it; the parent contract's
remaining budget is locked while the sub-contract is active.

### Sub-contract
A contract issued in the context of another contract — typically a
verifier sub-contract, or a callee subcontracting work to a third agent.
Has a `parent_id` pointing at its parent contract.

### Trace
The complete record of a rig run — a tree of spans, each carrying a
signed envelope where applicable. Compatible with OpenTelemetry's trace
schema; extended with `rig.*` attributes. Spec:
[`docs/spec/trace-v0.md`](./spec/trace-v0.md).

### Trust propagation
A field in the contract format declaring how trust attaches to the
callee's output: `transparent` (output is exposed to the caller as-is),
`sealed` (output is opaque to the caller, only the verdict is exposed),
`verified` (only verified output is admissible).

### ULID
**Universally Unique Lexicographically-sortable Identifier.** Used for
contract IDs. Sortable by issue order without requiring a separate
timestamp field. See
[ADR-0010](./adr/0010-ulid-for-contract-ids.md).

### Verifier
A rig participant whose declared capability is `verify`. Audits another
agent's output and signs a verdict (`accept` / `reject` / `abstain`).
Treated as a first-class agent — no privileged role. See
[ADR-0007](./adr/0007-verifier-as-agent.md).

### Verifier-as-agent
The design choice — adopted in v0 after rejecting verifier-as-role —
that the verifier is just another rig participant. Enables composition
(vote ensembles, recursive auditors) without runtime special cases.

### Void
A terminal contract state distinct from rejection: the runtime aborted
the contract for a structural reason (budget overrun, expiry, callee
unreachable, signature invalid, recursion cap exceeded). Always carries
a reason code.
