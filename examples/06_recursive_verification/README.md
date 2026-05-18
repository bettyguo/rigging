# 06 · Recursive verification

> **TL;DR** — a verifier audits the worker's output; a *meta-verifier* then
> audits the verifier's verdict envelope. The rig caps the recursion at
> `RigConfig.verification_recursion_cap` (default 3, configured to 3 here)
> so audit chains terminate.

## What this demonstrates

1. **Verification is compositional.** A verifier's signed verdict envelope
   is itself an output — and therefore subject to audit by another agent
   whose card declares the `verify` capability. The runtime mediates;
   the verifier never calls the meta-verifier directly.
2. **Recursion is bounded.** `RecursionCapExceeded` is the runtime's
   structural answer to "what if a verifier's verifier needs a verifier?"
3. **Blame stays mechanical even when the chain runs deep.** Every
   envelope is signed by the agent who issued it. The blame-chain
   extractor walks the DAG backwards and points at the proximate cause —
   worker, primary verifier, or meta-verifier — without ambiguity.

## Run it

```bash
rig run 06-recursive-verification
```

No API keys. No network. The classifier returns a hard-coded label;
the primary verifier checks shape + confidence; the meta-verifier
checks the verdict envelope's well-formedness.

## The invariant being exercised

> A verifier is just an agent. Its outputs are just outputs. Audit
> chains compose; the rig caps their depth so the chain always
> terminates in a reachable verdict.

See [ADR-0007 — verifier-as-agent](../../docs/adr/0007-verifier-as-agent.md)
and [`rig-contract-v0` §7 (recursion semantics)](../../docs/spec/rig-contract-v0.md).
