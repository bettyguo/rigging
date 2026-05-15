"""rigging-trace — span recording, blame extraction, and the inspect CLI.

The trace package has two responsibilities:

1. **Record.** Give the runtime a typed, in-process recorder
   (:class:`TraceRecorder`) that collects rig-level spans into
   :class:`SpanRecord` instances and snapshots them into a
   :class:`TraceRecord`.
2. **Extract.** Given a finished trace, compute the blame chain — the
   ordered DAG of contracts that produced the failing output.

OpenTelemetry export is optional and additive. When an OTel tracer is
provided, the recorder mirrors each rig span as an OTel span with
``rig.*`` attributes so that the same data flows to any OTel-compatible
backend.
"""

from __future__ import annotations

from rigging.trace.blame import (
    BlameExtractionError,
    extract_blame_chain,
)
from rigging.trace.otel import OtelBridge, install_otel_bridge
from rigging.trace.recorder import (
    SpanBuilder,
    TraceRecorder,
)

__all__ = [
    "BlameExtractionError",
    "OtelBridge",
    "SpanBuilder",
    "TraceRecorder",
    "extract_blame_chain",
    "install_otel_bridge",
]
