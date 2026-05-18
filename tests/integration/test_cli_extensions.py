"""CLI-level tests for the extended rig surface.

Covers ``rig card show``, ``rig contract show``, ``rig doctor``,
``rig examples``, and ``rig version``. Uses Typer's ``CliRunner`` so the
tests stay portable across operating systems.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from rigging.adapters import LocalPythonAdapter
from rigging.cli import app
from rigging.core import (
    AgentCard,
    Capability,
    CostModel,
    OperatorInfo,
)
from rigging.identity import KeyPair, sign_card
from rigging.runtime import Rig
from typer.testing import CliRunner

runner = CliRunner()


def _capability() -> Capability:
    return Capability(
        name="translate_pdf",
        description="Translate a PDF.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        cost_model=CostModel(
            unit="usd",
            base=Decimal("0.05"),
            per_input_unit=Decimal("0"),
            per_output_unit=Decimal("0"),
            input_unit="call",
            output_unit="call",
        ),
        verifier_kinds=["self"],
    )


def _card_for(kp: KeyPair) -> AgentCard:
    now = datetime.now(tz=UTC)
    raw = AgentCard(
        agent_id=kp.did,
        public_key=base64.b64encode(kp.public_bytes).decode("ascii"),
        operator=OperatorInfo(name="Test Operator"),
        capabilities=[_capability()],
        issued=now,
        expires=now + timedelta(hours=1),
    )
    return sign_card(raw, key=kp)


def test_doctor_runs_and_exits_zero() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "rig doctor" in result.output
    assert "all checks passed" in result.output


def test_examples_lists_six_built_ins() -> None:
    result = runner.invoke(app, ["examples"])
    assert result.exit_code == 0
    for name in (
        "01-two-agent-handoff",
        "02-three-vendor-rig",
        "03-adversarial-subagent",
        "04-cost-attribution",
        "05-vote-ensemble",
        "06-recursive-verification",
    ):
        assert name in result.output


def test_version_prints_something() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "rigging" in result.output


def test_card_show_pretty_prints(tmp_path: Path) -> None:
    kp = KeyPair.generate()
    card = _card_for(kp)
    target = tmp_path / "card.json"
    target.write_text(card.model_dump_json(indent=2), encoding="utf-8")

    result = runner.invoke(app, ["card", "show", str(target)])
    assert result.exit_code == 0
    assert "Test Operator" in result.output
    assert "translate_pdf" in result.output
    assert "signature" in result.output


def test_card_show_rejects_bad_signature(tmp_path: Path) -> None:
    kp = KeyPair.generate()
    card = _card_for(kp)
    target = tmp_path / "bad.json"
    raw = json.loads(card.model_dump_json())
    # Flip a bit in the signature — verification must fail.
    sig = raw["signature"]
    head, _, payload = sig.partition(".")
    raw["signature"] = head + ".tampered." + payload
    target.write_text(json.dumps(raw), encoding="utf-8")

    result = runner.invoke(app, ["card", "show", str(target)])
    assert result.exit_code != 0


async def _build_trace_with_contract(tmp_path: Path) -> Path:
    """Run a tiny rig, export the issued contract to disk, return path."""
    kp_a, kp_b = KeyPair.generate(), KeyPair.generate()
    card_a = _card_for(kp_a)
    card_b = _card_for(kp_b)
    a = LocalPythonAdapter(
        card=card_a, keypair=kp_a, handlers={"translate_pdf": lambda i: {"pages": 1}}
    )
    b = LocalPythonAdapter(
        card=card_b, keypair=kp_b, handlers={"translate_pdf": lambda i: {"pages": 2}}
    )
    rig = Rig(name="cli-test")
    rig.register(a, keypair=kp_a)
    rig.register(b, keypair=kp_b)
    await rig.call(
        caller=a,
        callee_did=b.did,
        capability="translate_pdf",
        input={"uri": "s3://x"},
        cost_budget=("usd", "0.50"),
    )
    contract = rig.last_contract_to(b.did, "translate_pdf")
    assert contract is not None
    target = tmp_path / "contract.json"
    target.write_text(contract.model_dump_json(indent=2), encoding="utf-8")
    return target


def test_contract_show_pretty_prints(tmp_path: Path, anyio_backend: str) -> None:
    import anyio

    del anyio_backend  # unused — async runner uses default backend
    target = anyio.run(_build_trace_with_contract, tmp_path)
    result = runner.invoke(app, ["contract", "show", str(target)])
    assert result.exit_code == 0
    assert "translate_pdf" in result.output
    assert "0.50" in result.output
    assert "did:rig:" in result.output


def test_run_unknown_example_exits_with_code_2() -> None:
    result = runner.invoke(app, ["run", "999-not-a-real-example"])
    assert result.exit_code == 2
    assert "unknown example" in result.output
