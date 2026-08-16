from __future__ import annotations

import json

import pytest

from metaengine.reference_vault import (
    ReferenceVault,
    ReferenceVaultEntry,
    REFERENCE_VAULT_VERSION,
)
from metaengine.source_registry import SourceClass
from metaengine.util import sha256_bytes


VALID_LICENSE_HASH = "a" * 64


def _entry(
    *,
    content_sha256: str = "f" * 64,
    source_record_id: str = "src.glm.1",
    source_class: SourceClass = SourceClass.PERMISSIVE_CODE,
    stored: bool = True,
    blocker_reason: str | None = None,
    license_sha256: str | None = VALID_LICENSE_HASH,
) -> ReferenceVaultEntry:
    return ReferenceVaultEntry.create(
        content_sha256=content_sha256,
        size=11 if stored else 0,
        source_record_id=source_record_id,
        source_class=source_class,
        license_name="MIT",
        license_sha256=license_sha256,
        stored=stored,
        blocker_reason=blocker_reason,
    )


# ---------------------------------------------------------------------------
# Entry validation / fail-closed
# ---------------------------------------------------------------------------


def test_entry_create_and_hash():
    e = _entry()
    payload = e.payload()
    assert payload["content_sha256"] == "f" * 64
    assert e.entry_hash


def test_closed_behavioral_only_entry_cannot_be_stored():
    with pytest.raises(ValueError, match="CLOSED_BEHAVIORAL_ONLY_CANNOT_BE_STORED"):
        _entry(source_class=SourceClass.CLOSED_BEHAVIORAL_ONLY, stored=True)


def test_closed_behavioral_only_unstored_entry_records_blocker():
    e = _entry(
        source_class=SourceClass.CLOSED_BEHAVIORAL_ONLY,
        stored=False,
        blocker_reason="CLOSED_NO_SOURCE_BYTES",
        license_sha256=None,
        license_name="Proprietary",
    ) if False else ReferenceVaultEntry.create(
        content_sha256="0" * 64,
        size=0,
        source_record_id="src.claude.1",
        source_class=SourceClass.CLOSED_BEHAVIORAL_ONLY,
        license_name="Proprietary",
        license_sha256=None,
        stored=False,
        blocker_reason="CLOSED_NO_SOURCE_BYTES",
    )
    assert e.stored is False
    assert e.blocker_reason == "CLOSED_NO_SOURCE_BYTES"


def test_permissive_stored_entry_requires_license_hash():
    with pytest.raises(ValueError, match="PERMISSIVE_STORED_REQUIRES_LICENSE_HASH"):
        ReferenceVaultEntry.create(
            content_sha256="f" * 64,
            size=11,
            source_record_id="src.glm.1",
            source_class=SourceClass.PERMISSIVE_CODE,
            license_name="MIT",
            license_sha256=None,  # missing
            stored=True,
            blocker_reason=None,
        )


def test_unstored_entry_requires_blocker_reason():
    with pytest.raises(ValueError, match="UNSTORED_REQUIRES_BLOCKER_REASON"):
        ReferenceVaultEntry.create(
            content_sha256="f" * 64,
            size=0,
            source_record_id="src.glm.1",
            source_class=SourceClass.PERMISSIVE_CODE,
            license_name="MIT",
            license_sha256=None,
            stored=False,
            blocker_reason=None,  # missing
        )


def test_stored_entry_forbids_blocker_reason():
    with pytest.raises(ValueError, match="STORED_MUST_NOT_HAVE_BLOCKER"):
        _entry(stored=True, blocker_reason="should-not-be-here")


def test_entry_from_dict_revalidates_hash():
    e = _entry()
    restored = ReferenceVaultEntry.from_dict(e.as_dict())
    assert restored.entry_hash == e.entry_hash
    tampered = e.as_dict()
    tampered["entry_hash"] = "0" * 64
    with pytest.raises(ValueError, match="VAULT_ENTRY_HASH_MISMATCH"):
        ReferenceVaultEntry.from_dict(tampered)


# ---------------------------------------------------------------------------
# Vault collection
# ---------------------------------------------------------------------------


def test_vault_create_deterministic_and_hashed():
    e1 = _entry(content_sha256="1" * 64, source_record_id="src.a")
    e2 = _entry(content_sha256="2" * 64, source_record_id="src.b")
    v1 = ReferenceVault.create((e1, e2))
    v2 = ReferenceVault.create((e2, e1))
    assert v1.vault_hash == v2.vault_hash
    assert v1.vault_version == REFERENCE_VAULT_VERSION


def test_vault_rejects_duplicate_content_for_same_source():
    e1 = _entry(content_sha256="3" * 64, source_record_id="src.a")
    e2 = _entry(content_sha256="3" * 64, source_record_id="src.a")
    with pytest.raises(ValueError, match="VAULT_ENTRY_DUPLICATE"):
        ReferenceVault.create((e1, e2))


def test_vault_from_dict_roundtrip_and_verify():
    e1 = _entry(content_sha256="4" * 64, source_record_id="src.a")
    e2 = _entry(content_sha256="5" * 64, source_record_id="src.b")
    vault = ReferenceVault.create((e1, e2))
    blob = json.dumps(vault.as_dict(), sort_keys=True)
    restored = ReferenceVault.from_dict(json.loads(blob))
    assert restored.vault_hash == vault.vault_hash
    assert restored.verify() is True


# ---------------------------------------------------------------------------
# Content-addressed byte storage (bytes live OUTSIDE metaengine/ Core)
# ---------------------------------------------------------------------------


def test_vault_store_bytes_writes_content_addressed_and_verifies(tmp_path):
    vault_root = tmp_path / "reference_vault"
    data = b"foreign-source-bytes"
    digest = sha256_bytes(data)
    entry = ReferenceVaultEntry.create(
        content_sha256=digest,
        size=len(data),
        source_record_id="src.glm.1",
        source_class=SourceClass.PERMISSIVE_CODE,
        license_name="MIT",
        license_sha256=VALID_LICENSE_HASH,
        stored=True,
        blocker_reason=None,
    )
    path = ReferenceVault.store_bytes(vault_root, entry, data)
    # content-addressed layout: <root>/<sha[:2]>/<sha>
    assert path == vault_root / digest[:2] / digest
    assert path.is_file()
    assert path.read_bytes() == data
    # verify reads back and checks the hash
    assert ReferenceVault.verify_bytes(vault_root, [entry]) is True


def test_vault_verify_bytes_detects_corruption(tmp_path):
    vault_root = tmp_path / "reference_vault"
    data = b"foreign-source-bytes"
    digest = sha256_bytes(data)
    entry = ReferenceVaultEntry.create(
        content_sha256=digest,
        size=len(data),
        source_record_id="src.glm.1",
        source_class=SourceClass.PERMISSIVE_CODE,
        license_name="MIT",
        license_sha256=VALID_LICENSE_HASH,
        stored=True,
        blocker_reason=None,
    )
    path = ReferenceVault.store_bytes(vault_root, entry, data)
    path.write_bytes(b"corrupted-bytes")
    with pytest.raises(ValueError, match="VAULT_BYTE_HASH_MISMATCH"):
        ReferenceVault.verify_bytes(vault_root, [entry])


def test_vault_store_bytes_rejects_hash_mismatch(tmp_path):
    vault_root = tmp_path / "reference_vault"
    data = b"foreign-source-bytes"
    wrong_digest = "9" * 64
    entry = ReferenceVaultEntry.create(
        content_sha256=wrong_digest,
        size=len(data),
        source_record_id="src.glm.1",
        source_class=SourceClass.PERMISSIVE_CODE,
        license_name="MIT",
        license_sha256=VALID_LICENSE_HASH,
        stored=True,
        blocker_reason=None,
    )
    with pytest.raises(ValueError, match="VAULT_STORE_HASH_MISMATCH"):
        ReferenceVault.store_bytes(vault_root, entry, data)
