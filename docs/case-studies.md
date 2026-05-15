# Case studies

> Synthesised from real conversations with practitioners. Names and
> numbers are redacted; the *patterns* are not. If you have a story like
> these and would like to see it added — or contested — open an issue.

---

## Case study 1 · The runaway subcontractor

**Industry:** Fintech.
**Team:** A platform engineering group running ten product agents for
research, summarisation, and chart generation. About 30 engineers.

### Before

Their planner agent (built on a popular supervisor framework) ramped a
research subtask onto a chain of three reasoning subagents. Under load,
one of the subagents began silently spinning off siblings on transient
errors — what the team later realised was a poorly-thought-out
"resilience" fallback inside the framework.

Each sibling re-issued the same query against the same backing model.
There was no enforced budget, only soft per-task spend alerts that fired
on a 15-minute polling interval.

One Friday afternoon, a single user-initiated task spawned an estimated
**52 siblings** across two hours. The total token spend hit **\$8,400**
before alerting tripped. Six hours of incident response. One refund. A
month of trust-building with finance.

### What rigging would have prevented, structurally

- **The retry would have been a new contract.** Every retry has its own
  signed `contract_id`, its own caller-signed envelope, and its own
  per-contract budget. There is no "silent" retry in a rig.
- **The sibling's budget would have been carved.** A sibling subcontract
  can only carry a budget carved from the parent's allocation. The first
  sibling's overrun would have hit `BudgetOverrun` at `\$0.50`, not
  `\$8,400`.
- **The trace would have named the framework path.** The runaway pattern
  shows up as a fan-out of contracts under a single parent. The blame
  chain would have terminated at the offending framework adapter, with
  a signed envelope as proof.

### What rigging would *not* have prevented

The underlying bug — a poorly-thought-out resilience policy — would
still have been in the code. But the cost-cap would have been
\$0.50, not \$8,400, and the post-mortem would have started with a
signed envelope rather than a forensic log search.

---

## Case study 2 · The 3 AM "which agent broke it"

**Industry:** Developer tools.
**Team:** A code-review pipeline composed of four agents from three
vendors: a static analyser, a security scanner, a style reviewer, and a
test runner. Each from a different vendor's harness; integrated by a
hand-written supervisor.

### Before

Their code-review system auto-merged when three of the four reviewers
approved. One night, a regression made it through — a memory safety bug
that the security scanner *should* have caught but had silently scored
as a low-priority warning.

The post-mortem the next morning took **six engineers eight hours**:
- The static analyser ran in their internal CI cluster with custom
  log format.
- The security scanner was a SaaS with its own per-call IDs.
- The style reviewer was a local container with no persistent logs.
- The test runner was the only well-instrumented component.

Attributing fault required correlating four log streams by timestamp,
guessing at intermediate state, and three vendor support tickets. Two
of the four agents emitted no signed evidence of their decisions at all.

### What rigging would have given them

- **One trace.** Every reviewer's verdict is a signed envelope in the
  same trace, regardless of which vendor's harness it ran in.
- **One blame chain.** `rig trace inspect ./trace.json --highlight=blame`
  would have walked from the auto-merge decision backwards. The
  scanner's "low priority" verdict would be the proximate cause, signed
  by the scanner's identity key, with the verdict's reason field
  captured.
- **Six engineer-hours back.** The post-mortem starts with "the
  scanner's verdict said low-priority; here is the signed envelope; here
  is what the scanner saw as input." The other three reviewers are
  exonerated by their signed accepts.

### The composition fix is also explicit

The team's next move would be a *vote-ensemble verifier* (see example
05): "auto-merge only if all four reviewers, including a redundant
second scanner, accept." That fix is a one-line change in a rig — and
literally a new ADR's worth of complexity in a hand-written supervisor.

---

## Case study 3 · The "who said what" compliance audit

**Industry:** Regulated industry (insurance underwriting).
**Team:** Five-person research team running an automated triage pipeline
on policy applications. Three agents: an extractor, a risk scorer, and a
recommender.

### Before

A regulator asked, in a routine audit: *"For last month's automated
decisions, prove which agent made each call, under what budget, and
attach the evidence the agent used."*

The team had:
- Per-agent logs in three different formats.
- A unified application log that *referenced* agents by short string
  names, not signed identifiers.
- No structured record of *what input* each agent received — only what
  it returned.

Reconstructing the audit took **two weeks** and required hand-built
scripts that joined logs by timestamp and free-text application IDs.
The audit passed, but the team was told that next time the regulator
expected the answer "in days, not weeks."

### How a rig changes the answer

- **Every decision is a signed contract.** The contract records the
  caller, the callee, the capability, the inputs, the budget, the
  verifier, and the timestamp. It is the audit document.
- **Every output is a signed envelope.** "What did the recommender say,
  and what did it see as input?" is one query against the trace store.
- **Every cost is attributed to a contract.** Per-application,
  per-agent cost decomposition is mechanical.

The two-week audit becomes a SQL query against the OpenTelemetry trace
backend.

### Why this is more than convenience

The point is not faster audits — it is *legible* automation. When a
regulator (or a senior engineer, or a curious customer) asks "what
happened here?", the system has an answer in a form that humans agree
counts as evidence. A rig is not a compliance product, but it produces
the substrate compliance is built on.

---

## Pattern across the three

In each of these, **the bug was real and the rig would not have fixed
the underlying bug**. What the rig changes is the *cost of the bug*:

| | Before | With rig |
| --- | --- | --- |
| Case 1 | \$8,400 token bill | \$0.50, typed exception |
| Case 2 | 6 engineers × 8 hours | one blame chain, minutes |
| Case 3 | 2-week audit | a database query |

The rig is, in this sense, the **insurance product** of an agentic
stack: it does not prevent the storm, but it makes "what was damaged
and who is responsible" answerable. The premium is the discipline of
typed contracts and signed envelopes. The payout is every incident
that *used* to take a day to attribute.

---

## Submit a case study

Have a real failure mode a rig would have changed the cost of?
Open an issue. We synthesise these carefully to preserve anonymity, and
we always run the write-up by the original team before publishing.
