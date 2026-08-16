"""METAENGINE-1-SLICE-3 — content-addressed Reference Vault.

Stores foreign source *bytes* as inert content-addressed blobs **outside**
MetaEngine Core/CONTROL.  The tracked project keeps only small metadata
(hashes, provenance, license metadata) so that no direct runtime dependency
on a foreign repository is created.

Layout::

    reference_vault/<sha256[:2]>/<sha256>   # the bytes
    research/architecture_library/...      # tracked metadata only

Constitutional guarantees:

* ``CLOSED_BEHAVIORAL_ONLY`` sources may **not** have stored bytes.
* ``PERMISSIVE_CODE`` stored bytes require a verified ``license_sha256``.
* Every stored blob is re-hashed on verify; corruption raises
  ``VAULT_BYTE_HASH_MISMATCH``.
* A non-stored entry (download blocked) carries an explicit ``blocker_reason``
  — it is never silently omitted (``PRESERVE_ABSTENTION``).
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .source_registry import SourceClass
from .util import canonical_hash, sha256_bytes


REFERENCE_VAULT_VERSION = "METAENGINE-REFERENCE-VAULT-1"


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(ch in string.hexdigits for ch in value)


def _text(value: object, code: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(code)
    return result


def _normalize_optional_hash(value: object, code: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not _is_hex(text, 64):
        raise ValueError(code)
    return text


# ---------------------------------------------------------------------------
# ReferenceVaultEntry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceVaultEntry:
    content_sha256: str
    size: int
    source_record_id: str
    source_class: SourceClass
    license_name: str
    license_sha256: str | None
    stored: bool
    blocker_reason: str | None

    @classmethod
    def create(
        cls,
        *,
        content_sha256: str,
        size: int,
        source_record_id: str,
        source_class: SourceClass | str,
        license_name: str,
        license_sha256: str | None,
        stored: bool,
        blocker_reason: str | None,
    ) -> "ReferenceVaultEntry":
        source_class = SourceClass(source_class)
        content_sha256 = _text(content_sha256, "VAULT_CONTENT_HASH_REQUIRED")
        if not _is_hex(content_sha256, 64):
            raise ValueError("VAULT_CONTENT_HASH_INVALID")
        size = int(size)
        if size < 0:
            raise ValueError("VAULT_SIZE_INVALID")
        license_sha256 = _normalize_optional_hash(license_sha256, "VAULT_LICENSE_HASH_INVALID")

        # Fail-closed license / source-class enforcement.
        if source_class is SourceClass.CLOSED_BEHAVIORAL_ONLY and stored:
            raise ValueError("CLOSED_BEHAVIORAL_ONLY_CANNOT_BE_STORED")
        if (
            source_class is SourceClass.PERMISSIVE_CODE
            and stored
            and not license_sha256
        ):
            raise ValueError("PERMISSIVE_STORED_REQUIRES_LICENSE_HASH")
        if stored and blocker_reason is not None:
            raise ValueError("STORED_MUST_NOT_HAVE_BLOCKER")
        if not stored and not blocker_reason:
            raise ValueError("UNSTORED_REQUIRES_BLOCKER_REASON")
        if not stored and size != 0:
            raise ValueError("UNSTORED_SIZE_MUST_BE_ZERO")

        item = cls(
            content_sha256=content_sha256,
            size=size,
            source_record_id=_text(source_record_id, "VAULT_SOURCE_RECORD_ID_REQUIRED"),
            source_class=source_class,
            license_name=_text(license_name, "VAULT_LICENSE_NAME_REQUIRED"),
            license_sha256=license_sha256,
            stored=bool(stored),
            blocker_reason=_text(blocker_reason, "VAULT_BLOCKER_REASON_REQUIRED")
            if blocker_reason
            else None,
        )
        item.validate()
        return item

    def validate(self) -> None:
        if not _is_hex(self.content_sha256, 64):
            raise ValueError("VAULT_CONTENT_HASH_INVALID")
        SourceClass(self.source_class)
        if self.source_class is SourceClass.CLOSED_BEHAVIORAL_ONLY and self.stored:
            raise ValueError("CLOSED_BEHAVIORAL_ONLY_CANNOT_BE_STORED")
        if (
            self.source_class is SourceClass.PERMISSIVE_CODE
            and self.stored
            and not self.license_sha256
        ):
            raise ValueError("PERMISSIVE_STORED_REQUIRES_LICENSE_HASH")
        if self.stored and self.blocker_reason is not None:
            raise ValueError("STORED_MUST_NOT_HAVE_BLOCKER")
        if not self.stored:
            if not self.blocker_reason:
                raise ValueError("UNSTORED_REQUIRES_BLOCKER_REASON")
            if self.size != 0:
                raise ValueError("UNSTORED_SIZE_MUST_BE_ZERO")

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "vault_version": REFERENCE_VAULT_VERSION,
            "content_sha256": self.content_sha256,
            "size": self.size,
            "source_record_id": self.source_record_id,
            "source_class": self.source_class.value,
            "license_name": self.license_name,
            "license_sha256": self.license_sha256,
            "stored": self.stored,
            "blocker_reason": self.blocker_reason,
        }

    @property
    def entry_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "entry_hash": self.entry_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReferenceVaultEntry":
        item = cls(
            content_sha256=str(value["content_sha256"]),
            size=int(value["size"]),
            source_record_id=str(value["source_record_id"]),
            source_class=SourceClass(str(value["source_class"])),
            license_name=str(value["license_name"]),
            license_sha256=value.get("license_sha256"),
            stored=bool(value["stored"]),
            blocker_reason=value.get("blocker_reason"),
        )
        item.validate()
        claimed = value.get("entry_hash")
        if claimed is not None and str(claimed) != item.entry_hash:
            raise ValueError("VAULT_ENTRY_HASH_MISMATCH")
        return item


# ---------------------------------------------------------------------------
# ReferenceVault (collection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceVault:
    vault_version: str
    entries: tuple[ReferenceVaultEntry, ...]

    @classmethod
    def create(cls, entries: Iterable[ReferenceVaultEntry]) -> "ReferenceVault":
        ordered = tuple(
            sorted(entries, key=lambda e: (e.source_record_id, e.content_sha256))
        )
        seen: set[tuple[str, str]] = set()
        for entry in ordered:
            key = (entry.source_record_id, entry.content_sha256)
            if key in seen:
                raise ValueError("VAULT_ENTRY_DUPLICATE")
            seen.add(key)
            entry.validate()
        return cls(vault_version=REFERENCE_VAULT_VERSION, entries=ordered)

    def payload(self) -> dict[str, Any]:
        return {
            "vault_version": self.vault_version,
            "entries": [entry.as_dict() for entry in self.entries],
        }

    @property
    def vault_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "vault_hash": self.vault_hash}

    def verify(self) -> bool:
        for entry in self.entries:
            entry.validate()
            if canonical_hash(entry.payload()) != entry.entry_hash:
                return False
        return canonical_hash(self.payload()) == self.vault_hash

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReferenceVault":
        entries = tuple(
            ReferenceVaultEntry.from_dict(item) for item in value.get("entries", ())
        )
        vault = cls(
            vault_version=str(value.get("vault_version", REFERENCE_VAULT_VERSION)),
            entries=entries,
        )
        claimed = value.get("vault_hash")
        if claimed is not None and str(claimed) != vault.vault_hash:
            raise ValueError("VAULT_HASH_MISMATCH")
        return vault

    # ------------------------------------------------------------------
    # Content-addressed byte storage (bytes live OUTSIDE metaengine/ Core)
    # ------------------------------------------------------------------

    @staticmethod
    def blob_path(vault_root: Path, content_sha256: str) -> Path:
        if not _is_hex(content_sha256, 64):
            raise ValueError("VAULT_CONTENT_HASH_INVALID")
        return Path(vault_root) / content_sha256[:2] / content_sha256

    @staticmethod
    def store_bytes(
        vault_root: str | Path, entry: ReferenceVaultEntry, data: bytes
    ) -> Path:
        """Write ``data`` to the content-addressed layout and verify the hash.

        Raises ``VAULT_STORE_HASH_MISMATCH`` if the bytes do not match the
        entry's declared ``content_sha256``.
        """
        if not entry.stored:
            raise ValueError("VAULT_STORE_ENTRY_NOT_STORED")
        digest = sha256_bytes(data)
        if digest != entry.content_sha256:
            raise ValueError("VAULT_STORE_HASH_MISMATCH")
        path = ReferenceVault.blob_path(Path(vault_root), entry.content_sha256)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    @staticmethod
    def verify_bytes(
        vault_root: str | Path, entries: Iterable[ReferenceVaultEntry]
    ) -> bool:
        """Re-read every stored entry and confirm the on-disk hash matches."""
        root = Path(vault_root)
        for entry in entries:
            if not entry.stored:
                continue
            path = ReferenceVault.blob_path(root, entry.content_sha256)
            if not path.is_file():
                raise ValueError("VAULT_BYTE_MISSING")
            digest = sha256_bytes(path.read_bytes())
            if digest != entry.content_sha256:
                raise ValueError("VAULT_BYTE_HASH_MISMATCH")
            if path.stat().st_size != entry.size:
                raise ValueError("VAULT_BYTE_SIZE_MISMATCH")
        return True
