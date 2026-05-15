"""Property-based tests for JCS canonicalization."""

from __future__ import annotations

import json
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from rigging.identity.jcs import canonicalize


_json_safe = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(2**53) + 1, max_value=(2**53) - 1),
        st.text(),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=8), children, max_size=5),
    ),
    max_leaves=8,
)


@given(_json_safe)
@settings(max_examples=200, deadline=None)
def test_canonicalize_is_deterministic(value: Any) -> None:
    assert canonicalize(value) == canonicalize(value)


@given(_json_safe)
@settings(max_examples=200, deadline=None)
def test_canonicalize_is_valid_json(value: Any) -> None:
    parsed = json.loads(canonicalize(value).decode("utf-8"))
    # The parsed JSON must equal the input value (modulo dict ordering).
    assert _normalise(parsed) == _normalise(value)


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    return value
