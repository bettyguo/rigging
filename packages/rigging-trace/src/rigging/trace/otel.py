"""Optional OpenTelemetry bridge.

The rig is fully usable without OpenTelemetry; the in-process recorder
is the authoritative source for blame extraction. The bridge exists so
that rig spans can be mirrored to an OTel-compatible backend (Jaeger,
Tempo, Honeycomb, etc.) for human consumption.

Usage::

    from opentelemetry import trace
    from rigging.trace import install_otel_bridge

    bridge = install_otel_bridge(recorder, trace.get_tracer("rigging"))

After installation, every span the recorder commits also surfaces as an
OTel span with ``rig.*`` attributes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from rigging.core.trace import SpanRecord

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from opentelemetry.trace import Tracer

    from rigging.trace.recorder import TraceRecorder


class OtelBridge:
    """A trace recorder listener that mirrors spans to OpenTelemetry."""

    def __init__(self, tracer: "Tracer") -> None:
        self._tracer = tracer

    def __call__(self, span: SpanRecord) -> None:  # noqa: D401 - listener API
        with self._tracer.start_as_current_span(span.kind.value) as otel_span:
            for key, value in _attributes(span).items():
                otel_span.set_attribute(key, value)


def install_otel_bridge(recorder: "TraceRecorder", tracer: "Tracer") -> OtelBridge:
    """Attach an :class:`OtelBridge` to ``recorder`` and return it.

    The bridge is also registered as a listener; the caller does not
    need to retain the return value unless they want to remove it
    later.
    """
    bridge = OtelBridge(tracer)
    recorder.add_listener(bridge)
    return bridge


def _attributes(span: SpanRecord) -> dict[str, Any]:
    """Convert a :class:`SpanRecord` into OTel-friendly attribute pairs."""
    attrs: dict[str, Any] = {}

    def maybe(key: str, value: Any) -> None:
        if value is None:
            return
        attrs[key] = str(value) if not isinstance(value, (bool, int, float, str)) else value

    maybe("rig.contract.id", span.contract_id)
    maybe("rig.contract.parent_id", span.parent_contract_id)
    maybe("rig.caller.agent_id", str(span.caller) if span.caller else None)
    maybe("rig.callee.agent_id", str(span.callee) if span.callee else None)
    maybe("rig.capability", span.capability)
    maybe("rig.cost.unit", span.cost_unit)
    maybe("rig.cost.value", str(span.cost_value) if span.cost_value is not None else None)
    maybe(
        "rig.cost.budget_max",
        str(span.cost_budget_max) if span.cost_budget_max is not None else None,
    )
    maybe("rig.verifier.agent_id", span.verifier)
    maybe("rig.verifier.verdict", span.verifier_verdict)
    maybe("rig.verifier.reason", span.verifier_reason)
    maybe("rig.signature.envelope", span.signature_envelope)
    maybe("rig.reason_code", span.reason_code)
    maybe("rig.input.hash", span.input_hash)
    maybe("rig.output.hash", span.output_hash)
    if span.blame_chain is not None:
        attrs["rig.blame.chain"] = json.dumps(span.blame_chain)
    if span.consumed_contract_ids is not None:
        attrs["rig.consumed.contract_ids"] = json.dumps(span.consumed_contract_ids)
    return attrs
