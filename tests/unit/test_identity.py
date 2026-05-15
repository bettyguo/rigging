"""Unit tests for ``rigging.core.identity`` and ``rigging.identity``."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from rigging.core.identity import DID, DIDParseError, derive_did, parse_did
from rigging.identity import KeyPair, sign_jws, verify_jws
from rigging.identity.keys import KeyStorageError


def test_did_grammar_accepts_valid() -> None:
    raw = "did:rig:tihtfhkojvxgu7emjqpsuoymjrlh7cu3"
    did = parse_did(raw)
    assert str(did) == raw
    assert did.fingerprint == "tihtfhkojvxgu7emjqpsuoymjrlh7cu3"


@pytest.mark.parametrize(
    "bad",
    [
        "did:rig:TOO-SHORT",
        "did:rig:" + "A" * 32,  # uppercase rejected
        "did:rig:" + "1" * 32,  # '1' is not in the base32 alphabet (2-7 only)
        "DID:RIG:tihtfhkojvxgu7emjqpsuoymjrlh7cu3",
        "",
        "did:foo:tihtfhkojvxgu7emjqpsuoymjrlh7cu3",
    ],
)
def test_did_grammar_rejects(bad: str) -> None:
    with pytest.raises(DIDParseError):
        parse_did(bad)


def test_derive_did_is_deterministic() -> None:
    pk = b"\x01" * 32
    assert derive_did(pk) == derive_did(pk)


def test_derive_did_changes_with_key() -> None:
    a = derive_did(b"\x01" * 32)
    b = derive_did(b"\x02" * 32)
    assert a != b


def test_derive_did_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        derive_did(b"\x01" * 31)


def test_keypair_generate_signs_and_verifies() -> None:
    kp = KeyPair.generate()
    sig = kp.sign(b"hello")
    assert kp.verify(sig, b"hello")
    assert not kp.verify(sig, b"hellp")


def test_keypair_did_matches_public_bytes() -> None:
    kp = KeyPair.generate()
    assert kp.did == derive_did(kp.public_bytes)
    # Also: the DID is a string in canonical form
    assert isinstance(kp.did, DID)
    assert isinstance(kp.did, str)


def test_keypair_encrypted_roundtrip(tmp_path: Path) -> None:
    kp = KeyPair.generate()
    path = tmp_path / "test.key"
    kp.save_encrypted(path, passphrase=b"correct horse")
    loaded = KeyPair.load_encrypted(path, passphrase=b"correct horse")
    assert loaded.did == kp.did
    # Wrong passphrase fails clean
    with pytest.raises(KeyStorageError):
        KeyPair.load_encrypted(path, passphrase=b"battery staple")


def test_keypair_refuses_empty_passphrase(tmp_path: Path) -> None:
    kp = KeyPair.generate()
    with pytest.raises(KeyStorageError):
        kp.save_encrypted(tmp_path / "x.key", passphrase=b"")


def test_jws_roundtrip() -> None:
    kp = KeyPair.generate()
    payload = b"some bytes to sign"
    jws = sign_jws(payload, key=kp)
    decoded = verify_jws(jws, public_key_bytes=kp.public_bytes)
    assert decoded == payload


def test_jws_tampered_signature_fails() -> None:
    kp = KeyPair.generate()
    jws = sign_jws(b"hi", key=kp)
    parts = jws.split(".")
    # Flip a byte in the signature segment
    tampered = base64.urlsafe_b64decode(parts[2] + "==")
    tampered = (bytes([tampered[0] ^ 0xFF])) + tampered[1:]
    parts[2] = base64.urlsafe_b64encode(tampered).rstrip(b"=").decode()
    with pytest.raises(Exception):
        verify_jws(".".join(parts), public_key_bytes=kp.public_bytes)


def test_jws_wrong_key_fails() -> None:
    kp = KeyPair.generate()
    other = KeyPair.generate()
    jws = sign_jws(b"hi", key=kp)
    with pytest.raises(Exception):
        verify_jws(jws, public_key_bytes=other.public_bytes)
