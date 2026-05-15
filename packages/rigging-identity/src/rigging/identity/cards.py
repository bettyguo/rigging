"""Signing and verifying agent cards and contracts.

The crypto operations live one layer down (:mod:`rigging.identity.jws`).
This module is the *trust-aware* layer that knows how the pydantic
models are signed: which fields are included in the signing input, how
the canonical bytes are derived, and what counts as a valid signature.

Two pieces of subtle policy live here, both documented in the
``agent-card-v0`` / ``rig-contract-v0`` specs:

1. The ``signature`` field is omitted from the JCS canonical input
   (the signature can't cover itself).
2. The signing key's derived DID MUST equal the document's stated
   identity (``agent_id`` for a card, ``caller`` for a contract).
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from rigging.core.agent_card import AgentCard
from rigging.core.contract import Contract
from rigging.core.errors import SignatureInvalid
from rigging.core.identity import DID, derive_did
from rigging.identity.jcs import canonicalize
from rigging.identity.jws import JWSVerifyError, sign_jws, verify_jws
from rigging.identity.keys import KeyPair


def _canonical_bytes_without_signature(obj: dict[str, Any]) -> bytes:
    """Return JCS bytes of ``obj`` with the ``signature`` field cleared."""
    cleaned = dict(obj)
    cleaned["signature"] = ""
    return canonicalize(cleaned)


def card_hash(card: AgentCard) -> str:
    """Return ``sha256:<hex>`` digest of the JCS-canonical (signature-free) card.

    This is what the contract's ``callee_card_hash`` field carries.
    """
    blob = card.model_dump(mode="json")
    digest = hashlib.sha256(_canonical_bytes_without_signature(blob)).hexdigest()
    return f"sha256:{digest}"


# --- agent cards ----------------------------------------------------------


def sign_card(card: AgentCard, *, key: KeyPair) -> AgentCard:
    """Return a new :class:`AgentCard` with the signature field populated.

    Args:
        card: An unsigned (``signature == ""``) card. The card's
            ``agent_id`` and ``public_key`` MUST be consistent with the
            signing key.
        key: The operator's keypair.

    Raises:
        SignatureInvalid: If ``card.agent_id`` or ``card.public_key``
            does not match the signing key.
    """
    if key.did != card.agent_id:
        raise SignatureInvalid(
            "signing key's DID does not match card.agent_id",
            details={"key_did": str(key.did), "card_did": str(card.agent_id)},
        )
    expected_pk = base64.b64encode(key.public_bytes).decode("ascii")
    if card.public_key != expected_pk:
        raise SignatureInvalid(
            "card.public_key does not match the signing key's bytes",
        )

    blob = card.model_dump(mode="json")
    payload = _canonical_bytes_without_signature(blob)
    blob["signature"] = sign_jws(payload, key=key)
    return AgentCard.model_validate(blob)


def verify_card(card: AgentCard) -> None:
    """Verify the JWS on an agent card.

    The card's embedded ``public_key`` must base64-decode to 32 raw
    bytes whose derived DID equals ``agent_id``, and the JWS must
    verify against that key.

    Raises:
        SignatureInvalid: For any failure (missing signature, malformed
            public key, DID mismatch, JWS verification failure).
    """
    if not card.signature:
        raise SignatureInvalid("card has no signature")
    try:
        pubkey_bytes = base64.b64decode(card.public_key, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise SignatureInvalid(f"card.public_key is not valid base64: {exc}") from exc
    if len(pubkey_bytes) != 32:
        raise SignatureInvalid("card.public_key must decode to 32 bytes")
    derived = derive_did(pubkey_bytes)
    if derived != card.agent_id:
        raise SignatureInvalid(
            "agent_id does not match derived DID of public key",
            details={"agent_id": str(card.agent_id), "derived": str(derived)},
        )
    blob = card.model_dump(mode="json")
    payload = _canonical_bytes_without_signature(blob)
    try:
        signed_payload = verify_jws(card.signature, public_key_bytes=pubkey_bytes)
    except JWSVerifyError as exc:
        raise SignatureInvalid(f"card JWS did not verify: {exc}") from exc
    if signed_payload != payload:
        raise SignatureInvalid("card JWS payload does not match canonical card")


# --- contracts ------------------------------------------------------------


def sign_contract(contract: Contract, *, key: KeyPair) -> Contract:
    """Return a new :class:`Contract` with the caller's JWS populated.

    Args:
        contract: An unsigned contract whose ``caller`` matches ``key``.
        key: The caller's keypair.

    Raises:
        SignatureInvalid: If ``key.did != contract.caller``.
    """
    if key.did != contract.caller:
        raise SignatureInvalid(
            "signing key's DID does not match contract.caller",
            details={"key_did": str(key.did), "caller": str(contract.caller)},
        )
    blob = contract.model_dump(mode="json")
    payload = _canonical_bytes_without_signature(blob)
    blob["signature"] = sign_jws(payload, key=key)
    return Contract.model_validate(blob)


def verify_contract(contract: Contract, *, caller_public_key: bytes) -> None:
    """Verify the JWS on a contract using the caller's known public key.

    Args:
        contract: The (signed) contract.
        caller_public_key: 32 raw bytes of the caller's public key. The
            runtime gets this from the caller's registered agent card.

    Raises:
        SignatureInvalid: For any failure.
    """
    if not contract.signature:
        raise SignatureInvalid("contract has no signature")
    if len(caller_public_key) != 32:
        raise SignatureInvalid("caller public key must be 32 bytes")
    derived = derive_did(caller_public_key)
    if derived != contract.caller:
        raise SignatureInvalid(
            "supplied public key does not derive to contract.caller",
            details={"derived": str(derived), "caller": str(contract.caller)},
        )
    blob = contract.model_dump(mode="json")
    payload = _canonical_bytes_without_signature(blob)
    try:
        signed_payload = verify_jws(contract.signature, public_key_bytes=caller_public_key)
    except JWSVerifyError as exc:
        raise SignatureInvalid(f"contract JWS did not verify: {exc}") from exc
    if signed_payload != payload:
        raise SignatureInvalid("contract JWS payload does not match canonical contract")


def did_for_pubkey_bytes(public_key_bytes: bytes) -> DID:
    """Convenience: derive the DID for a given public-key byte string."""
    return derive_did(public_key_bytes)
