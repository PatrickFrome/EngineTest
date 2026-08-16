from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from metaengine.architecture_sources import (
    ClaimKind,
    IngestionStatus,
    MechanismStatus,
    SourceClass,
    SourcePack,
    SourceRecord,
    SourceRegistry,
)
from metaengine.devfabric.codec import canonical_digest
from metaengine.reference_vault import ReferenceVault, VaultVerificationReceipt
from scripts.architecture_source_registry import verify_registry


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "research" / "architecture_library"
VAULT = ROOT / "reference-vault"
REQUIRED_INGESTED = {
    "deepseek-v3.2-exp-87e509a",
    "qwen3.6-0886e34",
    "kimi-linear-8c1d85e",
    "mistral-inference-9eaeb91",
    "glm-4.5-170f20b",
}
RESTRICTED = {"kimi-k3-3cb39df", "llama4-0e0b8c5"}
CLOSED = {
    "openai-gpt-5.6-public",
    "anthropic-claude-public",
    "google-gemini-deep-think-public",
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _records(registry: SourceRegistry) -> dict[str, SourceRecord]:
    return {
        entry.source_id: SourceRecord.from_dict(_load(LIBRARY / "sources" / f"{entry.source_id}.json"))
        for entry in registry.sources
    }


def _packs(registry: SourceRegistry) -> dict[str, SourcePack]:
    return {
        entry.source_id: SourcePack.from_dict(_load(LIBRARY / "packs" / f"{entry.source_id}.json"))
        for entry in registry.sources
        if entry.pack_root_sha256 is not None
    }


def _git_blob_id(data: bytes) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()


def test_first_wave_registry_materially_verifies_and_preserves_class_ceilings():
    registry = SourceRegistry.from_dict(_load(LIBRARY / "registry.json"))
    records = _records(registry)
    packs = _packs(registry)

    result = verify_registry(registry_path=LIBRARY / "registry.json", vault_root=VAULT)
    assert result == {
        "status": "PASS",
        "registry_snapshot_sha256": "b50ee520f2dd605fb48f94c44dbb5fd26980fbcacf6a2150aafe178d41f631e8",
        "source_count": 10,
        "ingested_source_count": 5,
        "verified_blob_count": 13,
        "verified_total_bytes": 150521,
        "findings": [],
    }
    assert set(records) == REQUIRED_INGESTED | RESTRICTED | CLOSED
    assert set(packs) == REQUIRED_INGESTED

    for source_id in REQUIRED_INGESTED:
        record = records[source_id]
        pack = packs[source_id]
        receipt = VaultVerificationReceipt.from_dict(
            _load(LIBRARY / "receipts" / f"{source_id}.json")
        )
        assert record.source_class is SourceClass.PERMISSIVE_CODE
        assert record.ingestion_status is IngestionStatus.INGESTED
        assert record.source_sha256 == pack.pack_root_sha256
        assert record.license_sha256 in {blob.digest for blob in pack.blob_descriptors}
        assert ReferenceVault(VAULT).verify(pack) == receipt

    for source_id in RESTRICTED:
        record = records[source_id]
        assert record.source_class is SourceClass.RESTRICTED_REFERENCE
        assert record.ingestion_status is IngestionStatus.REGISTERED_ONLY
        assert record.source_sha256 is None
        assert record.blob_descriptors == ()

    for source_id in CLOSED:
        record = records[source_id]
        assert record.source_class is SourceClass.CLOSED_BEHAVIORAL_ONLY
        assert record.ingestion_status is IngestionStatus.REGISTERED_ONLY
        assert record.source_sha256 is None
        assert all(claim.kind is not ClaimKind.SOURCE_FACT for claim in record.architecture_claims)

    assert all(
        record.epistemic_ceiling in {
            MechanismStatus.A0_OBSERVED,
            MechanismStatus.A1_MECHANISM_HYPOTHESIS,
        }
        and all(
            mechanism.status in {
                MechanismStatus.A0_OBSERVED,
                MechanismStatus.A1_MECHANISM_HYPOTHESIS,
            }
            for mechanism in record.mechanism_candidates
        )
        for record in records.values()
    )


def test_retrieval_evidence_binds_upstream_git_blobs_to_retained_sha256():
    evidence = _load(LIBRARY / "retrieval_evidence.json")
    claimed = evidence.pop("manifest_sha256")
    assert canonical_digest(evidence) == claimed
    assert evidence["retrieval_evidence_version"] == "ARCHITECTURE-SOURCE-RETRIEVAL-EVIDENCE-1"
    assert evidence["file_count"] == 13
    assert evidence["total_bytes"] == 150521
    assert str(ROOT) not in json.dumps(evidence)

    registry = SourceRegistry.from_dict(_load(LIBRARY / "registry.json"))
    descriptors = {
        (source_id, blob.relative_path): blob
        for source_id, pack in _packs(registry).items()
        for blob in pack.blob_descriptors
    }
    assert len(evidence["files"]) == len(descriptors)
    for row in evidence["files"]:
        descriptor = descriptors[(row["source_id"], row["relative_path"])]
        blob = VAULT / "blobs" / "sha256" / descriptor.digest
        data = blob.read_bytes()
        assert row["sha256"] == descriptor.digest == hashlib.sha256(data).hexdigest()
        assert row["size"] == descriptor.size == len(data)
        assert row["git_blob_id"] == descriptor.git_blob_id == _git_blob_id(data)
        assert row["exact_commit_or_release"]
        assert row["official_file_locator"].startswith("https://github.com/")


def test_mutated_copy_of_materialized_vault_fails_independent_verification(tmp_path):
    registry = SourceRegistry.from_dict(_load(LIBRARY / "registry.json"))
    source_id = "deepseek-v3.2-exp-87e509a"
    pack = _packs(registry)[source_id]
    copied_vault = tmp_path / "reference-vault"
    shutil.copytree(VAULT / "blobs", copied_vault / "blobs")
    descriptor = pack.blob_descriptors[0]
    blob = copied_vault / "blobs" / "sha256" / descriptor.digest
    blob.chmod(0o644)
    blob.write_bytes(b"mutated")

    result = ReferenceVault(copied_vault).verify(pack)

    assert result.status == "FAIL"
    assert {(finding.code, finding.relative_path) for finding in result.findings} == {
        ("HASH_MISMATCH", descriptor.relative_path)
    }


def test_reference_vault_is_ignored_and_has_no_tracked_foreign_bytes():
    tracked = subprocess.run(
        ("git", "ls-files", "--", "reference-vault"),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    ignored = subprocess.run(
        ("git", "check-ignore", "-q", "reference-vault/blobs/sha256/" + "a" * 64),
        cwd=ROOT,
        check=False,
    )

    assert tracked.stdout == ""
    assert ignored.returncode == 0
