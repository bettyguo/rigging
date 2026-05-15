"""Property tests for the cost ledger over random tree shapes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from rigging.core import Contract, CostBudget
from rigging.core.errors import BudgetExhausted, BudgetOverrun
from rigging.identity import KeyPair
from rigging.runtime.budget import CostLedger
from rigging.runtime.ulid import new_ulid


def _contract(
    *,
    parent: Contract | None,
    budget: Decimal,
    unit: str = "usd",
) -> Contract:
    caller, callee = KeyPair.generate(), KeyPair.generate()
    now = datetime.now(tz=UTC)
    return Contract(
        contract_id=new_ulid(),
        parent_id=parent.contract_id if parent else None,
        caller=caller.did,
        callee=callee.did,
        callee_card_hash="sha256:" + ("a" * 64),
        capability="x",
        input={},
        cost_budget=CostBudget(unit=unit, max=budget),
        verifier="self",
        issued=now,
        expires=now + timedelta(minutes=5),
    )


@given(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100"), places=2))
@settings(max_examples=50, deadline=None)
def test_single_debit_at_or_below_budget_always_succeeds(budget: Decimal) -> None:
    ledger = CostLedger()
    c = _contract(parent=None, budget=budget)
    ledger.register(c)
    ledger.debit(c.contract_id, budget)  # exactly budget — should pass


@given(
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10"), places=2),
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10"), places=2),
)
@settings(max_examples=50, deadline=None)
def test_debit_above_budget_always_raises(budget: Decimal, excess: Decimal) -> None:
    ledger = CostLedger()
    c = _contract(parent=None, budget=budget)
    ledger.register(c)
    try:
        ledger.debit(c.contract_id, budget + excess)
    except BudgetOverrun:
        return
    raise AssertionError("expected BudgetOverrun")


@given(
    st.decimals(min_value=Decimal("0.10"), max_value=Decimal("10"), places=2),
    st.integers(min_value=1, max_value=4),
)
@settings(max_examples=30, deadline=None)
def test_children_cannot_exceed_parent_remaining(
    parent_budget: Decimal, n_children: int,
) -> None:
    """Sum of accepted child budgets MUST never exceed parent budget,
    and an overflow attempt MUST raise BudgetExhausted (not silently
    succeed)."""
    ledger = CostLedger()
    parent = _contract(parent=None, budget=parent_budget)
    ledger.register(parent)

    # Each child wants slightly more than its fair share — so the
    # last one will overflow.
    share = parent_budget / Decimal(n_children)
    accepted_total = Decimal(0)
    for _ in range(n_children):
        request = share + Decimal("0.01")
        child = _contract(parent=parent, budget=request)
        try:
            ledger.register(child)
            accepted_total += request
        except BudgetExhausted:
            pass
    # The core invariant: accepted total ≤ parent budget.
    assert accepted_total <= parent_budget


@given(
    st.decimals(min_value=Decimal("0.10"), max_value=Decimal("10"), places=2),
    st.integers(min_value=1, max_value=4),
)
@settings(max_examples=30, deadline=None)
def test_child_debit_does_not_affect_parent_spent(
    parent_budget: Decimal, n_children: int,
) -> None:
    """A child's debit increments the child ledger, never the parent's."""
    ledger = CostLedger()
    parent = _contract(parent=None, budget=parent_budget)
    ledger.register(parent)
    share = parent_budget / Decimal(n_children + 1)
    children = []
    for _ in range(n_children):
        child = _contract(parent=parent, budget=share)
        ledger.register(child)
        children.append(child)
    for child in children:
        ledger.debit(child.contract_id, share / Decimal(2))
    assert ledger.spent(parent.contract_id) == Decimal(0)
