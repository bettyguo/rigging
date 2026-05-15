# Example 04 — cost attribution

**TL;DR.** Three agents A→B→C, each with its own budget. C
deliberately overruns. The runtime detects the overrun, attributes the
cost to C's *parent* contract (B's), and leaves A's budget untouched.
This is what makes ADR-0006 ("explicit budget propagation") concrete.

Run with:

```
rig run 04-cost-attribution
```

## What it shows

- A's contract to B has budget $0.50.
- B's sub-contract to C has budget $0.20 (carved out of B's
  allocation).
- C reports a cost of $0.30 — overrunning its $0.20 budget.
- The rig raises ``BudgetOverrun`` against C's contract; the failure
  does not propagate to A's budget.
- The trace shows the failure pinned to C's contract and the blame
  chain ends at C.
