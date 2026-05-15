# Example 01 — Two-agent handoff

**TL;DR.** The smallest meaningful rig: a planner agent delegates one
step to a worker agent. Demonstrates contract negotiation, signed
execution, and a clean trace with no verifier in the loop.

Run with:

```
rig run 01-two-agent-handoff
```

or directly:

```
python -m examples.01_two_agent_handoff.run
```

## What it shows

- Two agents, two keypairs, two signed agent cards.
- A single delegation contract from planner to worker.
- A complete OpenTelemetry-shaped trace with rig-level attributes.
- No verifier (the contract names ``verifier: "self"``).

## What to look at after running

The script prints the trace's spans (`rig.contract.propose`,
`rig.contract.accept`, `rig.execute`, `rig.cost.debit`) and confirms
the worker's output is signed by the worker's keypair. There is no
blame chain because nothing failed; the next example —
`03-adversarial-subagent` — exercises the failure path.
