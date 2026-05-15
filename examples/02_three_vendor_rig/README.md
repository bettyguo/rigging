# Example 02 — Three-vendor rig

**TL;DR.** Three agents from three different "vendors" collaborate on a
small task: a planner, a coder, and a reviewer. Each carries its own
keypair and card; the rig coordinates. Demonstrates *heterogeneous*
composition — the rig is provider-agnostic by design.

This example uses :class:`LocalPythonAdapter` for all three so it runs
offline. The same script with each handler swapped for a
:class:`LiteLLMAdapter` would talk to three distinct providers; we
don't ship that variant by default to keep examples deterministic and
cost-free.

Run with:

```
rig run 02-three-vendor-rig
```

## What to look at

- Three signed cards, three distinct DIDs.
- A two-step delegation: planner → coder, then planner → reviewer.
- Cost is attributed *per call* against the planner's budget; the rig's
  ledger keeps a per-contract running total.
