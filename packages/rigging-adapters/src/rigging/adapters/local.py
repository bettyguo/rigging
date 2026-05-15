"""LocalPythonAdapter — wraps Python callables as rig participants.

This is the most boring possible adapter, and it is by far the most
useful one for testing, examples, and benchmarks. A
:class:`LocalPythonAdapter` registers one Python callable per declared
capability and routes execute calls into them.

Handlers may be either ``async def`` *or* sync ``def`` functions. Sync
handlers are run on a worker thread via ``anyio.to_thread.run_sync`` so
they don't block the event loop. This makes the adapter ergonomic for
test fixtures and demos written in plain Python.
"""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any, TypeAlias

import anyio

from rigging.core.agent_card import AgentCard
from rigging.core.contract import Contract
from rigging.core.errors import (
    CapabilityMismatch,
    ContractRejected,
    PolicyDenied,
)
from rigging.core.identity import DID
from rigging.core.protocols import ExecuteResult
from rigging.identity.cards import card_hash
from rigging.identity.jcs import canonicalize
from rigging.identity.jws import sign_jws
from rigging.identity.keys import KeyPair

AsyncCapabilityFn: TypeAlias = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
SyncCapabilityFn: TypeAlias = Callable[[dict[str, Any]], dict[str, Any]]
CapabilityFn: TypeAlias = AsyncCapabilityFn | SyncCapabilityFn
"""Either an ``async def fn(input: dict) -> dict`` or a sync equivalent."""

CostFn: TypeAlias = Callable[[dict[str, Any], dict[str, Any]], Decimal]
"""``cost(input, output) -> Decimal``. Defaults to the capability's base cost."""


class LocalPythonAdapter:
    """Expose Python coroutines as a rig agent.

    Example::

        async def echo(input: dict) -> dict:
            return {"text": input["text"]}

        adapter = LocalPythonAdapter(
            card=signed_card,
            keypair=keypair,
            handlers={"echo": echo},
        )
    """

    def __init__(
        self,
        *,
        card: AgentCard,
        keypair: KeyPair,
        handlers: dict[str, CapabilityFn],
        cost_fns: dict[str, CostFn] | None = None,
    ) -> None:
        if keypair.did != card.agent_id:
            raise ValueError("keypair DID does not match card.agent_id")
        missing = {c.name for c in card.capabilities} - set(handlers)
        if missing:
            raise ValueError(
                f"handlers missing for declared capabilities: {sorted(missing)}"
            )
        extra = set(handlers) - {c.name for c in card.capabilities}
        if extra:
            raise ValueError(
                f"handlers provided for undeclared capabilities: {sorted(extra)}"
            )
        self._card = card
        self._keypair = keypair
        self._handlers = handlers
        self._cost_fns = cost_fns or {}
        self._card_hash = card_hash(card)

    # --- protocol surface ----------------------------------------------

    @property
    def did(self) -> DID:
        return self._card.agent_id

    @property
    def card(self) -> AgentCard:
        return self._card

    async def accept(self, contract: Contract) -> bool:
        if contract.callee != self._card.agent_id:
            raise PolicyDenied("contract.callee does not match this adapter's DID")
        if contract.callee_card_hash != self._card_hash:
            raise CapabilityMismatch(
                "contract was issued against a different card revision",
                details={
                    "expected": self._card_hash,
                    "received": contract.callee_card_hash,
                },
            )
        if not self._card.has_capability(contract.capability):
            raise CapabilityMismatch(
                f"capability {contract.capability!r} not declared on this card"
            )
        cap = self._card.capability(contract.capability)
        if cap.cost_model.unit != contract.cost_budget.unit:
            raise CapabilityMismatch(
                "contract budget unit does not match capability cost unit"
            )
        if contract.cost_budget.max < cap.cost_model.base:
            raise PolicyDenied("contract budget is below the capability's base cost")
        return True

    async def execute(self, contract: Contract) -> ExecuteResult:
        handler = self._handlers.get(contract.capability)
        if handler is None:  # pragma: no cover — guarded by accept()
            raise CapabilityMismatch(
                f"no handler for capability {contract.capability!r}"
            )
        try:
            output = await self._invoke(handler, contract.input)
        except RigErrorPassthrough as exc:
            raise exc.original
        except Exception as exc:  # noqa: BLE001 - re-raise as rig error
            raise ContractRejected(
                f"handler raised: {exc}",
                contract_id=contract.contract_id,
            ) from exc
        if not isinstance(output, dict):
            raise ContractRejected(
                "handler must return a dict",
                contract_id=contract.contract_id,
            )
        cost = self._compute_cost(contract.capability, contract.input, output)
        signature = sign_jws(canonicalize(output), key=self._keypair)
        return ExecuteResult(output=output, cost=cost, signature=signature)

    @staticmethod
    async def _invoke(
        handler: CapabilityFn,
        input_payload: dict[str, Any],
    ) -> dict[str, Any]:
        if inspect.iscoroutinefunction(handler):
            async_out: Any = await handler(input_payload)
            if not isinstance(async_out, dict):
                raise TypeError(
                    f"async handler must return dict, got {type(async_out).__name__}"
                )
            return dict(async_out)
        sync_handler: Any = handler
        sync_out: Any = await anyio.to_thread.run_sync(sync_handler, input_payload)
        if not isinstance(sync_out, dict):
            raise TypeError(
                f"sync handler must return dict, got {type(sync_out).__name__}"
            )
        return dict(sync_out)

    # --- helpers --------------------------------------------------------

    def _compute_cost(
        self,
        capability_name: str,
        input_payload: dict[str, Any],
        output: dict[str, Any],
    ) -> Decimal:
        fn = self._cost_fns.get(capability_name)
        if fn is not None:
            return fn(input_payload, output)
        return self._card.capability(capability_name).cost_model.base

    def output_hash(self, output: dict[str, Any]) -> str:
        """Convenience: ``sha256:<hex>`` of canonical ``output``."""
        return f"sha256:{hashlib.sha256(canonicalize(output)).hexdigest()}"


class RigErrorPassthrough(Exception):
    """Internal: pass a ``RigError`` through the sync→async boundary.

    Sync handlers that need to raise a typed rig error can raise this
    wrapping the real error, and the adapter re-raises the original on
    the async side.
    """

    def __init__(self, original: Exception) -> None:
        super().__init__(str(original))
        self.original = original
