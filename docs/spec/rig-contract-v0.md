# Rigging Delegation Contract Specification — v0

> Status: **DRAFT** · Version: `v0` · Last updated: 2026-05-15
>
> This specification uses RFC 2119 / RFC 8174 normative keywords.
> Companion specifications: `identity-v0.md`, `agent-card-v0.md`,
> `trace-v0.md`.

---

## 1. Purpose

A *delegation contract* is the signed document exchanged between two
agents before any work crosses their boundary. It binds:

- *who* is asking (caller DID),
- *who* is being asked (callee DID),
- *what* is being requested (a named capability the callee has advertised),
- *under what cost ceiling*,
- *under what verifier*,
- *for how long the agreement holds*.

It is the only mechanism by which work flows between agents under a rig.
The rig refuses to route a call that is not backed by a contract; the
runtime refuses to issue a contract whose constraints cannot be satisfied
by the callee's signed agent card.

## 2. Structure

### 2.1 Canonical JSON form

```json
{
  "contract_version": "rigging/contract/v0",
  "contract_id":      "01HW8E4QV3X8N2W3F1A0X5KQAB",
  "parent_id":        null,
  "caller":           "did:rig:<caller-fingerprint>",
  "callee":           "did:rig:<callee-fingerprint>",
  "callee_card_hash": "sha256:<hex>",
  "capability":       "translate_pdf",
  "input":            { "uri": "s3://...", "target_language": "fr" },
  "cost_budget": {
    "unit":      "usd",
    "max":       "0.50"
  },
  "verifier":         "self",
  "trust_propagation": "verified",
  "issued":           "2026-05-15T10:00:00Z",
  "expires":          "2026-05-15T10:05:00Z",
  "signature":        "<JWS over the above with this field omitted>"
}
```

### 2.2 Required fields

| Field               | Type   | Requirement                                                              |
|---------------------|--------|--------------------------------------------------------------------------|
| `contract_version`  | string | MUST equal `"rigging/contract/v0"`.                                      |
| `contract_id`       | string | A ULID (RFC draft, lexicographically sortable). MUST be globally unique. |
| `parent_id`         | string \| null | Contract ID of the parent contract, if this is a sub-contract. |
| `caller`            | string | DID of the calling agent.                                                |
| `callee`            | string | DID of the callee agent. MUST differ from `caller`.                      |
| `callee_card_hash`  | string | `sha256:` plus hex digest of the JCS-canonical callee card *as known to the caller at issuance*. |
| `capability`        | string | A capability name. MUST appear in the callee's card.                     |
| `input`             | object | The input payload. MUST validate against the capability's `input_schema`. |
| `cost_budget`       | object | A cost budget; `unit` MUST match the capability's cost model.            |
| `verifier`          | string | Either `"self"` or a DID of a verifier agent.                            |
| `trust_propagation` | string | Either `"sealed"` or `"verified"`. See §3.                               |
| `issued`            | string | RFC 3339 timestamp.                                                      |
| `expires`           | string | RFC 3339 timestamp; MUST be after `issued`. SHOULD be ≤ 1 hour after `issued`. |
| `signature`         | string | JWS Compact Serialization (`alg=EdDSA`) by the caller.                   |

### 2.3 Why these fields and no others

Every field above earns its place against the discipline "what does the rig
need to make decisions about *routing, cost, and blame*?". The fields drop
cleanly into one of those three buckets:

- **Routing.** `caller`, `callee`, `callee_card_hash`, `capability`,
  `input`, `expires`.
- **Cost.** `cost_budget`, `parent_id` (so child budgets can be checked
  against parents).
- **Blame.** `contract_id`, `verifier`, `trust_propagation`, `signature`,
  `issued`.

Fields that did not earn a place in v0:

- Predicate-language pre- and post-conditions (DSL hazard).
- Retry policy (belongs to the caller's harness).
- Priority / SLA (no scheduler in v0).
- Multi-dimensional budgets (forces unit clarity).
- Free-text justification (encourages bullshit).
- Idempotency keys (re-issue the same contract instead).

## 3. Trust propagation

`trust_propagation` controls how verification recurses across a chain of
contracts.

- `"verified"` — the callee's output MUST be checked by the named
  verifier. If that verifier is itself an agent (not `"self"`), the rig
  issues a sub-contract to it, also `"verified"`, up to the recursion cap.
- `"sealed"` — the callee's output is trusted without further verification.
  This terminates recursion. A contract MAY only be `"sealed"` if the
  caller's policy (carried out-of-band) accepts the callee as trusted
  bedrock. The rig refuses to silently treat a contract as sealed.

The recursion cap in v0 is **3**. A chain of verification deeper than 3
levels MUST be rejected by the rig at issuance.

## 4. Negotiation protocol

A contract is negotiated as follows:

1. **Proposal.** The caller constructs a contract with all fields filled in
   *except* `signature`, signs it, and transmits it to the callee.
2. **Validation.** The callee:
   - Verifies the JWS signature.
   - Confirms `caller` matches the signing key's DID.
   - Confirms `callee` matches the callee's own DID.
   - Confirms `callee_card_hash` matches the JCS-canonical hash of its
     currently-published card.
   - Confirms `capability` exists on its card.
   - Confirms `input` validates against the capability's `input_schema`.
   - Confirms `cost_budget.unit` matches the capability's cost-model unit.
   - Confirms `cost_budget.max` is ≥ the capability's minimum (base cost).
   - If `parent_id` is non-null, confirms that the rig can present a
     parent contract whose remaining budget (parent budget minus child
     budgets already in flight) is ≥ this contract's budget.
   - Confirms `expires` is in the future and within the callee's policy
     for maximum contract lifetime.
3. **Acceptance.** If all validations pass, the callee MAY accept. It
   responds with a *contract acknowledgement*: the contract bytes (echoed)
   plus a second JWS signature by the callee. The contract is now *active*.
4. **Rejection.** The callee MAY reject for any reason. The rejection
   includes a reason code from §6 plus an optional human-readable note.

## 5. Lifecycle and termination

A contract is in exactly one of these states at any time:

- `proposed` — signed by caller; awaiting callee acceptance.
- `active` — accepted by callee; work in progress.
- `fulfilled` — callee produced an output and the verifier (if any)
  accepted it.
- `rejected` — callee or verifier rejected.
- `voided` — terminated abnormally (callee unreachable, expired before
  acceptance, budget exhausted).

Transitions:

```
proposed --(accept)--> active --(success+verify)--> fulfilled
       \--(reject)--> rejected            \--(verify rejects)--> rejected
                                          \--(budget overrun)--> voided
                                          \--(callee unreachable)--> voided
                                          \--(expiry)--> voided
```

Once a contract reaches a terminal state, it is immutable. Retries produce
a *new* contract with a new `contract_id`.

## 6. Reason codes

Rejections and voidings carry a reason code. The v0 codes are:

| Code                          | Meaning                                                          |
|-------------------------------|------------------------------------------------------------------|
| `capability_unknown`          | Capability is not on the callee's current card.                  |
| `capability_mismatch`         | `callee_card_hash` did not match callee's current card.          |
| `schema_invalid`              | `input` failed the capability's input-schema validation.         |
| `budget_unit_mismatch`        | Budget unit differs from the capability's cost-model unit.       |
| `budget_too_low`              | Budget ceiling is below the capability's base cost.              |
| `budget_overrun`              | Execution exceeded the contract's budget.                        |
| `expired`                     | Contract was processed past its `expires`.                       |
| `recursion_cap_exceeded`      | Verification chain exceeded the v0 recursion cap of 3.           |
| `callee_unreachable`          | Callee could not be contacted; contract voided.                  |
| `verifier_unreachable`        | Verifier could not be contacted; contract voided.                |
| `verifier_rejected`           | Verifier returned a `reject` verdict.                            |
| `output_schema_invalid`       | Callee output did not validate against the output schema.        |
| `signature_invalid`           | One of the signatures (caller, callee, verifier) failed.         |
| `parent_budget_exhausted`     | Sub-contract budget exceeds parent's remaining budget.           |
| `policy_rejected`             | Callee's local policy refused the contract for an unenumerated reason. |

## 7. Sub-contracts

A callee that needs to delegate further (B → C while serving A) issues a
new contract with `parent_id` set to the current contract's `contract_id`.
The rig enforces:

- Sub-contract budget ≤ parent's remaining budget (parent budget minus the
  sum of all live and fulfilled sub-contract budgets).
- Sub-contract `expires` ≤ parent's `expires`.
- `trust_propagation` of the sub-contract MAY be the same as or stricter
  than the parent's. Loosening (from `"verified"` to `"sealed"`) is
  forbidden.

The cost-attribution semantics of sub-contracts are defined in ADR-0006:
**costs are billed against the immediate parent, not the root**. Each agent
sees only its direct children's costs in its own ledger.

## 8. Worked example

A planner agent delegates a translation to a worker. The planner has a
budget of $5; this particular translation gets $0.50.

```json
{
  "contract_version": "rigging/contract/v0",
  "contract_id": "01HW8E4QV3X8N2W3F1A0X5KQAB",
  "parent_id": "01HW8E1AAA0000000000000000",
  "caller":  "did:rig:wm6pj4eoa3wq6e5kgu5dluxihy3vctj2",
  "callee":  "did:rig:tihtfhkojvxgu7emjqpsuoymjrlh7cu3",
  "callee_card_hash": "sha256:4f7c0a9e8b3d1f2c5a6e0b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e",
  "capability": "translate_pdf",
  "input": { "uri": "s3://docs/report.pdf", "target_language": "fr" },
  "cost_budget": { "unit": "usd", "max": "0.50" },
  "verifier": "self",
  "trust_propagation": "verified",
  "issued":  "2026-05-15T10:00:00Z",
  "expires": "2026-05-15T10:05:00Z",
  "signature": "eyJhbGciOiJFZERTQSJ9.<payload>.<sig>"
}
```

The callee inspects, validates, and either acknowledges (signs and
returns) or rejects with a code from §6.

## 9. Rationale (non-normative)

- **`callee_card_hash` is mandatory.** Without it, a malicious callee
  could quietly update its card between the caller fetching it and the
  contract being issued, smuggling in a less-restrictive cost model. The
  hash binds the contract to a specific card revision.
- **Expiry is mandatory and short.** A contract is a *short-lived* bill of
  lading. Long-lived authorization belongs to a different layer (a
  capability grant, an OAuth scope). 1-hour soft limit is enough for the
  longest reasonable single delegation; longer work should be broken up.
- **No retry policy.** The most common source of bugs in supervisor
  patterns is implicit retry inside the routing layer. We deliberately
  exclude it: each retry is a new contract.
- **Recursion cap.** Three is the smallest number that supports the common
  pattern *caller → callee → verifier-of-verifier*. Deeper chains are
  almost certainly a bug; we'd rather force the user to flatten than
  silently allow runaway recursion.

## 10. Future versions

- Cancellation protocol (caller wants to withdraw an in-flight contract).
- Streamed contracts (output is delivered incrementally; the contract
  remains active until end-of-stream).
- Multi-dimensional budgets.
- A `policy_id` field linking a contract to a published policy document.
- Pre/post-condition predicates against a constrained subset of CEL.
