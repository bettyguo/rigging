# Related Work

> A survey of what already exists. For each entry the question is the same:
> *what does Rigging do that this does not?* If the answer is fuzzy, the
> positioning of Rigging is fuzzy and the concept needs sharpening, not the
> implementation.

The short version: every system below solves *one slice* of the composition
problem — the wire format, the supervisor pattern, the identity record, the
harness portability layer. Rigging is the layer that *sits above* all of them
and makes the composition itself the named, typed, signed object.

---

## Google A2A (Agent2Agent)

A2A is an HTTP+JSON-RPC protocol for inter-agent messaging, with a notion of
an *Agent Card* discovery document advertising what an agent does, and a
task lifecycle (`submit`, `get`, `cancel`) for long-running work. A2A was
proposed by Google in April 2025 and contributed to the Linux Foundation later
that year; the v0.3 specification standardised the agent card schema and a
streaming task model. Its strengths are exactly the wire-format strengths:
clear endpoints, framing, message envelopes, and an agreed shape for capability
advertisement.

*What Rigging does that A2A does not.* A2A defines the *channel* between
agents; it does not define the *contract* about cost, verifier, blame, or
trust propagation that flows over the channel. A2A's agent card is a
discovery document — it tells you what is callable; it does not tell you
under what terms. Rigging treats the A2A agent card as a starting point and
extends it: every Rigging agent card is A2A-compatible at the wire layer,
plus signed, plus carries verifier compatibility and cost models. The rig
*contract* is the missing semantic above A2A's *message*.

---

## Anthropic MCP (Model Context Protocol)

MCP is a JSON-RPC protocol between an agent and its tools (filesystem, search,
databases, etc.), with a small, opinionated set of primitives: `resources`,
`tools`, `prompts`, `roots`, `sampling`. Servers expose tools; clients (the
agent's harness) call them. MCP has become the de-facto standard for the
agent↔tool boundary since its November 2024 release, with hundreds of public
servers and adoption inside Claude Desktop, OpenAI's responses API, and the
major IDE assistants.

*What Rigging does that MCP does not.* MCP describes one direction of one
boundary — the tool surface visible *to* an agent. It is silent on what
happens when two MCP-using agents need to collaborate. There is no concept
of a delegating call, no signed identity for the calling agent, no cost
attribution, no notion of a verifier between agents. Rigging operates *one
floor up*: an MCP server is an agent's tool manifest; a rig contract is
how two such MCP-using agents safely delegate to each other. The relationship
is formalized in ADR-0008.

---

## IBM ACP (Agent Communication Protocol)

ACP is IBM/BeeAI's REST-based protocol for stateful agent communication,
optimized for long-running tasks and tool-using agents in enterprise stacks.
It introduces the notions of a *session*, a *turn*, and an *agent manifest*,
and offers richer state management than A2A's task model. The 1.0 release
landed in late 2025 and is the protocol of choice inside several Linux
Foundation AI projects.

*What Rigging does that ACP does not.* ACP, like A2A, is a wire format with
a session model. It is silent on signed identity, on cost-budget enforcement
between sessions, on verifier roles, and on blame attribution after a session
fails. ACP's *agent manifest* is a description; Rigging's *agent card* is a
signed and verifiable *commitment*. A rig can ferry contracts over ACP just
as well as over A2A — the protocol is interchangeable; the contract is not.

---

## OASF (Open Agent Specification Framework)

OASF, contributed to the Linux Foundation in 2025, is a meta-description
layer: a standard schema for describing what an agent is (purpose,
capabilities, models, training data, known limitations). Think of it as the
*model card* idea generalized to agents. OASF is read by humans and by
tooling that catalogs available agents in an enterprise marketplace.

*What Rigging does that OASF does not.* OASF is a documentation layer; it has
no runtime presence. Two agents can both have impeccable OASF descriptions
and still fail catastrophically at the moment one tries to delegate to the
other because nothing in OASF is *enforced at call time*. Rigging is the
runtime that takes OASF-style declarations and makes them load-bearing: an
agent card declares a cost model, and the rig refuses to issue a contract
whose budget exceeds that model. OASF is the catalog entry; the rig contract
is the purchase order.

---

## KYA / Trulioo Digital Agent Passport

KYA ("Know Your Agent", riffing on KYC) and the Trulioo Digital Agent
Passport are identity products: signed credentials that assert an agent's
operator, jurisdiction, compliance posture, and provenance. Launched in
mid-2025, they are aimed at regulated industries that need an auditable
record of which legal entity is on the hook for what an agent does.

*What Rigging does that KYA does not.* KYA solves *who*; it does not solve
*what under what terms*. A KYA passport tells you that an agent is operated
by Acme Co.; it does not tell you that this particular call from Acme's
agent to Initech's agent was authorized for $0.50 and is subject to verifier
V. Rigging's `agent-card-v0` can embed a KYA-style assertion as one of its
signed *trust assertions*, and the runtime can refuse delegation when the
required jurisdictional or compliance posture is missing. KYA is an input to
Rigging, not a substitute for it.

---

## OpenHarness.ai

OpenHarness is a portability SDK for the harness layer: a way to write your
agent's tools, memory, and loop in one place and run them under different
host harnesses (Claude Code, Cursor, a custom CLI, a service). It addresses
the lock-in problem of harness-specific glue and is the closest thing the
ecosystem has to an *agent runtime portability standard*.

*What Rigging does that OpenHarness does not.* OpenHarness lets you *move*
an agent between harnesses; it does not let two harnessed agents *compose*.
Rigging is orthogonal: an OpenHarness-portable agent and a custom-harnessed
agent can both expose Rigging agent cards and delegate to each other.
OpenHarness is *one agent, many hosts*; Rigging is *many agents, one
composition*. The two complement cleanly and we have an adapter on the v1
roadmap for OpenHarness-wrapped agents.

---

## LangGraph supervisor pattern

LangGraph's supervisor pattern (and the broader StateGraph DSL it sits in) is
the most widely-deployed approach to multi-agent composition in Python today.
A supervisor node receives a request, routes it to one of several worker
nodes, and integrates their outputs into a final answer. It is small,
expressive, and has shipped in many production systems since LangChain
0.2.

*What Rigging does that LangGraph supervisors do not.* The supervisor
pattern is an *application-level* convention: cost, identity, blame, and
trust between supervisor and workers are open-coded in each project, usually
as a tangle of try/except blocks and ad-hoc trace IDs. Rigging is the *named
primitive* that replaces this tangle. A rig is the supervisor pattern with
the implicit decisions made explicit: contracts instead of routing functions,
signed agent cards instead of class names, blame chains instead of
print-statement archaeology. The intent is not to compete with LangGraph but
to give LangGraph users a typed substrate for the parts they were already
inventing by hand.

---

## CrewAI task delegation

CrewAI organises agents into *crews* with declared *roles* and *tasks*. An
orchestrator assigns tasks to agents based on roles, and agents can delegate
subtasks to peers via an "Ask Question" tool. The framework is friendly,
opinionated, and has driven a great deal of demoware in 2024–2025.

*What Rigging does that CrewAI does not.* CrewAI's delegation lives entirely
inside one Python process and one trust domain: there is no cross-vendor
signed identity, no cost-budget propagation between agents, no verifier role,
and no machine-extractable blame chain. Roles are strings; identity is
process-local. Rigging makes each delegation a signed contract that survives
crossing trust domains. A CrewAI crew can be wrapped as a *single* rig
participant whose internal delegation is opaque, or it can be re-expressed as
a rig of N participants each with their own agent card. Both are valid; the
latter is what Rigging is for.

---

## `loom-agent` PyPI package

The `loom-agent` package (released March 2026) is a small, opinionated agent
runtime focused on threading multiple LLM calls through a single typed state
machine. It is heavily inspired by railway-oriented programming and pairs
well with structured-output models. Its core abstraction is a `Loom`: a
sequence of typed transitions over a shared state.

*What Rigging does that loom-agent does not.* `loom-agent` is single-agent,
single-process, deliberately. Its threading metaphor is intra-agent (multiple
calls woven into one task), where Rigging's is inter-agent (multiple agents
woven into one system). The name collision is unfortunate; the layers do not
overlap. A `loom-agent`-internal pipeline can sit *inside* a rig participant
without either layer noticing the other.

---

## Teradata `loom` multi-agent harness

Teradata's `loom` (no relation to the PyPI package) is an enterprise
multi-agent harness shipped with Teradata's analytics platform in 2025. It
provides a closed-source supervisor, a small DSL for declaring agent roles,
and integration with Teradata's identity and observability stack. It is
LangGraph-like in spirit but built for enterprise SQL/analytics workloads.

*What Rigging does that Teradata `loom` does not.* Teradata `loom` is a
vertical product: agents inside it compose well, but agents outside it are
invisible to it. Rigging is the *horizontal* layer that lets a Teradata
`loom`-managed agent collaborate with, say, a Goose-harnessed agent at
another company, with a contract that both their compliance teams can read.
The benchmark — `Rigging-Bench v0` — was explicitly designed to be runnable
by Teradata `loom`, Crew, LangGraph, or any other supervisor framework, so
that the framework competition can be settled on shared ground.

---

## Synthesis

The honest summary of the landscape: *protocols, frameworks, and identity
products exist; the layer that binds them does not.* Rigging fills exactly
that gap. We do not replace MCP (we ride above it). We do not replace A2A or
ACP (we ride above them too). We do not replace harnesses (we compose them).
We do not replace OASF or KYA (we consume their assertions as inputs to
contracts). What we replace is the **tribal knowledge** that today lives in
each team's `supervisor.py`.

If, after reading this survey, the reader cannot tell what Rigging adds — the
fault is in our positioning, and we will rewrite this document until it can
no longer be misread.
