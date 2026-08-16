"""METAENGINE-1-SLICE-3 — Architecture Source Registry.

A provider/model-independent, content-addressed registry of external
architecture *sources*.  Each source pins exact upstream release/commit
identity, source and license hashes, source class, allowed use, retained
reference paths, architecture claims, and mechanism candidates.

Design constraints (see ``docs/superpowers/specs/2026-08-13-metaengine-1-
constitutional-assimilation-design.md`` section 9 and the Slice-3 pre-step
review):

* License / source-class enforcement is **fail-closed**.  No source enters
  the library without an explicit ``source_class`` and ``license_name``.
* ``CLOSED_BEHAVIORAL_ONLY`` sources may **not** retain source bytes.
* ``PERMISSIVE_CODE`` retention requires a verified ``license_sha256``.
* A download that cannot be performed or verified is recorded as an explicit
  ``UNOBSERVED`` ingestion blocker — never silently converted to a fabricated
  hash.  This preserves the ``PRESERVE_ABSTENTION`` constitutional invariant.
* Records are content-addressed via :func:`metaengine.util.canonical_hash`;
  ``from_dict`` re-verifies the claimed hash.

This module stores only small tracked metadata.  Foreign source *bytes* live
in the separate content-addressed Reference Vault (see
:mod:`metaengine.reference_vault`), outside MetaEngine Core/CONTROL.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .util import canonical_hash


SOURCE_REGISTRY_VERSION = "METAENGINE-SOURCE-REGISTRY-1"


class SourceClass(str, Enum):
    """Mandatory source classification (spec section 9.2)."""

    PERMISSIVE_CODE = "PERMISSIVE_CODE"
    RESTRICTED_REFERENCE = "RESTRICTED_REFERENCE"
    CLOSED_BEHAVIORAL_ONLY = "CLOSED_BEHAVIORAL_ONLY"


class IngestionStatus(str, Enum):
    """Evidence-bound ingestion status.  Preserves abstention."""

    OBSERVED = "OBSERVED"
    UNOBSERVED = "UNOBSERVED"


# ---------------------------------------------------------------------------
# Validation helpers (mirror the ResourceDescriptor conventions)
# ---------------------------------------------------------------------------


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(ch in string.hexdigits for ch in value)


def _text(value: object, code: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(code)
    return result


def _strings(values: Iterable[object], *, code: str) -> tuple[str, ...]:
    return tuple(sorted({_text(value, code) for value in values}))


# ---------------------------------------------------------------------------
# ArchitectureClaim
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArchitectureClaim:
    claim_id: str
    statement: str
    evidence_kind: str
    evidence_refs: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        claim_id: str,
        statement: str,
        evidence_kind: str,
        evidence_refs: Iterable[str],
    ) -> "ArchitectureClaim":
        refs = _strings(evidence_refs, code="CLAIM_EVIDENCE_REF_REQUIRED")
        if not refs:
            raise ValueError("CLAIM_EVIDENCE_REF_REQUIRED")
        return cls(
            claim_id=_text(claim_id, "CLAIM_ID_REQUIRED"),
            statement=_text(statement, "CLAIM_STATEMENT_REQUIRED"),
            evidence_kind=_text(evidence_kind, "CLAIM_EVIDENCE_KIND_REQUIRED"),
            evidence_refs=refs,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "evidence_kind": self.evidence_kind,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArchitectureClaim":
        return cls.create(
            claim_id=str(value["claim_id"]),
            statement=str(value["statement"]),
            evidence_kind=str(value["evidence_kind"]),
            evidence_refs=tuple(value.get("evidence_refs", ())),
        )

    def __eq__(self, other: object) -> bool:  # deterministic equality
        if not isinstance(other, ArchitectureClaim):
            return NotImplemented
        return self.payload() == other.payload()

    def __hash__(self) -> int:
        return hash(canonical_hash(self.payload()))


# ---------------------------------------------------------------------------
# IngestionBlocker (PRESERVE_ABSTENTION)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestionBlocker:
    """Records *why* source bytes are UNOBSERVED.

    A blocker is itself UNOBSERVED evidence: it states that a download was
    not performed/verified, never that it succeeded with a fabricated value.
    """

    status: IngestionStatus
    reason: str
    detail: str | None

    @classmethod
    def create(
        cls,
        *,
        status: IngestionStatus,
        reason: str,
        detail: str | None = None,
    ) -> "IngestionBlocker":
        status = IngestionStatus(status)
        if status is not IngestionStatus.UNOBSERVED:
            raise ValueError("BLOCKER_MUST_BE_UNOBSERVED")
        item = cls(
            status=status,
            reason=_text(reason, "BLOCKER_REASON_REQUIRED"),
            detail=str(detail).strip() if detail is not None else None,
        )
        return item

    def payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IngestionBlocker":
        return cls.create(
            status=IngestionStatus(str(value["status"])),
            reason=str(value["reason"]),
            detail=value.get("detail"),
        )


# ---------------------------------------------------------------------------
# SourceRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    publisher: str
    system_name: str
    version: str
    source_class: SourceClass
    official_source_locator: str
    exact_commit_or_release: str
    retrieved_at: str
    source_sha256: str | None
    license_name: str
    license_sha256: str | None
    allowed_use: tuple[str, ...]
    architecture_claims: tuple[ArchitectureClaim, ...]
    retained_reference_paths: tuple[str, ...]
    mechanism_candidates: tuple[str, ...]
    ingestion: IngestionStatus
    ingestion_blocker: IngestionBlocker | None

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        publisher: str,
        system_name: str,
        version: str,
        source_class: SourceClass | str,
        official_source_locator: str,
        exact_commit_or_release: str,
        retrieved_at: str,
        source_sha256: str | None,
        license_name: str,
        license_sha256: str | None,
        allowed_use: Iterable[str],
        architecture_claims: Iterable[ArchitectureClaim] = (),
        retained_reference_paths: Iterable[str] = (),
        mechanism_candidates: Iterable[str] = (),
        ingestion: IngestionStatus | str,
        ingestion_blocker: IngestionBlocker | None = None,
    ) -> "SourceRecord":
        source_class = SourceClass(source_class)
        ingestion = IngestionStatus(ingestion)

        allowed = _strings(allowed_use, code="ALLOWED_USE_REQUIRED")
        if not allowed:
            raise ValueError("ALLOWED_USE_REQUIRED")
        claims = tuple(architecture_claims)
        retained = _strings(retained_reference_paths, code="RETAINED_PATH_INVALID")
        mechanisms = _strings(mechanism_candidates, code="MECHANISM_CANDIDATE_INVALID")

        # --- license / source-class fail-closed enforcement ---
        license_name = _text(license_name, "LICENSE_NAME_REQUIRED")

        source_sha256 = _normalize_optional_hash(source_sha256, "SOURCE_HASH_INVALID")
        license_sha256 = _normalize_optional_hash(license_sha256, "LICENSE_HASH_INVALID")

        if source_class is SourceClass.CLOSED_BEHAVIORAL_ONLY and retained:
            raise ValueError("CLOSED_BEHAVIORAL_ONLY_RETENTION_FORBIDDEN")

        if (
            source_class is SourceClass.PERMISSIVE_CODE
            and retained
            and not license_sha256
        ):
            raise ValueError("PERMISSIVE_LICENSE_HASH_REQUIRED")

        # --- ingestion / abstention enforcement ---
        if ingestion is IngestionStatus.OBSERVED:
            if not source_sha256:
                raise ValueError("OBSERVED_REQUIRES_SOURCE_HASH")
            if ingestion_blocker is not None:
                raise ValueError("OBSERVED_MUST_NOT_HAVE_BLOCKER")
        else:  # UNOBSERVED
            if source_sha256:
                raise ValueError("UNOBSERVED_MUST_NOT_HAVE_SOURCE_HASH")
            if ingestion_blocker is None:
                raise ValueError("UNOBSERVED_REQUIRES_BLOCKER")

        item = cls(
            source_id=_text(source_id, "SOURCE_ID_REQUIRED"),
            publisher=_text(publisher, "SOURCE_PUBLISHER_REQUIRED"),
            system_name=_text(system_name, "SOURCE_SYSTEM_NAME_REQUIRED"),
            version=_text(version, "SOURCE_VERSION_REQUIRED"),
            source_class=source_class,
            official_source_locator=_text(
                official_source_locator, "SOURCE_LOCATOR_REQUIRED"
            ),
            exact_commit_or_release=_text(
                exact_commit_or_release, "SOURCE_COMMIT_OR_RELEASE_REQUIRED"
            ),
            retrieved_at=_text(retrieved_at, "SOURCE_RETRIEVED_AT_REQUIRED"),
            source_sha256=source_sha256,
            license_name=license_name,
            license_sha256=license_sha256,
            allowed_use=allowed,
            architecture_claims=claims,
            retained_reference_paths=retained,
            mechanism_candidates=mechanisms,
            ingestion=ingestion,
            ingestion_blocker=ingestion_blocker,
        )
        item.validate()
        return item

    def validate(self) -> None:
        # Re-check the invariants cheaply.  ``create`` already enforces them,
        # but ``from_dict`` constructs the dataclass directly so this guards it.
        _text(self.source_id, "SOURCE_ID_REQUIRED")
        _text(self.publisher, "SOURCE_PUBLISHER_REQUIRED")
        _text(self.system_name, "SOURCE_SYSTEM_NAME_REQUIRED")
        _text(self.version, "SOURCE_VERSION_REQUIRED")
        _text(self.official_source_locator, "SOURCE_LOCATOR_REQUIRED")
        _text(self.exact_commit_or_release, "SOURCE_COMMIT_OR_RELEASE_REQUIRED")
        _text(self.retrieved_at, "SOURCE_RETRIEVED_AT_REQUIRED")
        _text(self.license_name, "LICENSE_NAME_REQUIRED")
        if not self.allowed_use:
            raise ValueError("ALLOWED_USE_REQUIRED")
        SourceClass(self.source_class)
        IngestionStatus(self.ingestion)
        if self.source_sha256 is not None and not _is_hex(self.source_sha256, 64):
            raise ValueError("SOURCE_HASH_INVALID")
        if self.license_sha256 is not None and not _is_hex(self.license_sha256, 64):
            raise ValueError("LICENSE_HASH_INVALID")
        if self.source_class is SourceClass.CLOSED_BEHAVIORAL_ONLY and self.retained_reference_paths:
            raise ValueError("CLOSED_BEHAVIORAL_ONLY_RETENTION_FORBIDDEN")
        if (
            self.source_class is SourceClass.PERMISSIVE_CODE
            and self.retained_reference_paths
            and not self.license_sha256
        ):
            raise ValueError("PERMISSIVE_LICENSE_HASH_REQUIRED")
        if self.ingestion is IngestionStatus.OBSERVED:
            if not self.source_sha256:
                raise ValueError("OBSERVED_REQUIRES_SOURCE_HASH")
            if self.ingestion_blocker is not None:
                raise ValueError("OBSERVED_MUST_NOT_HAVE_BLOCKER")
        else:
            if self.source_sha256:
                raise ValueError("UNOBSERVED_MUST_NOT_HAVE_SOURCE_HASH")
            if self.ingestion_blocker is None:
                raise ValueError("UNOBSERVED_REQUIRES_BLOCKER")

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "registry_version": SOURCE_REGISTRY_VERSION,
            "source_id": self.source_id,
            "publisher": self.publisher,
            "system_name": self.system_name,
            "version": self.version,
            "source_class": self.source_class.value,
            "official_source_locator": self.official_source_locator,
            "exact_commit_or_release": self.exact_commit_or_release,
            "retrieved_at": self.retrieved_at,
            "source_sha256": self.source_sha256,
            "license_name": self.license_name,
            "license_sha256": self.license_sha256,
            "allowed_use": list(self.allowed_use),
            "architecture_claims": [claim.payload() for claim in self.architecture_claims],
            "retained_reference_paths": list(self.retained_reference_paths),
            "mechanism_candidates": list(self.mechanism_candidates),
            "ingestion": self.ingestion.value,
            "ingestion_blocker": (
                self.ingestion_blocker.payload() if self.ingestion_blocker else None
            ),
        }

    @property
    def source_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "source_hash": self.source_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceRecord":
        claims = tuple(
            ArchitectureClaim.from_dict(item)
            for item in value.get("architecture_claims", ())
        )
        blocker_raw = value.get("ingestion_blocker")
        blocker = IngestionBlocker.from_dict(blocker_raw) if blocker_raw else None
        item = cls(
            source_id=str(value["source_id"]),
            publisher=str(value["publisher"]),
            system_name=str(value["system_name"]),
            version=str(value["version"]),
            source_class=SourceClass(str(value["source_class"])),
            official_source_locator=str(value["official_source_locator"]),
            exact_commit_or_release=str(value["exact_commit_or_release"]),
            retrieved_at=str(value["retrieved_at"]),
            source_sha256=value.get("source_sha256"),
            license_name=str(value["license_name"]),
            license_sha256=value.get("license_sha256"),
            allowed_use=tuple(value.get("allowed_use", ())),
            architecture_claims=claims,
            retained_reference_paths=tuple(value.get("retained_reference_paths", ())),
            mechanism_candidates=tuple(value.get("mechanism_candidates", ())),
            ingestion=IngestionStatus(str(value["ingestion"])),
            ingestion_blocker=blocker,
        )
        item.validate()
        claimed = value.get("source_hash")
        if claimed is not None and str(claimed) != item.source_hash:
            raise ValueError("SOURCE_RECORD_HASH_MISMATCH")
        return item


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
# SourceRegistry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRegistry:
    registry_version: str
    records: tuple[SourceRecord, ...]

    @classmethod
    def create(cls, records: Iterable[SourceRecord]) -> "SourceRegistry":
        ordered = tuple(sorted(records, key=lambda r: r.source_id))
        ids = [r.source_id for r in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("SOURCE_ID_DUPLICATE")
        for record in ordered:
            record.validate()
        return cls(registry_version=SOURCE_REGISTRY_VERSION, records=ordered)

    def payload(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "records": [record.as_dict() for record in self.records],
        }

    @property
    def registry_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "registry_hash": self.registry_hash}

    def verify(self) -> bool:
        for record in self.records:
            record.validate()
            # Re-derive the hash from the payload and confirm it matches.
            if canonical_hash(record.payload()) != record.source_hash:
                return False
        return canonical_hash(self.payload()) == self.registry_hash

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceRegistry":
        records = tuple(
            SourceRecord.from_dict(item) for item in value.get("records", ())
        )
        registry = cls(
            registry_version=str(value.get("registry_version", SOURCE_REGISTRY_VERSION)),
            records=records,
        )
        claimed = value.get("registry_hash")
        if claimed is not None and str(claimed) != registry.registry_hash:
            raise ValueError("REGISTRY_HASH_MISMATCH")
        return registry
