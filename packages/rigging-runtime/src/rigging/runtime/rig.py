"""The :class:`Rig` orchestrator — registers agents and routes contracts.

This is the only place that:

- holds the agent-card registry,
- constructs and signs contracts,
- mediates propose / accept / reject / void,
- invokes verifiers as sub-contracts (or noops when ``verifier="self"``),
- updates the cost ledger,
- builds the trace (with proper span hierarchy) and the blame chain.

The implementation is deliberately one file. Adapter authors and
example readers should be able to read it end-to-end and understand
exactly what the rig does and does not do.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import anyio
import structlog

from rigging.core.agent_card import AgentCard
from rigging.core.config import RigConfig
from rigging.core.contract import (
    Contract,
    CostBudget,
    ReasonCode,
    TrustPropagation,
)
from rigging.core.errors import (
    BudgetExhausted,
    BudgetOverrun,
    CalleeUnreachable,
    CapabilityMismatch,
    ContractExpired,
    ContractInvalid,
    ContractRejected,
    PolicyDenied,
    RecursionCapExceeded,
    RigError,
    SignatureInvalid,
    VerifierRejected,
    VerifierUnreachable,
)
from rigging.core.identity import DID, parse_did
from rigging.core.protocols import Agent, ExecuteResult
from rigging.core.trace import RigSpanKind, TraceRecord
from rigging.identity.cards import card_hash, sign_contract, verify_card
from rigging.identity.jcs import canonicalize
from rigging.identity.jws import JWSVerifyError, verify_jws
from rigging.identity.keys import KeyPair
from rigging.runtime.budget import CostLedger
from rigging.runtime.ulid import new_ulid
from rigging.trace.blame import extract_blame_chain
from rigging.trace.recorder import SpanBuilder, TraceRecorder

VERIFY_CAPABILITY = "verify"
"""The well-known capability name verifier agents declare on their cards.

Verifier-as-agent (ADR-0007) means a verifier is just an agent whose
card declares a ``verify`` capability; the runtime issues a sub-contract
against it.
"""

log = structlog.get_logger("rigging.runtime")


class Rig:
    """The rig orchestrator.

    A rig owns:

    - a *registry* of :class:`Agent` instances keyed by their DID,
    - a *keyring* of :class:`KeyPair` instances for agents whose
      caller-signing keys this rig holds,
    - a *trace recorder* that collects spans,
    - a *cost ledger* that enforces budget invariants,
    - a *config* (:class:`RigConfig`) holding policy knobs.

    The :meth:`call` method is the only entrypoint for issuing
    contracts.
    """

    def __init__(
        self,
        *,
        name: str = "rig",
        config: RigConfig | None = None,
    ) -> None:
        self._name = name
        self._config = config or RigConfig()
        self._agents: dict[DID, Agent] = {}
        self._keys: dict[DID, KeyPair] = {}
        self._recorder = TraceRecorder()
        self._ledger = CostLedger()
        self._contract_depth: dict[str, int] = {}
        self._verification_depth: dict[str, int] = {}
        self._contracts: dict[str, Contract] = {}

    # --- registration ---------------------------------------------------

    @property
    def config(self) -> RigConfig:
        return self._config

    def register(self, agent: Agent, *, keypair: KeyPair | None = None) -> None:
        """Register an agent. Verifies the card signature first."""
        verify_card(agent.card)
        self._agents[agent.did] = agent
        if keypair is not None:
            if keypair.did != agent.did:
                raise SignatureInvalid(
                    "keypair DID does not match agent DID",
                    details={"key_did": str(keypair.did), "agent_did": str(agent.did)},
                )
            self._keys[agent.did] = keypair
        log.info(
            "agent_registered",
            did=str(agent.did),
            caps=[c.name for c in agent.card.capabilities],
        )

    def agent(self, did: DID | str) -> Agent:
        """Look up a registered agent."""
        d = did if isinstance(did, DID) else parse_did(did)
        if d not in self._agents:
            raise CalleeUnreachable(
                f"no agent registered for {d}",
                details={"did": str(d)},
            )
        return self._agents[d]

    def keypair(self, did: DID) -> KeyPair:
        if did not in self._keys:
            raise PolicyDenied(
                f"no signing key held by this rig for {did}",
                details={"did": str(did)},
            )
        return self._keys[did]

    # --- the entrypoint -------------------------------------------------

    async def call(
        self,
        *,
        caller: Agent,
        callee_did: DID | str,
        capability: str,
        input: dict[str, Any],
        cost_budget: tuple[str, str | Decimal] | CostBudget,
        verifier: str | DID = "self",
        trust_propagation: TrustPropagation = "verified",
        parent_contract: Contract | None = None,
        parent_span: SpanBuilder | None = None,
    ) -> ExecuteResult:
        """Issue and execute a delegation contract.

        See ``docs/spec/rig-contract-v0.md`` for the full normative
        semantics. This method:

        1. Constructs and signs the contract.
        2. Proposes it to the callee.
        3. On acceptance, executes it under a cancel scope bounded by
           ``contract.expires``.
        4. Invokes the verifier sub-contract if ``verifier != "self"``.
        5. Verifies the verifier's signed verdict envelope.
        6. Debits cost; updates trace with proper parent-child span
           linkage.

        Raises:
            RigError: Any rig-level failure.
        """
        callee_did_obj = (
            callee_did if isinstance(callee_did, DID) else parse_did(callee_did)
        )
        callee_agent = self.agent(callee_did_obj)

        contract = self._build_contract(
            caller=caller,
            callee=callee_agent,
            capability=capability,
            input=input,
            cost_budget=_coerce_budget(cost_budget),
            verifier=str(verifier) if not isinstance(verifier, str) else verifier,
            trust_propagation=trust_propagation,
            parent_contract=parent_contract,
        )

        depth = self._compute_depth(parent_contract)
        if depth > self._config.max_contract_depth:
            raise RecursionCapExceeded(
                f"contract nesting depth {depth} exceeds "
                f"max_contract_depth={self._config.max_contract_depth}",
                contract_id=contract.contract_id,
            )
        self._contract_depth[contract.contract_id] = depth
        self._contracts[contract.contract_id] = contract

        try:
            self._ledger.register(contract)
        except BudgetExhausted as exc:
            self._record_terminal(
                contract,
                parent_span,
                RigSpanKind.CONTRACT_VOID,
                reason=exc.reason_code,
            )
            raise

        with self._recorder.span(
            RigSpanKind.CONTRACT_PROPOSE, parent=parent_span
        ) as propose:
            self._stamp_contract(propose, contract)

        try:
            accepted = await callee_agent.accept(contract)
        except ContractRejected as exc:
            self._record_terminal(
                contract,
                parent_span,
                RigSpanKind.CONTRACT_REJECT,
                reason=exc.reason_code,
            )
            raise
        if not accepted:
            self._record_terminal(
                contract,
                parent_span,
                RigSpanKind.CONTRACT_REJECT,
                reason=ReasonCode.POLICY_REJECTED.value,
            )
            raise ContractRejected(
                "callee rejected the contract without a reason code",
                contract_id=contract.contract_id,
            )

        with self._recorder.span(
            RigSpanKind.CONTRACT_ACCEPT, parent=parent_span
        ) as accept:
            self._stamp_contract(accept, contract)

        result = await self._execute_with_span(
            contract, callee_agent, parent_span=parent_span,
        )

        if contract.verifier != "self":
            await self._run_verifier(contract, result, parent_span=parent_span)

        return result

    # --- inspection / export --------------------------------------------

    def contract(self, contract_id: str) -> Contract:
        """Look up a previously-issued contract by ID."""
        if contract_id not in self._contracts:
            raise ContractInvalid(
                f"no contract issued with id {contract_id!r}",
                contract_id=contract_id,
            )
        return self._contracts[contract_id]

    def issued_contracts(self) -> list[Contract]:
        """Return contracts in issue order (chronological by ULID prefix)."""
        return sorted(self._contracts.values(), key=lambda c: c.contract_id)

    def last_contract_to(
        self,
        callee: DID,
        capability: str | None = None,
    ) -> Contract | None:
        """Return the most recently issued contract to ``callee`` (and
        optionally for ``capability``), or ``None``."""
        matches = [
            c
            for c in self._contracts.values()
            if c.callee == callee and (capability is None or c.capability == capability)
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda c: c.contract_id)[-1]

    def trace(self) -> TraceRecord:
        """Snapshot the trace, with blame chain computed if applicable."""
        record = self._recorder.snapshot()
        chain = extract_blame_chain(record)
        if chain is None:
            return record
        return record.model_copy(update={"blame_chain": chain})

    def finish(self) -> TraceRecord:
        """Close the trace and return the final :class:`TraceRecord`."""
        self._recorder.finish()
        return self.trace()

    def export_trace(self, path: str | Path) -> Path:
        """Write the current trace to ``path`` as JSON. Returns the path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.trace().model_dump_json(indent=2), encoding="utf-8")
        return target

    @staticmethod
    def import_trace(path: str | Path) -> TraceRecord:
        """Load a previously-exported trace from disk."""
        return TraceRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))

    # --- internals ------------------------------------------------------

    def _build_contract(
        self,
        *,
        caller: Agent,
        callee: Agent,
        capability: str,
        input: dict[str, Any],
        cost_budget: CostBudget,
        verifier: str,
        trust_propagation: TrustPropagation,
        parent_contract: Contract | None,
    ) -> Contract:
        if callee.did not in self._agents:
            raise CalleeUnreachable(
                f"callee {callee.did} is not registered with this rig"
            )
        if not callee.card.has_capability(capability):
            raise CapabilityMismatch(
                f"callee does not declare capability {capability!r}"
            )
        cap = callee.card.capability(capability)
        if cap.cost_model.unit != cost_budget.unit:
            raise CapabilityMismatch(
                "contract budget unit does not match capability cost-model unit",
                details={
                    "capability_unit": cap.cost_model.unit,
                    "budget_unit": cost_budget.unit,
                },
            )
        if cost_budget.max < cap.cost_model.base:
            raise ContractInvalid(
                "budget is below the capability's base cost",
                details={
                    "base": str(cap.cost_model.base),
                    "max": str(cost_budget.max),
                },
            )
        now = datetime.now(tz=UTC)
        draft = Contract(
            contract_id=new_ulid(int(now.timestamp() * 1000)),
            parent_id=parent_contract.contract_id if parent_contract else None,
            caller=caller.did,
            callee=callee.did,
            callee_card_hash=card_hash(callee.card),
            capability=capability,
            input=input,
            cost_budget=cost_budget,
            verifier=verifier,
            trust_propagation=trust_propagation,
            issued=now,
            expires=now + self._config.default_contract_lifetime,
        )
        signed = sign_contract(draft, key=self.keypair(caller.did))
        return signed

    def _compute_depth(self, parent: Contract | None) -> int:
        if parent is None:
            return 1
        return self._contract_depth.get(parent.contract_id, 0) + 1

    def _stamp_contract(self, span: SpanBuilder, contract: Contract) -> None:
        span.set_contract(
            contract_id=contract.contract_id,
            parent_contract_id=contract.parent_id,
            caller=contract.caller,
            callee=contract.callee,
            capability=contract.capability,
        )

    async def _execute_with_span(
        self,
        contract: Contract,
        callee: Agent,
        *,
        parent_span: SpanBuilder | None,
    ) -> ExecuteResult:
        # Pre-flight: contract already past its deadline?
        now = datetime.now(tz=UTC)
        if now >= contract.expires:
            self._record_terminal(
                contract,
                parent_span,
                RigSpanKind.CONTRACT_VOID,
                reason=ReasonCode.EXPIRED.value,
            )
            raise ContractExpired(
                "contract expired before execute",
                contract_id=contract.contract_id,
                details={"expires": contract.expires.isoformat()},
            )
        timeout_seconds = (contract.expires - now).total_seconds()
        input_hash = (
            f"sha256:{hashlib.sha256(canonicalize(contract.input)).hexdigest()}"
        )

        with self._recorder.span(
            RigSpanKind.EXECUTE, parent=parent_span
        ) as exec_span:
            self._stamp_contract(exec_span, contract)
            exec_span.set_hashes(input_hash=input_hash, output_hash=None)

            result: ExecuteResult | None = None
            if self._config.enforce_execute_timeout:
                with anyio.move_on_after(timeout_seconds) as scope:
                    result = await self._run_callee(callee, contract, exec_span)
                if scope.cancelled_caught:
                    exec_span.set_reason(ReasonCode.EXPIRED.value)
                    # Emit an additional void span as a sibling marker so
                    # tooling that filters by kind sees the termination.
                    self._record_terminal(
                        contract,
                        parent_span,
                        RigSpanKind.CONTRACT_VOID,
                        reason=ReasonCode.EXPIRED.value,
                    )
                    raise ContractExpired(
                        "contract expired during execute",
                        contract_id=contract.contract_id,
                    )
            else:
                result = await self._run_callee(callee, contract, exec_span)

            assert result is not None  # mypy-only; either branch sets it
            output_hash = (
                f"sha256:{hashlib.sha256(canonicalize(result.output)).hexdigest()}"
            )
            exec_span.set_hashes(input_hash=input_hash, output_hash=output_hash)
            exec_span.set_envelope(result.signature)
            if result.consumed_contract_ids is not None:
                exec_span.set_consumed(list(result.consumed_contract_ids))

            # Debit cost; raises BudgetOverrun on excess. Promotes to void.
            try:
                self._ledger.debit(contract.contract_id, result.cost)
            except BudgetOverrun as exc:
                exec_span.set_reason(exc.reason_code)
                self._record_terminal(
                    contract,
                    parent_span,
                    RigSpanKind.CONTRACT_VOID,
                    reason=exc.reason_code,
                )
                raise
            exec_span.set_cost(
                result.cost,
                unit=contract.cost_budget.unit,
                budget_max=contract.cost_budget.max,
            )

        # Cost-debit marker span at the parent level (tooling-friendly).
        with self._recorder.span(
            RigSpanKind.COST_DEBIT, parent=parent_span
        ) as debit_span:
            self._stamp_contract(debit_span, contract)
            debit_span.set_cost(
                result.cost,
                unit=contract.cost_budget.unit,
                budget_max=contract.cost_budget.max,
            )
        return result

    async def _run_callee(
        self,
        callee: Agent,
        contract: Contract,
        exec_span: SpanBuilder,
    ) -> ExecuteResult:
        try:
            return await callee.execute(contract)
        except RigError as exc:
            exec_span.set_reason(exc.reason_code)
            raise

    async def _run_verifier(
        self,
        contract: Contract,
        result: ExecuteResult,
        *,
        parent_span: SpanBuilder | None,
    ) -> None:
        verifier_did = parse_did(contract.verifier)
        try:
            verifier_agent = self.agent(verifier_did)
        except CalleeUnreachable as exc:
            self._record_terminal(
                contract,
                parent_span,
                RigSpanKind.CONTRACT_VOID,
                reason=ReasonCode.VERIFIER_UNREACHABLE.value,
            )
            raise VerifierUnreachable(
                f"verifier {verifier_did} is not registered",
                contract_id=contract.contract_id,
            ) from exc

        if not verifier_agent.card.has_capability(VERIFY_CAPABILITY):
            raise PolicyDenied(
                f"verifier {verifier_did} does not declare 'verify' capability",
                contract_id=contract.contract_id,
            )

        # Recursion-cap accounting against the parent contract's chain.
        v_depth = self._verification_depth.get(contract.contract_id, 0) + 1
        if v_depth > self._config.verification_recursion_cap:
            raise RecursionCapExceeded(
                f"verification recursion {v_depth} exceeds "
                f"verification_recursion_cap={self._config.verification_recursion_cap}",
                contract_id=contract.contract_id,
            )

        verify_cap = verifier_agent.card.capability(VERIFY_CAPABILITY)
        sub_budget = CostBudget(
            unit=verify_cap.cost_model.unit,
            max=Decimal(verify_cap.cost_model.base),
        )
        verifier_input = {
            "verified_contract_id": contract.contract_id,
            "verified_capability": contract.capability,
            "callee_did": str(contract.callee),
            "output": result.output,
            "output_signature": result.signature,
        }
        with self._recorder.span(
            RigSpanKind.VERIFY, parent=parent_span
        ) as verify_span:
            self._stamp_contract(verify_span, contract)
            verify_span.set_verifier(
                agent_id=str(verifier_did), verdict=None, reason=None,
            )
            self._verification_depth[contract.contract_id] = v_depth
            verdict_result = await self.call(
                caller=self._agents[contract.caller],
                callee_did=verifier_did,
                capability=VERIFY_CAPABILITY,
                input=verifier_input,
                cost_budget=sub_budget,
                verifier="self",
                trust_propagation="sealed",
                parent_contract=contract,
                parent_span=verify_span,
            )

            # Verify the verifier's signed envelope before trusting the verdict.
            self._check_envelope(
                verifier_agent.card,
                verdict_result.output,
                verdict_result.signature,
                contract_id=contract.contract_id,
            )

            verdict = verdict_result.output.get("verdict", "abstain")
            reason = verdict_result.output.get("reason")
            verify_span.set_verifier(
                agent_id=str(verifier_did),
                verdict=verdict,
                reason=reason,
            )
            verify_span.set_envelope(verdict_result.signature)
            if verdict == "reject":
                verify_span.set_reason(ReasonCode.VERIFIER_REJECTED.value)
                raise VerifierRejected(
                    f"verifier {verifier_did} rejected output: {reason}",
                    contract_id=contract.contract_id,
                    details={"reason": reason},
                )

    def _check_envelope(
        self,
        signer_card: AgentCard,
        payload: dict[str, Any],
        jws: str,
        *,
        contract_id: str,
    ) -> None:
        """Verify a JWS envelope over ``payload`` against ``signer_card``.

        Raises :class:`SignatureInvalid` on any mismatch.
        """
        if not jws:
            raise SignatureInvalid(
                "missing signature envelope",
                contract_id=contract_id,
            )
        try:
            pubkey_bytes = base64.b64decode(signer_card.public_key, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise SignatureInvalid(
                "signer card has malformed public_key",
                contract_id=contract_id,
            ) from exc
        try:
            signed_payload = verify_jws(jws, public_key_bytes=pubkey_bytes)
        except JWSVerifyError as exc:
            raise SignatureInvalid(
                f"envelope JWS did not verify: {exc}",
                contract_id=contract_id,
            ) from exc
        canonical = canonicalize(payload)
        if signed_payload != canonical:
            raise SignatureInvalid(
                "envelope payload does not match canonicalised output",
                contract_id=contract_id,
            )

    def _record_terminal(
        self,
        contract: Contract,
        parent_span: SpanBuilder | None,
        kind: RigSpanKind,
        *,
        reason: str,
    ) -> None:
        with self._recorder.span(kind, parent=parent_span) as span:
            self._stamp_contract(span, contract)
            span.set_reason(reason)


def _coerce_budget(value: tuple[str, str | Decimal] | CostBudget) -> CostBudget:
    if isinstance(value, CostBudget):
        return value
    unit, amount = value
    return CostBudget(unit=unit, max=Decimal(str(amount)))
