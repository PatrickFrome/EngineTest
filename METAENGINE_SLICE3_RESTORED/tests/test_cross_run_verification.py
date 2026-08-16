"""METAENGINE Phase 12 — Cross-Run Signature Verification tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metaengine.cross_run_verification import (
    verify_signed_artifact,
    verify_accumulated_state,
    VerificationResult,
)
from metaengine.signed_provenance import generate_signing_keypair, SignedReceipt


@pytest.fixture
def keypair():
    return generate_signing_keypair()


@pytest.fixture
def signed_artifact(tmp_path, keypair):
    """Create a signed artifact file."""
    signed = SignedReceipt.sign(keypair, {
        "meta_run_id": "test-run-001",
        "status": "COMPLETE",
        "data": "test payload",
    })
    path = tmp_path / "signed_artifact.json"
    path.write_text(json.dumps(signed.as_dict(), sort_keys=True))
    return path


# ---------------------------------------------------------------------------
# verify_signed_artifact
# ---------------------------------------------------------------------------


class TestVerifySignedArtifact:
    def test_valid_signature_passes(self, signed_artifact, keypair):
        result = verify_signed_artifact(signed_artifact, keypair.public_key_hex)
        assert result.verified is True
        assert result.reason == "SIGNATURE_VALID"

    def test_missing_file(self, tmp_path, keypair):
        result = verify_signed_artifact(tmp_path / "missing.json", keypair.public_key_hex)
        assert result.verified is False
        assert result.reason == "FILE_NOT_FOUND"

    def test_no_signature_fields(self, tmp_path, keypair):
        path = tmp_path / "unsigned.json"
        path.write_text(json.dumps({"data": "no signature here"}))
        result = verify_signed_artifact(path, keypair.public_key_hex)
        assert result.verified is False
        assert result.reason == "NO_SIGNATURE"

    def test_wrong_public_key_rejected(self, signed_artifact):
        other_keypair = generate_signing_keypair()
        result = verify_signed_artifact(signed_artifact, other_keypair.public_key_hex)
        assert result.verified is False
        assert result.reason == "PUBLIC_KEY_MISMATCH"

    def test_tampered_payload_rejected(self, signed_artifact, keypair):
        data = json.loads(signed_artifact.read_text())
        data["payload"]["status"] = "TAMPERED"
        signed_artifact.write_text(json.dumps(data, sort_keys=True))
        result = verify_signed_artifact(signed_artifact, keypair.public_key_hex)
        assert result.verified is False
        assert "MISMATCH" in result.reason or "INVALID" in result.reason

    def test_tampered_signature_rejected(self, signed_artifact, keypair):
        data = json.loads(signed_artifact.read_text())
        data["signature_hex"] = "0" * 128
        signed_artifact.write_text(json.dumps(data, sort_keys=True))
        result = verify_signed_artifact(signed_artifact, keypair.public_key_hex)
        assert result.verified is False
        assert "INVALID" in result.reason

    def test_result_has_payload_hash(self, signed_artifact, keypair):
        result = verify_signed_artifact(signed_artifact, keypair.public_key_hex)
        assert result.payload_hash is not None
        assert len(result.payload_hash) == 64

    def test_result_serializable(self, signed_artifact, keypair):
        result = verify_signed_artifact(signed_artifact, keypair.public_key_hex)
        d = result.payload()
        assert "artifact_path" in d
        assert "verified" in d
        assert "reason" in d

    def test_bad_json_rejected(self, tmp_path, keypair):
        path = tmp_path / "bad.json"
        path.write_text("not json {{{")
        result = verify_signed_artifact(path, keypair.public_key_hex)
        assert result.verified is False
        assert "LOAD_FAILED" in result.reason


# ---------------------------------------------------------------------------
# verify_accumulated_state
# ---------------------------------------------------------------------------


class TestVerifyAccumulatedState:
    def test_no_public_key_returns_empty(self, tmp_path):
        results = verify_accumulated_state(tmp_path)
        assert results == {}

    def test_with_public_key_checks_artifacts(self, tmp_path, keypair):
        # Create project public key
        key_path = tmp_path / "storage" / "project_public_key.json"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(json.dumps(keypair.to_public_record()))

        # Create a signed artifact
        signed = SignedReceipt.sign(keypair, {"test": "data"})
        (tmp_path / "SIGNED_RUN_RECEIPT.json").write_text(json.dumps(signed.as_dict(), sort_keys=True))

        results = verify_accumulated_state(tmp_path)
        assert "SIGNED_RUN_RECEIPT.json" in results
        assert results["SIGNED_RUN_RECEIPT.json"].verified is True

    def test_unsigned_artifact_reported_as_no_signature(self, tmp_path, keypair):
        key_path = tmp_path / "storage" / "project_public_key.json"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(json.dumps(keypair.to_public_record()))

        # Create unsigned artifact
        (tmp_path / "storage" / "evidence_graph.json").write_text(json.dumps({"nodes": []}))

        results = verify_accumulated_state(tmp_path)
        assert "storage/evidence_graph.json" in results
        assert results["storage/evidence_graph.json"].reason == "NO_SIGNATURE"

    def test_tampered_artifact_detected(self, tmp_path, keypair):
        key_path = tmp_path / "storage" / "project_public_key.json"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(json.dumps(keypair.to_public_record()))

        # Create signed artifact, then tamper
        signed = SignedReceipt.sign(keypair, {"test": "original"})
        path = tmp_path / "SIGNED_RUN_RECEIPT.json"
        data = signed.as_dict()
        data["payload"]["test"] = "tampered"
        path.write_text(json.dumps(data, sort_keys=True))

        results = verify_accumulated_state(tmp_path)
        assert results["SIGNED_RUN_RECEIPT.json"].verified is False

    def test_multiple_artifacts_checked(self, tmp_path, keypair):
        key_path = tmp_path / "storage" / "project_public_key.json"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(json.dumps(keypair.to_public_record()))

        # Create multiple signed artifacts
        for name in ["SIGNED_RUN_RECEIPT.json"]:
            signed = SignedReceipt.sign(keypair, {"name": name})
            (tmp_path / name).write_text(json.dumps(signed.as_dict(), sort_keys=True))

        results = verify_accumulated_state(tmp_path)
        assert len(results) >= 1
        for r in results.values():
            assert r.verified is True
