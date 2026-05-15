"""rigging-adapters — bridges from existing harnesses to the rig protocol.

Each adapter wraps an existing kind of agent (a Python function, a
LiteLLM-backed model, an MCP server) and exposes it as a
:class:`rigging.core.Agent`. The runtime sees only the protocol; the
adapter handles the translation.

The package's LOC budget is deliberately small (under 500 lines across
all three adapters). Adapters are not where complexity belongs; the
complexity belongs in the runtime.
"""

from __future__ import annotations

from rigging.adapters.litellm_adapter import LiteLLMAdapter
from rigging.adapters.local import (
    AsyncCapabilityFn,
    CapabilityFn,
    LocalPythonAdapter,
    SyncCapabilityFn,
)
from rigging.adapters.mcp_adapter import MCPAdapter
from rigging.adapters.vote import VoteEnsembleVerifier

__all__ = [
    "AsyncCapabilityFn",
    "CapabilityFn",
    "LiteLLMAdapter",
    "LocalPythonAdapter",
    "MCPAdapter",
    "SyncCapabilityFn",
    "VoteEnsembleVerifier",
]
