# Phase 1 — THINK: open questions

> No code is written until each of these has a defended answer.
> The point of this document is to make the irreversible decisions
> explicit so they can be re-litigated in an ADR instead of in commit
> history.

---

## Q1. What is the smallest possible delegation contract that is still useful?

A delegation contract is the *bill of lading* exchanged between two agents
before any work is done. Strip away everything but what is needed for the rig
to make decisions about three things at runtime — *routing, cost, and blame* —
and you arrive at a contract that is depressingly small:

```json
{
  "contract_id": "01HW8E4QV3X8N2W3F1A0X5KQAB",
  "caller":     "did:rig:Vk3z…7p",
  "callee":     "did:rig:Q9aH…2c",
  "capability": "translate_pdf",
  "cost_budget": { "unit": "usd", "max": "0.50" },
  "verifier":   "self",
  "expiry":     "2026-05-15T18:00:00Z",
  "signature":  "<JWS over the above, signed by caller>"
}
```

Seven fields earn their place: a correlation identifier so traces can be joined
across process boundaries; the caller and callee DIDs so identity is preserved
end-to-end; a capability name that *must* appear in the callee's signed agent
card (a contract referencing an undeclared capability is invalid on its face);
a single-dimensional cost budget so the runtime can enforce something concrete;
a verifier handle (which may be the callee itself or another agent); an
expiry; and the caller's signature.

What is tempting but premature: preconditions/postconditions as a predicate
language (a DSL hazard that produces a half-baked Cedar/Rego clone); retry
policy (belongs to the caller's harness, not the contract); priorities and
SLAs (you can't enforce what you can't measure, and v0 has no scheduler);
multi-dimensional budgets (we *will* want tokens-and-dollars eventually, but
shipping one dimension forces clarity about what it means). The MCP authors
made the same minimum-viable bet on tools (`name`, `description`,
`inputSchema`) and have been able to layer on without breaking it.[^mcp-tools]

The single most important constraint: **a contract is invalid if the
capability it references is not present and signed in the callee's agent
card.** This binds the contract to a verifiable advertisement; it is what
makes the contract format itself trust-bearing rather than mere paperwork.

[^mcp-tools]: Anthropic, *Model Context Protocol — Tools* (2024-11), §2.

---

## Q2. Where does blame attribution come from?

In a multi-agent run, *something* misbehaved. The honest engineering question
is: against what evidence can you blame a specific component? Three things in
the trace make blame mechanically extractable:

1. **Signed envelopes at every hop.** Every output that crosses an agent
   boundary is signed by the producing agent's identity key. If the verifier
   later rejects the planner's plan, the signature pins the bad output to the
   planner's keypair. The signature is the receipt.

2. **Span-level separation of harness events from model events.** Inside an
   agent's harness, the OpenTelemetry trace distinguishes
   `harness.tool_call`, `harness.retry`, `model.completion`, and so on. If the
   *content* of the model completion is wrong, blame is on the model. If the
   harness silently swallowed an exception and synthesized a fallback
   response, blame is on the harness. If the rig delivered the wrong contract
   to the wrong callee, blame is on the rig itself — and `rig.delegation.id`
   plus `rig.callee.agent_id` will show that. This is the same discipline
   distributed-tracing reviewers have used since Dapper[^dapper] and what
   recent work on accountability in multi-agent systems calls
   *attributability*.[^accountability]

3. **The blame chain.** Every span carries `rig.blame.chain`: the ordered DAG
   of agent outputs that the current span *depends on*. When a final output
   is rejected, you can walk back along this chain and find the earliest
   span whose output, if replaced with ground truth, would have prevented
   the rejection. That span's signing agent is the proximate cause; the rig
   layer is exonerated by the existence of a non-empty blame chain that
   terminates inside another agent's trust domain.

The deliberate corollary: **the rig must never transparently retry on its
own.** A silent retry severs the chain of custody between the contract
signature and the actual delivered output, and destroys the basis for blame.
Retries are first-class events that produce new contracts with their own
identifiers.

[^dapper]: Sigelman et al., *Dapper, a Large-Scale Distributed Systems Tracing
    Infrastructure* (Google Tech Report, 2010).
[^accountability]: Christianos et al., *Accountability in Multi-Agent
    Systems*, arXiv:2402.05005 (2024).

---

## Q3. What is the relationship between an agent card and an MCP server descriptor?

These look superficially similar — both describe named, typed capabilities —
and treating them as interchangeable is a common mistake. They are *dual*.

An **MCP server descriptor**[^mcp-spec] describes what an agent *can use*: it
enumerates the tools available *to* an LLM-backed agent. The descriptor is
read by the agent's harness as part of forming the prompt. It is the
*consumer-side* surface.

An **agent card** describes what an agent *can do*: it enumerates the
capabilities the agent will accept delegation for, signed by its identity
key. The card is read by other agents (or by the rig on their behalf) when
they need to decide whether to delegate. It is the *producer-side* surface.

A consequence: an agent may *both* expose an agent card and consume MCP
servers. Its card might say "I can translate PDFs" (capability advertised to
other agents) while its harness internally calls an MCP server that exposes
`extract_pdf_text` and a translation model. The MCP descriptor never leaks
out of the agent's harness boundary. The agent card is the *only*
externally-visible contract for what this agent does.

A cleaner way to put it: MCP server descriptors are the agent's *tool
manifest*; agent cards are the agent's *job description*. ADR-0008 formalizes
the relationship and forbids the runtime from conflating them.

[^mcp-spec]: Anthropic, *Model Context Protocol Specification* (2024-11),
    §3.2 "Server Capabilities".

---

## Q4. How is cost attributed when B subcontracts to C?

Three honest options exist; each has been tried in production. We pick **(c)
explicit budget propagation** and defend it.

(a) *Flat caller-pays* — A's budget is debited for every downstream call,
regardless of depth. Simple, but it lets B burn A's budget on any
subcontract B chooses. Trust-asymmetric: A delegates a small task and B can
spend the whole envelope. This is what naïve LangGraph supervisor patterns
do today, and it is consistently the surprise that wakes someone up at 3 AM.

(b) *Call-chain accumulation* — every agent in the chain is debited
proportionally. Sounds fair; in practice it muddies attribution. If A spent
$1 and the chain A→B→C is debited $0.33 each, you cannot answer "how much
did task X cost?" because every agent's costs are now a mixture of every
task it participated in.

(c) *Explicit budget propagation* — B receives a contract from A with budget
$1. To subcontract to C, B *must carve out* a sub-budget from its own
allocation: e.g., a contract from B to C with budget $0.40. C bills against
*that* allocation, not A's. If C exceeds, the failure is local: C breached
its contract with B. A's budget is untouched until B explicitly bills A.

The third option is the only one that makes cost a *property of a contract*
rather than a property of an agent. This matters for the same reason capability
isolation matters in capability-based operating systems[^capsystems]: you can
reason about a sub-call without reasoning about the entire call graph. It also
gives the verifier a clean predicate to enforce: every child contract's budget
must be ≤ the unspent budget on its parent.

(Recorded as ADR-0006.)

[^capsystems]: Miller, *Robust Composition: Towards a Unified Approach to
    Access Control and Concurrency Control* (PhD thesis, JHU, 2006).

---

## Q5. What is the verifier's relationship to the rig?

The verifier can be modeled two ways: as a privileged role *outside* the rig
(special-cased by the runtime), or as just another *agent under the rig*
whose declared capability happens to be `verify`. We choose **verifier-as-
agent**.

The argument: every special case in the rig runtime is a future bug. A
privileged "verifier-outside-the-rig" needs its own identity model, its own
cost-attribution rules, its own failure semantics, and — critically — its
own audit trail that is *not* part of the cross-agent trace. Treating the
verifier as a rig participant means the rig's invariants apply to it
uniformly: it has an agent card, its outputs are signed, its decisions
appear in `rig.verifier.verdict` spans, and disagreements between verifiers
become a *composition* problem (vote ensemble, recursive verification) rather
than a *runtime* problem.

The price: infinite recursion is possible. "Who verifies the verifier?" In
v0 we cap recursion depth at three and require that the leaf of any
verification chain be marked `trust_propagation: "sealed"` (it is trusted
without further verification). This matches how reflection works in formal
verification systems[^metareasoning]: at some depth you must declare bedrock,
and the system makes that declaration *explicit and signed* rather than
hidden.

(Recorded as ADR-0007.)

[^metareasoning]: Russell & Wefald, *Do the Right Thing: Studies in Limited
    Rationality* (MIT Press, 1991), Ch. 3 on metareasoning and termination.

---

## Q6. What does "the rig fails gracefully" mean?

"Gracefully" is a word that hides too much. Concretely: when a callee is
unreachable (network failure, expired key, agent process gone), the rig
MUST:

1. **Void the contract.** The unfulfilled contract is marked `voided` in the
   trace with reason `callee_unreachable`. It cannot be silently retried.
2. **Surface a typed failure.** The caller receives a `RigError.CalleeUnreachable`
   exception carrying the contract ID, the callee DID, and the last-known
   liveness signal (timestamp of last successful contact, if any).
3. **Not synthesize fallback content.** Producing made-up output on the
   callee's behalf would forge the callee's signature, which is the single
   thing the rig must never do. Better to fail loudly.
4. **Preserve partial trace.** Any spans the callee did emit before
   disappearing are kept; the trace shows what work was completed and what
   was lost.

Decisions about retry, fallback, degradation, and human-in-the-loop escalation
belong to the *caller's harness*, not to the rig. This is the same boundary
distributed systems engineers have learned the hard way: idempotency and
retry are concerns of the application, not the transport.[^lameportetal] The
rig is transport-plus-trust, not a control plane for resilience.

A secondary case: the *verifier* is unreachable. Same semantics: contract is
voided, caller receives `RigError.VerifierUnreachable`, no implicit
acceptance. A contract whose verifier cannot opine is by definition
unverified, and the rig refuses to admit unverified output as if it were
verified.

[^lameportetal]: Lamport, *Time, Clocks, and the Ordering of Events in a
    Distributed System*, CACM 21:7 (1978). The general lesson: do not paper
    over partial failure inside a protocol that promises atomicity.

---

## Cross-cutting notes

A pattern in the answers above: **every time we were tempted to special-case
something inside the runtime, we instead pushed the case out to the
contract.** The runtime stays small; the contract carries the semantics. This
is the same instinct that made Unix `read(2)` win over richer record-oriented
I/O — the structure lives in the data, not the kernel — and it is the
discipline most likely to keep v0 honest.

The other recurring pattern: **make the rig refuse to silently fix things.**
Silent retries, fallback synthesis, transparent failover — every one of them
sounds friendly and every one of them severs blame attribution. A rig that
fails loudly is a rig you can debug.
