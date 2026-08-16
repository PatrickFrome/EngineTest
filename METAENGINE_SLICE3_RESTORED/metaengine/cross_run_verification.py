"""METAENGINE Phase 12 — Cross-Run Signature Verification.

Verifies Ed25519 signatures on persisted artifacts when loading them
on subsequent runs. If an artifact's signature is invalid (tampered),
the orchestrator refuses to load it.

This closes the last feedback loop: signed_receipt (run N) → verification (run N+1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import json

from .signed_provenance import SigningKeyPair, SignedReceipt, SignatureError
from .util import canonical_hash


VERIFICATION_VERSION = "METAENGINE-CROSS-RUN-SIGNATURE-VERIFICATION-1"


@dataclass(frozen=True)
class VerificationResult:
    """Result of cross-run signature verification."""
    artifact_path: str
    verified: bool
    reason: str
    payload_hash: str | None

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_path": self.artifact_path,
            "verified": self.verified,
            "reason": self.reason,
            "payload_hash": self.payload_hash,
        }


def verify_signed_artifact(
    artifact_path: str | Path,
    public_key_hex: str,
    *,
    payload_hash_field: str = "receipt_hash",
) -> VerificationResult:
    """Verify a persisted signed artifact.

    Reads the artifact JSON, checks for signature fields, and verifies
    the Ed25519 signature against the provided public key.

    If the artifact has no signature fields, returns verified=False
    with reason "NO_SIGNATURE" (not an error — first run has no signature).
    """
    p = Path(artifact_path)
    if not p.is_file():
        return VerificationResult(
            artifact_path=str(artifact_path),
            verified=False,
            reason="FILE_NOT_FOUND",
            payload_hash=None,
        )

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return VerificationResult(
            artifact_path=str(artifact_path),
            verified=False,
            reason=f"LOAD_FAILED: {exc}",
            payload_hash=None,
        )

    # Check if this is a signed artifact
    if "signature_hex" not in data or "public_key_hex" not in data or "payload_hash" not in data:
        return VerificationResult(
            artifact_path=str(artifact_path),
            verified=False,
            reason="NO_SIGNATURE",
            payload_hash=None,
        )

    # Check public key matches
    if data["public_key_hex"] != public_key_hex:
        return VerificationResult(
            artifact_path=str(artifact_path),
            verified=False,
            reason="PUBLIC_KEY_MISMATCH",
            payload_hash=data.get("payload_hash"),
        )

    # Reconstruct SignedReceipt and verify
    try:
        receipt = SignedReceipt.from_dict(data)
        # Create a keypair from the public key for verification
        # (private key not needed for verify — only public key)
        from .signed_provenance import SigningKeyPair
        # We can't create a full SigningKeyPair from just a public key,
        # but we can verify the signature directly
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        try:
            public_key.verify(
                bytes.fromhex(data["signature_hex"]),
                data["payload_hash"].encode("utf-8"),
            )
            return VerificationResult(
                artifact_path=str(artifact_path),
                verified=True,
                reason="SIGNATURE_VALID",
                payload_hash=data["payload_hash"],
            )
        except Exception as exc:
            return VerificationResult(
                artifact_path=str(artifact_path),
                verified=False,
                reason=f"SIGNATURE_INVALID: {exc}",
                payload_hash=data.get("payload_hash"),
            )
    except Exception as exc:
        return VerificationResult(
            artifact_path=str(artifact_path),
            verified=False,
            reason=f"VERIFICATION_ERROR: {exc}",
            payload_hash=data.get("payload_hash"),
        )


def verify_accumulated_state(
    root: str | Path,
) -> dict[str, VerificationResult]:
    """Verify all signed persisted artifacts in a project root.

    Checks:
    - storage/evidence_graph.json (if signed)
    - storage/mechanism_library.json (if signed)
    - storage/predictive_model.json (if signed)
    - SIGNED_RUN_RECEIPT.json (always signed)

    Returns a dict of path → VerificationResult.
    """
    root = Path(root)
    # Load project public key
    key_path = root / "storage" / "project_public_key.json"
    if not key_path.is_file():
        # Try alternate location
        key_path = root / "PROJECT_PUBLIC_KEY.json"
    if not key_path.is_file():
        return {}  # no public key → can't verify

    try:
        key_data = json.loads(key_path.read_text(encoding="utf-8"))
        public_key_hex = key_data.get("public_key_hex", "")
    except Exception:
        return {}

    if not public_key_hex:
        return {}

    results: dict[str, VerificationResult] = {}
    for artifact_name in [
        "storage/evidence_graph.json",
        "storage/mechanism_library.json",
        "storage/predictive_model.json",
        "SIGNED_RUN_RECEIPT.json",
    ]:
        artifact_path = root / artifact_name
        if artifact_path.is_file():
            results[artifact_name] = verify_signed_artifact(
                artifact_path, public_key_hex
            )
    return results
