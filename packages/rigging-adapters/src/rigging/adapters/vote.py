"""VoteEnsembleVerifier — a verifier that delegates to N child verifiers.

This is the canonical example of *composition without runtime
feature*. The vote ensemble is itself a normal :class:`rigging.core.Agent`
that declares a ``verify`` capability; when invoked, it issues N
sub-contracts to its constituent verifiers and reports the majority
verdict back to its caller.

Nothing in :mod:`rigging.runtime` needed to change to support this.
The runtime sees a verifier; the verifier happens to be a coordinator;
the coordinator's children happen to be other verifiers. The rig's
invariants apply uniformly all the way down.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from rigging.core.agent_card import AgentCard
from rigging.core.contract import Contract, CostBudget
from rigging.core.errors import ContractRejected
from rigging.core.identity import DID
from rigging.core.protocols import Agent, ExecuteResult
from rigging.identity.cards import card_hash
from rigging.identity.jcs import canonicalize
from rigging.identity.jws import sign_jws
from rigging.identity.keys import KeyPair

_VERDICTS = ("accept", "reject", "abstain")


class VoteEnsembleVerifier:
    """A verifier whose ``verify`` capability runs a majority vote.

    The constructor takes a :class:`Rig` reference (so the ensemble can
    issue sub-contracts to its constituents) plus a list of DIDs of
    other verifier agents. When :meth:`execute` is invoked, the
    ensemble:

    1. Issues a ``verify`` sub-contract to each constituent.
    2. Collects ``ExecuteResult`` outputs.
    3. Tallies verdicts. A simple majority of non-``abstain`` verdicts
       wins; ties default to ``abstain``.
    4. Returns an output of shape ``{"verdict": ..., "reason": ...,
       "votes": [{"verifier": <did>, "verdict": ..., "reason": ...}, ...]}``.

    The ensemble's own card must declare a ``verify`` capability whose
    output schema includes the ``verdict`` and ``votes`` fields.
    """

    def __init__(
        self,
        *,
        card: AgentCard,
        keypair: KeyPair,
        rig: "RigLike",
        constituents: Sequence[DID],
    ) -> None:
        if keypair.did != card.agent_id:
            raise ValueError("keypair DID does not match card.agent_id")
        if not constituents:
            raise ValueError("vote ensemble must have at least one constituent")
        self._card = card
        self._keypair = keypair
        self._rig = rig
        self._constituents = list(constituents)
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
        return contract.capability == "verify"

    async def execute(self, contract: Contract) -> ExecuteResult:
        votes: list[dict[str, Any]] = []
        consumed: list[str] = []
        verify_cap = self._card.capability("verify")
        sub_unit = verify_cap.cost_model.unit

        for constituent_did in self._constituents:
            # Honour each constituent's declared cost; the coordinator
            # carries the *sum* of those as its own base cost.
            constituent_agent = self._rig.agent(constituent_did)
            constituent_cap = constituent_agent.card.capability("verify")
            sub_budget = CostBudget(
                unit=sub_unit,
                max=Decimal(constituent_cap.cost_model.base),
            )
            try:
                result = await self._rig.call(
                    caller=self,
                    callee_did=constituent_did,
                    capability="verify",
                    input=dict(contract.input),
                    cost_budget=sub_budget,
                    verifier="self",
                    trust_propagation="sealed",
                    parent_contract=contract,
                )
            except ContractRejected as exc:
                votes.append(
                    {
                        "verifier": str(constituent_did),
                        "verdict": "abstain",
                        "reason": f"sub-contract failed: {exc.message}",
                    }
                )
                continue
            votes.append(
                {
                    "verifier": str(constituent_did),
                    "verdict": result.output.get("verdict", "abstain"),
                    "reason": result.output.get("reason"),
                }
            )
            consumed.append(_extract_contract_id(result))

        verdict, reason = _tally(votes)
        output: dict[str, Any] = {
            "verdict": verdict,
            "reason": reason,
            "votes": votes,
        }
        signature = sign_jws(canonicalize(output), key=self._keypair)
        return ExecuteResult(
            output=output,
            cost=Decimal(verify_cap.cost_model.base),
            signature=signature,
            consumed_contract_ids=tuple(consumed) if consumed else None,
        )


def _tally(votes: list[dict[str, Any]]) -> tuple[str, str]:
    counter: Counter[str] = Counter()
    for v in votes:
        verdict = v.get("verdict", "abstain")
        if verdict in _VERDICTS:
            counter[verdict] += 1
    accept = counter.get("accept", 0)
    reject = counter.get("reject", 0)
    if accept > reject:
        return "accept", f"majority accept ({accept}/{len(votes)})"
    if reject > accept:
        return "reject", f"majority reject ({reject}/{len(votes)})"
    return "abstain", f"tied vote ({accept} accept / {reject} reject)"


def _extract_contract_id(result: ExecuteResult) -> str:
    """Best-effort extraction of the sub-contract id from a result.

    The v0 ``ExecuteResult`` doesn't carry the contract id directly;
    callers wanting to mark consumed_contract_ids precisely need to
    record them at issue-time. For the vote ensemble we don't
    currently surface this through the rig API, so we return the empty
    string and rely on the runtime's over-approximation default.
    """
    del result
    return ""


from typing import Protocol


class RigLike(Protocol):  # pragma: no cover - structural type only
    """Minimal protocol of the methods the vote ensemble calls on a Rig.

    Declared here to avoid a circular import on :mod:`rigging.runtime`.
    """

    def agent(self, did: DID) -> Agent: ...

    async def call(  # noqa: D401 - matches Rig.call exactly
        self,
        *,
        caller: Agent,
        callee_did: DID,
        capability: str,
        input: dict[str, Any],
        cost_budget: CostBudget,
        verifier: str | DID,
        trust_propagation: str,
        parent_contract: Contract | None,
    ) -> ExecuteResult: ...
