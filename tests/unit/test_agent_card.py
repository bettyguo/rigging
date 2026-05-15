"""Agent card model tests."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from rigging.core import AgentCard, Capability, CostModel, OperatorInfo
from rigging.core.errors import SignatureInvalid
from rigging.identity import KeyPair, sign_card, verify_card


def _unsigned(keypair: KeyPair, *caps: Capability) -> AgentCard:
    now = datetime.now(tz=UTC)
    return AgentCard(
        agent_id=keypair.did,
        public_key=base64.b64encode(keypair.public_bytes).decode("ascii"),
        operator=OperatorInfo(name="Test Co."),
        capabilities=list(caps),
        issued=now,
        expires=now + timedelta(hours=1),
    )


def _cap(name: str) -> Capability:
    return Capability(
        name=name,
        description="x",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        cost_model=CostModel(
            unit="usd",
            base=Decimal("0.01"),
            per_input_unit=Decimal("0"),
            per_output_unit=Decimal("0"),
            input_unit="c",
            output_unit="c",
        ),
        verifier_kinds=["self"],
    )


def test_card_requires_at_least_one_capability() -> None:
    kp = KeyPair.generate()
    with pytest.raises(ValidationError):
        AgentCard(
            agent_id=kp.did,
            public_key=base64.b64encode(kp.public_bytes).decode("ascii"),
            operator=OperatorInfo(name="x"),
            capabilities=[],
            issued=datetime.now(tz=UTC),
            expires=datetime.now(tz=UTC) + timedelta(hours=1),
        )


def test_card_capability_names_must_be_unique() -> None:
    kp = KeyPair.generate()
    with pytest.raises(ValidationError):
        _unsigned(kp, _cap("a"), _cap("a"))


def test_capability_name_grammar() -> None:
    with pytest.raises(ValidationError):
        _cap("Bad-Name")


def test_card_expires_must_be_after_issued() -> None:
    kp = KeyPair.generate()
    now = datetime.now(tz=UTC)
    with pytest.raises(ValidationError):
        AgentCard(
            agent_id=kp.did,
            public_key=base64.b64encode(kp.public_bytes).decode("ascii"),
            operator=OperatorInfo(name="x"),
            capabilities=[_cap("a")],
            issued=now,
            expires=now,
        )


def test_card_sign_and_verify_roundtrip() -> None:
    kp = KeyPair.generate()
    card = _unsigned(kp, _cap("a"))
    signed = sign_card(card, key=kp)
    assert signed.signature.count(".") == 2
    verify_card(signed)


def test_card_verify_rejects_tampered_payload() -> None:
    kp = KeyPair.generate()
    card = _unsigned(kp, _cap("a"))
    signed = sign_card(card, key=kp)
    # Re-create the card with a modified field but keep the original signature
    bad = signed.model_copy(update={"operator": OperatorInfo(name="Different")})
    with pytest.raises(SignatureInvalid):
        verify_card(bad)


def test_card_sign_requires_matching_keypair() -> None:
    kp = KeyPair.generate()
    other = KeyPair.generate()
    card = _unsigned(kp, _cap("a"))
    with pytest.raises(SignatureInvalid):
        sign_card(card, key=other)


def test_card_lookup() -> None:
    kp = KeyPair.generate()
    card = _unsigned(kp, _cap("a"), _cap("b"))
    assert card.has_capability("a")
    assert card.has_capability("b")
    assert not card.has_capability("c")
    assert card.capability("a").name == "a"
