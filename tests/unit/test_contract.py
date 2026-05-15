"""Contract model and signing tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from rigging.core import Contract, CostBudget
from rigging.core.errors import SignatureInvalid
from rigging.identity import KeyPair, sign_contract, verify_contract
from rigging.runtime.ulid import new_ulid


def _draft(caller: KeyPair, callee: KeyPair) -> Contract:
    now = datetime.now(tz=UTC)
    return Contract(
        contract_id=new_ulid(),
        caller=caller.did,
        callee=callee.did,
        callee_card_hash="sha256:" + ("a" * 64),
        capability="echo",
        input={"x": 1},
        cost_budget=CostBudget(unit="usd", max=Decimal("0.10")),
        verifier="self",
        issued=now,
        expires=now + timedelta(minutes=5),
    )


def test_contract_expires_after_issued() -> None:
    a, b = KeyPair.generate(), KeyPair.generate()
    now = datetime.now(tz=UTC)
    with pytest.raises(ValidationError):
        Contract(
            contract_id=new_ulid(),
            caller=a.did,
            callee=b.did,
            callee_card_hash="sha256:" + ("a" * 64),
            capability="x",
            input={},
            cost_budget=CostBudget(unit="usd", max=Decimal("0.10")),
            verifier="self",
            issued=now,
            expires=now,
        )


def test_caller_and_callee_must_differ() -> None:
    a = KeyPair.generate()
    with pytest.raises(ValidationError):
        _draft(a, a)


def test_contract_sign_and_verify_roundtrip() -> None:
    a, b = KeyPair.generate(), KeyPair.generate()
    signed = sign_contract(_draft(a, b), key=a)
    verify_contract(signed, caller_public_key=a.public_bytes)


def test_contract_verify_rejects_wrong_caller_key() -> None:
    a, b, c = (KeyPair.generate() for _ in range(3))
    signed = sign_contract(_draft(a, b), key=a)
    with pytest.raises(SignatureInvalid):
        verify_contract(signed, caller_public_key=c.public_bytes)


def test_contract_invalid_callee_card_hash() -> None:
    a, b = KeyPair.generate(), KeyPair.generate()
    now = datetime.now(tz=UTC)
    with pytest.raises(ValidationError):
        Contract(
            contract_id=new_ulid(),
            caller=a.did,
            callee=b.did,
            callee_card_hash="notahash",
            capability="x",
            input={},
            cost_budget=CostBudget(unit="usd", max=Decimal("0.10")),
            verifier="self",
            issued=now,
            expires=now + timedelta(minutes=5),
        )


def test_contract_id_must_be_ulid() -> None:
    a, b = KeyPair.generate(), KeyPair.generate()
    now = datetime.now(tz=UTC)
    with pytest.raises(ValidationError):
        Contract(
            contract_id="not-a-ulid",
            caller=a.did,
            callee=b.did,
            callee_card_hash="sha256:" + ("a" * 64),
            capability="x",
            input={},
            cost_budget=CostBudget(unit="usd", max=Decimal("0.10")),
            verifier="self",
            issued=now,
            expires=now + timedelta(minutes=5),
        )


def test_negative_budget_rejected() -> None:
    with pytest.raises(ValidationError):
        CostBudget(unit="usd", max=Decimal("-1"))


def test_float_budget_rejected() -> None:
    with pytest.raises(ValidationError):
        CostBudget(unit="usd", max=0.10)  # type: ignore[arg-type]
