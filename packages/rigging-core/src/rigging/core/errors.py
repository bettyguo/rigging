"""The rig error hierarchy.

Every failure that can be diagnosed at the rig layer is one of these.
Adapters and callers catch `RigError` (or a specific subclass) and
translate as needed; the rig itself raises *only* these types.
"""

from __future__ import annotations

from typing import Self


class RigError(Exception):
    """Root of the rig-error hierarchy.

    Every rig-originating failure is a subclass of this. Catching
    ``RigError`` is the right way for a caller to handle "anything the
    rig might raise"; catching the more specific subclasses is the right
    way to implement retry/fallback policy.
    """

    reason_code: str = "rig_error"

    def __init__(
        self,
        message: str,
        *,
        contract_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.contract_id = contract_id
        self.details = details or {}

    def __reduce__(self) -> tuple[type[Self], tuple[str], dict[str, object]]:
        return (
            type(self),
            (self.message,),
            {"contract_id": self.contract_id, "details": self.details},
        )


# --- contract validity ----------------------------------------------------


class ContractInvalid(RigError):
    """The contract failed validation before negotiation began.

    Examples: schema mismatch, signature didn't verify, expiry in the
    past, capability not declared on the callee's card.
    """

    reason_code = "contract_invalid"


class SignatureInvalid(ContractInvalid):
    """A required signature (caller, callee, verifier) failed to verify."""

    reason_code = "signature_invalid"


class CapabilityMismatch(ContractInvalid):
    """The contract's capability/input did not match the callee's card."""

    reason_code = "capability_mismatch"


class RecursionCapExceeded(ContractInvalid):
    """Verification chain would exceed the v0 recursion cap of 3."""

    reason_code = "recursion_cap_exceeded"


# --- contract execution ---------------------------------------------------


class ContractRejected(RigError):
    """The callee or verifier rejected the contract.

    Carries the reason code from ``rig-contract-v0.md`` §6 so callers can
    branch on it.
    """

    reason_code = "rejected"


class VerifierRejected(ContractRejected):
    """The verifier returned a ``reject`` verdict on the callee's output."""

    reason_code = "verifier_rejected"


class PolicyDenied(ContractRejected):
    """A local policy refused to issue or accept the contract."""

    reason_code = "policy_rejected"


# --- runtime / liveness ---------------------------------------------------


class CalleeUnreachable(RigError):
    """The callee could not be contacted; contract is voided."""

    reason_code = "callee_unreachable"


class VerifierUnreachable(RigError):
    """The verifier could not be contacted; contract is voided."""

    reason_code = "verifier_unreachable"


class ContractExpired(RigError):
    """The contract reached its ``expires`` deadline before completing.

    Raised both at execute-entry (already past expiry) and on
    deadline-induced cancellation during execute. The contract is
    voided with ``reason_code=expired``.
    """

    reason_code = "expired"


# --- budgets --------------------------------------------------------------


class BudgetOverrun(RigError):
    """Execution exceeded the contract's cost budget."""

    reason_code = "budget_overrun"


class BudgetExhausted(RigError):
    """A sub-contract budget exceeds the parent's remaining budget.

    Distinct from ``BudgetOverrun``: this fires at issuance, before any
    cost is incurred. ``BudgetOverrun`` fires during execution.
    """

    reason_code = "parent_budget_exhausted"


# --- trace / blame --------------------------------------------------------


class BlameAttributionError(RigError):
    """The blame-chain extractor could not produce a valid chain.

    A trace that produces this is a bug in either the rig or in an
    adapter that emitted malformed spans. The caller should preserve the
    trace and file an issue.
    """

    reason_code = "blame_attribution_failed"
