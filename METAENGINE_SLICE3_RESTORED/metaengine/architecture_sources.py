from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, NoReturn

from .devfabric.codec import canonical_digest

REGISTRY_SCHEMA_VERSION = "ARCHITECTURE-SOURCE-REGISTRY-1"
PACK_SCHEMA_VERSION = "ARCHITECTURE-SOURCE-PACK-1"
PERMISSIVE_LICENSE_EXPRESSIONS = frozenset({"MIT", "Apache-2.0"})


class ArchitectureSourceValidationError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


class SourceClass(str, Enum):
    PERMISSIVE_CODE = "PERMISSIVE_CODE"
    RESTRICTED_REFERENCE = "RESTRICTED_REFERENCE"
    CLOSED_BEHAVIORAL_ONLY = "CLOSED_BEHAVIORAL_ONLY"


class IngestionStatus(str, Enum):
    REGISTERED_ONLY = "REGISTERED_ONLY"
    INGESTED = "INGESTED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"


class ClaimKind(str, Enum):
    SOURCE_FACT = "SOURCE_FACT"
    PUBLISHER_CLAIM = "PUBLISHER_CLAIM"
    METAENGINE_HYPOTHESIS = "METAENGINE_HYPOTHESIS"


class MechanismStatus(str, Enum):
    A0_OBSERVED = "A0_OBSERVED"
    A1_MECHANISM_HYPOTHESIS = "A1_MECHANISM_HYPOTHESIS"


_HEX_40_OR_64 = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ArchitectureSourceValidationError(code, detail)


def _text(value: object, code: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        _fail(code)
    return text


def _source_id(value: object) -> str:
    text = _text(value, "SOURCE_ID_REQUIRED")
    if not _SAFE_ID.fullmatch(text):
        _fail("SOURCE_ID_INVALID", text)
    return text


def _sha256(value: object, code: str) -> str:
    text = str(value) if value is not None else ""
    if not _HEX_64.fullmatch(text):
        _fail(code)
    return text


def _optional_sha256(value: object, code: str) -> str | None:
    if value is None:
        return None
    return _sha256(value, code)


def _enum_value(enum_type: type[Enum], value: object, code: str):
    if value is None or str(value).strip() == "":
        _fail(code)
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        _fail(code, str(value))
        raise AssertionError("unreachable") from exc


def _texts(values: Iterable[object], *, code: str, required: bool = False) -> tuple[str, ...]:
    normalized = tuple(sorted({_text(value, code) for value in values}))
    if required and not normalized:
        _fail(code)
    return normalized


def _relative_path(value: object) -> str:
    text = _text(value, "PATH_NOT_RELATIVE")
    pure = PurePosixPath(text)
    if pure.is_absolute():
        _fail("PATH_NOT_RELATIVE", text)
    if ".." in pure.parts:
        _fail("PATH_ESCAPE", text)
    if not pure.parts or any(part in {"", "."} for part in pure.parts):
        _fail("PATH_NOT_RELATIVE", text)
    return pure.as_posix()


def _retrieved_at(value: object) -> str:
    text = _text(value, "RETRIEVED_AT_REQUIRED")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        _fail("RETRIEVED_AT_INVALID", text)
        raise AssertionError("unreachable") from exc
    if parsed.tzinfo is None:
        _fail("RETRIEVED_AT_INVALID", text)
    return text


@dataclass(frozen=True)
class ArchitectureClaim:
    claim_id: str
    kind: ClaimKind
    statement: str
    evidence_locator: str

    @classmethod
    def create(
        cls,
        *,
        claim_id: str,
        kind: ClaimKind | str,
        statement: str,
        evidence_locator: str,
    ) -> ArchitectureClaim:
        return cls(
            claim_id=_source_id(claim_id),
            kind=_enum_value(ClaimKind, kind, "CLAIM_KIND_REQUIRED"),
            statement=_text(statement, "CLAIM_STATEMENT_REQUIRED"),
            evidence_locator=_text(evidence_locator, "CLAIM_EVIDENCE_LOCATOR_REQUIRED"),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ArchitectureClaim:
        return cls.create(**dict(value))

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "kind": self.kind.value,
            "statement": self.statement,
            "evidence_locator": self.evidence_locator,
        }


@dataclass(frozen=True)
class MechanismCandidate:
    mechanism_id: str
    status: MechanismStatus
    semantic_definition: str
    source_fact_boundary: str
    hypothesized_effect: str
    falsification_test: str

    @classmethod
    def create(
        cls,
        *,
        mechanism_id: str,
        status: MechanismStatus | str,
        semantic_definition: str,
        source_fact_boundary: str,
        hypothesized_effect: str,
        falsification_test: str,
    ) -> MechanismCandidate:
        parsed_status = _enum_value(MechanismStatus, status, "MECHANISM_CEILING_EXCEEDED")
        return cls(
            mechanism_id=_source_id(mechanism_id),
            status=parsed_status,
            semantic_definition=_text(semantic_definition, "MECHANISM_DEFINITION_REQUIRED"),
            source_fact_boundary=_text(source_fact_boundary, "MECHANISM_FACT_BOUNDARY_REQUIRED"),
            hypothesized_effect=_text(hypothesized_effect, "MECHANISM_EFFECT_REQUIRED"),
            falsification_test=_text(falsification_test, "MECHANISM_FALSIFICATION_TEST_REQUIRED"),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> MechanismCandidate:
        return cls.create(**dict(value))

    def as_dict(self) -> dict[str, Any]:
        return {
            "mechanism_id": self.mechanism_id,
            "status": self.status.value,
            "semantic_definition": self.semantic_definition,
            "source_fact_boundary": self.source_fact_boundary,
            "hypothesized_effect": self.hypothesized_effect,
            "falsification_test": self.falsification_test,
        }


@dataclass(frozen=True)
class BlobDescriptor:
    media_type: str
    digest_algorithm: str
    digest: str
    size: int
    relative_path: str
    git_blob_id: str | None

    @classmethod
    def create(
        cls,
        *,
        media_type: str,
        digest: str,
        size: int,
        relative_path: str,
        digest_algorithm: str = "sha256",
        git_blob_id: str | None = None,
    ) -> BlobDescriptor:
        algorithm = _text(digest_algorithm, "DIGEST_ALGORITHM_REQUIRED")
        if algorithm != "sha256":
            _fail("DIGEST_ALGORITHM_UNSUPPORTED", algorithm)
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            _fail("BLOB_SIZE_INVALID", str(size))
        if git_blob_id is not None and not _HEX_40_OR_64.fullmatch(str(git_blob_id)):
            _fail("GIT_BLOB_ID_INVALID", str(git_blob_id))
        return cls(
            media_type=_text(media_type, "MEDIA_TYPE_REQUIRED"),
            digest_algorithm=algorithm,
            digest=_sha256(digest, "BLOB_DIGEST_INVALID"),
            size=size,
            relative_path=_relative_path(relative_path),
            git_blob_id=str(git_blob_id) if git_blob_id is not None else None,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> BlobDescriptor:
        return cls.create(**dict(value))

    def as_dict(self) -> dict[str, Any]:
        return {
            "media_type": self.media_type,
            "digest_algorithm": self.digest_algorithm,
            "digest": self.digest,
            "size": self.size,
            "relative_path": self.relative_path,
            "git_blob_id": self.git_blob_id,
        }


def _descriptors(values: Iterable[BlobDescriptor | Mapping[str, Any]]) -> tuple[BlobDescriptor, ...]:
    result = tuple(
        value if isinstance(value, BlobDescriptor) else BlobDescriptor.from_dict(value)
        for value in values
    )
    ordered = tuple(sorted(result, key=lambda item: (item.relative_path, item.digest)))
    paths = tuple(item.relative_path for item in ordered)
    if len(paths) != len(set(paths)):
        _fail("DUPLICATE_REFERENCE_PATH")
    return ordered


@dataclass(frozen=True)
class SourcePack:
    pack_schema_version: str
    source_id: str
    exact_commit_or_release: str
    blob_descriptors: tuple[BlobDescriptor, ...]
    pack_root_sha256: str

    @staticmethod
    def _payload(
        *,
        pack_schema_version: str,
        source_id: str,
        exact_commit_or_release: str,
        blob_descriptors: tuple[BlobDescriptor, ...],
    ) -> dict[str, Any]:
        return {
            "pack_schema_version": pack_schema_version,
            "source_id": source_id,
            "exact_commit_or_release": exact_commit_or_release,
            "blob_descriptors": [descriptor.as_dict() for descriptor in blob_descriptors],
        }

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        exact_commit_or_release: str,
        blob_descriptors: Iterable[BlobDescriptor | Mapping[str, Any]],
        pack_schema_version: str = PACK_SCHEMA_VERSION,
    ) -> SourcePack:
        version = _text(pack_schema_version, "PACK_SCHEMA_VERSION_REQUIRED")
        if version != PACK_SCHEMA_VERSION:
            _fail("PACK_SCHEMA_VERSION_UNSUPPORTED", version)
        normalized_source_id = _source_id(source_id)
        revision = _text(exact_commit_or_release, "UNPINNED_SOURCE_REVISION")
        descriptors = _descriptors(blob_descriptors)
        payload = cls._payload(
            pack_schema_version=version,
            source_id=normalized_source_id,
            exact_commit_or_release=revision,
            blob_descriptors=descriptors,
        )
        return cls(
            pack_schema_version=version,
            source_id=normalized_source_id,
            exact_commit_or_release=revision,
            blob_descriptors=descriptors,
            pack_root_sha256=canonical_digest(payload),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourcePack:
        fields = dict(value)
        expected = fields.pop("pack_root_sha256", None)
        pack = cls.create(**fields)
        if expected != pack.pack_root_sha256:
            _fail("HASH_MISMATCH", pack.source_id)
        return pack

    def payload(self) -> dict[str, Any]:
        return self._payload(
            pack_schema_version=self.pack_schema_version,
            source_id=self.source_id,
            exact_commit_or_release=self.exact_commit_or_release,
            blob_descriptors=self.blob_descriptors,
        )

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "pack_root_sha256": self.pack_root_sha256}


def _claims(values: Iterable[ArchitectureClaim | Mapping[str, Any]]) -> tuple[ArchitectureClaim, ...]:
    result = tuple(
        value if isinstance(value, ArchitectureClaim) else ArchitectureClaim.from_dict(value)
        for value in values
    )
    ordered = tuple(sorted(result, key=lambda item: item.claim_id))
    ids = tuple(item.claim_id for item in ordered)
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_CLAIM_ID")
    return ordered


def _mechanisms(values: Iterable[MechanismCandidate | Mapping[str, Any]]) -> tuple[MechanismCandidate, ...]:
    result = tuple(
        value if isinstance(value, MechanismCandidate) else MechanismCandidate.from_dict(value)
        for value in values
    )
    ordered = tuple(sorted(result, key=lambda item: item.mechanism_id))
    ids = tuple(item.mechanism_id for item in ordered)
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_MECHANISM_ID")
    return ordered


@dataclass(frozen=True)
class SourceRecord:
    registry_schema_version: str
    source_id: str
    publisher: str
    system_name: str
    version: str
    source_class: SourceClass
    ingestion_status: IngestionStatus
    official_source_locator: str
    exact_commit_or_release: str
    retrieved_at: str
    source_sha256: str | None
    source_sha256_scope: str | None
    license_name: str
    license_expression: str
    license_sha256: str | None
    license_evidence_locator: str
    allowed_use: tuple[str, ...]
    forbidden_use: tuple[str, ...]
    epistemic_ceiling: MechanismStatus
    architecture_claims: tuple[ArchitectureClaim, ...]
    retained_reference_paths: tuple[str, ...]
    blob_descriptors: tuple[BlobDescriptor, ...]
    mechanism_candidates: tuple[MechanismCandidate, ...]
    blockers: tuple[str, ...]
    record_sha256: str

    @staticmethod
    def _payload(**fields: Any) -> dict[str, Any]:
        return {
            "registry_schema_version": fields["registry_schema_version"],
            "source_id": fields["source_id"],
            "publisher": fields["publisher"],
            "system_name": fields["system_name"],
            "version": fields["version"],
            "source_class": fields["source_class"].value,
            "ingestion_status": fields["ingestion_status"].value,
            "official_source_locator": fields["official_source_locator"],
            "exact_commit_or_release": fields["exact_commit_or_release"],
            "retrieved_at": fields["retrieved_at"],
            "source_sha256": fields["source_sha256"],
            "source_sha256_scope": fields["source_sha256_scope"],
            "license_name": fields["license_name"],
            "license_expression": fields["license_expression"],
            "license_sha256": fields["license_sha256"],
            "license_evidence_locator": fields["license_evidence_locator"],
            "allowed_use": list(fields["allowed_use"]),
            "forbidden_use": list(fields["forbidden_use"]),
            "epistemic_ceiling": fields["epistemic_ceiling"].value,
            "architecture_claims": [claim.as_dict() for claim in fields["architecture_claims"]],
            "retained_reference_paths": list(fields["retained_reference_paths"]),
            "blob_descriptors": [descriptor.as_dict() for descriptor in fields["blob_descriptors"]],
            "mechanism_candidates": [mechanism.as_dict() for mechanism in fields["mechanism_candidates"]],
            "blockers": list(fields["blockers"]),
        }

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        publisher: str,
        system_name: str,
        version: str,
        source_class: SourceClass | str,
        ingestion_status: IngestionStatus | str,
        official_source_locator: str,
        exact_commit_or_release: str,
        retrieved_at: str,
        source_sha256: str | None,
        source_sha256_scope: str | None,
        license_name: str,
        license_expression: str,
        license_sha256: str | None,
        license_evidence_locator: str,
        allowed_use: Iterable[str],
        forbidden_use: Iterable[str],
        epistemic_ceiling: MechanismStatus | str,
        architecture_claims: Iterable[ArchitectureClaim | Mapping[str, Any]],
        retained_reference_paths: Iterable[str],
        blob_descriptors: Iterable[BlobDescriptor | Mapping[str, Any]],
        mechanism_candidates: Iterable[MechanismCandidate | Mapping[str, Any]],
        blockers: Iterable[str],
        registry_schema_version: str = REGISTRY_SCHEMA_VERSION,
    ) -> SourceRecord:
        schema_version = _text(registry_schema_version, "REGISTRY_SCHEMA_VERSION_REQUIRED")
        if schema_version != REGISTRY_SCHEMA_VERSION:
            _fail("REGISTRY_SCHEMA_VERSION_UNSUPPORTED", schema_version)
        normalized_id = _source_id(source_id)
        parsed_class = _enum_value(SourceClass, source_class, "SOURCE_CLASS_REQUIRED")
        parsed_status = _enum_value(IngestionStatus, ingestion_status, "INGESTION_STATUS_INVALID")
        revision = _text(exact_commit_or_release, "UNPINNED_SOURCE_REVISION")
        license_label = _text(license_name, "LICENSE_CLASSIFICATION_REQUIRED")
        license_id = _text(license_expression, "LICENSE_CLASSIFICATION_REQUIRED")
        descriptors = _descriptors(blob_descriptors)
        paths = tuple(sorted({_relative_path(path) for path in retained_reference_paths}))
        claims = _claims(architecture_claims)
        mechanisms = _mechanisms(mechanism_candidates)
        source_digest = _optional_sha256(source_sha256, "SOURCE_DIGEST_INVALID")
        license_digest = _optional_sha256(license_sha256, "LICENSE_DIGEST_INVALID")
        digest_scope = str(source_sha256_scope).strip() if source_sha256_scope is not None else None
        normalized_blockers = _texts(blockers, code="BLOCKER_INVALID")
        normalized_allowed = _texts(allowed_use, code="ALLOWED_USE_REQUIRED", required=True)
        normalized_forbidden = _texts(forbidden_use, code="FORBIDDEN_USE_REQUIRED", required=True)
        if set(normalized_allowed) & set(normalized_forbidden):
            _fail("ALLOWED_FORBIDDEN_USE_OVERLAP")
        ceiling = _enum_value(MechanismStatus, epistemic_ceiling, "MECHANISM_CEILING_EXCEEDED")

        if parsed_class is SourceClass.CLOSED_BEHAVIORAL_ONLY and (
            descriptors or paths or source_digest is not None or license_digest is not None
        ):
            _fail("CLOSED_SOURCE_BYTES_FORBIDDEN")
        if parsed_status is IngestionStatus.REGISTERED_ONLY and (
            descriptors or paths or source_digest is not None or digest_scope is not None or license_digest is not None
        ):
            _fail("REGISTERED_ONLY_SOURCE_DIGEST_FORBIDDEN")
        if parsed_status is IngestionStatus.BLOCKED and not normalized_blockers:
            _fail("BLOCKER_REQUIRED")
        if parsed_status is IngestionStatus.INGESTED:
            if not descriptors:
                if parsed_class is SourceClass.PERMISSIVE_CODE:
                    _fail("PERMISSIVE_PACK_EMPTY")
                _fail("SOURCE_PACK_EMPTY")
            if source_digest is None or digest_scope != "RETAINED_SOURCE_PACK":
                _fail("SOURCE_DIGEST_REQUIRED")
            if paths != tuple(descriptor.relative_path for descriptor in descriptors):
                _fail("RETAINED_PATHS_MISMATCH")
            pack = SourcePack.create(
                source_id=normalized_id,
                exact_commit_or_release=revision,
                blob_descriptors=descriptors,
            )
            if source_digest != pack.pack_root_sha256:
                _fail("HASH_MISMATCH", normalized_id)
        elif parsed_status not in {IngestionStatus.SUPERSEDED} and (
            descriptors or paths or source_digest is not None or digest_scope is not None
        ):
            _fail("NON_INGESTED_SOURCE_BYTES_FORBIDDEN")

        if parsed_class is SourceClass.PERMISSIVE_CODE:
            if parsed_status not in {IngestionStatus.INGESTED, IngestionStatus.BLOCKED}:
                _fail("PERMISSIVE_PACK_EMPTY")
            if license_id not in PERMISSIVE_LICENSE_EXPRESSIONS:
                _fail("PERMISSIVE_LICENSE_NOT_APPROVED", license_id)
            if parsed_status is IngestionStatus.INGESTED and (
                license_digest is None or license_digest not in {item.digest for item in descriptors}
            ):
                _fail("LICENSE_EVIDENCE_REQUIRED")

        if parsed_class is SourceClass.CLOSED_BEHAVIORAL_ONLY:
            if parsed_status not in {IngestionStatus.REGISTERED_ONLY, IngestionStatus.BLOCKED}:
                _fail("CLOSED_SOURCE_BYTES_FORBIDDEN")
            if any(claim.kind is ClaimKind.SOURCE_FACT for claim in claims):
                _fail("CLOSED_INTERNAL_SOURCE_FACT_FORBIDDEN")

        rank = {
            MechanismStatus.A0_OBSERVED: 0,
            MechanismStatus.A1_MECHANISM_HYPOTHESIS: 1,
        }
        if any(rank[mechanism.status] > rank[ceiling] for mechanism in mechanisms):
            _fail("MECHANISM_CEILING_EXCEEDED")

        fields = {
            "registry_schema_version": schema_version,
            "source_id": normalized_id,
            "publisher": _text(publisher, "PUBLISHER_REQUIRED"),
            "system_name": _text(system_name, "SYSTEM_NAME_REQUIRED"),
            "version": _text(version, "SOURCE_VERSION_REQUIRED"),
            "source_class": parsed_class,
            "ingestion_status": parsed_status,
            "official_source_locator": _text(official_source_locator, "OFFICIAL_SOURCE_LOCATOR_REQUIRED"),
            "exact_commit_or_release": revision,
            "retrieved_at": _retrieved_at(retrieved_at),
            "source_sha256": source_digest,
            "source_sha256_scope": digest_scope,
            "license_name": license_label,
            "license_expression": license_id,
            "license_sha256": license_digest,
            "license_evidence_locator": _text(
                license_evidence_locator,
                "LICENSE_EVIDENCE_LOCATOR_REQUIRED",
            ),
            "allowed_use": normalized_allowed,
            "forbidden_use": normalized_forbidden,
            "epistemic_ceiling": ceiling,
            "architecture_claims": claims,
            "retained_reference_paths": paths,
            "blob_descriptors": descriptors,
            "mechanism_candidates": mechanisms,
            "blockers": normalized_blockers,
        }
        return cls(**fields, record_sha256=canonical_digest(cls._payload(**fields)))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourceRecord:
        fields = dict(value)
        expected = fields.pop("record_sha256", None)
        record = cls.create(**fields)
        if expected != record.record_sha256:
            _fail("HASH_MISMATCH", record.source_id)
        return record

    def payload(self) -> dict[str, Any]:
        fields = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "record_sha256"}
        return self._payload(**fields)

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "record_sha256": self.record_sha256}


@dataclass(frozen=True)
class SourceRegistryEntry:
    source_id: str
    record_sha256: str
    pack_root_sha256: str | None

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        record_sha256: str,
        pack_root_sha256: str | None,
    ) -> SourceRegistryEntry:
        return cls(
            source_id=_source_id(source_id),
            record_sha256=_sha256(record_sha256, "RECORD_DIGEST_INVALID"),
            pack_root_sha256=_optional_sha256(pack_root_sha256, "PACK_DIGEST_INVALID"),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "record_sha256": self.record_sha256,
            "pack_root_sha256": self.pack_root_sha256,
        }


@dataclass(frozen=True)
class SourceRegistry:
    registry_schema_version: str
    sources: tuple[SourceRegistryEntry, ...]
    registry_snapshot_sha256: str

    @staticmethod
    def _payload(
        *,
        registry_schema_version: str,
        sources: tuple[SourceRegistryEntry, ...],
    ) -> dict[str, Any]:
        return {
            "registry_schema_version": registry_schema_version,
            "sources": [entry.as_dict() for entry in sources],
        }

    @classmethod
    def create(
        cls,
        *,
        records: Iterable[SourceRecord],
        packs: Iterable[SourcePack],
        registry_schema_version: str = REGISTRY_SCHEMA_VERSION,
    ) -> SourceRegistry:
        version = _text(registry_schema_version, "REGISTRY_SCHEMA_VERSION_REQUIRED")
        if version != REGISTRY_SCHEMA_VERSION:
            _fail("REGISTRY_SCHEMA_VERSION_UNSUPPORTED", version)
        record_values = tuple(records)
        pack_values = tuple(packs)
        record_ids = tuple(record.source_id for record in record_values)
        pack_ids = tuple(pack.source_id for pack in pack_values)
        if len(record_ids) != len(set(record_ids)):
            _fail("DUPLICATE_SOURCE_ID")
        if len(pack_ids) != len(set(pack_ids)):
            _fail("DUPLICATE_SOURCE_PACK")
        records_by_id = {record.source_id: record for record in record_values}
        packs_by_id = {pack.source_id: pack for pack in pack_values}
        if set(packs_by_id) - set(records_by_id):
            _fail("UNREGISTERED_SOURCE_PACK")
        entries: list[SourceRegistryEntry] = []
        for source_id in sorted(records_by_id):
            record = records_by_id[source_id]
            pack = packs_by_id.get(source_id)
            if record.ingestion_status is IngestionStatus.INGESTED:
                if pack is None:
                    _fail("VAULT_BLOB_MISSING", source_id)
                if (
                    pack.exact_commit_or_release != record.exact_commit_or_release
                    or pack.pack_root_sha256 != record.source_sha256
                ):
                    _fail("HASH_MISMATCH", source_id)
            elif pack is not None:
                _fail("NON_INGESTED_SOURCE_PACK_FORBIDDEN", source_id)
            entries.append(
                SourceRegistryEntry.create(
                    source_id=source_id,
                    record_sha256=record.record_sha256,
                    pack_root_sha256=pack.pack_root_sha256 if pack is not None else None,
                )
            )
        ordered = tuple(entries)
        payload = cls._payload(registry_schema_version=version, sources=ordered)
        return cls(
            registry_schema_version=version,
            sources=ordered,
            registry_snapshot_sha256=canonical_digest(payload),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourceRegistry:
        version = _text(value.get("registry_schema_version"), "REGISTRY_SCHEMA_VERSION_REQUIRED")
        if version != REGISTRY_SCHEMA_VERSION:
            _fail("REGISTRY_SCHEMA_VERSION_UNSUPPORTED", version)
        entries = tuple(
            sorted(
                (SourceRegistryEntry.create(**dict(item)) for item in value.get("sources", ())),
                key=lambda item: item.source_id,
            )
        )
        ids = tuple(entry.source_id for entry in entries)
        if len(ids) != len(set(ids)):
            _fail("DUPLICATE_SOURCE_ID")
        payload = cls._payload(registry_schema_version=version, sources=entries)
        actual = canonical_digest(payload)
        if value.get("registry_snapshot_sha256") != actual:
            _fail("REGISTRY_SNAPSHOT_MISMATCH")
        return cls(
            registry_schema_version=version,
            sources=entries,
            registry_snapshot_sha256=actual,
        )

    def payload(self) -> dict[str, Any]:
        return self._payload(
            registry_schema_version=self.registry_schema_version,
            sources=self.sources,
        )

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "registry_snapshot_sha256": self.registry_snapshot_sha256}
