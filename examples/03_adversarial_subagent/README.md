# Example 03 — Adversarial subagent

**TL;DR.** A planner delegates to a worker that returns deliberately
bad output. The verifier — itself a registered rig agent — catches it.
The blame chain points unambiguously at the worker, not at the rig.
This is the example that justifies why a rig exists.

Run with:

```
rig run 03-adversarial-subagent
```

## What it shows

- The worker is configured to always return ``"42"`` regardless of the
  question. A reasonable harness might never notice.
- The verifier is an agent whose card declares the well-known
  ``verify`` capability. The runtime issues a sub-contract to it as
  part of the parent contract's lifecycle (see ``Rig._run_verifier``).
- The verifier rejects; the runtime surfaces ``VerifierRejected``; the
  trace contains a `rig.verify` span with ``verdict=reject``; the
  blame-chain extractor produces a chain ending at the worker's DID.

## After running

The example prints the blame chain. The fact that **the proximate
cause is the worker's DID, not the rig's** is the whole point: a
multi-agent failure is mechanically attributable to a specific
participant.
