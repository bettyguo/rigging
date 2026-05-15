"""rigging-identity — Ed25519 keys, DIDs, JCS, JWS, and card signing.

This package owns every cryptographic operation in the rig. Other
packages call into this one; this one calls into ``cryptography`` and
nothing else rig-specific.

Typical use::

    from rigging.identity import KeyPair, sign_card

    kp = KeyPair.generate()
    signed = sign_card(unsigned_card_dict, kp)

The CLI subcommands are mounted by ``rigging.cli``; ``rig identity
create`` writes a new keypair and prints its DID.
"""

from __future__ import annotations

from rigging.identity.cards import (
    sign_card,
    sign_contract,
    verify_card,
    verify_contract,
)
from rigging.identity.jcs import canonicalize
from rigging.identity.jws import sign_jws, verify_jws
from rigging.identity.keys import KeyPair, KeyStorageError

__all__ = [
    "KeyPair",
    "KeyStorageError",
    "canonicalize",
    "sign_card",
    "sign_contract",
    "sign_jws",
    "verify_card",
    "verify_contract",
    "verify_jws",
]
