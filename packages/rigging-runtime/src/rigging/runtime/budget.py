"""Per-contract cost ledger and budget arithmetic.

The ledger holds, for each contract, the cumulative cost debited
against it and the sum of budgets allocated to its child sub-contracts.
The invariants the runtime enforces:

- A debit must not push a contract's total cost above its budget.
- A child contract's budget must not exceed the parent's remaining
  capacity (parent's budget minus parent's own debits minus already-
  allocated child budgets).

These two invariants are the *only* rules cost attribution depends on.
They are enforced at contract-issuance time (for the parent-capacity
check) and at debit time (for the per-contract budget check).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from decimal import Decimal

from rigging.core.contract import Contract
from rigging.core.errors import BudgetExhausted, BudgetOverrun


@dataclass(slots=True)
class _ContractLedger:
    budget: Decimal
    unit: str
    spent: Decimal = Decimal(0)
    children_allocated: Decimal = Decimal(0)


class CostLedger:
    """Tracks per-contract spend and child-budget allocations.

    Thread-safe; a rig may run multiple delegations in parallel.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, _ContractLedger] = {}

    # --- registration ---------------------------------------------------

    def register(self, contract: Contract) -> None:
        """Record the contract's budget; raise if its parent cannot fund it."""
        with self._lock:
            if contract.parent_id is not None:
                parent = self._entries.get(contract.parent_id)
                if parent is None:
                    raise BudgetExhausted(
                        f"parent contract {contract.parent_id} is not registered",
                        contract_id=contract.contract_id,
                    )
                if parent.unit != contract.cost_budget.unit:
                    raise BudgetExhausted(
                        "child budget unit differs from parent's",
                        contract_id=contract.contract_id,
                    )
                remaining = parent.budget - parent.spent - parent.children_allocated
                if contract.cost_budget.max > remaining:
                    raise BudgetExhausted(
                        "child budget exceeds parent's remaining capacity",
                        contract_id=contract.contract_id,
                        details={
                            "parent_id": contract.parent_id,
                            "parent_remaining": str(remaining),
                            "child_request": str(contract.cost_budget.max),
                        },
                    )
                parent.children_allocated += contract.cost_budget.max
            self._entries[contract.contract_id] = _ContractLedger(
                budget=contract.cost_budget.max,
                unit=contract.cost_budget.unit,
            )

    # --- debits ---------------------------------------------------------

    def debit(self, contract_id: str, cost: Decimal) -> Decimal:
        """Record a cost against ``contract_id`` and return new total.

        Raises:
            BudgetOverrun: If the new total exceeds the contract's budget.
        """
        if cost < 0:
            raise ValueError("debits must be non-negative")
        with self._lock:
            entry = self._entries[contract_id]
            new_total = entry.spent + cost
            if new_total > entry.budget:
                raise BudgetOverrun(
                    f"cost {new_total} exceeds budget {entry.budget}",
                    contract_id=contract_id,
                )
            entry.spent = new_total
            return new_total

    # --- inspection ------------------------------------------------------

    def spent(self, contract_id: str) -> Decimal:
        with self._lock:
            return self._entries[contract_id].spent

    def remaining(self, contract_id: str) -> Decimal:
        with self._lock:
            entry = self._entries[contract_id]
            return entry.budget - entry.spent - entry.children_allocated

    def has(self, contract_id: str) -> bool:
        with self._lock:
            return contract_id in self._entries
