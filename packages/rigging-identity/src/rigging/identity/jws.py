"""JWS Compact Serialization with Ed25519 (RFC 7515 / RFC 8037).

The rig encodes its signatures as detached-payload JWS in compact form:
``<base64url(header)>.<base64url(payload)>.<base64url(signature)>``,
where ``alg=EdDSA`` and the payload is the JCS-canonical bytes of the
signed object.

We embed the payload in the compact form rather than using detached
mode — keeping the signed bytes inline simplifies the trace's evidence
chain: a verifier needs only the JWS string to check the claim.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from rigging.identity.keys import KeyPair, verify_signature


@dataclass(frozen=True, slots=True)
class JWSVerifyError(Exception):
    """Raised when a JWS fails to verify (malformed or bad signature)."""

    reason: str

    def __str__(self) -> str:
        return self.reason


_HEADER = {"alg": "EdDSA", "typ": "JOSE"}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign_jws(payload: bytes, *, key: KeyPair) -> str:
    """Sign ``payload`` and return a JWS Compact Serialization string.

    Args:
        payload: The byte string to sign — typically JCS-canonical bytes.
        key: The signer's keypair.

    Returns:
        ``<header>.<payload>.<signature>`` with each segment
        base64url-encoded without padding.
    """
    header_bytes = json.dumps(_HEADER, separators=(",", ":")).encode("utf-8")
    header_b = _b64url(header_bytes)
    payload_b = _b64url(payload)
    signing_input = f"{header_b}.{payload_b}".encode("ascii")
    signature = key.sign(signing_input)
    return f"{header_b}.{payload_b}.{_b64url(signature)}"


def verify_jws(jws: str, *, public_key_bytes: bytes) -> bytes:
    """Verify a JWS Compact Serialization and return its payload.

    Args:
        jws: A compact JWS produced by :func:`sign_jws` or equivalent.
        public_key_bytes: 32 raw bytes of the expected signer's public key.

    Returns:
        The decoded payload bytes.

    Raises:
        JWSVerifyError: If the JWS is malformed, the header is wrong,
            or the signature does not verify.
    """
    parts = jws.split(".")
    if len(parts) != 3:
        raise JWSVerifyError("JWS must have three dot-separated parts")
    header_b, payload_b, signature_b = parts
    try:
        header_bytes = _b64url_decode(header_b)
        payload_bytes = _b64url_decode(payload_b)
        signature = _b64url_decode(signature_b)
    except Exception as exc:  # noqa: BLE001 - report cleanly
        raise JWSVerifyError(f"JWS segments did not base64url-decode: {exc}") from exc
    try:
        header = json.loads(header_bytes)
    except json.JSONDecodeError as exc:
        raise JWSVerifyError(f"JWS header is not valid JSON: {exc}") from exc
    if header.get("alg") != "EdDSA":
        raise JWSVerifyError(f"unsupported alg: {header.get('alg')!r}")
    signing_input = f"{header_b}.{payload_b}".encode("ascii")
    if not verify_signature(public_key_bytes, signature, signing_input):
        raise JWSVerifyError("JWS signature did not verify")
    return payload_bytes
