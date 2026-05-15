"""Axis 3 — identity propagation under adversarial conditions."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

from rigging.core import AgentCard, OperatorInfo
from rigging.core.errors import SignatureInvalid
from rigging.identity import KeyPair, sign_card, verify_card
from rigging.identity.cards import verify_contract
from rigging.identity.jws import JWSVerifyError, verify_jws

from benchmarks.rig_bench.harness import usd_capability


def run(full: bool = False) -> dict[str, object]:  # noqa: ARG001
    results = {
        "spoofing_rejected": _check_spoofing(),
        "tampered_card_rejected": _check_tampered_card(),
        "wrong_key_rejected": _check_wrong_key(),
    }
    score = sum(1 for v in results.values() if v) / len(results)
    return {
        "score": score,
        "scenarios": results,
        "notes": (
            "Replay-attack rejection is asserted by contract_id uniqueness + "
            "expiry; covered structurally rather than scenario-driven in v0."
        ),
    }


def _check_spoofing() -> bool:
    """An attacker constructs a card claiming a victim's DID without
    holding the corresponding private key."""
    attacker = KeyPair.generate()
    victim = KeyPair.generate()
    now = datetime.now(tz=UTC)
    forged = AgentCard(
        agent_id=victim.did,
        public_key=base64.b64encode(attacker.public_bytes).decode("ascii"),
        operator=OperatorInfo(name="Forger Inc."),
        capabilities=[usd_capability("x")],
        issued=now,
        expires=now + timedelta(hours=1),
    )
    # Sign with attacker's key — this should fail because attacker.did !=
    # forged.agent_id (the spoofed identity).
    try:
        signed = sign_card(forged, key=attacker)
    except SignatureInvalid:
        return True
    # If somehow signed, verification must fail because derived DID won't match.
    try:
        verify_card(signed)
    except SignatureInvalid:
        return True
    return False


def _check_tampered_card() -> bool:
    kp = KeyPair.generate()
    now = datetime.now(tz=UTC)
    card = sign_card(
        AgentCard(
            agent_id=kp.did,
            public_key=base64.b64encode(kp.public_bytes).decode("ascii"),
            operator=OperatorInfo(name="A"),
            capabilities=[usd_capability("x")],
            issued=now,
            expires=now + timedelta(hours=1),
        ),
        key=kp,
    )
    tampered = card.model_copy(update={"operator": OperatorInfo(name="B")})
    try:
        verify_card(tampered)
    except SignatureInvalid:
        return True
    return False


def _check_wrong_key() -> bool:
    """Verify that a JWS signed by key A cannot be verified against key B."""
    a, b = KeyPair.generate(), KeyPair.generate()
    from rigging.identity import sign_jws

    jws = sign_jws(b"payload", key=a)
    try:
        verify_jws(jws, public_key_bytes=b.public_bytes)
    except JWSVerifyError:
        return True
    return False
