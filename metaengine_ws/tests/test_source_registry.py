from __future__ import annotations

import json

import pytest

from metaengine.source_registry import (
    ArchitectureClaim,
    IngestionBlocker,
    IngestionStatus,
    SourceClass,
    SourceRecord,
    SourceRegistry,
    SOURCE_REGISTRY_VERSION,
)
from metaengine.util import canonical_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_LICENSE_HASH = "a" * 64
VALID_SOURCE_HASH = "b" * 64


def _permissive_record(
    *,
    source_id: str = "src.glm.1",
    ingestion: IngestionStatus = IngestionStatus.OBSERVED,
    source_sha256: str | None = VALID_SOURCE_HASH,
    license_sha256: str | None = VALID_LICENSE_HASH,
    retained_reference_paths: tuple[str, ...] = ("reference_vault/aa/aaaa",),
    ingestion_blocker: IngestionBlocker | None = None,
) -> SourceRecord:
    return SourceRecord.create(
        source_id=source_id,
        publisher="Z.ai",
        system_name="GLM",
        version="5.2",
        source_class=SourceClass.PERMISSIVE_CODE,
        official_source_locator="https://github.com/zai-org/glm-reference",
        exact_commit_or_release="v5.2.0",
        retrieved_at="2026-08-14T00:00:00Z",
        source_sha256=source_sha256,
        license_name="MIT",
        license_sha256=license_sha256,
        allowed_use=("ANALYSIS", "REFERENCE", "REIMPLEMENTATION"),
        architecture_claims=(
            ArchitectureClaim.create(
                claim_id="glm.moe",
                statement="GLM uses a mixture-of-experts feed-forward block.",
                evidence_kind="PUBLIC_PAPER",
                evidence_refs=("https://example.org/glm-card",),
            ),
        ),
        retained_reference_paths=retained_reference_paths,
        mechanism_candidates=("mec.sparse_conditional_routing",),
        ingestion=ingestion,
        ingestion_blocker=ingestion_blocker,
    )


# ---------------------------------------------------------------------------
# SourceClass / IngestionStatus enums
# ---------------------------------------------------------------------------


def test_source_class_enum_has_exactly_three_mandatory_classes():
    assert {c.value for c in SourceClass} == {
        "PERMISSIVE_CODE",
        "RESTRICTED_REFERENCE",
        "CLOSED_BEHAVIORAL_ONLY",
    }


def test_ingestion_status_preserves_abstention_values():
    assert IngestionStatus.OBSERVED.value == "OBSERVED"
    assert IngestionStatus.UNOBSERVED.value == "UNOBSERVED"


# ---------------------------------------------------------------------------
# SourceRecord creation & hashing
# ---------------------------------------------------------------------------


def test_source_record_create_and_hash_roundtrip():
    rec = _permissive_record()
    payload = rec.payload()
    assert payload["source_id"] == "src.glm.1"
    assert payload["source_class"] == "PERMISSIVE_CODE"
    assert payload["ingestion"] == "OBSERVED"
    assert rec.source_hash == canonical_hash(payload)
    assert rec.as_dict()["source_hash"] == rec.source_hash


def test_source_record_from_dict_revalidates_claimed_hash():
    rec = _permissive_record()
    as_dict = rec.as_dict()
    restored = SourceRecord.from_dict(as_dict)
    assert restored.source_hash == rec.source_hash


def test_source_record_from_dict_rejects_tampered_hash():
    rec = _permissive_record()
    tampered = rec.as_dict()
    tampered["source_hash"] = "0" * 64
    with pytest.raises(ValueError, match="SOURCE_RECORD_HASH_MISMATCH"):
        SourceRecord.from_dict(tampered)


def test_source_record_from_dict_rejects_tampered_payload():
    rec = _permissive_record()
    tampered = rec.as_dict()
    tampered["version"] = "9.9.9"  # changes payload but not claimed hash
    with pytest.raises(ValueError, match="SOURCE_RECORD_HASH_MISMATCH"):
        SourceRecord.from_dict(tampered)


# ---------------------------------------------------------------------------
# Fail-closed license / source-class enforcement
# ---------------------------------------------------------------------------


def test_permissive_retention_requires_license_hash():
    with pytest.raises(ValueError, match="PERMISSIVE_LICENSE_HASH_REQUIRED"):
        _permissive_record(license_sha256=None)


def test_permissive_retention_rejects_non_hex_license_hash():
    with pytest.raises(ValueError, match="LICENSE_HASH_INVALID"):
        _permissive_record(license_sha256="not-a-hex")


def test_closed_behavioral_only_cannot_retain_source_bytes():
    with pytest.raises(ValueError, match="CLOSED_BEHAVIORAL_ONLY_RETENTION_FORBIDDEN"):
        SourceRecord.create(
            source_id="src.claude.1",
            publisher="Anthropic",
            system_name="Claude",
            version="opus",
            source_class=SourceClass.CLOSED_BEHAVIORAL_ONLY,
            official_source_locator="https://www.anthropic.com/claude",
            exact_commit_or_release="n/a",
            retrieved_at="2026-08-14T00:00:00Z",
            source_sha256=None,
            license_name="Proprietary",
            license_sha256=None,
            allowed_use=("BEHAVIORAL_OBSERVATION",),
            architecture_claims=(),
            retained_reference_paths=("reference_vault/cc/cccc",),  # illegal for closed
            mechanism_candidates=(),
            ingestion=IngestionStatus.UNOBSERVED,
            ingestion_blocker=IngestionBlocker.create(
                status=IngestionStatus.UNOBSERVED,
                reason="CLOSED_NO_SOURCE_BYTES",
                detail="Closed system; only public behavior/cards are available.",
            ),
        )


def test_closed_behavioral_only_with_no_retention_is_accepted():
    rec = SourceRecord.create(
        source_id="src.claude.1",
        publisher="Anthropic",
        system_name="Claude",
        version="opus",
        source_class=SourceClass.CLOSED_BEHAVIORAL_ONLY,
        official_source_locator="https://www.anthropic.com/claude",
        exact_commit_or_release="n/a",
        retrieved_at="2026-08-14T00:00:00Z",
        source_sha256=None,
        license_name="Proprietary",
        license_sha256=None,
        allowed_use=("BEHAVIORAL_OBSERVATION",),
        architecture_claims=(
            ArchitectureClaim.create(
                claim_id="claude.constitutional",
                statement="Claude uses constitutional-AI style alignment training.",
                evidence_kind="PUBLIC_PAPER",
                evidence_refs=("https://example.org/constitutional-ai",),
            ),
        ),
        retained_reference_paths=(),
        mechanism_candidates=(),
        ingestion=IngestionStatus.UNOBSERVED,
        ingestion_blocker=IngestionBlocker.create(
            status=IngestionStatus.UNOBSERVED,
            reason="CLOSED_NO_SOURCE_BYTES",
            detail="Closed system; only public behavior/cards are available.",
        ),
    )
    assert rec.source_class is SourceClass.CLOSED_BEHAVIORAL_ONLY
    assert rec.retained_reference_paths == ()


def test_missing_source_class_rejected():
    with pytest.raises(ValueError):
        SourceRecord.create(
            source_id="x",
            publisher="p",
            system_name="s",
            version="1",
            source_class="",  # invalid
            official_source_locator="loc",
            exact_commit_or_release="r",
            retrieved_at="2026-08-14T00:00:00Z",
            source_sha256=None,
            license_name="MIT",
            license_sha256=None,
            allowed_use=("ANALYSIS",),
            architecture_claims=(),
            retained_reference_paths=(),
            mechanism_candidates=(),
            ingestion=IngestionStatus.UNOBSERVED,
            ingestion_blocker=IngestionBlocker.create(
                status=IngestionStatus.UNOBSERVED,
                reason="BLOCKED_NO_NETWORK",
                detail="download not performed",
            ),
        )


def test_missing_license_name_rejected():
    with pytest.raises(ValueError, match="LICENSE_NAME_REQUIRED"):
        SourceRecord.create(
            source_id="x",
            publisher="p",
            system_name="s",
            version="1",
            source_class=SourceClass.PERMISSIVE_CODE,
            official_source_locator="loc",
            exact_commit_or_release="r",
            retrieved_at="2026-08-14T00:00:00Z",
            source_sha256=None,
            license_name="",  # invalid
            license_sha256=None,
            allowed_use=("ANALYSIS",),
            architecture_claims=(),
            retained_reference_paths=(),
            mechanism_candidates=(),
            ingestion=IngestionStatus.UNOBSERVED,
            ingestion_blocker=IngestionBlocker.create(
                status=IngestionStatus.UNOBSERVED,
                reason="BLOCKED_NO_NETWORK",
                detail="download not performed",
            ),
        )


# ---------------------------------------------------------------------------
# Preserves abstention: UNOBSERVED ingestion must carry a blocker, no fake hash
# ---------------------------------------------------------------------------


def test_unobserved_ingestion_requires_blocker_and_forbids_hash():
    with pytest.raises(ValueError, match="UNOBSERVED_REQUIRES_BLOCKER"):
        _permissive_record(
            ingestion=IngestionStatus.UNOBSERVED,
            source_sha256=None,
            ingestion_blocker=None,
            retained_reference_paths=(),
        )


def test_unobserved_ingestion_forbids_fabricated_hash():
    with pytest.raises(ValueError, match="UNOBSERVED_MUST_NOT_HAVE_SOURCE_HASH"):
        _permissive_record(
            ingestion=IngestionStatus.UNOBSERVED,
            source_sha256=VALID_SOURCE_HASH,  # fabricated hash forbidden
            ingestion_blocker=IngestionBlocker.create(
                status=IngestionStatus.UNOBSERVED,
                reason="BLOCKED_NO_NETWORK",
                detail="download not performed",
            ),
            retained_reference_paths=(),
        )


def test_observed_ingestion_requires_source_hash():
    with pytest.raises(ValueError, match="OBSERVED_REQUIRES_SOURCE_HASH"):
        _permissive_record(
            ingestion=IngestionStatus.OBSERVED,
            source_sha256=None,
        )


def test_ingestion_blocker_status_must_be_unobserved():
    with pytest.raises(ValueError, match="BLOCKER_MUST_BE_UNOBSERVED"):
        IngestionBlocker.create(
            status=IngestionStatus.OBSERVED,  # illegal for a blocker
            reason="BLOCKED_NO_NETWORK",
            detail="x",
        )


# ---------------------------------------------------------------------------
# ArchitectureClaim
# ---------------------------------------------------------------------------


def test_architecture_claim_roundtrip_and_hash():
    claim = ArchitectureClaim.create(
        claim_id="glm.moe",
        statement="GLM uses a mixture-of-experts feed-forward block.",
        evidence_kind="PUBLIC_PAPER",
        evidence_refs=("https://example.org/glm-card", "https://example.org/glm-tech"),
    )
    payload = claim.payload()
    assert payload["evidence_refs"] == sorted(payload["evidence_refs"])
    restored = ArchitectureClaim.from_dict(payload)
    assert restored == claim


def test_architecture_claim_requires_non_empty_refs():
    with pytest.raises(ValueError, match="CLAIM_EVIDENCE_REF_REQUIRED"):
        ArchitectureClaim.create(
            claim_id="x",
            statement="s",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=(),
        )


# ---------------------------------------------------------------------------
# SourceRegistry: determinism, uniqueness, verification
# ---------------------------------------------------------------------------


def test_source_registry_is_deterministic_regardless_of_input_order():
    a = _permissive_record(source_id="src.a")
    b = _permissive_record(
        source_id="src.b",
        source_sha256="c" * 64,
        retained_reference_paths=("reference_vault/cc/cccc",),
    )
    reg1 = SourceRegistry.create((a, b))
    reg2 = SourceRegistry.create((b, a))
    assert reg1.registry_hash == reg2.registry_hash
    assert [r.source_id for r in reg1.records] == ["src.a", "src.b"]


def test_source_registry_rejects_duplicate_source_id():
    a = _permissive_record(source_id="src.dup")
    b = _permissive_record(
        source_id="src.dup",
        source_sha256="d" * 64,
        retained_reference_paths=("reference_vault/dd/dddd",),
    )
    with pytest.raises(ValueError, match="SOURCE_ID_DUPLICATE"):
        SourceRegistry.create((a, b))


def test_source_registry_detects_tampered_record_hash():
    # Defense in depth: a tampered record hash is caught at the RECORD level
    # (SOURCE_RECORD_HASH_MISMATCH) before the registry hash is even checked.
    a = _permissive_record(source_id="src.a")
    bad = a.as_dict()
    bad["source_hash"] = "0" * 64  # corrupted record hash
    forged = {
        "registry_version": SOURCE_REGISTRY_VERSION,
        "records": [bad],
        "registry_hash": "0" * 64,
    }
    with pytest.raises(ValueError, match="SOURCE_RECORD_HASH_MISMATCH"):
        SourceRegistry.from_dict(forged)


def test_source_registry_detects_tampered_registry_hash():
    # Records are valid; only the aggregate registry hash is corrupted.
    a = _permissive_record(source_id="src.a")
    forged = {
        "registry_version": SOURCE_REGISTRY_VERSION,
        "records": [a.as_dict()],
        "registry_hash": "0" * 64,  # stale/wrong aggregate hash
    }
    with pytest.raises(ValueError, match="REGISTRY_HASH_MISMATCH"):
        SourceRegistry.from_dict(forged)


def test_source_registry_from_dict_roundtrip():
    a = _permissive_record(source_id="src.a")
    b = _permissive_record(
        source_id="src.b",
        source_sha256="e" * 64,
        retained_reference_paths=("reference_vault/ee/eeee",),
    )
    reg = SourceRegistry.create((a, b))
    restored = SourceRegistry.from_dict(reg.as_dict())
    assert restored.registry_hash == reg.registry_hash
    assert restored.verify() is True


def test_source_registry_payload_is_json_serializable():
    a = _permissive_record(source_id="src.a")
    reg = SourceRegistry.create((a,))
    # Must round-trip through JSON without losing the hash
    blob = json.dumps(reg.as_dict(), sort_keys=True)
    restored = SourceRegistry.from_dict(json.loads(blob))
    assert restored.registry_hash == reg.registry_hash
