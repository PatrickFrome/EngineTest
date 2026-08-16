from __future__ import annotations

from dataclasses import replace

import pytest

from metaengine.architecture_sources import (
    ArchitectureClaim,
    ArchitectureSourceValidationError,
    BlobDescriptor,
    ClaimKind,
    IngestionStatus,
    MechanismCandidate,
    MechanismStatus,
    SourceClass,
    SourcePack,
    SourceRecord,
    SourceRegistry,
)

REVISION = "1" * 40
LICENSE_DIGEST = "b" * 64
README_DIGEST = "a" * 64


def _license_blob() -> BlobDescriptor:
    return BlobDescriptor.create(
        media_type="text/plain",
        digest=LICENSE_DIGEST,
        size=2,
        relative_path="LICENSE",
    )


def _readme_blob() -> BlobDescriptor:
    return BlobDescriptor.create(
        media_type="text/markdown",
        digest=README_DIGEST,
        size=1,
        relative_path="README.md",
    )


def _claim(claim_id: str = "publisher-claim") -> ArchitectureClaim:
    return ArchitectureClaim.create(
        claim_id=claim_id,
        kind=ClaimKind.PUBLISHER_CLAIM,
        statement="The publisher documents a sparse routing mechanism.",
        evidence_locator="https://example.invalid/README.md",
    )


def _mechanism(mechanism_id: str = "sparse-routing") -> MechanismCandidate:
    return MechanismCandidate.create(
        mechanism_id=mechanism_id,
        status=MechanismStatus.A1_MECHANISM_HYPOTHESIS,
        semantic_definition="Route only a bounded subset of workers for each request.",
        source_fact_boundary="The public README describes conditional routing.",
        hypothesized_effect="Reduce marginal compute while preserving task quality.",
        falsification_test="Compare fixed-compute routed and dense baselines.",
    )


def _permissive_record(
    *,
    descriptors: tuple[BlobDescriptor, ...] | None = None,
    mechanisms: tuple[MechanismCandidate, ...] | None = None,
    source_sha256: str | None = None,
    source_class: SourceClass | str = SourceClass.PERMISSIVE_CODE,
    ingestion_status: IngestionStatus | str = IngestionStatus.INGESTED,
    exact_revision: str = REVISION,
    license_name: str = "MIT License",
    license_expression: str = "MIT",
    license_sha256: str | None = LICENSE_DIGEST,
) -> SourceRecord:
    descriptors = descriptors if descriptors is not None else (_readme_blob(), _license_blob())
    mechanisms = mechanisms if mechanisms is not None else (_mechanism(),)
    if source_sha256 is None and descriptors:
        source_sha256 = SourcePack.create(
            source_id="example-model-deadbee",
            exact_commit_or_release=exact_revision,
            blob_descriptors=descriptors,
        ).pack_root_sha256
    return SourceRecord.create(
        source_id="example-model-deadbee",
        publisher="Example Publisher",
        system_name="Example Model",
        version="deadbee",
        source_class=source_class,
        ingestion_status=ingestion_status,
        official_source_locator="https://example.invalid/repo",
        exact_commit_or_release=exact_revision,
        retrieved_at="2026-08-13T12:00:00Z",
        source_sha256=source_sha256,
        source_sha256_scope="RETAINED_SOURCE_PACK" if source_sha256 else None,
        license_name=license_name,
        license_expression=license_expression,
        license_sha256=license_sha256,
        license_evidence_locator="https://example.invalid/repo/LICENSE",
        allowed_use=("REFERENCE", "ANALYSIS", "CLEAN_ROOM_REIMPLEMENTATION"),
        forbidden_use=("AUTOMATIC_RUNTIME_DEPENDENCY", "AUTOMATIC_PROMOTION"),
        epistemic_ceiling=MechanismStatus.A1_MECHANISM_HYPOTHESIS,
        architecture_claims=(_claim(),),
        retained_reference_paths=tuple(blob.relative_path for blob in descriptors),
        blob_descriptors=descriptors,
        mechanism_candidates=mechanisms,
        blockers=(),
    )


def _closed_record() -> SourceRecord:
    return SourceRecord.create(
        source_id="closed-model-public",
        publisher="Closed Publisher",
        system_name="Closed Model",
        version="public-docs-2026-08-13",
        source_class=SourceClass.CLOSED_BEHAVIORAL_ONLY,
        ingestion_status=IngestionStatus.REGISTERED_ONLY,
        official_source_locator="https://example.invalid/docs",
        exact_commit_or_release="public-docs-retrieved-2026-08-13",
        retrieved_at="2026-08-13T12:00:00Z",
        source_sha256=None,
        source_sha256_scope=None,
        license_name="Proprietary public documentation",
        license_expression="LicenseRef-Proprietary-Public-Documentation",
        license_sha256=None,
        license_evidence_locator="https://example.invalid/terms",
        allowed_use=("BEHAVIORAL_REFERENCE",),
        forbidden_use=("INTERNAL_ARCHITECTURE_FACT", "RUNTIME_DEPENDENCY"),
        epistemic_ceiling=MechanismStatus.A1_MECHANISM_HYPOTHESIS,
        architecture_claims=(_claim("public-capability-claim"),),
        retained_reference_paths=(),
        blob_descriptors=(),
        mechanism_candidates=(_mechanism("behavioral-routing-hypothesis"),),
        blockers=(),
    )


def test_source_pack_has_literal_digest_and_is_descriptor_order_independent():
    left = SourcePack.create(
        source_id="example-model-deadbee",
        exact_commit_or_release=REVISION,
        blob_descriptors=(_readme_blob(), _license_blob()),
    )
    right = SourcePack.create(
        source_id="example-model-deadbee",
        exact_commit_or_release=REVISION,
        blob_descriptors=(_license_blob(), _readme_blob()),
    )

    assert left.pack_root_sha256 == "8f47683846ab3f50001371c24e44cd77a29c4372d9464d450237c94c92a50ae5"
    assert right.pack_root_sha256 == left.pack_root_sha256
    assert tuple(blob.relative_path for blob in left.blob_descriptors) == ("LICENSE", "README.md")
    assert SourcePack.from_dict(left.as_dict()) == left


def test_source_record_normalizes_unordered_fields_and_round_trips():
    first = _permissive_record(
        descriptors=(_readme_blob(), _license_blob()),
        mechanisms=(_mechanism("z-mechanism"), _mechanism("a-mechanism")),
    )
    value = first.as_dict()
    value["allowed_use"] = list(reversed(value["allowed_use"]))
    value["blob_descriptors"] = list(reversed(value["blob_descriptors"]))
    value["mechanism_candidates"] = list(reversed(value["mechanism_candidates"]))
    value.pop("record_sha256")
    second = SourceRecord.create(**value)

    assert second.record_sha256 == first.record_sha256
    assert SourceRecord.from_dict(first.as_dict()) == first


def test_source_record_tamper_is_detected():
    record = _permissive_record()
    value = record.as_dict()
    value["system_name"] = "Tampered Model"

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        SourceRecord.from_dict(value)

    assert exc.value.code == "HASH_MISMATCH"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ({"source_class": ""}, "SOURCE_CLASS_REQUIRED"),
        ({"exact_revision": ""}, "UNPINNED_SOURCE_REVISION"),
        ({"license_name": ""}, "LICENSE_CLASSIFICATION_REQUIRED"),
        ({"license_expression": ""}, "LICENSE_CLASSIFICATION_REQUIRED"),
        ({"license_sha256": None}, "LICENSE_EVIDENCE_REQUIRED"),
        ({"descriptors": (), "source_sha256": None, "license_sha256": None}, "PERMISSIVE_PACK_EMPTY"),
    ),
)
def test_permissive_sources_fail_closed_on_missing_classification_or_evidence(mutation, expected_code):
    with pytest.raises(ArchitectureSourceValidationError) as exc:
        _permissive_record(**mutation)

    assert exc.value.code == expected_code


def test_registered_only_source_cannot_claim_a_retained_source_digest():
    with pytest.raises(ArchitectureSourceValidationError) as exc:
        _permissive_record(
            source_class=SourceClass.RESTRICTED_REFERENCE,
            ingestion_status=IngestionStatus.REGISTERED_ONLY,
            descriptors=(),
            source_sha256="c" * 64,
            license_sha256=None,
        )

    assert exc.value.code == "REGISTERED_ONLY_SOURCE_DIGEST_FORBIDDEN"


def test_closed_behavioral_source_cannot_retain_foreign_source_bytes():
    value = _closed_record().as_dict()
    value.pop("record_sha256")
    value["ingestion_status"] = "INGESTED"
    value["source_sha256"] = "c" * 64
    value["source_sha256_scope"] = "RETAINED_SOURCE_PACK"
    value["license_sha256"] = LICENSE_DIGEST
    value["retained_reference_paths"] = ["model.py"]
    value["blob_descriptors"] = [
        BlobDescriptor.create(
            media_type="text/x-python",
            digest="c" * 64,
            size=10,
            relative_path="model.py",
        ).as_dict()
    ]

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        SourceRecord.create(**value)

    assert exc.value.code == "CLOSED_SOURCE_BYTES_FORBIDDEN"


def test_slice_three_rejects_a2_or_a3_mechanism_status():
    with pytest.raises(ArchitectureSourceValidationError) as exc:
        MechanismCandidate.create(
            mechanism_id="premature-assimilation",
            status="A2_TRANSFERABLE",
            semantic_definition="An untested mechanism.",
            source_fact_boundary="Only a publisher claim exists.",
            hypothesized_effect="Unknown.",
            falsification_test="Not yet run.",
        )

    assert exc.value.code == "MECHANISM_CEILING_EXCEEDED"


@pytest.mark.parametrize(
    ("path", "expected_code"),
    (
        ("/absolute/LICENSE", "PATH_NOT_RELATIVE"),
        ("../escape/LICENSE", "PATH_ESCAPE"),
        ("nested/../../escape", "PATH_ESCAPE"),
    ),
)
def test_blob_descriptor_rejects_paths_that_escape_the_source_pack(path, expected_code):
    with pytest.raises(ArchitectureSourceValidationError) as exc:
        BlobDescriptor.create(
            media_type="text/plain",
            digest="d" * 64,
            size=1,
            relative_path=path,
        )

    assert exc.value.code == expected_code


def test_registry_snapshot_is_order_independent_and_requires_ingested_pack():
    permissive = _permissive_record()
    closed = _closed_record()
    pack = SourcePack.create(
        source_id=permissive.source_id,
        exact_commit_or_release=permissive.exact_commit_or_release,
        blob_descriptors=permissive.blob_descriptors,
    )

    left = SourceRegistry.create(records=(permissive, closed), packs=(pack,))
    right = SourceRegistry.create(records=(closed, permissive), packs=(pack,))

    assert left.registry_snapshot_sha256 == right.registry_snapshot_sha256
    assert SourceRegistry.from_dict(left.as_dict()) == left

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        SourceRegistry.create(records=(permissive, closed), packs=())
    assert exc.value.code == "VAULT_BLOB_MISSING"


def test_pack_hash_changes_when_a_descriptor_digest_changes():
    original = SourcePack.create(
        source_id="example-model-deadbee",
        exact_commit_or_release=REVISION,
        blob_descriptors=(_license_blob(), _readme_blob()),
    )
    changed_blob = replace(_readme_blob(), digest="c" * 64)
    changed = SourcePack.create(
        source_id="example-model-deadbee",
        exact_commit_or_release=REVISION,
        blob_descriptors=(_license_blob(), changed_blob),
    )

    assert changed.pack_root_sha256 != original.pack_root_sha256
