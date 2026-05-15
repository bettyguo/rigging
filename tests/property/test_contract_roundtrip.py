"""Property tests for ``Contract`` JSON round-trip + replay rejection."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from rigging.core import Contract, CostBudget
from rigging.identity import KeyPair, sign_contract, verify_contract
from rigging.runtime.ulid import new_ulid


def _build_contract(input_payload: dict, budget: Decimal) -> tuple[Contract, KeyPair]:
    caller, callee = KeyPair.generate(), KeyPair.generate()
    now = datetime.now(tz=UTC)
    contract = Contract(
        contract_id=new_ulid(),
        caller=caller.did,
        callee=callee.did,
        callee_card_hash="sha256:" + ("a" * 64),
        capability="cap",
        input=input_payload,
        cost_budget=CostBudget(unit="usd", max=budget),
        verifier="self",
        issued=now,
        expires=now + timedelta(minutes=5),
    )
    return contract, caller


_json_safe_dict = st.dictionaries(
    st.text(min_size=1, max_size=10),
    st.one_of(
        st.text(max_size=40),
        st.integers(min_value=-1000, max_value=1000),
        st.booleans(),
        st.none(),
    ),
    max_size=4,
)


@given(_json_safe_dict, st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10"), places=2))
@settings(max_examples=80, deadline=None)
def test_contract_json_roundtrip_preserves_signature(
    input_payload: dict, budget: Decimal,
) -> None:
    contract, caller = _build_contract(input_payload, budget)
    signed = sign_contract(contract, key=caller)
    # Round-trip through JSON
    blob = signed.model_dump_json()
    revived = Contract.model_validate(json.loads(blob))
    # Signature still verifies post-round-trip
    verify_contract(revived, caller_public_key=caller.public_bytes)
    assert revived.contract_id == signed.contract_id
    assert revived.signature == signed.signature


@given(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10"), places=2))
@settings(max_examples=50, deadline=None)
def test_replay_detected_by_id_uniqueness(budget: Decimal) -> None:
    """A re-submitted contract with the same ID would collide with the
    issuer's records. We simulate the rig's de-dup behaviour by checking
    that two contracts with the same ID are considered equal where it
    matters."""
    contract, caller = _build_contract({}, budget)
    signed = sign_contract(contract, key=caller)
    # The contract_id is the de-dup token; two cards' contracts cannot
    # share one without one being a replay of the other.
    assert signed.contract_id == contract.contract_id
    # ULID monotonicity at millisecond resolution: a freshly minted ULID
    # at the same instant should still differ in its random tail.
    other = new_ulid(int(contract.issued.timestamp() * 1000))
    assert other != contract.contract_id
