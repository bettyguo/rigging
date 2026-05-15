"""rigging-runtime — the Rig orchestrator.

The runtime is the only place that holds the registry of agents,
mediates contract negotiation, enforces cost budgets, invokes
verifiers, and produces traces. It depends on ``rigging-core``,
``rigging-identity``, and ``rigging-trace``, but never on
``rigging-adapters``: adapters depend on the runtime's *protocol*
(``Agent``) only, never the other way around.

The public entry point is :class:`Rig`. Everything else in this package
is an implementation detail.
"""

from __future__ import annotations

from rigging.runtime.budget import CostLedger
from rigging.runtime.rig import Rig
from rigging.runtime.ulid import new_ulid

__all__ = ["CostLedger", "Rig", "new_ulid"]
