"""Ed25519 keypairs — generation, encrypted storage, in-memory handling.

The keypair is the cryptographic anchor of every rig identity. The
private key MUST be stored encrypted at rest; this module's
``KeyPair.save_encrypted`` enforces that. Operators wanting HSM-backed
signing implement the smaller :class:`Signer` protocol in v1; v0 ships
software keys only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from rigging.core.identity import DID, derive_did


class KeyStorageError(RuntimeError):
    """Raised when an on-disk key cannot be loaded or stored safely."""


@dataclass(frozen=True, slots=True)
class KeyPair:
    """An Ed25519 keypair with a derived rig DID.

    Construct via :meth:`generate` for new identities or
    :meth:`load_encrypted` for existing ones. Keep the private object
    out of logs and serialised state.
    """

    private: ed25519.Ed25519PrivateKey
    public: ed25519.Ed25519PublicKey
    did: DID

    # --- constructors -----------------------------------------------------

    @classmethod
    def generate(cls) -> "KeyPair":
        """Generate a new keypair from the OS entropy pool."""
        priv = ed25519.Ed25519PrivateKey.generate()
        pub = priv.public_key()
        return cls(private=priv, public=pub, did=derive_did(cls._public_bytes(pub)))

    @classmethod
    def from_private_bytes(cls, raw: bytes) -> "KeyPair":
        """Reconstruct a keypair from 32 raw bytes of private key."""
        priv = ed25519.Ed25519PrivateKey.from_private_bytes(raw)
        pub = priv.public_key()
        return cls(private=priv, public=pub, did=derive_did(cls._public_bytes(pub)))

    @classmethod
    def load_encrypted(cls, path: str | os.PathLike[str], *, passphrase: bytes) -> "KeyPair":
        """Load an encrypted PEM keypair from disk.

        Args:
            path: Path to a PEM file produced by :meth:`save_encrypted`.
            passphrase: The bytes used to encrypt the file.

        Raises:
            KeyStorageError: If the file is missing, malformed, or the
                passphrase is wrong.
        """
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            raise KeyStorageError(f"cannot read key at {path}: {exc}") from exc
        try:
            obj = serialization.load_pem_private_key(data, password=passphrase)
        except (ValueError, TypeError) as exc:
            raise KeyStorageError("key file could not be decrypted") from exc
        if not isinstance(obj, ed25519.Ed25519PrivateKey):
            raise KeyStorageError("key file is not Ed25519")
        pub = obj.public_key()
        return cls(private=obj, public=pub, did=derive_did(cls._public_bytes(pub)))

    # --- public surface ---------------------------------------------------

    @property
    def public_bytes(self) -> bytes:
        """Raw 32-byte public key."""
        return self._public_bytes(self.public)

    def sign(self, message: bytes) -> bytes:
        """Sign ``message`` with the private key. Returns 64 raw bytes."""
        return self.private.sign(message)

    def verify(self, signature: bytes, message: bytes) -> bool:
        """Verify ``signature`` over ``message`` with this keypair's public key."""
        return verify_signature(self.public_bytes, signature, message)

    def save_encrypted(
        self,
        path: str | os.PathLike[str],
        *,
        passphrase: bytes,
    ) -> None:
        """Write the private key to ``path`` encrypted under ``passphrase``.

        The encryption is ``BestAvailableEncryption`` from the
        ``cryptography`` library — currently PBES2/PBKDF2 with AES-256.

        Args:
            path: Destination path; will be overwritten if it exists.
            passphrase: Non-empty bytes used to derive the file's
                encryption key.

        Raises:
            KeyStorageError: For an empty passphrase or an I/O failure.
        """
        if not passphrase:
            raise KeyStorageError("refusing to write a private key without a passphrase")
        encryption = serialization.BestAvailableEncryption(passphrase)
        pem = self.private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )
        try:
            target = Path(path)
            target.write_bytes(pem)
            try:
                os.chmod(target, 0o600)
            except OSError:
                # Windows filesystems may not support chmod; not fatal.
                pass
        except OSError as exc:
            raise KeyStorageError(f"cannot write key to {path}: {exc}") from exc

    # --- helpers ----------------------------------------------------------

    @staticmethod
    def _public_bytes(key: ed25519.Ed25519PublicKey) -> bytes:
        return key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )


def verify_signature(public_key_bytes: bytes, signature: bytes, message: bytes) -> bool:
    """Verify an Ed25519 signature against raw key bytes.

    Returns ``True`` on success and ``False`` on any failure (bad
    signature, wrong key, malformed bytes). Never raises — callers
    invariably wrap this in policy logic.
    """
    try:
        public = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public.verify(signature, message)
    except Exception:  # noqa: BLE001 - intentional broad catch
        return False
    return True
