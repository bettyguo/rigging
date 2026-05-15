"""Shared helpers for the example scripts.

Each example reuses the same agent-card / keypair scaffolding; pulling
it out keeps the example scripts focused on the *idea* they demonstrate
rather than on boilerplate.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from rigging.core import AgentCard, Capability, CostModel, OperatorInfo
from rigging.identity import KeyPair, sign_card


def build_card(
    keypair: KeyPair,
    *,
    operator_name: str,
    capabilities: list[Capability],
    lifetime: timedelta = timedelta(hours=1),
) -> AgentCard:
    """Construct and sign an agent card for ``keypair``."""
    now = datetime.now(tz=UTC)
    unsigned = AgentCard(
        agent_id=keypair.did,
        public_key=base64.b64encode(keypair.public_bytes).decode("ascii"),
        operator=OperatorInfo(name=operator_name),
        capabilities=capabilities,
        issued=now,
        expires=now + lifetime,
    )
    return sign_card(unsigned, key=keypair)


def usd_capability(
    name: str,
    *,
    description: str,
    base_cost: str = "0.01",
    verifier_kinds: list[str] | None = None,
    input_schema: dict | None = None,
    output_schema: dict | None = None,
) -> Capability:
    """A simple USD-priced capability for examples."""
    return Capability(
        name=name,
        description=description,
        input_schema=input_schema or {"type": "object"},
        output_schema=output_schema or {"type": "object"},
        cost_model=CostModel(
            unit="usd",
            base=Decimal(base_cost),
            per_input_unit=Decimal("0"),
            per_output_unit=Decimal("0"),
            input_unit="call",
            output_unit="call",
        ),
        verifier_kinds=verifier_kinds or ["self"],
    )
