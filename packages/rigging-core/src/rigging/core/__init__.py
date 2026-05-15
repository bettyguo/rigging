"""rigging-core — the bedrock types and protocols of a rig.

This package owns the schemas (agent cards, delegation contracts, traces),
the abstract protocols (`Agent`, `Verifier`, `Rig`), and the error
hierarchy. It contains no I/O, no network code, no LLM-specific logic.

The runtime, identity, trace, and adapter packages all depend on this
one. It depends on nothing rig-specific.
"""

from __future__ import annotations

from rigging.core.agent_card import (
    AgentCard,
    Capability,
    CostModel,
    OperatorInfo,
    TrustAssertion,
)
from rigging.core.config import RigConfig
from rigging.core.contract import (
    Contract,
    ContractState,
    CostBudget,
    ReasonCode,
    TrustPropagation,
)
from rigging.core.errors import (
    BlameAttributionError,
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
from rigging.core.identity import (
    DID,
    DIDParseError,
    derive_did,
    parse_did,
)
from rigging.core.protocols import (
    Agent,
    Rig,
    Verifier,
    VerifierVerdict,
)
from rigging.core.trace import (
    BlameChain,
    RigSpanKind,
    SpanRecord,
    TraceRecord,
)

__all__ = [
    "DID",
    "Agent",
    "AgentCard",
    "BlameAttributionError",
    "BlameChain",
    "BudgetExhausted",
    "BudgetOverrun",
    "CalleeUnreachable",
    "Capability",
    "CapabilityMismatch",
    "Contract",
    "ContractExpired",
    "ContractInvalid",
    "ContractRejected",
    "ContractState",
    "CostBudget",
    "CostModel",
    "DIDParseError",
    "OperatorInfo",
    "PolicyDenied",
    "ReasonCode",
    "RecursionCapExceeded",
    "Rig",
    "RigConfig",
    "RigError",
    "RigSpanKind",
    "SignatureInvalid",
    "SpanRecord",
    "TraceRecord",
    "TrustAssertion",
    "TrustPropagation",
    "Verifier",
    "VerifierRejected",
    "VerifierUnreachable",
    "VerifierVerdict",
    "derive_did",
    "parse_did",
]
