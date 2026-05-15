# Roadmap

> What is explicitly **out of scope** for v0 and queued for later.
> The list is short on purpose; the master execution prompt names the
> non-goals and the discipline is to keep v0 narrow.

## v1 candidates

### Identity & trust
- Successor-key linking format for controlled rotation.
- A revocation list format that rigs subscribe to.
- KMS-backed signers via a pluggable :class:`Signer` protocol.
- Pluggable signature algorithm field (anticipating post-quantum).
- Optional W3C DID resolution for ecosystems that adopt registries.

### Contracts
- Cancellation protocol (caller wants to withdraw an in-flight contract).
- Streamed contracts (output delivered incrementally; the contract
  remains active until end-of-stream).
- Multi-dimensional cost budgets (tokens AND dollars).
- A `policy_id` field linking contracts to published policies.
- Pre/post-condition predicates against a constrained subset of CEL.
- `transparent` trust-propagation value (pass-through without
  re-signing).

### Trace
- `rig.causal_link` attribute for explicit causality across span trees.
- Sampling guidance.
- Trace-redaction profile for outputs containing PII.
- Signed-trace format (whole-trace signatures for tamper-evidence).

### Adapters / integration
- LangGraph adapter (wrap a LangGraph supervisor as a rig participant).
- AutoGen adapter.
- Goose adapter.
- Claude-Code-as-rig-participant.
- TypeScript adapter speaking to the Python runtime over a future wire
  protocol.
- OpenHarness.ai adapter.

### Tooling
- A web visualizer (`rigging-viz`) for traces.
- A formal TLA+ model of the contract-negotiation protocol; liveness
  and safety checks.
- Coverage of mid-chain blame attribution in the benchmark.

### Operations
- Production-grade auth (OIDC / OAuth flows) for the operator boundary.

## Explicitly *not* on the roadmap

- A new wire protocol replacing MCP or A2A. We ride above them.
- A model router / load balancer.
- A vector store / RAG layer.
- A general-purpose harness. We compose existing harnesses.
- A marketplace, directory, or scheduler.
