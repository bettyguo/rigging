"""Axis 1 — capability-advertisement fidelity.

For each probe in the suite, invoke the capability and check that:
(a) the output is JSON-shaped, (b) it matches the output schema's
``required`` fields, (c) the type-tag of each required field matches.

A real implementation would use a JSON Schema validator; we keep the
benchmark dependency-light and check the structural shape we care
about. The point of the axis is the *score shape*, not the validator's
sophistication.
"""

from __future__ import annotations

import anyio

from rigging.runtime import Rig

from benchmarks.rig_bench.harness import make_agent, usd_capability


_PROBES: list[dict[str, str]] = [
    {"text": "alpha"},
    {"text": "beta"},
    {"text": "gamma"},
    {"text": ""},
    {"text": "12345"},
]


def run(full: bool = False) -> dict[str, object]:
    probes = _PROBES * (3 if full else 1)
    return anyio.run(_run_axis, probes)


async def _run_axis(probes: list[dict[str, str]]) -> dict[str, object]:
    schema = {
        "type": "object",
        "properties": {"echoed": {"type": "string"}},
        "required": ["echoed"],
    }

    async def echo_honest(input: dict) -> dict:
        return {"echoed": input["text"]}

    async def echo_dishonest(input: dict) -> dict:
        # Returns a number, not the declared string.
        return {"echoed": 42}  # type: ignore[dict-item]

    rig = Rig(name="bench-fidelity")
    honest, honest_key = make_agent(
        operator="Honest Echo Co.",
        capabilities=[
            usd_capability(
                "echo",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                output_schema=schema,
            )
        ],
        handlers={"echo": echo_honest},
    )
    dishonest, dishonest_key = make_agent(
        operator="Liar Co.",
        capabilities=[
            usd_capability("echo", output_schema=schema)
        ],
        handlers={"echo": echo_dishonest},
    )
    caller, caller_key = make_agent(
        operator="Caller",
        capabilities=[usd_capability("ping")],
        handlers={"ping": lambda i: _yield({})},
    )
    rig.register(honest, keypair=honest_key)
    rig.register(dishonest, keypair=dishonest_key)
    rig.register(caller, keypair=caller_key)

    def conforms(payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        for field in schema["required"]:
            if field not in payload:
                return False
            expected = schema["properties"][field]["type"]
            if expected == "string" and not isinstance(payload[field], str):
                return False
        return True

    results: list[bool] = []
    for callee in (honest, dishonest):
        for probe in probes:
            try:
                exec_result = await rig.call(
                    caller=caller,
                    callee_did=callee.did,
                    capability="echo",
                    input=probe,
                    cost_budget=("usd", "0.10"),
                )
                results.append(conforms(exec_result.output))
            except Exception:  # noqa: BLE001 - any failure is non-conformance
                results.append(False)

    score = sum(1 for r in results if r) / len(results)
    return {
        "score": score,
        "passed": sum(results),
        "total": len(results),
        "notes": (
            "honest agent should score 1.0; dishonest agent should score 0.0; "
            "axis score is the average."
        ),
    }


async def _yield(value: dict) -> dict:
    return value
