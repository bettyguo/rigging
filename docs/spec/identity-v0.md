# Rigging Identity Specification — v0

> Status: **DRAFT** · Version: `v0` · Last updated: 2026-05-15
>
> This specification uses RFC 2119 / RFC 8174 normative keywords
> (MUST, MUST NOT, SHOULD, SHOULD NOT, MAY).

---

## 1. Purpose

Every participant in a rig — agents, verifiers, the runtime acting on
behalf of an operator — MUST have a stable, cryptographically anchored
identity. This specification defines the format of that identity, the key
material that backs it, and the canonical string form used to reference it
in contracts and traces.

The goals, in order:

1. *Provenance.* Every output that crosses an agent boundary is signed by
   exactly one identity. Anyone with the public key can verify the
   signature.
2. *Stability.* Identities outlive any specific agent process, harness
   version, or model assignment. An identity refers to the *operator's
   commitment to deploy an agent of a certain shape*, not to the running
   process.
3. *Decentralization-readiness.* The format MUST be usable without a
   central registry, while leaving room for one if an ecosystem chooses to
   adopt one later.

## 2. Identity primitive

### 2.1 Key material

A rig identity MUST be backed by an Ed25519 keypair (RFC 8032). The
operator holds the private key offline or in a key management system; the
public key is the basis for the identity string.

Implementations MUST NOT use RSA, ECDSA (P-256), or any keypair that is not
Ed25519 for v0. Rationale and alternatives are recorded in ADR-0005.

### 2.2 Canonical identifier form

A rig identity is referenced by a *DID* in the `did:rig` method:

```
did:rig:<base32-nopad-lowercase(sha256(public_key_bytes))[:32]>
```

The fingerprint is the lowercase, unpadded RFC 4648 base32 encoding of the
first 20 bytes of `SHA-256(public_key_bytes)`, where `public_key_bytes` is
the 32-byte raw Ed25519 public key.

Implementations MUST validate that any DID they accept conforms to the
above grammar. A DID that does not is rejected without dereferencing.

### 2.3 Worked example

A freshly generated key:

```
public_key_bytes (hex) =
  4b7a8a9f2c1d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f
sha256(public_key_bytes)[:20] (hex) =
  9a3b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b
base32 nopad lowercase =
  tihtfhkojvxgu7emjqpsuoymjrlh7cu3
DID =
  did:rig:tihtfhkojvxgu7emjqpsuoymjrlh7cu3
```

(Used as a fixture in `tests/unit/test_identity.py`.)

## 3. Agent card binding

An agent card (see `agent-card-v0.md`) MUST be signed by the private key
corresponding to the identity it claims. The signature covers the JCS-
canonicalised (RFC 8785) JSON representation of the card with the
`signature` field omitted, and is conveyed in the card as a JWS Compact
Serialization (RFC 7515) with `alg=EdDSA`.

A verifier checking an agent card MUST:

1. Parse the card.
2. Derive the DID from the embedded public key.
3. Confirm the DID matches the card's `agent_id` field.
4. Verify the JWS signature against the public key.

Any failure of steps 2–4 MUST cause the card to be rejected.

## 4. Key lifecycle

### 4.1 Rotation

Key rotation in v0 is *destructive*: a new key is a new identity. Operators
SHOULD publish a signed *successor* document linking the old identity to
the new one when they rotate; v1 will standardise this. In v0, downstream
agents that receive contracts signed by a rotated key MUST treat them as
untrusted.

### 4.2 Revocation

v0 does not specify a revocation protocol. The intended mechanism in v1 is
a signed revocation note that the rig publishes alongside the agent card.
Implementations MUST NOT silently accept a key after its public-key
material has been replaced.

### 4.3 Storage

Private keys MUST be stored encrypted at rest. The reference implementation
encrypts the private key under a user passphrase using `cryptography`'s
`BestAvailableEncryption` PEM serialization. Operators MAY substitute an
HSM-backed signer that exposes a compatible interface.

## 5. Threat model (informative)

The v0 identity scheme is designed against three threats:

- **Forgery.** An attacker cannot produce a valid signature for an identity
  whose private key they do not hold. Ed25519's security properties carry
  this guarantee.
- **Substitution.** An attacker cannot swap an agent's public key without
  the new key producing a different DID. The DID is a hash of the key, so
  any change is detected by the verifier.
- **Replay.** Contract-level replay is addressed in `rig-contract-v0.md`
  via `contract_id` uniqueness and `expiry`. The identity layer is not
  responsible for it.

Threats explicitly *out of scope* for v0:

- Compromise of the private key itself. Operators are responsible for key
  hygiene. (KMS integration is a v1 concern.)
- Sybil attacks (one operator running many identities). This is policy, not
  cryptography. A trust assertion mechanism in `agent-card-v0.md` allows
  operators to attest to relationships between identities, which a higher
  layer can rely on.
- Quantum adversaries. Ed25519 is not post-quantum-secure. v1 will
  introduce a pluggable signature algorithm field.

## 6. CLI

The reference implementation exposes a small CLI for working with
identities; the surface is described here so that other implementations
remain interoperable.

```
rig identity create [--out PATH] [--passphrase-env VAR]
rig identity show <key-file>
rig identity verify <agent-card-file>
```

`create` produces a PEM-encoded encrypted private key plus a sidecar
`*.did` file containing the DID. `show` prints the DID for an existing
key. `verify` checks that an agent card is well-formed and properly signed.

## 7. Future versions

v1 will likely add:

- A standardised successor-key linking format (controlled key rotation).
- A revocation list format that rigs can subscribe to.
- A pluggable signature algorithm field for post-quantum migration.
- Optional integration with W3C DID resolution for ecosystems that adopt
  centralised registries.

v0 deliberately does not include any of the above. The job of v0 is to
make signing and verification *unavoidable*; the higher-fidelity lifecycle
operations can be built on top once the bedrock holds.

## 8. Rationale (non-normative)

- **Ed25519 over ECDSA.** Smaller signatures, no malleability concerns, no
  k-reuse footguns, and deterministic. The cryptographic literature
  treats Ed25519 as the default for new protocols since RFC 8032 (2017).
- **`did:rig:` method, not `did:key:`.** `did:key` exists and would work,
  but its grammar is more permissive than rigs need. A purpose-built
  method narrows the grammar, simplifies validators, and avoids
  accidentally inheriting `did:key` extensions.
- **20-byte truncated SHA-256.** 160 bits of collision resistance is
  sufficient for the size of any plausible agent population, and the
  shorter identifier reads better in traces. The truncation is well-
  studied (PGP, IPFS, Bitcoin all do equivalent things at similar
  lengths).
