# The Rigging Completeness Matrix

> A benchmark for cross-agent composition systems. v0.

The matrix scores a rig implementation on **five axes**, each yielding a
number in `[0.0, 1.0]`. A score of 1.0 means perfect; we publish the
reference implementation's scores honestly and reviewers should distrust
any submission with 1.0 across the board.

The matrix is intentionally narrow. It does not try to evaluate
*usability*, *cost*, *latency*, or *coverage of LLM providers*. Those
are real but unrelated. The matrix scores the claims a rig makes about
identity, contracts, cost, and blame — the claims that distinguish a
rig from an ad-hoc supervisor.

## The five axes

### 1. Capability-advertisement fidelity
For each capability the agent declares on its card, does its actual
behaviour conform to the declared input and output schemas? The score
is the fraction of held-out probes that produce schema-valid output.

Probes are JSON payloads constructed against the input schema. The
agent's output is validated against the output schema. The probe set is
shipped with the benchmark; the agent's card is not allowed to refer to
it.

### 2. Delegation-contract expressiveness
Can the contract format encode each of the following standard
delegation patterns?

- *Handoff:* A → B, single call.
- *Voting ensemble:* A → {B, C, D}, A picks the majority.
- *Recursive subcontracting:* A → B; B → C; B → D.
- *Conditional delegation:* A → B; on rejection, A → C.

Score = fraction expressible. The contract format is allowed to use
operator-level composition (multiple contracts forming a pattern); a
single contract need not encode the pattern by itself.

### 3. Identity propagation under adversarial conditions
Under the following adversarial scenarios, does identity remain
preserved end-to-end?

- *Key compromise:* An agent's private key is leaked; an attacker
  signs a contract as that agent. Score 1 if the rig accepts only the
  legitimate key's signatures *and* would accept a revocation
  notification if one were issued (v0 stub).
- *Replay:* A valid contract from an earlier run is resubmitted.
  Score 1 if the rig rejects via `contract_id` uniqueness or `expires`.
- *Identity spoofing:* An agent claims another's DID without holding
  the corresponding private key. Score 1 if the rig rejects at card
  verification.

Score = fraction passed.

### 4. Cost-attribution accuracy
For a multi-hop run with known per-agent costs, does the rig's
per-contract ledger match ground truth? Score = 1 - normalised L1 error.

The benchmark sets up a chain A → B → C with synthetic cost functions
that yield known totals; the rig's ledger is compared.

### 5. Blame-resolution correctness
Under a suite of injected-failure scenarios, does the blame chain
extractor identify the responsible agent? Score = F1 between extracted
proximate-cause DIDs and the ground-truth offending DIDs across the
suite.

Scenarios:
- Adversarial leaf (one bad worker).
- Adversarial middle agent (a planner that misroutes; verifier catches
  the worker, but the planner is the root cause).
- Verifier itself wrong (deliberately accepting bad output; the
  verifier's parent is responsible).
- Budget overrun deep in the tree.

## Smoke vs full

The benchmark runs in two modes:

- **Smoke** (`rig bench run`) — under 5 minutes on a laptop. Each axis
  uses a small probe set; sufficient for CI and for sanity-checking
  changes.
- **Full** (`rig bench run --full`) — larger probe sets, more
  adversarial scenarios, more synthetic chains. Used to publish a
  number in a paper or release notes.

## Output format

Results are emitted as JSON and Markdown. The JSON contains scores
and per-probe details; the Markdown contains the headline scores and
notes. Both files are placed under `benchmarks/results/`.
