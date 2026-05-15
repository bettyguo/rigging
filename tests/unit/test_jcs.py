"""JCS canonicalization tests."""

from __future__ import annotations

import math

import pytest

from rigging.identity.jcs import canonicalize


def test_basic_object_sorts_keys() -> None:
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_nested_object() -> None:
    assert canonicalize({"a": {"y": 1, "x": 2}}) == b'{"a":{"x":2,"y":1}}'


def test_array_preserves_order() -> None:
    assert canonicalize([3, 1, 2]) == b"[3,1,2]"


def test_string_escapes() -> None:
    assert canonicalize("a\"b\\c\nd") == b'"a\\"b\\\\c\\nd"'


def test_control_characters_become_unicode_escapes() -> None:
    # 0x01 is a control char; must be 
    assert canonicalize("\x01") == b'"\\u0001"'


def test_zero_renders_as_zero() -> None:
    assert canonicalize(0) == b"0"
    assert canonicalize(0.0) == b"0"


def test_integer_renders_naturally() -> None:
    assert canonicalize(42) == b"42"
    assert canonicalize(-7) == b"-7"


def test_float_integral_collapses() -> None:
    assert canonicalize(2.0) == b"2"


def test_nan_rejected() -> None:
    with pytest.raises(TypeError):
        canonicalize(float("nan"))


def test_inf_rejected() -> None:
    with pytest.raises(TypeError):
        canonicalize(math.inf)


def test_unsupported_type_rejected() -> None:
    with pytest.raises(TypeError):
        canonicalize({1, 2, 3})


def test_non_string_object_key_rejected() -> None:
    with pytest.raises(TypeError):
        canonicalize({1: "a"})


def test_canonical_is_byte_for_byte_stable() -> None:
    payload = {"z": [1, 2, {"k": "v"}], "a": True, "n": None}
    assert canonicalize(payload) == canonicalize(payload)
