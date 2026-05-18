# Security policy

> The rig is, by design, a *trust-bearing* substrate. We take that
> seriously.

## Reporting a vulnerability

**Please do not file public GitHub issues for security reports.**

If you believe you have found a security vulnerability in `rigging`,
please report it privately through one of the following channels:

**Use GitHub Security Advisories.** Go to the repository's
[Security tab → Advisories](https://github.com/bettyguo/rigging/security/advisories/new)
and click *Report a vulnerability*. This is the only supported channel
for v0 — it gives us a private workspace, attributable disclosure, and
a clean CVE pipeline if one is warranted.

If GitHub Security Advisories are unavailable to you (e.g., you do not
have a GitHub account), please open a [Discussion](https://github.com/bettyguo/rigging/discussions)
in the *Security* category instead. **Do not** open a public issue.

Please include:

- A description of the issue.
- A minimal reproduction (or a clear thought experiment if the
  vulnerability is conceptual).
- The affected version or commit.
- Your name / handle if you would like to be credited.

## Disclosure timeline

We aim to:

- **Acknowledge** your report within **3 business days**.
- **Triage and confirm** within **7 business days**.
- **Issue a fix or mitigation** within **30 days** for high-severity
  reports.
- **Coordinate public disclosure** with you. We will not name you
  publicly without your consent.

If a vulnerability is being actively exploited, we will accelerate this
timeline.

## What counts as a security issue

The rig's threat model is documented at
[`docs/spec/identity-v0.md`](./docs/spec/identity-v0.md). In v0 we treat
the following as security issues:

- **Signature forgery.** Any way to make the rig accept an envelope that
  was not produced by the holder of the signing key.
- **Card spoofing.** Any way to make the rig route work to an agent
  whose card was not signed by the operator's identity key.
- **Cost-budget escape.** Any way for a sub-contract's cost overrun to
  be charged to a contract other than its parent.
- **Blame-chain laundering.** Any way for an envelope to appear in a
  trace under a signing key that did not produce it.
- **Replay.** Any way for a contract to be accepted twice.

Out of scope for v0 (we know these are limitations and intend to address
them in v1):

- Revocation of compromised cards. v0 has no revocation protocol;
  operators must rotate keys. This is *documented*, not a bug.
- KMS-backed signing. v0 uses local-file Ed25519 keys.
- Side-channel attacks on the verifier.
- DoS against the rig itself (the rig is in-process in v0; rate limits
  belong in your transport layer).

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| v0.x    | ✅ Active            |
| < v0.1  | ❌ Pre-release only  |

When v1 ships, v0 will receive security fixes for at least six months
after v1.0.0.

## Hall of fame

Researchers who responsibly disclose security issues will be credited
here (with consent).

*(Empty for now — be the first.)*
