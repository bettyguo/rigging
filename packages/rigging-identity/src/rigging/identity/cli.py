"""``rig identity ...`` subcommands.

Three operations, all small:

- ``rig identity create`` — generate a keypair, save it encrypted, print the DID.
- ``rig identity show <key-file>`` — print the DID stored on disk.
- ``rig identity verify <card-file>`` — verify a card's JWS.

The CLI is glue. The interesting work is in :mod:`rigging.identity.cards`
and :mod:`rigging.identity.keys`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint

from rigging.core.agent_card import AgentCard
from rigging.core.errors import SignatureInvalid
from rigging.identity.cards import verify_card
from rigging.identity.keys import KeyPair, KeyStorageError

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Manage rig identities.")


def _resolve_passphrase(env_var: str | None) -> bytes:
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value is None:
            raise typer.BadParameter(f"environment variable {env_var!r} is not set")
        return env_value.encode("utf-8")
    prompted: str = str(
        typer.prompt("Passphrase", hide_input=True, confirmation_prompt=False)
    )
    if not prompted:
        raise typer.BadParameter("passphrase must be non-empty")
    return prompted.encode("utf-8")


@app.command("create")
def create(
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Path to write the encrypted PEM key."),
    ] = Path("rig.key"),
    passphrase_env: Annotated[
        str | None,
        typer.Option("--passphrase-env", help="Env var to read the passphrase from."),
    ] = None,
) -> None:
    """Generate a new rig identity and write it encrypted to disk."""
    passphrase = _resolve_passphrase(passphrase_env)
    keypair = KeyPair.generate()
    keypair.save_encrypted(out, passphrase=passphrase)
    sidecar = out.with_suffix(out.suffix + ".did")
    sidecar.write_text(str(keypair.did) + "\n", encoding="utf-8")
    rprint(f"[green]created[/green] {keypair.did}")
    rprint(f"  key file: [bold]{out}[/bold]")
    rprint(f"  did file: [bold]{sidecar}[/bold]")


@app.command("show")
def show(
    key_file: Annotated[Path, typer.Argument(help="Encrypted PEM key path.")],
    passphrase_env: Annotated[
        str | None,
        typer.Option("--passphrase-env", help="Env var to read the passphrase from."),
    ] = None,
) -> None:
    """Print the DID associated with an on-disk key file."""
    passphrase = _resolve_passphrase(passphrase_env)
    try:
        keypair = KeyPair.load_encrypted(key_file, passphrase=passphrase)
    except KeyStorageError as exc:
        rprint(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    rprint(str(keypair.did))


@app.command("verify")
def verify(
    card_file: Annotated[Path, typer.Argument(help="JSON file containing an agent card.")],
) -> None:
    """Verify the JWS on an agent card stored as JSON."""
    try:
        payload = json.loads(card_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        rprint(f"[red]error reading card:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    try:
        card = AgentCard.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - present pydantic errors plainly
        rprint(f"[red]card failed structural validation:[/red] {exc}")
        raise typer.Exit(code=3) from exc
    try:
        verify_card(card)
    except SignatureInvalid as exc:
        rprint(f"[red]signature invalid:[/red] {exc.message}")
        raise typer.Exit(code=4) from exc
    rprint(f"[green]ok[/green] {card.agent_id}  ({len(card.capabilities)} capabilities)")
