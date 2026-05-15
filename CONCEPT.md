# Rigging

*If Harness is for one agent, Rigging is for the fleet.*

---

A harness is the thing that wraps an LLM and makes it useful. It owns the
agent's loop, its memory, its tool surface, its observability, its evals.
The term has settled in the industry the way "container" did a decade ago —
the same idea was reinvented in five places, the names varied, and then
practitioners agreed on a word and moved on. Every serious agent
infrastructure team now has a harness, and the better ones now have an
opinion about how to swap harnesses without rewriting the agent.

We are now well past the point where one harness is enough.

The interesting systems in 2026 do not have an agent. They have a planner,
two coders that disagree, a reviewer that gates merges, a test-runner that
is older and more boring than any of them, a security scanner that belongs
to a different team, a release manager that runs on someone else's
infrastructure, and a verifier whose entire job is to look at the planner's
plans and reject the ones that try to do too much. Each of these is its own
agent. Each has its own harness. Each has its own opinions about retries,
observability, and budget. They were not designed to work together. Most of
them were not designed by the same team. Some of them were not designed by
humans whose names anyone remembers.

And yet they have to behave like a single system.

This is the layer that does not have a name yet. *Rigging.*

---

The word matters. There is a temptation, when naming a new abstraction, to
invent something Greek and proprietary. Resist it. The English word
*rigging* — the maritime sense — is exactly right. The rigging of a sailing
ship is the entire web of ropes, blocks, lines, and spars that translates
the wind in the sails into motion of the hull. The sails do not move the
ship. The hull does not move the ship. The rigging does. The sails and the
hull are *both* useless without it, and a beautiful sail on a poorly-rigged
ship will tear itself apart in a storm.

You can buy excellent sails. You can buy a beautiful hull. The thing you
must build yourself is the rigging.

(We will note the obvious connotation of *rigged* once and then leave it
behind. We are not talking about fraud. We are talking about ropes.)

---

What is a rig, concretely?

A rig is a runtime that does three things, and refuses to do anything else.

It makes **capability advertisements** explicit. Today, when one agent calls
another, the caller knows roughly what the callee can do because someone on
Slack mentioned it. Maybe there is a wiki page. Maybe the calling agent's
prompt was hand-written with the callee's name in it. The advertisement is
informal. In a rig, the callee publishes a signed *agent card* that names
its capabilities, declares the inputs and outputs for each, and binds the
declaration to a long-lived identity key. The card is the only thing the rig
will route against. If the capability is not on the card, the call does not
happen. If the card is not signed, the rig will not load it. There is no
informal channel.

It makes **delegation contracts** explicit. When agent A wants agent B to do
work, it does not send a free-text request. It proposes a contract: *I, A,
ask you, B, to perform capability C, with budget D, under verifier V, before
time T.* B signs the contract or rejects it. The rig persists the contract.
Every action that follows — every span in the trace, every cost debit, every
verifier verdict — is bound back to that contract identifier. If something
goes wrong tomorrow and the on-call engineer needs to know what was agreed
to, the contract is the document.

It makes **blame attribution** mechanical. When the system fails, the trace
contains an ordered chain of signed envelopes. Each envelope is an output
produced by some agent under some contract. You can walk the chain
backwards. The first envelope whose contents, if replaced with ground
truth, would have prevented the failure — that envelope's signing key is
the proximate cause. Not "the rig screwed up somewhere." Not "the model
hallucinated." Specifically: *this output, signed by this agent, under this
contract, at this time*. The rig does not adjudicate fault — it does not
know what the right answer was — but it makes the question of fault
mechanically *answerable*.

That is the entire job. Cards, contracts, blame. Everything else in a rig
exists to keep those three primitives honest.

---

Stop and notice what a rig is *not*.

A rig is not a model. It does not run inference. It has no idea what a token
is. It will never apologise for being unable to write a sonnet.

A rig is not a harness. It does not own the loop, the memory, or the tools
of any agent that participates in it. If you change the harness of
participant B, the rig does not care, provided B's agent card and identity
key are unchanged.

A rig is not a protocol. MCP is a protocol. A2A is a protocol. ACP is a
protocol. A rig *uses* protocols — typically several at once. The contract
flows over A2A; the tool calls inside a participant's harness flow over MCP;
the trace flows over OpenTelemetry. A rig does not invent a new wire format,
and any rig implementation that does is, by this definition, doing it wrong.

A rig is not a supervisor. Supervisor patterns — LangGraph's, CrewAI's,
Teradata `loom`'s — are application-level conventions for routing tasks
inside one trust domain. A rig is the layer one floor up: it lets two
supervisor-managed agent populations *delegate to each other across trust
domains*. If your supervisor pattern works inside one company's repository,
a rig is what makes it work between two companies' repositories.

A rig is not a marketplace, a directory, a router, or a scheduler. Each of
those is a real layer. Each is a real product. None of them is a rig.

What a rig is, precisely: *the thin, opinionated, runtime layer that turns
ad-hoc multi-agent glue into a typed, signed, auditable substrate.*

---

You can tell the layer is real because it is already being open-coded
everywhere.

Look at any production multi-agent stack. There will be a function called
`route_to_agent` or `delegate` or `supervisor_next`. Inside it, three or
four things happen, every time. A trace ID is generated. A pseudo-contract
— usually a JSON dict — is constructed. Some sort of identity for the
calling agent is asserted, perhaps a string in a header, perhaps nothing.
A cost counter is incremented somewhere. If the callee fails, an exception
is caught and reshaped, sometimes with a retry, sometimes not. None of it
is consistent across calls. None of it survives across services. None of it
is signed.

This is the same pre-history every infrastructure abstraction has gone
through. Before Kubernetes there was a function called
`deploy_service_to_box` and it ran SSH in a loop. Before Docker there was
`build_my_python_app` and it copied a tarball to a chroot. Before TCP there
was a thing in the corner of every protocol that did
`retry_until_acknowledged` and got it wrong differently each time. The
function was real, and useful, and load-bearing, and every team wrote it,
and the cost of *not* having a name for the abstraction was the entire
field's collective inability to talk about its bugs.

Rigging is the name for the next one of those.

---

The most important discipline a rig enforces is *refusing to silently fix
things*.

This sounds backwards. Resilience is good. Retries are good. Fallbacks are
good. A friendly system absorbs partial failure and gives the caller a
working answer.

A friendly system also destroys the chain of evidence that blame attribution
depends on.

If agent A calls agent B, and B fails, and the rig silently retries on
B' — which gets a different model assignment, or runs in a different
region, or has a different memory state — then the output the caller
receives is not signed by the agent the caller addressed. The contract A
believed it had with B has been quietly transferred to B', and A has no
record of the substitution. When the output is wrong tomorrow, the trace
shows A→B but the work was done by B', and the blame analysis terminates
in a contradiction.

A rig refuses to do this. Retries are first-class events with their own
contracts and their own identifiers. Fallbacks are explicit choices the
caller makes after a typed failure. The rig fails loudly, with a typed
exception, every time. This makes rig-managed systems initially *more*
brittle than ad-hoc systems and eventually *much* more debuggable. The
brittleness is a feature: it forces the caller's harness — which is where
retry policy belongs anyway — to make its retry behavior explicit.

The general lesson, from a generation of distributed-systems engineers:
**the protocol that promises atomicity but quietly hides partial failure is
the one that wakes you up at 3 AM**. Lamport said this in 1978 about clocks
and event ordering. It is just as true for agent composition in 2026. A rig
that hides partial failure under retries is a rig you cannot debug; a rig
that surfaces it as typed errors is a rig you can.

---

Cost attribution is the other place rigs differ from supervisors. The naïve
choice — *the original caller pays for everything in the call graph* — is
the choice every prototype makes and every production system regrets. Once
agent B can subcontract to agent C without A's awareness, A is on the hook
for arbitrary downstream spending, and the only check on that spending is
B's discretion. This is the agentic version of letting a subcontractor put
arbitrary charges on the general contractor's credit card.

The right move is the move capability-based operating systems made: cost is
a property of a contract, not of an agent. A passes B a budget. B may
subcontract to C only by carving out a sub-budget from its own allocation.
C's overruns are visible to B; B's overruns are visible to A; A's budget is
inviolable. This composes. It survives recursion. It makes "how much did
that task cost?" a question with a defensible answer, broken down by which
agent contributed what.

It also requires the rig to know about budgets in the first place — which
is why the cost_budget field is not optional in the contract format. A
contract without a budget is a contract with an unbounded budget, and an
unbounded budget is what a supervisor pattern silently has when no one was
paying attention.

---

The verifier deserves its own paragraph, because it is the design choice we
got wrong twice before getting right.

Early in this work we wanted the verifier to be a privileged role *outside*
the rig — a kind of trusted oracle that the runtime would invoke at
specific points. This is appealing because it puts the verifier in a clean,
protected slot, distinct from the agents under test.

It is also wrong. Every special case in the runtime is a future bug; a
privileged verifier requires its own identity model, its own cost story,
its own audit trail, and — soon — its own argument with operators about
*who* gets to be a verifier and *why*. The runtime accretes complexity.
Worse, you cannot easily compose two verifiers (a vote ensemble, a
recursive auditor) because they are not first-class participants.

The right move is to treat the verifier as just another rig participant
whose declared capability happens to be `verify`. The rig's invariants
apply to it uniformly. Its decisions appear in the trace. Disagreements
become a composition problem (vote, recurse), not a runtime problem. The
price is the obvious one — *who verifies the verifier?* — and the answer is
the obvious one: at some depth, you declare bedrock and sign it. The depth
is bounded. The bedrock is explicit. This is how every formal verification
system terminates, and it is the only honest way for a rig to terminate
too.

---

The reason this layer matters now, and did not matter three years ago, is
that the work being done by multi-agent systems is starting to be load-
bearing.

A toy multi-agent demo can have terrible rigging and no one notices,
because the failures are amusing. A financial reconciliation pipeline run
by three agents from three vendors cannot have terrible rigging, because
the failures are billable to someone. A code-review system that auto-merges
when three agents agree cannot have terrible rigging, because the failures
ship to production. The shift from demo to production is the shift from
"who cares about composition" to "composition is the system."

We are in the first months of that shift. The teams who get rigging right
will look, in five years, like the teams who took CAP theorem seriously in
2010 or who took TLA+ seriously in 2015. Most teams will not. Most teams
will continue to write `route_to_agent` and absorb the cost. The argument
of this project is that the cost is no longer worth absorbing, and that the
layer is ready to be named.

---

There is a version of this essay that ends with a manifesto. We will resist
it. The right way to end is with a refusal:

A rig refuses to route against unsigned cards.

A rig refuses to issue contracts whose capabilities are undeclared.

A rig refuses to retry silently.

A rig refuses to attribute cost to anyone other than the contract holder.

A rig refuses to admit unverified output as verified.

A rig refuses to be a marketplace, a scheduler, a router, or a harness.

The art of this layer is in what it refuses, not in what it provides.

You can have a great harness on every agent and still have terrible rigging.

If you are not the model, and you are not the harness, you are the rigging.

Welcome aboard.
