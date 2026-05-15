"""Minimal ULID generator.

Avoids a runtime dependency on a ULID package. The format is:
- 48-bit Unix-time-ms big-endian timestamp prefix,
- 80-bit cryptographic randomness suffix,
- Crockford-base32 encoded (no padding, uppercase), 26 characters total.

This is sufficient for ``contract_id`` use. See ADR-0010 for why we
chose ULIDs over UUIDv7 or random UUIDs.
"""

from __future__ import annotations

import os
import time
from typing import Final

_CROCKFORD: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
"""Crockford base32 alphabet (no I, L, O, U)."""


def _encode(bits: int, length: int) -> str:
    out: list[str] = []
    for _ in range(length):
        out.append(_CROCKFORD[bits & 0x1F])
        bits >>= 5
    return "".join(reversed(out))


def new_ulid(now_ms: int | None = None) -> str:
    """Return a fresh ULID string (26 Crockford-base32 chars, uppercase).

    Args:
        now_ms: Override timestamp in Unix milliseconds. Used in tests
            to produce stable IDs; production callers leave it ``None``.

    Returns:
        A 26-character ULID.
    """
    ts = now_ms if now_ms is not None else int(time.time() * 1000)
    if not 0 <= ts < (1 << 48):
        raise ValueError("ULID timestamp must fit in 48 bits")
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode(ts, 10) + _encode(randomness, 16)
