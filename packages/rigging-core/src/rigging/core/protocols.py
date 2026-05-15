"""Protocols and abstract base classes for rig participants.

These are the structural types that the runtime targets. A class is a
valid rig participant if it conforms to :class:`Agent`; a verifier is a
specialised :class:`Agent` whose :meth:`Agent.execute` returns a
:class:`VerifierVerdict` for one capability.

The :class:`Rig` class is *the* orchestrator. Phase 2 fixes its
signatures here; Phase 3 implements them in :mod:`rigging.runtime`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from rigging.core.agent_card import AgentCard
from rigging.core.contract import Contract
from rigging.core.identity import DID
from rigging.core.trace import TraceRecord


class VerifierVerdict(str, Enum):
    """The three valid verdicts a verifier may return."""

    ACCEPT = "accept"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class ExecuteResult:
    """The return value of :meth:`Agent.execute`.

    Adapters construct this; the runtime consumes it.

    Attributes:
        output: The capability output. Must validate against the
            capability's declared output schema.
        cost: The cost the rig should debit against the contract, in the
            contract's budget unit.
        signature: JWS Compact Serialization over the JCS-canonical
            output, signed by the callee's identity key.
        consumed_contract_ids: Optional list of sub-contract IDs whose
            outputs were *load-bearing* for this output. Used by the
            blame-chain extractor to prune speculative fan-out
            (``trace-v0.md`` §3.4). Adapters that fan out and use only
            a subset of results SHOULD populate this. When ``None`` the
            extractor conservatively assumes all sub-contracts are
            load-bearing.
    """

    output: dict[str, Any]
    cost: Decimal
    signature: str
    consumed_contract_ids: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """The return value of :meth:`Verifier.verify`."""

    verdict: VerifierVerdict
    reason: str | None
    signature: str
    """JWS over the (output_hash, verdict, reason) triple by the verifier."""


@runtime_checkable
class Agent(Protocol):
    """The structural type every rig participant must satisfy.

    An ``Agent`` is anything that has an identity (a signed agent card),
    can accept a contract for one of its declared capabilities, and can
    execute that contract under the rig's cost and verification rules.

    Implementations live under :mod:`rigging.adapters` (and in
    user code). The runtime sees only this protocol.
    """

    @property
    def did(self) -> DID:
        """The agent's stable DID."""
        ...

    @property
    def card(self) -> AgentCard:
        """The agent's currently-published signed card."""
        ...

    async def accept(self, contract: Contract) -> bool:
        """Decide whether to accept a proposed contract.

        Implementations MUST verify that the contract's ``callee_card_hash``
        matches their current card, that the capability exists, and that
        local policy permits the call.

        Args:
            contract: The proposed contract, fully signed by the caller.

        Returns:
            ``True`` if the contract is accepted; ``False`` to reject.
            On reject, the agent SHOULD raise a :class:`ContractRejected`
            with a reason code instead of returning ``False`` silently.
        """
        ...

    async def execute(self, contract: Contract) -> ExecuteResult:
        """Run the contract and produce a signed output.

        The runtime invokes this only on contracts the agent already
        accepted. Implementations must sign the output with the agent's
        identity key.

        Args:
            contract: The accepted contract.

        Returns:
            An :class:`ExecuteResult` containing the output, cost, and
            the agent's signature over the output.

        Raises:
            RigError: For any rig-level failure (budget overrun, schema
                mismatch, internal error).
        """
        ...


@runtime_checkable
class Verifier(Protocol):
    """An agent specialised for checking other agents' outputs.

    A verifier is just an :class:`Agent` whose declared capability ends
    in ``_verify`` or whose card lists ``verify`` in
    ``verifier_kinds``, plus the :meth:`verify` method below for
    convenience. The runtime can verify with anything that satisfies
    :class:`Agent`; this protocol exists so adapter authors writing
    verifiers have a sharper type.
    """

    @property
    def did(self) -> DID: ...

    async def verify(
        self,
        contract: Contract,
        output: dict[str, Any],
    ) -> VerificationResult:
        """Return a verdict on ``output`` for the given contract.

        Implementations MUST NOT modify ``output``. The verdict must be
        deterministic in the sense that the same (contract, output) pair
        produces the same verdict modulo verifier-internal randomness;
        non-deterministic verifiers MUST surface their decision in
        ``reason``.
        """
        ...


class Rig(Protocol):
    """The rig orchestrator.

    A rig holds a registry of participants' agent cards, mediates
    contract negotiation, enforces cost budgets, invokes verifiers, and
    produces traces. Implementations live in :mod:`rigging.runtime`.

    The protocol is described here so adapter and example code can be
    written against the surface without depending on the runtime
    package.
    """

    def register(self, agent: Agent) -> None:
        """Register an agent with the rig.

        After registration, the rig can route contracts to this agent.
        Re-registering the same DID replaces the card (and is the only
        way to update a card's contents in v0).
        """
        ...

    async def call(
        self,
        *,
        caller: Agent,
        callee_did: DID,
        capability: str,
        input: dict[str, Any],
        cost_budget: tuple[str, str],
        verifier: str | DID = "self",
        parent_contract: Contract | None = None,
    ) -> ExecuteResult:
        """Issue and execute a contract.

        This is the primary entrypoint for adapter and harness code.
        The rig:

        1. Constructs the contract.
        2. Has the caller sign it.
        3. Proposes it to the callee.
        4. On acceptance, executes it.
        5. Invokes the verifier on the output.
        6. Debits cost; updates trace.

        Args:
            caller: The :class:`Agent` issuing the contract.
            callee_did: DID of the callee.
            capability: Capability name from the callee's card.
            input: Input payload.
            cost_budget: ``(unit, max)`` tuple; ``max`` is a decimal
                string.
            verifier: ``"self"`` or a verifier DID.
            parent_contract: If this call is a sub-contract, the parent.

        Returns:
            The :class:`ExecuteResult` from the callee, after the
            verifier has accepted.

        Raises:
            RigError: For any rig-level failure.
        """
        ...

    def trace(self) -> TraceRecord:
        """Return the trace produced so far by this rig.

        Calling :meth:`trace` while a contract is in-flight returns a
        snapshot; subsequent calls may return a longer trace.
        """
        ...
