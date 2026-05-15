# ADR-0005 — Ed25519 over ECDSA / RSA

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

Every contract is signed; every agent card is signed; every execute and
verify span carries a signed envelope. The signature scheme is one of
the few cryptographic primitives that pervades the rig. Changing it
later is expensive (every key rotates, every persisted trace becomes
historically incompatible). The choice deserves an ADR.

Practical candidates:

- **Ed25519** (RFC 8032). Modern, fast, deterministic, no nonce reuse.
- **ECDSA P-256.** Widely deployed, standardized by FIPS, but has nonce-
  reuse footguns and is harder to audit.
- **RSA-PSS.** Mature, ubiquitous in TLS PKI, but signatures are large
  (≥256 bytes for 2048-bit keys) and key generation is slow.
- **BLS** signatures. Aggregation-friendly, interesting for vote
  ensembles. Larger libraries, less mainstream tooling.

## Decision

Rig identities are Ed25519 keypairs. All signatures (agent cards,
contracts, execute envelopes, verifier verdicts) use Ed25519 with the
JWS `alg=EdDSA` identifier.

## Consequences

- *Pro:* 32-byte public keys, 64-byte signatures. Small enough to embed
  in traces and contracts without bloat.
- *Pro:* Deterministic. The same input always produces the same
  signature; no random nonce required. This makes traces reproducible
  for testing.
- *Pro:* Constant-time verification, well-vetted implementations in
  `cryptography` and in browser/Node ecosystems.
- *Pro:* No malleability concerns of the sort that plague ECDSA when
  implementations differ.
- *Con:* Not FIPS-validated as of writing. Operators in FIPS-mandated
  environments must wait for FIPS-compliant Ed25519 (in progress at
  NIST) or use a different rig key type. v1 will introduce a pluggable
  algorithm field.
- *Con:* Not quantum-resistant. v1 anticipates a hybrid signature
  scheme; v0 explicitly defers this.

## Alternatives considered

### Alternative A — ECDSA P-256
Lost on safety. The nonce-reuse footgun is unforgiving and our
implementation surface (Pydantic models, custom JSON canonicalisation,
adapter authors implementing the same logic in other languages later)
maximises the blast radius of a bad choice.

### Alternative B — RSA-PSS
Lost on size. A 2048-bit signature is ~10× an Ed25519 signature. Multiply
by every span in a multi-hop trace.

### Alternative C — BLS12-381
Lost on maturity. Interesting for v2; today the library ecosystem is
narrower and the cryptanalysis story still maturing.

## References

- Bernstein et al., *Ed25519: high-speed high-security signatures*
  (CHES 2011 / RFC 8032).
- `docs/spec/identity-v0.md` §5 — threat model.
