"""METAENGINE Step 3 — Signed provenance tests (Ed25519 signatures on receipts).

Adds cryptographic signatures to content-addressed receipts so that tamper-
detection works even if an attacker replaces both the manifest and the files
(current limitation: content-addressing alone verifies hash-against-data, but
if both are replaced the check passes).

A SignedReceipt wraps any content-addressed receipt payload with an Ed25519
signature over its canonical hash. Verification checks:
1. The payload hash matches (content integrity).
2. The signature is valid for the signing public key (authenticity).
3. The signing key is the expected project key (authority).
"""

from __future__ import annotations

import json

import pytest

from metaengine.signed_provenance import (
    SigningKeyPair,
    SignedReceipt,
    SignatureError,
    generate_signing_keypair,
)


# ---------------------------------------------------------------------------
# Key pair generation + serialization
# ---------------------------------------------------------------------------


def test_generate_signing_keypair():
    kp = generate_signing_keypair()
    assert kp.public_key_hex  # non-empty
    assert len(kp.public_key_hex) == 64  # Ed25519 public key = 32 bytes = 64 hex
    assert kp.private_key_hex  # non-empty (never exposed in receipts)


def test_keypair_serialization_roundtrip():
    kp1 = generate_signing_keypair()
    serialized = kp1.to_public_record()
    assert "public_key_hex" in serialized
    assert "algorithm" in serialized
    assert serialized["algorithm"] == "Ed25519"
    # private key must NOT be in the public record
    assert "private_key_hex" not in serialized


def test_different_keypairs_have_different_public_keys():
    kp1 = generate_signing_keypair()
    kp2 = generate_signing_keypair()
    assert kp1.public_key_hex != kp2.public_key_hex


# ---------------------------------------------------------------------------
# SignedReceipt: sign + verify
# ---------------------------------------------------------------------------


def test_sign_and_verify_receipt():
    kp = generate_signing_keypair()
    # The payload's receipt_hash will be recomputed by sign() to match canonical_hash
    payload = {"decision": "ACCEPT", "step_id": "TEST"}
    signed = SignedReceipt.sign(kp, payload)
    assert signed.signature_hex
    assert signed.payload_hash == signed.payload["receipt_hash"]  # sign() inserts the real hash
    assert signed.verify(kp) is True


def test_signed_receipt_tamper_payload_detected():
    kp = generate_signing_keypair()
    payload = {"receipt_hash": "b" * 64, "decision": "ACCEPT"}
    signed = SignedReceipt.sign(kp, payload)
    # Tamper the payload hash in the signed receipt
    tampered = SignedReceipt(
        payload_hash="c" * 64,  # wrong hash
        payload=payload,
        signature_hex=signed.signature_hex,
        public_key_hex=kp.public_key_hex,
        algorithm="Ed25519",
    )
    with pytest.raises(SignatureError, match="PAYLOAD_HASH_MISMATCH"):
        tampered.verify(kp)


def test_signed_receipt_wrong_key_rejected():
    kp1 = generate_signing_keypair()
    kp2 = generate_signing_keypair()
    payload = {"decision": "ACCEPT"}
    signed = SignedReceipt.sign(kp1, payload)
    # Verify with wrong key — PUBLIC_KEY_MISMATCH is the correct first check
    # (we check the key BEFORE checking the signature, because a valid signature
    # from the wrong key is still unauthorized)
    with pytest.raises(SignatureError, match="PUBLIC_KEY_MISMATCH"):
        signed.verify(kp2)


def test_signed_receipt_tamper_signature_detected():
    kp = generate_signing_keypair()
    payload = {"receipt_hash": "e" * 64, "decision": "ACCEPT"}
    signed = SignedReceipt.sign(kp, payload)
    # Tamper the signature
    tampered = SignedReceipt(
        payload_hash=signed.payload_hash,
        payload=signed.payload,
        signature_hex="0" * 128,  # invalid signature
        public_key_hex=kp.public_key_hex,
        algorithm="Ed25519",
    )
    with pytest.raises(SignatureError, match="SIGNATURE_INVALID"):
        tampered.verify(kp)


# ---------------------------------------------------------------------------
# Serialization roundtrip (persist + reload)
# ---------------------------------------------------------------------------


def test_signed_receipt_json_roundtrip():
    kp = generate_signing_keypair()
    payload = {"receipt_hash": "f" * 64, "decision": "ACCEPT", "data": [1, 2, 3]}
    signed = SignedReceipt.sign(kp, payload)
    blob = json.dumps(signed.as_dict(), sort_keys=True)
    restored = SignedReceipt.from_dict(json.loads(blob))
    assert restored.payload_hash == signed.payload_hash
    assert restored.signature_hex == signed.signature_hex
    assert restored.verify(kp) is True


def test_signed_receipt_from_dict_rejects_tampered_hash():
    kp = generate_signing_keypair()
    payload = {"receipt_hash": "1" * 64, "decision": "ACCEPT"}
    signed = SignedReceipt.sign(kp, payload)
    tampered = signed.as_dict()
    tampered["payload_hash"] = "0" * 64  # mismatch with actual payload
    with pytest.raises(SignatureError, match="PAYLOAD_HASH_MISMATCH"):
        SignedReceipt.from_dict(tampered)


# ---------------------------------------------------------------------------
# Sign a real experiment receipt
# ---------------------------------------------------------------------------


def test_sign_experiment_receipt():
    """Sign the Slice-4 experiment receipt with a project key."""
    kp = generate_signing_keypair()
    # Simulate a real receipt payload
    receipt_payload = {
        "receipt_hash": "7349731c3884c43dabbbd906955de646547edb0ea5b0f3e91a3df52c88b34791",
        "local_decision": "SUPPORTED_LOCAL",
        "truth_effect": "NONE",
        "assimilation_effect": "NONE",
        "contract_hash": "ebadbcd2ac9d83147b2a12087292c47634d2b4c085d4837b0f9f7a1b646a5662",
    }
    signed = SignedReceipt.sign(kp, receipt_payload)
    assert signed.verify(kp) is True
    assert signed.algorithm == "Ed25519"
    assert signed.public_key_hex == kp.public_key_hex


# ---------------------------------------------------------------------------
# Manifest signing (multiple receipts under one signature)
# ---------------------------------------------------------------------------


def test_sign_manifest():
    """Sign a manifest of receipt hashes (batch provenance)."""
    kp = generate_signing_keypair()
    receipt_hashes = [
        "7349731c3884c43dabbbd906955de646547edb0ea5b0f3e91a3df52c88b34791",
        "36f6a486e1144ceed5135d72" + "0" * 40,
        "4c2310152895bb4650f9a02d41ae4f5d618c7c98e13d4edc502a5366a24a0e54",
    ]
    manifest = {"receipt_hashes": receipt_hashes, "manifest_version": "METAENGINE-SIGNED-MANIFEST-1"}
    signed = SignedReceipt.sign(kp, manifest, payload_hash_field="manifest_hash")
    # verify must use the same payload_hash_field
    assert signed.verify(kp, payload_hash_field="manifest_hash") is True
    assert signed.payload_hash != receipt_hashes[0]  # it's the manifest hash, not a receipt hash
