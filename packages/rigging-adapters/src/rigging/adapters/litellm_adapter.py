"""LiteLLMAdapter — expose a LiteLLM-backed model as a rig participant.

The adapter is a thin shim. The model id, system prompt, and any
provider-specific options live on the adapter; the rig sees a normal
:class:`Agent`.

LiteLLM is an optional dependency. The adapter imports it lazily so the
rest of the package remains importable without ``litellm`` installed —
that matters for users running with the ``LocalPythonAdapter`` alone.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from rigging.core.agent_card import AgentCard
from rigging.core.contract import Contract
from rigging.core.errors import ContractRejected
from rigging.core.identity import DID
from rigging.core.protocols import ExecuteResult
from rigging.identity.cards import card_hash
from rigging.identity.jcs import canonicalize
from rigging.identity.jws import sign_jws
from rigging.identity.keys import KeyPair

_DEFAULT_SYSTEM_PROMPT = (
    "You are an agent participating in a rig. The user message contains a "
    "JSON object as the input to the named capability. Reply with a JSON "
    "object that validates against the capability's output schema. Do not "
    "include any text outside the JSON object."
)


class LiteLLMAdapter:
    """Wrap a LiteLLM-callable model behind the rig :class:`Agent` protocol.

    For each declared capability, the adapter sends a chat-completion
    request to the configured model with the capability name as system
    metadata and the contract input as the user message. The response
    is parsed as JSON and signed.

    Cost is computed against the capability's cost model with the
    LiteLLM-reported token usage as the input-unit/output-unit values.
    """

    def __init__(
        self,
        *,
        card: AgentCard,
        keypair: KeyPair,
        model: str,
        system_prompt: str | None = None,
        extra_completion_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if keypair.did != card.agent_id:
            raise ValueError("keypair DID does not match card.agent_id")
        self._card = card
        self._keypair = keypair
        self._model = model
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self._extra = extra_completion_kwargs or {}
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
            return False
        return bool(self._card.has_capability(contract.capability))

    async def execute(self, contract: Contract) -> ExecuteResult:
        try:
            from litellm import acompletion  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ContractRejected(
                "LiteLLMAdapter requires the 'litellm' extra to be installed",
                contract_id=contract.contract_id,
            ) from exc

        capability = self._card.capability(contract.capability)
        user_message = json.dumps(
            {
                "capability": contract.capability,
                "input": contract.input,
                "output_schema": capability.output_schema,
            },
            separators=(",", ":"),
        )
        response = await acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            **self._extra,
        )
        try:
            text = response["choices"][0]["message"]["content"]
            output = json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ContractRejected(
                f"model did not return a parseable JSON object: {exc}",
                contract_id=contract.contract_id,
            ) from exc
        if not isinstance(output, dict):
            raise ContractRejected(
                "model output was JSON but not a JSON object",
                contract_id=contract.contract_id,
            )

        cost = self._cost_from_response(contract.capability, response)
        signature = sign_jws(canonicalize(output), key=self._keypair)
        return ExecuteResult(output=output, cost=cost, signature=signature)

    def _cost_from_response(self, capability_name: str, response: Any) -> Decimal:
        cap = self._card.capability(capability_name)
        cm = cap.cost_model
        base = Decimal(cm.base)
        usage = response.get("usage") if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            return base
        try:
            input_units = Decimal(str(usage.get("prompt_tokens", 0)))
            output_units = Decimal(str(usage.get("completion_tokens", 0)))
        except Exception:  # noqa: BLE001
            return base
        return base + Decimal(cm.per_input_unit) * input_units + Decimal(cm.per_output_unit) * output_units
