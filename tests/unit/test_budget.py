"""Cost-ledger tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from rigging.core import Contract, CostBudget
from rigging.core.errors import BudgetExhausted, BudgetOverrun
from rigging.identity import KeyPair
from rigging.runtime.budget import CostLedger
from rigging.runtime.ulid import new_ulid


def _contract(
    *,
    parent: Contract | None,
    budget: str,
    unit: str = "usd",
    caller: KeyPair | None = None,
    callee: KeyPair | None = None,
) -> Contract:
    caller = caller or KeyPair.generate()
    callee = callee or KeyPair.generate()
    now = datetime.now(tz=UTC)
    return Contract(
        contract_id=new_ulid(),
        parent_id=parent.contract_id if parent else None,
        caller=caller.did,
        callee=callee.did,
        callee_card_hash="sha256:" + ("a" * 64),
        capability="x",
        input={},
        cost_budget=CostBudget(unit=unit, max=Decimal(budget)),
        verifier="self",
        issued=now,
        expires=now + timedelta(minutes=5),
    )


def test_debit_within_budget() -> None:
    ledger = CostLedger()
    c = _contract(parent=None, budget="0.10")
    ledger.register(c)
    ledger.debit(c.contract_id, Decimal("0.05"))
    assert ledger.spent(c.contract_id) == Decimal("0.05")


def test_debit_over_budget_raises() -> None:
    ledger = CostLedger()
    c = _contract(parent=None, budget="0.10")
    ledger.register(c)
    with pytest.raises(BudgetOverrun):
        ledger.debit(c.contract_id, Decimal("0.20"))


def test_child_budget_within_parent_capacity() -> None:
    ledger = CostLedger()
    parent = _contract(parent=None, budget="1.00")
    ledger.register(parent)
    child = _contract(parent=parent, budget="0.40")
    ledger.register(child)
    # Parent's remaining capacity reflects allocation to child
    assert ledger.remaining(parent.contract_id) == Decimal("0.60")


def test_child_budget_exceeding_parent_capacity_raises() -> None:
    ledger = CostLedger()
    parent = _contract(parent=None, budget="0.50")
    ledger.register(parent)
    child = _contract(parent=parent, budget="0.80")
    with pytest.raises(BudgetExhausted):
        ledger.register(child)


def test_child_budget_unit_must_match_parent() -> None:
    ledger = CostLedger()
    parent = _contract(parent=None, budget="0.50", unit="usd")
    ledger.register(parent)
    child = _contract(parent=parent, budget="0.10", unit="tokens")
    with pytest.raises(BudgetExhausted):
        ledger.register(child)


def test_overrun_local_to_child_does_not_affect_parent() -> None:
    """ADR-0006 corollary: a child's overrun is billed to its parent's
    contract, not the root caller — but only up to the child's budget.
    """
    ledger = CostLedger()
    parent = _contract(parent=None, budget="1.00")
    ledger.register(parent)
    child = _contract(parent=parent, budget="0.20")
    ledger.register(child)
    with pytest.raises(BudgetOverrun):
        ledger.debit(child.contract_id, Decimal("0.30"))
    # Parent is untouched.
    assert ledger.spent(parent.contract_id) == Decimal("0")
