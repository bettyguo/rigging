"""Identity primitives — DID parsing, derivation, and the ``DID`` type.

The cryptographic operations (key generation, signing, verification) live
in ``rigging.identity``. This module only handles the *type-level* parts:
parsing a string into a ``DID``, deriving a DID from a public key, and
the canonical formatting rules.

Keeping the type-level concerns separate from the crypto means
``rigging-core`` has no `cryptography` dependency: a pydantic model can
hold a ``DID`` field without forcing every consumer to pull in the
Ed25519 library.

``DID`` subclasses ``str`` so that JSON serialisation, dict-key use, and
pydantic round-trips are all transparent. The DID-specific methods are
:attr:`DID.fingerprint` and the validating constructors :meth:`from_string`
and :func:`derive_did`.
"""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any, ClassVar

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

_DID_RE = re.compile(r"^did:rig:[a-z2-7]{32}$")
"""``did:rig:<32-char-base32-lowercase-nopad>``.

Derived from the first 20 bytes of SHA-256(public-key); base32-encoded
without padding (RFC 4648), lowercase. Always exactly 32 characters of
fingerprint.
"""


class DIDParseError(ValueError):
    """Raised when a string does not parse as a ``did:rig`` DID."""


class DID(str):
    """A rig identity reference.

    Subclasses ``str``: ``DID("did:rig:...")`` *is* a string with extra
    methods. This makes JSON round-trips, dict-key use, and pydantic
    integration trivial. Use :meth:`from_string` (or :func:`parse_did`)
    to validate untrusted input.
    """

    __slots__ = ()
    DID_RE: ClassVar[re.Pattern[str]] = _DID_RE

    def __new__(cls, value: str) -> "DID":
        if not _DID_RE.match(value):
            raise DIDParseError(f"not a well-formed did:rig identifier: {value!r}")
        return super().__new__(cls, value)

    @classmethod
    def from_string(cls, raw: str) -> "DID":
        """Parse a string into a :class:`DID`. Same as the constructor.

        Raises:
            DIDParseError: If ``raw`` does not match the grammar.
        """
        return cls(raw)

    @property
    def fingerprint(self) -> str:
        """The 32-character base32 fingerprint, sans the ``did:rig:`` prefix."""
        return str.__str__(self).split(":", 2)[2]

    # --- pydantic integration -------------------------------------------

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        def validate(value: Any) -> DID:
            if isinstance(value, DID):
                return value
            if isinstance(value, str):
                return cls(value)
            raise TypeError(
                f"DID must be a string, got {type(value).__name__}"
            )

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str, when_used="json-unless-none",
            ),
        )


def parse_did(raw: str) -> DID:
    """Convenience wrapper for :meth:`DID.from_string`."""
    return DID.from_string(raw)


def derive_did(public_key_bytes: bytes) -> DID:
    """Derive the canonical DID for a raw Ed25519 public key.

    Args:
        public_key_bytes: 32 raw bytes of the public key.

    Returns:
        The :class:`DID` corresponding to this key.

    Raises:
        ValueError: If ``public_key_bytes`` is not exactly 32 bytes.
    """
    if len(public_key_bytes) != 32:
        raise ValueError(
            f"Ed25519 public keys are 32 bytes; got {len(public_key_bytes)}"
        )
    digest = hashlib.sha256(public_key_bytes).digest()[:20]
    fingerprint = base64.b32encode(digest).decode("ascii").rstrip("=").lower()
    return DID(f"did:rig:{fingerprint}")
