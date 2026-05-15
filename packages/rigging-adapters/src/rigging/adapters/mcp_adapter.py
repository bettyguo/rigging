"""MCPAdapter — expose MCP-server tools as a rig participant.

The adapter holds a mapping ``rig_capability_name -> mcp_tool_name`` so
that the operator can choose which subset of an MCP server's tools to
surface as rig capabilities, and what to rename them to. The MCP
descriptor and the rig agent card are kept structurally separate per
ADR-0008; the adapter is the only place the translation happens.

The MCP client is supplied by the caller as an async callable. We avoid
depending on a specific MCP client library: that keeps the package's
dependency graph minimal and lets each user plug in their preferred
client.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any, TypeAlias

from rigging.core.agent_card import AgentCard
from rigging.core.contract import Contract
from rigging.core.errors import CapabilityMismatch, ContractRejected
from rigging.core.identity import DID
from rigging.core.protocols import ExecuteResult
from rigging.identity.cards import card_hash
from rigging.identity.jcs import canonicalize
from rigging.identity.jws import sign_jws
from rigging.identity.keys import KeyPair

MCPCaller: TypeAlias = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
"""``async def mcp_call(tool_name, arguments) -> result_dict``."""


class MCPAdapter:
    """Wrap an MCP server (or any tool-call-shaped backend) as a rig agent."""

    def __init__(
        self,
        *,
        card: AgentCard,
        keypair: KeyPair,
        mcp_caller: MCPCaller,
        capability_to_tool: dict[str, str],
    ) -> None:
        if keypair.did != card.agent_id:
            raise ValueError("keypair DID does not match card.agent_id")
        missing = {c.name for c in card.capabilities} - set(capability_to_tool)
        if missing:
            raise ValueError(
                f"capability_to_tool missing for: {sorted(missing)}"
            )
        self._card = card
        self._keypair = keypair
        self._caller = mcp_caller
        self._tool_map = dict(capability_to_tool)
        self._card_hash = card_hash(card)

    @property
    def did(self) -> DID:
        return self._card.agent_id

    @property
    def card(self) -> AgentCard:
        return self._card

    async def accept(self, contract: Contract) -> bool:
        if contract.callee != self._card.agent_id:
            return False
        if contract.callee_card_hash != self._card_hash:
            raise CapabilityMismatch(
                "contract was issued against a different card revision"
            )
        return self._card.has_capability(contract.capability)

    async def execute(self, contract: Contract) -> ExecuteResult:
        tool = self._tool_map.get(contract.capability)
        if tool is None:  # pragma: no cover — guarded by construction
            raise CapabilityMismatch(
                f"no MCP tool mapping for capability {contract.capability!r}"
            )
        try:
            output = await self._caller(tool, contract.input)
        except Exception as exc:  # noqa: BLE001 - normalise to rig error
            raise ContractRejected(
                f"MCP call failed: {exc}",
                contract_id=contract.contract_id,
            ) from exc
        if not isinstance(output, dict):
            raise ContractRejected(
                "MCP tool returned a non-dict result",
                contract_id=contract.contract_id,
            )
        cap = self._card.capability(contract.capability)
        cost = cap.cost_model.base
        signature = sign_jws(canonicalize(output), key=self._keypair)
        return ExecuteResult(output=output, cost=Decimal(cost), signature=signature)
