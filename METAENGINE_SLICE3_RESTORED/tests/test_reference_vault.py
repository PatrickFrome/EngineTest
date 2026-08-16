from __future__ import annotations

import os
from pathlib import Path

import pytest

from metaengine.architecture_sources import ArchitectureSourceValidationError
from metaengine.reference_vault import (
    ReferenceVault,
    StagedSourceFile,
    VaultLimits,
    VaultVerificationReceipt,
)

REVISION = "1" * 40
LICENSE_SHA256 = "adc37366f403835c1470ab2df93d3837d4719372fc1ef8593d922e06f033f8b2"
README_SHA256 = "3a5e74f672ab6c76befef92d7c7987060e39d089dbd6564d4c8705f048e47b4c"
PACK_SHA256 = "5948665b51ee649790cc9fac8c56fa5b01935bf3a31e4063d2e3b8cd70f7ebc6"


def _stage_files(tmp_path: Path) -> tuple[StagedSourceFile, StagedSourceFile]:
    staging = tmp_path / "staging"
    staging.mkdir()
    license_path = staging / "LICENSE"
    readme_path = staging / "README.md"
    license_path.write_bytes(b"MIT\n")
    readme_path.write_bytes(b"# Model\n")
    return (
        StagedSourceFile(
            path=readme_path,
            relative_path="README.md",
            media_type="text/markdown",
        ),
        StagedSourceFile(
            path=license_path,
            relative_path="LICENSE",
            media_type="text/plain",
        ),
    )


def _ingest_fixture(tmp_path: Path):
    vault = ReferenceVault(tmp_path / "reference-vault")
    pack = vault.ingest(
        source_id="fixture-source",
        exact_commit_or_release=REVISION,
        files=_stage_files(tmp_path),
    )
    return vault, pack


def test_ingest_stores_exact_bytes_at_literal_content_addresses_and_is_idempotent(tmp_path):
    files = _stage_files(tmp_path)
    vault = ReferenceVault(tmp_path / "reference-vault")

    first = vault.ingest(
        source_id="fixture-source",
        exact_commit_or_release=REVISION,
        files=files,
    )
    second = vault.ingest(
        source_id="fixture-source",
        exact_commit_or_release=REVISION,
        files=tuple(reversed(files)),
    )

    assert first.pack_root_sha256 == PACK_SHA256
    assert second == first
    assert vault.blob_path(LICENSE_SHA256).read_bytes() == b"MIT\n"
    assert vault.blob_path(README_SHA256).read_bytes() == b"# Model\n"
    assert tuple(blob.relative_path for blob in first.blob_descriptors) == ("LICENSE", "README.md")

    verification = vault.verify(first)
    assert verification.status == "PASS"
    assert verification.findings == ()
    assert verification.verified_blob_count == 2
    assert verification.verified_total_bytes == 12
    assert VaultVerificationReceipt.from_dict(verification.as_dict()) == verification


def test_verification_reports_altered_and_missing_blobs_without_passing(tmp_path):
    vault, pack = _ingest_fixture(tmp_path)
    license_blob = vault.blob_path(LICENSE_SHA256)
    license_blob.chmod(0o644)
    license_blob.write_bytes(b"changed")
    vault.blob_path(README_SHA256).unlink()

    result = vault.verify(pack)

    assert result.status == "FAIL"
    assert tuple((finding.code, finding.relative_path) for finding in result.findings) == (
        ("HASH_MISMATCH", "LICENSE"),
        ("VAULT_BLOB_MISSING", "README.md"),
    )
    assert result.verified_blob_count == 0


def test_ingest_refuses_to_replace_a_corrupt_preexisting_content_address(tmp_path):
    files = _stage_files(tmp_path)
    vault = ReferenceVault(tmp_path / "reference-vault")
    target = vault.blob_path(LICENSE_SHA256)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not the licensed bytes")

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        vault.ingest(
            source_id="fixture-source",
            exact_commit_or_release=REVISION,
            files=files,
        )

    assert exc.value.code == "HASH_MISMATCH"
    assert target.read_bytes() == b"not the licensed bytes"


def test_ingest_recomputes_and_enforces_the_pinned_git_blob_identity(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"safe")
    correct = ReferenceVault(tmp_path / "correct-vault").ingest(
        source_id="fixture-source",
        exact_commit_or_release=REVISION,
        files=(
            StagedSourceFile(
                source,
                "source.txt",
                "text/plain",
                git_blob_id="b9f5b7439c5d270594d262ba47697bc17dcdc741",
            ),
        ),
    )
    assert correct.blob_descriptors[0].git_blob_id == "b9f5b7439c5d270594d262ba47697bc17dcdc741"

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        ReferenceVault(tmp_path / "wrong-vault").ingest(
            source_id="fixture-source",
            exact_commit_or_release=REVISION,
            files=(
                StagedSourceFile(
                    source,
                    "source.txt",
                    "text/plain",
                    git_blob_id="a" * 40,
                ),
            ),
        )

    assert exc.value.code == "GIT_BLOB_ID_MISMATCH"
    assert not (tmp_path / "wrong-vault" / "blobs").exists()


@pytest.mark.parametrize(
    ("relative_path", "expected_code"),
    (
        ("/absolute/LICENSE", "PATH_NOT_RELATIVE"),
        ("../escape/LICENSE", "PATH_ESCAPE"),
    ),
)
def test_ingest_rejects_unsafe_retained_paths(tmp_path, relative_path, expected_code):
    source = tmp_path / "source.txt"
    source.write_text("safe")
    vault = ReferenceVault(tmp_path / "reference-vault")

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        vault.ingest(
            source_id="fixture-source",
            exact_commit_or_release=REVISION,
            files=(StagedSourceFile(source, relative_path, "text/plain"),),
        )

    assert exc.value.code == expected_code


def test_ingest_rejects_symlink_and_special_staged_files(tmp_path):
    regular = tmp_path / "regular.txt"
    regular.write_text("safe")
    symlink = tmp_path / "linked.txt"
    symlink.symlink_to(regular)
    fifo = tmp_path / "source.fifo"
    os.mkfifo(fifo)
    vault = ReferenceVault(tmp_path / "reference-vault")

    for path in (symlink, fifo):
        with pytest.raises(ArchitectureSourceValidationError) as exc:
            vault.ingest(
                source_id="fixture-source",
                exact_commit_or_release=REVISION,
                files=(StagedSourceFile(path, path.name, "text/plain"),),
            )
        assert exc.value.code == "NON_REGULAR_FILE"


@pytest.mark.parametrize(
    ("limits", "expected_code"),
    (
        (VaultLimits(max_files=1, max_total_bytes=100, max_file_bytes=100), "FILE_COUNT_LIMIT_EXCEEDED"),
        (VaultLimits(max_files=2, max_total_bytes=11, max_file_bytes=100), "BYTE_LIMIT_EXCEEDED"),
        (VaultLimits(max_files=2, max_total_bytes=100, max_file_bytes=7), "BYTE_LIMIT_EXCEEDED"),
    ),
)
def test_ingest_enforces_file_count_and_byte_budgets(tmp_path, limits, expected_code):
    vault = ReferenceVault(tmp_path / "reference-vault")

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        vault.ingest(
            source_id="fixture-source",
            exact_commit_or_release=REVISION,
            files=_stage_files(tmp_path),
            limits=limits,
        )

    assert exc.value.code == expected_code


@pytest.mark.parametrize(
    "secret_bytes",
    (
        b"-----BEGIN " + b"PRIVATE KEY-----\nfake-test-material",
        b"sk-proj-" + b"FAKEFAKEFAKEFAKEFAKEFAKE",
        b"postgresql://test_user:" + b"test_password@example.invalid/db",
    ),
)
def test_ingest_fails_closed_on_secret_like_bytes(tmp_path, secret_bytes):
    source = tmp_path / "unsafe.txt"
    source.write_bytes(secret_bytes)
    vault = ReferenceVault(tmp_path / "reference-vault")

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        vault.ingest(
            source_id="fixture-source",
            exact_commit_or_release=REVISION,
            files=(StagedSourceFile(source, "unsafe.txt", "text/plain"),),
        )

    assert exc.value.code == "SECRET_LIKE_CONTENT"
    assert not (tmp_path / "reference-vault" / "blobs").exists()


def test_verification_receipt_detects_its_own_tampering(tmp_path):
    vault, pack = _ingest_fixture(tmp_path)
    value = vault.verify(pack).as_dict()
    value["verified_total_bytes"] = 999

    with pytest.raises(ArchitectureSourceValidationError) as exc:
        VaultVerificationReceipt.from_dict(value)

    assert exc.value.code == "HASH_MISMATCH"
