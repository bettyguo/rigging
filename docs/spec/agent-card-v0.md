# Rigging Agent Card Specification — v0

> Status: **DRAFT** · Version: `v0` · Last updated: 2026-05-15
>
> This specification uses RFC 2119 / RFC 8174 normative keywords.
> Companion specifications: `identity-v0.md`, `rig-contract-v0.md`.

---

## 1. Purpose

An *agent card* is the externally-visible, signed advertisement of what an
agent can do. It is the *only* document the rig consults when deciding
whether a delegation contract can be issued to that agent.

An agent card is, deliberately, **not**:

- a description of the agent's internal tools or memory (those live behind
  the harness boundary);
- an MCP server descriptor (that describes the *consumer* surface; the card
  describes the *producer* surface — see ADR-0008);
- a human-readable spec sheet (humans MAY read it, but its primary audience
  is other agents and the rig).

## 2. Card structure

### 2.1 Canonical JSON form

```json
{
  "card_version": "rigging/agent-card/v0",
  "agent_id":     "did:rig:<fingerprint>",
  "public_key":   "<base64-raw-ed25519-public-key>",
  "operator":     {
    "name":  "Acme AI Co.",
    "uri":   "https://acme.example/agents/translate",
    "contact": "agents@acme.example"
  },
  "capabilities": [
    {
      "name":          "translate_pdf",
      "description":   "Translate a PDF document into a target language.",
      "input_schema":  { "$schema": "https://json-schema.org/draft/2020-12/schema", ... },
      "output_schema": { "$schema": "https://json-schema.org/draft/2020-12/schema", ... },
      "cost_model":    {
        "unit":            "usd",
        "base":            "0.10",
        "per_input_unit":  "0.001",
        "per_output_unit": "0.001",
        "input_unit":      "page",
        "output_unit":     "page"
      },
      "verifier_kinds": ["self", "translation_quality_v1"]
    }
  ],
  "trust_assertions": [
    {
      "kind":     "kya",
      "value":    { "operator_did": "did:web:acme.example", "level": "verified" },
      "issuer":   "did:web:trulioo.example",
      "issued":   "2026-01-12T00:00:00Z",
      "expires":  "2027-01-12T00:00:00Z",
      "signature": "<JWS>"
    }
  ],
  "issued":    "2026-05-15T10:00:00Z",
  "expires":   "2026-11-15T10:00:00Z",
  "signature": "<JWS over the above with this field omitted>"
}
```

### 2.2 Required fields

The following fields MUST be present and well-formed:

| Field            | Type   | Requirement                                                      |
|------------------|--------|------------------------------------------------------------------|
| `card_version`   | string | MUST equal `"rigging/agent-card/v0"` for cards of this version.  |
| `agent_id`       | string | A valid `did:rig` per `identity-v0.md`.                          |
| `public_key`     | string | Base64-encoded 32-byte Ed25519 public key. MUST hash to `agent_id`. |
| `operator`       | object | Operator metadata; `name` is REQUIRED, others SHOULD be present. |
| `capabilities`   | array  | At least one capability entry (a card declaring no capabilities is invalid). |
| `issued`         | string | RFC 3339 timestamp.                                              |
| `expires`        | string | RFC 3339 timestamp; MUST be after `issued`.                      |
| `signature`      | string | JWS Compact Serialization (`alg=EdDSA`) over the canonical form. |

The following are OPTIONAL:

| Field                | Type   | Default behaviour                                |
|----------------------|--------|--------------------------------------------------|
| `trust_assertions`   | array  | Empty array — agent has no third-party attestations. |
| `aliases`            | array  | Empty — no alternative names.                    |

### 2.3 Capability entries

Each capability entry MUST contain:

- `name` — a string, unique within the card. The name MUST match
  `^[a-z][a-z0-9_]{0,63}$`.
- `description` — a human-readable string (1–500 characters).
- `input_schema` — a JSON Schema draft 2020-12 document.
- `output_schema` — a JSON Schema draft 2020-12 document.
- `cost_model` — a structured cost model (see §2.4).
- `verifier_kinds` — an array of strings naming verifier *kinds* the
  agent's output is compatible with. The special value `"self"` means the
  agent can verify its own output (a valid choice for deterministic
  capabilities; a suspect choice for LLM-backed ones).

### 2.4 Cost model

A cost model MUST declare a single `unit` (one of `tokens`, `usd`,
`wall_seconds`). The `base` field is the fixed cost of any invocation;
`per_input_unit` and `per_output_unit` scale with the declared
`input_unit` and `output_unit` strings. Decimals are encoded as strings to
avoid float drift (we adopt the same convention as the JSON-RPC currency
APIs).

This intentionally limits the cost model. Operators with multi-dimensional
costs (e.g., both tokens and dollars) MUST pick one dimension for v0; the
rig refuses to enforce a budget whose unit does not match the card's. A
multi-dimensional cost model is on the v1 roadmap.

### 2.5 Trust assertions

A trust assertion is a third-party-signed claim about the agent or its
operator. v0 defines two well-known `kind` values:

- `"kya"` — a Know-Your-Agent passport (e.g., Trulioo, similar issuers).
  The `value` is opaque to the rig but inspectable by policy layers.
- `"benchmark"` — a signed benchmark result. `value` includes the benchmark
  name, score, and revision. Used by `rig bench` to surface comparable
  numbers.

Implementations MUST verify the `signature` on each trust assertion against
the asserted `issuer`. Trust assertions whose signatures fail to verify
MUST be ignored (not rejected — an unverifiable assertion does not poison
the card).

## 3. Canonicalisation and signing

Agent cards are signed using JWS Compact Serialization (RFC 7515) with
`alg=EdDSA`. The signing input is the JCS-canonicalised (RFC 8785) JSON
representation of the card with `signature` set to the empty string.

Verifiers MUST canonicalise identically before verifying. Implementations
that re-emit a card (e.g., for caching) MUST preserve the original byte
form rather than re-serializing — re-canonicalisation is not idempotent
across all JSON libraries.

## 4. Discovery

v0 does not standardise a discovery mechanism. Operators MAY publish their
agent cards at:

- A well-known URL (e.g., `https://acme.example/.well-known/rig-agent-card.json`),
- An A2A-compatible discovery endpoint,
- A static file shipped alongside the agent's process.

The rig runtime accepts cards from any of the above; it does not crawl.

## 5. Lifecycle

### 5.1 Expiry

A card with `expires` in the past MUST NOT be used to issue new contracts.
In-flight contracts whose card has just expired SHOULD be allowed to
complete (a contract is bound to the card that was current at issuance
time, not to the agent's current card).

### 5.2 Updates

An operator updating an agent's capabilities re-issues a new signed card.
There is no in-place mutation. Consumers SHOULD cache cards by their
content hash; a content-hash change is sufficient signal to re-load.

### 5.3 Withdrawal

To withdraw a capability, the operator publishes a new card omitting that
capability. There is no "tombstone" record in v0.

## 6. Worked example

A minimal valid card. (Whitespace added for readability; the
canonicalised form is compact.)

```json
{
  "card_version": "rigging/agent-card/v0",
  "agent_id": "did:rig:tihtfhkojvxgu7emjqpsuoymjrlh7cu3",
  "public_key": "S3qKnywdPk9aa3yNng8aKzxNXm96i5wNHi86S1xtfo8=",
  "operator": { "name": "Worked Example Co." },
  "capabilities": [
    {
      "name": "echo",
      "description": "Echo the input string back unchanged.",
      "input_schema": { "type": "object", "properties": { "text": { "type": "string" } }, "required": ["text"] },
      "output_schema": { "type": "object", "properties": { "text": { "type": "string" } }, "required": ["text"] },
      "cost_model": { "unit": "tokens", "base": "0", "per_input_unit": "0", "per_output_unit": "0", "input_unit": "char", "output_unit": "char" },
      "verifier_kinds": ["self"]
    }
  ],
  "issued":  "2026-05-15T10:00:00Z",
  "expires": "2027-05-15T10:00:00Z",
  "signature": "eyJhbGciOiJFZERTQSJ9.<payload>.<sig>"
}
```

## 7. Rationale (non-normative)

- **One capability per entry, named.** Tempting to allow capabilities to
  share schemas via reference or to be polymorphic. v0 forbids this: each
  capability has its own name, its own schemas, its own cost model. Reuse
  by reference is a v1 problem and creating it now would obscure the
  primitive.
- **JSON Schema for capability I/O.** It is the standard the agent world
  has converged on (MCP uses it; A2A uses it; OASF uses it). Using
  something else here would force every adapter to bridge.
- **Cost expressed as decimal strings.** Anyone who has worked on a
  payments system knows the trap of representing money as floats. We pay
  the small cost of string parsing to avoid the much larger cost of float
  drift in cost attribution.
- **Mandatory `verifier_kinds`.** Forcing the operator to declare *what
  kinds of verifier this agent's output can be checked by* is a small
  amount of friction that pays back enormously in composition: the
  delegation contract can reject a verifier that the callee did not
  attest is compatible.

## 8. Future versions

- Multi-dimensional cost models (e.g., tokens AND dollars).
- A capability inheritance / extension mechanism.
- A formal discovery protocol.
- Withdrawal tombstones for capabilities.
- Card-level rate-limit advertisements.
