"""Common harness primitives used by every axis of Rigging-Bench v0."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from rigging.adapters import LocalPythonAdapter
from rigging.core import AgentCard, Capability, CostModel, OperatorInfo
from rigging.identity import KeyPair, sign_card


def usd_capability(
    name: str,
    *,
    description: str = "",
    base: str = "0.01",
    per_input: str = "0",
    per_output: str = "0",
    verifier_kinds: list[str] | None = None,
    input_schema: dict | None = None,
    output_schema: dict | None = None,
) -> Capability:
    return Capability(
        name=name,
        description=description or f"benchmark capability {name}",
        input_schema=input_schema or {"type": "object"},
        output_schema=output_schema or {"type": "object"},
        cost_model=CostModel(
            unit="usd",
            base=Decimal(base),
            per_input_unit=Decimal(per_input),
            per_output_unit=Decimal(per_output),
            input_unit="call",
            output_unit="call",
        ),
        verifier_kinds=verifier_kinds or ["self"],
    )


def make_agent(
    *,
    operator: str,
    capabilities: list[Capability],
    handlers: dict[str, Callable[[dict], Awaitable[dict]]],
    cost_fns: dict[str, Callable[[dict, dict], Decimal]] | None = None,
) -> tuple[LocalPythonAdapter, KeyPair]:
    kp = KeyPair.generate()
    now = datetime.now(tz=UTC)
    card = sign_card(
        AgentCard(
            agent_id=kp.did,
            public_key=base64.b64encode(kp.public_bytes).decode("ascii"),
            operator=OperatorInfo(name=operator),
            capabilities=capabilities,
            issued=now,
            expires=now + timedelta(hours=1),
        ),
        key=kp,
    )
    adapter = LocalPythonAdapter(
        card=card,
        keypair=kp,
        handlers=handlers,
        cost_fns=cost_fns,
    )
    return adapter, kp
