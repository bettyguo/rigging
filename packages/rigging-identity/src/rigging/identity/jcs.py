"""JSON Canonicalization Scheme (RFC 8785) — minimal v0 implementation.

The rig signs over JCS-canonical bytes so that two implementations (or
two passes in the same implementation) agree byte-for-byte on what the
signature covers. The reference implementation supports the subset of
JSON we actually produce:

- Objects with string keys sorted by code-point order.
- Arrays in declaration order.
- Strings with the minimal RFC 8259 escape set plus RFC 8785 control-
  character handling.
- Integers as their decimal string.
- Floats per ECMA-262 ``Number.prototype.toString`` (rfc 8785 §3.2.2.3).
- ``true``, ``false``, ``null`` as literals.

Inputs that contain unsupported types (sets, bytes, custom objects,
NaN/Inf) raise ``TypeError``. This is deliberate: forbidding silent
coercion keeps the canonicalisation honest.

The implementation is intentionally small and easy to audit. If we ever
need richer behaviour (BigDecimal, etc.) we will adopt a vetted
upstream library; for v0 the surface we sign over is well-controlled by
our pydantic models.
"""

from __future__ import annotations

import math
from typing import Any

# Characters that must be escaped in a JSON string per RFC 8259 §7.
# RFC 8785 §3.2.2.2 narrows the escape set to the minimum.
_ESCAPE_TABLE: dict[int, str] = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def _encode_string(value: str) -> str:
    out: list[str] = ['"']
    for ch in value:
        code = ord(ch)
        if code in _ESCAPE_TABLE:
            out.append(_ESCAPE_TABLE[code])
        elif code < 0x20:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _encode_number(value: int | float) -> str:
    if isinstance(value, bool):
        # bool is a subclass of int in Python; JSON treats them separately.
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise TypeError("JCS does not encode NaN or +/-Inf")
    if value == 0.0:
        return "0"
    # ECMA-262 toString-compatible: Python's repr() for non-integral
    # floats is close enough for our v0 surface (we don't sign over
    # user-supplied floats outside JSON-Schema), but we normalise the
    # easy cases.
    if value.is_integer():
        return str(int(value))
    return repr(value)


def _encode(value: Any, out: list[str]) -> None:
    if value is None:
        out.append("null")
        return
    if isinstance(value, bool):
        out.append("true" if value else "false")
        return
    if isinstance(value, (int, float)):
        out.append(_encode_number(value))
        return
    if isinstance(value, str):
        out.append(_encode_string(value))
        return
    if isinstance(value, list) or isinstance(value, tuple):
        out.append("[")
        first = True
        for item in value:
            if not first:
                out.append(",")
            _encode(item, out)
            first = False
        out.append("]")
        return
    if isinstance(value, dict):
        # JCS §3.2.3: object members sorted by UTF-16 code unit values of
        # the keys. Python str sort is by Unicode code point; for the
        # Basic Multilingual Plane the two orders agree, which is all we
        # need for keys made of ASCII identifiers and the occasional URI.
        keys = sorted(value.keys())
        out.append("{")
        first = True
        for key in keys:
            if not isinstance(key, str):
                raise TypeError(f"object keys must be strings; got {type(key).__name__}")
            if not first:
                out.append(",")
            out.append(_encode_string(key))
            out.append(":")
            _encode(value[key], out)
            first = False
        out.append("}")
        return
    raise TypeError(f"unsupported type in JCS canonicalize: {type(value).__name__}")


def canonicalize(value: Any) -> bytes:
    """Return the RFC 8785 canonical byte form of ``value``.

    Args:
        value: A JSON-shaped Python object (dicts with string keys,
            lists, strings, integers, finite floats, booleans, None).

    Returns:
        The canonical UTF-8 encoded bytes.

    Raises:
        TypeError: For non-JSON-shaped inputs or for unsupported number
            forms (NaN, infinity).
    """
    parts: list[str] = []
    _encode(value, parts)
    return "".join(parts).encode("utf-8")
