# ADR-0006 — Explicit budget propagation for cost attribution

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rigging core authors

## Context

When agent B subcontracts to agent C while serving a contract from A,
who pays? The choice has consequences for blame, debugging, and the
operator's ability to enforce per-agent spending limits. Phase 1 Q4 in
`docs/phase-reviews/think.md` argued through three alternatives.

## Decision

Costs propagate by *explicit budget delegation*. When B issues a sub-
contract to C, B MUST allocate a sub-budget from its own remaining
budget. C's spending is billed to *B*, not to A. The rig refuses to
issue a sub-contract whose budget exceeds the parent's remaining
budget.

Equivalently: each contract has its own ledger, and the ledger's
counterparty is the contract's *immediate* parent. The root contract's
counterparty is the operator.

## Consequences

- *Pro:* "How much did task X cost?" becomes answerable in closed form:
  walk the tree, summing each contract's debits against its parent.
- *Pro:* Per-agent spending limits are enforceable locally — each agent
  sees only its direct children's costs.
- *Pro:* An overspending sub-agent is a *local* failure: C blew its
  budget under B's contract, so B's contract with A is unaffected unless
  B chooses to retry.
- *Pro:* This is the cost-attribution model E-rights / capability OS
  research has been recommending since the early 2000s; we are not
  inventing anything novel.
- *Con:* B must explicitly size sub-budgets. There is no "spend
  whatever's left" idiom. We consider this a feature: the explicit
  allocation forces the operator to think about budget shape.
- *Con:* Costs of fan-out (B issues N parallel sub-contracts) must be
  pre-allocated; B cannot defer the choice until after some sub-
  contracts have completed. We accept this; future work can introduce
  budget reclamation.

## Alternatives considered

### Alternative A — Flat caller-pays
Every cost in the call graph is debited to the root caller. Simple but
trust-asymmetric: a single delegate can burn arbitrary downstream cost
on the root's tab. Lost.

### Alternative B — Proportional call-chain accumulation
Each agent in the chain is debited proportionally to some weight.
Sounds fair; muddies attribution. The question "how much did this task
cost?" becomes a question about every other task an agent participated
in. Lost.

### Alternative C — Explicit budget propagation (chosen)
Each contract is its own ledger, billed to its immediate parent. Wins.

## References

- `docs/phase-reviews/think.md`, Q4.
- Miller, *Robust Composition* (PhD thesis, JHU, 2006), Ch. 13–14 on
  reasoning locally about authority and resource use.
- `docs/spec/rig-contract-v0.md` §7 (sub-contracts).
