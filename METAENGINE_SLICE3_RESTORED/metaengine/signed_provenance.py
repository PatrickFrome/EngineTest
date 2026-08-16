"""METAENGINE Step 3 — Signed provenance via Ed25519 signatures.

Adds cryptographic signatures to content-addressed receipts so that tamper-
detection works even if an attacker replaces both the manifest and the files.

Content-addressing alone verifies ``hash(data) == claimed_hash``. If an
attacker replaces BOTH the data and the claimed hash, the check passes.
Ed25519 signatures close this gap: the signature is over the hash, using a
private key that the attacker does not have. Verification requires the
corresponding public key.

Design:
- :class:`SigningKeyPair` — Ed25519 key pair. The private key signs; the
  public key verifies. The private key is NEVER included in any receipt,
  manifest, or persisted artifact (Boundary 6: secret non-disclosure).
- :class:`SignedReceipt` — wraps a receipt payload with an Ed25519 signature
  over its canonical hash. Verification checks: (1) payload hash matches,
  (2) signature is valid for the public key, (3) the public key is the
  expected project key.
- The signing key is generated once per project and stored as a secret
  (never in the repository). The public key is recorded in project_meta so
  verifiers know which key to trust.

This does NOT replace content-addressing — it augments it. Every receipt is
still content-addressed; the signature adds authenticity on top of integrity.
"""

from __future__ import annotations

import json
import string
from dataclasses import dataclass
from typing import Any, Mapping

from .util import canonical_hash

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "cryptography package is required for signed provenance: "
        "python -m pip install cryptography"
    ) from exc


SIGNATURE_ALGORITHM = "Ed25519"


class SignatureError(RuntimeError):
    """Raised when signature verification fails."""


# ---------------------------------------------------------------------------
# SigningKeyPair
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SigningKeyPair:
    """An Ed25519 signing key pair.

    The private key signs receipts; the public key verifies them.
    The private key is NEVER serialized to a public record (Boundary 6).
    """

    private_key_hex: str
    public_key_hex: str

    @classmethod
    def from_private_key_hex(cls, private_key_hex: str) -> "SigningKeyPair":
        """Reconstruct a key pair from a stored private key (secret)."""
        private_bytes = bytes.fromhex(private_key_hex)
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
        public_key = private_key.public_key()
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return cls(
            private_key_hex=private_key_hex,
            public_key_hex=public_bytes.hex(),
        )

    def to_public_record(self) -> dict[str, Any]:
        """Return a public record of this key pair (NO private key)."""
        return {
            "algorithm": SIGNATURE_ALGORITHM,
            "public_key_hex": self.public_key_hex,
        }

    def _private_key(self) -> Ed25519PrivateKey:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.private_key_hex))

    def _public_key(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key_hex))


def generate_signing_keypair() -> SigningKeyPair:
    """Generate a new Ed25519 key pair. The private key must be stored as a
    secret (never in the repository); the public key is recorded in project_meta."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return SigningKeyPair(
        private_key_hex=private_bytes.hex(),
        public_key_hex=public_bytes.hex(),
    )


# ---------------------------------------------------------------------------
# SignedReceipt
# ---------------------------------------------------------------------------


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(ch in string.hexdigits for ch in value)


@dataclass(frozen=True)
class SignedReceipt:
    """A receipt payload signed with Ed25519.

    The signature is over ``payload_hash`` (the canonical hash of the payload),
    NOT over the payload itself. This means the signature is compact and
    deterministic regardless of payload size.
    """

    payload_hash: str  # canonical_hash of the payload
    payload: dict[str, Any]
    signature_hex: str
    public_key_hex: str
    algorithm: str

    @classmethod
    def sign(
        cls,
        keypair: SigningKeyPair,
        payload: Mapping[str, Any],
        *,
        payload_hash_field: str = "receipt_hash",
    ) -> "SignedReceipt":
        """Sign a payload. The signature is over the canonical hash of the
        payload **without** the hash field (so the hash field can store the
        signed hash without creating a self-reference).

        The hash field (``receipt_hash`` by default) is set to the signed hash
        in the returned payload.
        """
        payload_dict = dict(payload)
        # Remove any existing hash field to compute the signed hash
        payload_dict.pop(payload_hash_field, None)
        signed_hash = canonical_hash(payload_dict)
        # Insert the signed hash into the payload
        payload_dict[payload_hash_field] = signed_hash

        private_key = keypair._private_key()
        signature = private_key.sign(signed_hash.encode("utf-8"))
        return cls(
            payload_hash=signed_hash,
            payload=payload_dict,
            signature_hex=signature.hex(),
            public_key_hex=keypair.public_key_hex,
            algorithm=SIGNATURE_ALGORITHM,
        )

    def verify(self, expected_keypair: SigningKeyPair, *, payload_hash_field: str = "receipt_hash") -> bool:
        """Verify the signature against an expected key pair.

        Raises :class:`SignatureError` if verification fails.
        Returns True if valid.
        """
        # 1. Check the public key matches (authority)
        if self.public_key_hex != expected_keypair.public_key_hex:
            raise SignatureError(
                f"PUBLIC_KEY_MISMATCH: expected {expected_keypair.public_key_hex[:16]}..., "
                f"got {self.public_key_hex[:16]}..."
            )
        # 2. Check the payload hash matches (content integrity).
        # The payload_hash is the canonical hash of the payload WITHOUT the
        # hash field (the hash field stores the signed hash; self-reference
        # would be unsound).
        payload_without_hash = {k: v for k, v in self.payload.items() if k != payload_hash_field}
        actual_hash = canonical_hash(payload_without_hash)
        if actual_hash != self.payload_hash:
            raise SignatureError(
                f"PAYLOAD_HASH_MISMATCH: claimed {self.payload_hash[:16]}..., "
                f"actual {actual_hash[:16]}..."
            )
        # Also check that the payload's hash field stores the signed hash
        if self.payload.get(payload_hash_field) != self.payload_hash:
            raise SignatureError(
                f"PAYLOAD_HASH_FIELD_MISMATCH: payload[{payload_hash_field!r}] does not match signed hash"
            )
        # 3. Check the signature (authenticity)
        if not _is_hex(self.signature_hex, 128):  # Ed25519 sig = 64 bytes = 128 hex
            raise SignatureError("SIGNATURE_FORMAT_INVALID")
        public_key = expected_keypair._public_key()
        try:
            public_key.verify(
                bytes.fromhex(self.signature_hex),
                self.payload_hash.encode("utf-8"),
            )
        except InvalidSignature as exc:
            raise SignatureError("SIGNATURE_INVALID") from exc
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload_hash": self.payload_hash,
            "payload": self.payload,
            "signature_hex": self.signature_hex,
            "public_key_hex": self.public_key_hex,
            "algorithm": self.algorithm,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, payload_hash_field: str = "receipt_hash") -> "SignedReceipt":
        # Re-verify the payload hash on load (defensive).
        # The payload_hash is the hash of the payload WITHOUT the hash field.
        payload = dict(value.get("payload", {}))
        claimed_hash = str(value.get("payload_hash", ""))
        payload_without_hash = {k: v for k, v in payload.items() if k != payload_hash_field}
        actual_hash = canonical_hash(payload_without_hash)
        if claimed_hash and actual_hash != claimed_hash:
            raise SignatureError(
                f"PAYLOAD_HASH_MISMATCH: claimed {claimed_hash[:16]}..., "
                f"actual {actual_hash[:16]}..."
            )
        return cls(
            payload_hash=str(value["payload_hash"]),
            payload=payload,
            signature_hex=str(value["signature_hex"]),
            public_key_hex=str(value["public_key_hex"]),
            algorithm=str(value.get("algorithm", SIGNATURE_ALGORITHM)),
        )


# ---------------------------------------------------------------------------
# Manifest signing (batch provenance)
# ---------------------------------------------------------------------------


def sign_manifest(
    keypair: SigningKeyPair,
    receipt_hashes: list[str],
    *,
    manifest_version: str = "METAENGINE-SIGNED-MANIFEST-1",
) -> SignedReceipt:
    """Sign a manifest of receipt hashes (batch provenance).

    The manifest is a content-addressed structure containing a list of receipt
    hashes. Signing the manifest signs all receipts at once.
    """
    manifest = {
        "manifest_version": manifest_version,
        "receipt_hashes": sorted(receipt_hashes),
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    return SignedReceipt.sign(keypair, manifest, payload_hash_field="manifest_hash")
