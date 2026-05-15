# Example 05 — Vote-ensemble verifier

**TL;DR.** A worker delegates to three independent verifiers behind a
coordinator. The coordinator is itself a rig participant with a
`verify` capability; it fans out, tallies, and returns the majority
verdict. This is the *composition without runtime feature* claim from
ADR-0007 made concrete — nothing in `rigging.runtime` knows about
voting.

Run with:

```
rig run 05-vote-ensemble
```

## What it shows

- One worker (adversarial: returns `"42"` for everything).
- Three independent verifiers — two agree with ground truth, one
  doesn't.
- One :class:`rigging.adapters.VoteEnsembleVerifier` wrapping the
  three.
- The rig invokes the ensemble as if it were a single verifier; the
  ensemble issues three sub-contracts under the hood; majority wins.
- The trace shows the parent verify call *and* all three child verify
  calls, signed by their respective verifiers.

## What to inspect after running

The output prints the full per-verifier vote alongside the majority
verdict. Then the blame chain (if the ensemble rejected) names the
worker — *not* the ensemble or its constituents. The mid-chain blame
rule from `rigging.trace.blame` correctly attributes failure to the
worker rather than to the routing/verification layer.
