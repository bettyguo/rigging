# FAQ

> The questions practitioners actually ask in the first ten minutes after
> finding this repo. If you have one we have not answered, please open an
> issue.

---

## Positioning

### Is this a new wire protocol?

No. **A rig is not a protocol.** MCP is a protocol. A2A is a protocol. ACP
is a protocol. A rig *uses* protocols — typically several at once. The
delegation contract flows over A2A (or any equivalent envelope format);
tool calls inside a participant's harness flow over MCP; the trace flows
over OpenTelemetry. **A rig that invents a new wire format is, by our
definition, doing it wrong.**

### Is Rigging a replacement for my harness?

No. A rig **composes** harnesses. If you change the harness of an agent
that participates in a rig, the rig does not care, provided that agent's
card and identity key are unchanged. Rigging sits *one floor up* from
your harness.

### Is Rigging a supervisor pattern (LangGraph, CrewAI, AutoGen, …)?

No, and this is the most common misconception. A supervisor pattern is an
application-level convention for routing tasks **inside one trust domain**.
A rig is the layer that lets two supervisor-managed populations
**delegate to each other across trust domains**.

If your supervisor pattern works inside one company's repository, a rig is
what makes it work between two companies' repositories.

### Is Rigging an MCP server registry / agent marketplace?

No. A registry tells you *what is available*. A rig tells you *under what
terms a specific agent will accept work from a specific other agent right
now*. A registry has no opinion on cost, identity, blame, or expiry. A
rig refuses to operate without all four.

### Is this a model router?

Emphatically no. A rig does not pick which model to call. It does not
optimise latency. It does not weight providers. The caller chooses the
callee; the rig polices the boundary. If you want a model router, use one
— and then point it at a rig participant.

### Why "Rigging"? Doesn't that sound fraudulent?

We mean it in the **maritime** sense — the load-bearing web of ropes and
spars that translates wind into motion. The sails do not move the ship.
The hull does not move the ship. The rigging does. See the opening
section of [`CONCEPT.md`](../CONCEPT.md).

We considered alternatives (`fleet`, `flotilla`, `tackle`, `lattice`,
`weave`). None captured the *load-bearing* connotation as cleanly.

---

## Identity & trust

### Why Ed25519 and not OIDC/OAuth/JWT-with-OIDC?

For v0, the only question identity needs to answer is: *is this card real
and unchanged since the operator signed it?* Long-lived per-agent
Ed25519 keys answer that with no infrastructure, no IdP dependency, and
deterministic offline verification. See
[ADR-0005](./adr/0005-ed25519-over-ecdsa-rsa.md).

OAuth/OIDC integration is a v1 conversation. The JWS envelope format we
use is the same one OIDC uses; the migration path is mostly about *who
signs the card*, not *how the signature is encoded*.

### Where do agent identity keys come from?

In v0, from `rig identity create`. The key is generated locally,
encrypted at rest with a passphrase, and the DID is derived from the
public key. Operators are expected to manage these keys the way they
manage SSH keys for production hosts: with care.

v1 will support KMS-backed signing so the private key never leaves the
HSM. The card format does not change.

### What about revocation?

v0 has no revocation protocol. Operators rotate the key (destroying the
identity and minting a new one). This is honest and limited. v1's first
task is to add a revocation primitive so a compromised card can be
invalidated without forcing a fresh DID. This is one of the two reasons
the identity-propagation benchmark axis scores 0.85, not 1.00.

### Can an agent forge another agent's card?

The card is signed by the issuing identity key. The rig refuses to load
a card whose signature does not verify against the public key the card
itself declares. A forgery would require the private key. If the private
key is compromised, the operator's only recourse in v0 is rotation; v1
will add revocation.

---

## Contracts, budgets, and verifiers

### Why is `cost_budget` not optional?

Because a contract with no budget is a contract with an *unbounded*
budget, and an unbounded budget is what a supervisor pattern silently has
when no one was paying attention. Cost is a property of a contract, not
of an agent. See [ADR-0006](./adr/0006-explicit-budget-propagation.md).

### How do you stop a sub-agent from putting charges on the root caller's card?

By making cost a property of the contract: B may subcontract to C only
by carving out a sub-budget from B's own allocation. C's overruns hit
B's ledger; B's overruns hit A's ledger; A's budget is inviolable. This
composes and survives recursion. See
[ADR-0006](./adr/0006-explicit-budget-propagation.md) and example
[`04_cost_attribution`](../examples/04_cost_attribution/).

### Why is the verifier just another agent and not a privileged role?

We tried the privileged-role design first. It is appealing — the verifier
sits in a clean protected slot, distinct from the agents under test —
and it is wrong. A privileged verifier requires its own identity model,
its own cost story, its own audit trail, and soon enough its own argument
with operators about *who gets to be a verifier and why*. The runtime
accretes complexity. Worse, you cannot compose two verifiers (a vote
ensemble, a recursive auditor) because they are not first-class
participants.

Treating the verifier as just another agent with a declared `verify`
capability gives us all of those for free, and it forces "who verifies
the verifier?" to terminate the only way it can terminate in any formal
system: at a declared bedrock. The depth is bounded. The bedrock is
explicit. See [ADR-0007](./adr/0007-verifier-as-agent.md) and example
[`05_vote_ensemble`](../examples/05_vote_ensemble/).

### Why no silent retries?

If agent A calls agent B and B fails, and the rig silently retries on
B′ — which gets a different model assignment, or runs in a different
region, or has a different memory state — then the output the caller
receives is *not signed by the agent the caller addressed*. The contract
A believed it had with B has been quietly transferred to B′, and A has
no record of the substitution. When the output is wrong tomorrow, the
trace shows A → B but the work was done by B′, and the blame analysis
terminates in a contradiction.

A rig refuses this. Retries are first-class events with their own
contracts and their own identifiers. Fallbacks are explicit choices the
caller makes after a typed failure. See
[ADR-0009](./adr/0009-no-silent-retries.md).

---

## Tracing & blame

### What is a blame chain, mechanically?

The rig records every signed envelope in a per-run trace — every
proposed contract, every accepted contract, every output, every verifier
verdict — and records, for each output, which envelopes it consumed
upstream. The blame chain is the DAG that walks backwards from the
failure envelope. The proximate cause is the first envelope whose
contents, if replaced with ground truth, would have prevented the
failure.

### Will the blame chain always point at exactly one agent?

In v0, for **leaf-level** failures (bad output, leaf budget overrun, leaf
expiry, bad signature), yes. For **mid-chain** failures (planner
misroutes, verifier itself is wrong), the v0 extractor does not yet name
the higher culprit — it names the proximate envelope. The benchmark
report scores this honestly at 0.70.

### Does the rig adjudicate fault?

No. The rig does not know what the right answer was. It makes the
question of fault **mechanically answerable**. Adjudication is a
human-in-the-loop step (or a separate downstream agent).

---

## Performance & scope

### How fast is it?

v0 is not optimised. A typical end-to-end contract (propose, accept,
execute, verify, debit, trace) is around a millisecond in-process. The
runtime is async-native (anyio), so it scales with the slowest
participant.

We do not benchmark latency in `rig-bench v0` because latency is properly
a property of *your harnesses*, not of the rig. We will add a latency
axis to the benchmark in v1, but only to measure the rig's overhead, not
the participants'.

### What's in v0 vs v1?

v0 ships the five primitives, four specs, ten ADRs, five examples,
the five-axis benchmark, the CLI, the live site, and 61 tests.

v1 will add: mid-chain blame attribution, card revocation, KMS-backed
signing, a real web visualizer (`rigging-viz`), at least one real-world
harness adapter (LangGraph or AutoGen or Goose), and a TLA+ model of the
negotiation protocol. See [`roadmap.md`](./roadmap.md).

### Does the rig support streaming responses?

v0 does not. The contract's `execute` is request-response. The state
machine (`proposed → active → fulfilled`) does not have a streaming
state. We have a sketch of how it would work — partial-envelope chains —
but we deferred it from v0 because none of the examples needed it and
streaming-without-blame is worse than not streaming.

### Is the runtime distributed?

No. v0 is in-process. The contract format is wire-shaped (signed JSON),
so cross-process and cross-host rigs are mechanical, but the v0 runtime
does not implement the transport. v1 will add an A2A-native transport.

---

## Practical use

### Can I use Rigging with my LiteLLM-based harness today?

Yes. [`rigging-adapters/litellm_adapter.py`](../packages/rigging-adapters/src/rigging/adapters/litellm_adapter.py)
wraps any LiteLLM-compatible model as a rig participant. See example
[`02_three_vendor_rig`](../examples/02_three_vendor_rig/).

### Can I use it with MCP tools?

Yes. [`rigging-adapters/mcp_adapter.py`](../packages/rigging-adapters/src/rigging/adapters/mcp_adapter.py)
wraps an MCP server such that each tool becomes a rig capability.
ADR-0008 explains the translation rules.

### Can I write my own adapter?

Yes — and we want you to. The adapter contract is small: implement the
`Agent` protocol from `rigging-core`. The three reference adapters are
all under 200 LOC each. See
[`packages/rigging-adapters/`](../packages/rigging-adapters/).

### Can a rig participant be a *human*?

There is nothing structurally preventing it. A human-as-agent just means
the `execute` method blocks on a human action. The contract format does
not care. The benchmark probes assume programmatic agents, but the
runtime does not.

---

## Project & community

### Who is this for?

- Engineers building production multi-agent systems where blame
  attribution matters.
- Academic researchers who want a reference implementation to compare
  their own rigs / contracts / verifiers against.
- Open-source maintainers of harness frameworks who want a stable
  interop substrate.

### What does "v0" mean here?

It means the specs (`rigging/agent-card/v0`, `rigging/contract/v0`, etc.)
are *frozen for v0* and v1 is allowed to break them. No
backwards-compatibility shims will be added between v0 and v1. The whole
point of v0 is to make the v0 → v1 transition cheap by making it
explicit.

### Will you ship this to PyPI?

Yes. The package is currently in pre-release mode (you install from a git
checkout). The PyPI release will happen once we have one external rig
implementation scoring against the benchmark, so the v0 contract has
been stress-tested by something other than the reference.

### How can I help?

- Run the benchmark against your own multi-agent system and file the
  results.
- Write a real-world harness adapter (we will merge it).
- Find a blame-chain scenario the extractor gets wrong and file it as
  an issue. We will fix it.
- Disagree with a design call and write a counter-ADR. We will engage.
