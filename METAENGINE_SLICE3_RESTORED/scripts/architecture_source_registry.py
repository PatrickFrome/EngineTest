from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from metaengine.architecture_sources import (
    ArchitectureSourceValidationError,
    IngestionStatus,
    SourceClass,
    SourcePack,
    SourceRecord,
    SourceRegistry,
)
from metaengine.devfabric.codec import canonical_digest
from metaengine.reference_vault import (
    ReferenceVault,
    StagedSourceFile,
    VaultVerificationReceipt,
)

CATALOG_VERSION = "ARCHITECTURE-SOURCE-CATALOG-1"
MECHANISM_CARD_VERSION = "ARCHITECTURE-MECHANISM-CARD-1"


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ArchitectureSourceValidationError(code, detail)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        _fail("CATALOG_MISSING", str(path))
        raise AssertionError("unreachable") from exc
    except (OSError, json.JSONDecodeError) as exc:
        _fail("CATALOG_INVALID", str(exc))
        raise AssertionError("unreachable") from exc
    if not isinstance(value, dict):
        _fail("CATALOG_INVALID", "root must be an object")
    return value


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _safe_relative(value: object, code: str) -> PurePosixPath:
    text = str(value).strip() if value is not None else ""
    pure = PurePosixPath(text)
    if not text or pure.is_absolute():
        _fail(code, text)
    if ".." in pure.parts or not pure.parts:
        _fail("PATH_ESCAPE", text)
    return pure


def _staged_path(staging_root: Path, source_id: str, raw_path: object) -> Path:
    pure = _safe_relative(raw_path, "STAGED_PATH_INVALID")
    source_root = (staging_root / source_id).resolve()
    candidate = source_root.joinpath(*pure.parts)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(source_root)
    except ValueError as exc:
        _fail("PATH_ESCAPE", pure.as_posix())
        raise AssertionError("unreachable") from exc
    return candidate


def _catalog_sources(catalog: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    if catalog.get("catalog_version") != CATALOG_VERSION:
        _fail("CATALOG_VERSION_UNSUPPORTED", str(catalog.get("catalog_version")))
    raw_sources = catalog.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        _fail("CATALOG_SOURCES_REQUIRED")
    sources: list[dict[str, Any]] = []
    for raw in raw_sources:
        if not isinstance(raw, dict):
            _fail("CATALOG_SOURCE_INVALID")
        sources.append(dict(raw))
    ids = tuple(str(source.get("source_id", "")) for source in sources)
    if any(not source_id for source_id in ids) or len(ids) != len(set(ids)):
        _fail("DUPLICATE_SOURCE_ID")
    return tuple(sorted(sources, key=lambda source: str(source["source_id"])))


def _staged_files(
    entry: Mapping[str, Any],
    *,
    staging_root: Path,
) -> tuple[StagedSourceFile, ...]:
    source_id = str(entry["source_id"])
    revision = str(entry.get("exact_commit_or_release", ""))
    raw_files = entry.get("files", ())
    if not isinstance(raw_files, list):
        _fail("CATALOG_FILES_INVALID", source_id)
    files: list[StagedSourceFile] = []
    for raw in raw_files:
        if not isinstance(raw, dict):
            _fail("CATALOG_FILE_INVALID", source_id)
        if str(raw.get("source_revision", "")) != revision:
            _fail("SOURCE_REVISION_MISMATCH", str(raw.get("relative_path", "")))
        files.append(
            StagedSourceFile(
                path=_staged_path(staging_root, source_id, raw.get("staged_path")),
                relative_path=str(raw.get("relative_path", "")),
                media_type=str(raw.get("media_type", "")),
                git_blob_id=(
                    str(raw["git_blob_id"])
                    if raw.get("git_blob_id") is not None
                    else None
                ),
            )
        )
    return tuple(files)


def _record_from_catalog(
    entry: Mapping[str, Any],
    *,
    pack: SourcePack | None,
) -> SourceRecord:
    license_relative_path = entry.get("license_relative_path")
    if pack is None:
        source_sha256 = None
        source_sha256_scope = None
        license_sha256 = None
        descriptors = ()
        retained_paths = ()
    else:
        source_sha256 = pack.pack_root_sha256
        source_sha256_scope = "RETAINED_SOURCE_PACK"
        descriptors = pack.blob_descriptors
        retained_paths = tuple(descriptor.relative_path for descriptor in descriptors)
        if not license_relative_path:
            _fail("LICENSE_EVIDENCE_REQUIRED", str(entry["source_id"]))
        matching = tuple(
            descriptor.digest
            for descriptor in descriptors
            if descriptor.relative_path == str(license_relative_path)
        )
        if len(matching) != 1:
            _fail("LICENSE_EVIDENCE_REQUIRED", str(entry["source_id"]))
        license_sha256 = matching[0]
    return SourceRecord.create(
        source_id=str(entry.get("source_id", "")),
        publisher=str(entry.get("publisher", "")),
        system_name=str(entry.get("system_name", "")),
        version=str(entry.get("version", "")),
        source_class=str(entry.get("source_class", "")),
        ingestion_status=str(entry.get("ingestion_status", "")),
        official_source_locator=str(entry.get("official_source_locator", "")),
        exact_commit_or_release=str(entry.get("exact_commit_or_release", "")),
        retrieved_at=str(entry.get("retrieved_at", "")),
        source_sha256=source_sha256,
        source_sha256_scope=source_sha256_scope,
        license_name=str(entry.get("license_name", "")),
        license_expression=str(entry.get("license_expression", "")),
        license_sha256=license_sha256,
        license_evidence_locator=str(entry.get("license_evidence_locator", "")),
        allowed_use=tuple(entry.get("allowed_use", ())),
        forbidden_use=tuple(entry.get("forbidden_use", ())),
        epistemic_ceiling=str(entry.get("epistemic_ceiling", "")),
        architecture_claims=tuple(entry.get("architecture_claims", ())),
        retained_reference_paths=retained_paths,
        blob_descriptors=descriptors,
        mechanism_candidates=tuple(entry.get("mechanism_candidates", ())),
        blockers=tuple(entry.get("blockers", ())),
    )


def _mechanism_cards(records: Iterable[SourceRecord]) -> dict[str, dict[str, Any]]:
    variants: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for mechanism in record.mechanism_candidates:
            variants.setdefault(mechanism.mechanism_id, []).append(
                {"source_id": record.source_id, **mechanism.as_dict()}
            )
    cards: dict[str, dict[str, Any]] = {}
    for mechanism_id in sorted(variants):
        ordered_variants = sorted(variants[mechanism_id], key=lambda value: value["source_id"])
        status = (
            "A1_MECHANISM_HYPOTHESIS"
            if any(value["status"] == "A1_MECHANISM_HYPOTHESIS" for value in ordered_variants)
            else "A0_OBSERVED"
        )
        payload = {
            "mechanism_card_version": MECHANISM_CARD_VERSION,
            "mechanism_id": mechanism_id,
            "status": status,
            "origin_source_ids": sorted({value["source_id"] for value in ordered_variants}),
            "variants": ordered_variants,
            "assimilation_effect": "NONE",
        }
        cards[mechanism_id] = {**payload, "card_sha256": canonical_digest(payload)}
    return cards


def _publish_generated_output(
    output_root: Path,
    *,
    records: tuple[SourceRecord, ...],
    packs: tuple[SourcePack, ...],
    receipts: tuple[VaultVerificationReceipt, ...],
    registry: SourceRegistry,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".source-registry-", dir=output_root.parent) as temporary:
        generated = Path(temporary)
        for record in records:
            _write_json(generated / "sources" / f"{record.source_id}.json", record.as_dict())
        for pack in packs:
            _write_json(generated / "packs" / f"{pack.source_id}.json", pack.as_dict())
        for receipt in receipts:
            _write_json(generated / "receipts" / f"{receipt.source_id}.json", receipt.as_dict())
        for mechanism_id, card in _mechanism_cards(records).items():
            _write_json(generated / "mechanisms" / f"{mechanism_id}.json", card)
        for directory in ("sources", "packs", "receipts", "mechanisms"):
            source = generated / directory
            source.mkdir(exist_ok=True)
            destination = output_root / directory
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(source, destination)
        registry_staging = generated / "registry.json"
        _write_json(registry_staging, registry.as_dict())
        os.replace(registry_staging, output_root / "registry.json")


def _success_payload(
    *,
    registry: SourceRegistry,
    records: Iterable[SourceRecord],
    verified_blob_count: int,
    verified_total_bytes: int,
) -> dict[str, Any]:
    record_values = tuple(records)
    return {
        "status": "PASS",
        "registry_snapshot_sha256": registry.registry_snapshot_sha256,
        "source_count": len(record_values),
        "ingested_source_count": sum(
            record.ingestion_status is IngestionStatus.INGESTED for record in record_values
        ),
        "verified_blob_count": verified_blob_count,
        "verified_total_bytes": verified_total_bytes,
        "findings": [],
    }


def ingest_catalog(
    *,
    catalog_path: Path,
    staging_root: Path,
    vault_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    catalog = _load_json(catalog_path)
    entries = _catalog_sources(catalog)
    vault = ReferenceVault(vault_root)
    records: list[SourceRecord] = []
    packs: list[SourcePack] = []
    receipts: list[VaultVerificationReceipt] = []
    for entry in entries:
        source_class = SourceClass(str(entry.get("source_class", "")))
        status = IngestionStatus(str(entry.get("ingestion_status", "")))
        files = _staged_files(entry, staging_root=staging_root)
        if source_class is SourceClass.CLOSED_BEHAVIORAL_ONLY and files:
            _fail("CLOSED_SOURCE_BYTES_FORBIDDEN", str(entry["source_id"]))
        if status is not IngestionStatus.INGESTED and files:
            _fail("NON_INGESTED_SOURCE_BYTES_FORBIDDEN", str(entry["source_id"]))
        if (
            source_class is SourceClass.PERMISSIVE_CODE
            and status is IngestionStatus.INGESTED
            and not files
        ):
            _fail("PERMISSIVE_PACK_EMPTY", str(entry["source_id"]))
        pack: SourcePack | None = None
        if status is IngestionStatus.INGESTED:
            pack = vault.ingest(
                source_id=str(entry["source_id"]),
                exact_commit_or_release=str(entry.get("exact_commit_or_release", "")),
                files=files,
            )
            receipt = vault.verify(pack)
            if receipt.status != "PASS":
                first = receipt.findings[0]
                _fail(first.code, first.relative_path)
            packs.append(pack)
            receipts.append(receipt)
        records.append(_record_from_catalog(entry, pack=pack))
    registry = SourceRegistry.create(records=records, packs=packs)
    _publish_generated_output(
        output_root,
        records=tuple(records),
        packs=tuple(packs),
        receipts=tuple(receipts),
        registry=registry,
    )
    return _success_payload(
        registry=registry,
        records=records,
        verified_blob_count=sum(receipt.verified_blob_count for receipt in receipts),
        verified_total_bytes=sum(receipt.verified_total_bytes for receipt in receipts),
    )


def _read_record(path: Path) -> SourceRecord:
    return SourceRecord.from_dict(_load_json(path))


def _read_pack(path: Path) -> SourcePack:
    return SourcePack.from_dict(_load_json(path))


def _verify_mechanism_cards(root: Path, records: tuple[SourceRecord, ...]) -> list[dict[str, str]]:
    expected = _mechanism_cards(records)
    findings: list[dict[str, str]] = []
    directory = root / "mechanisms"
    actual_paths = {path.stem: path for path in directory.glob("*.json")} if directory.is_dir() else {}
    for missing in sorted(set(expected) - set(actual_paths)):
        findings.append({"code": "MECHANISM_CARD_MISSING", "detail": missing})
    for extra in sorted(set(actual_paths) - set(expected)):
        findings.append({"code": "MECHANISM_CARD_EXTRA", "detail": extra})
    for mechanism_id in sorted(set(expected) & set(actual_paths)):
        try:
            actual = _load_json(actual_paths[mechanism_id])
        except ArchitectureSourceValidationError as exc:
            findings.append({"code": exc.code, "detail": mechanism_id})
            continue
        if actual != expected[mechanism_id]:
            findings.append({"code": "HASH_MISMATCH", "detail": mechanism_id})
    return findings


def verify_registry(*, registry_path: Path, vault_root: Path) -> dict[str, Any]:
    registry_value = _load_json(registry_path)
    registry_snapshot = str(registry_value.get("registry_snapshot_sha256", ""))
    registry = SourceRegistry.from_dict(registry_value)
    root = registry_path.parent
    vault = ReferenceVault(vault_root)
    records: list[SourceRecord] = []
    packs: list[SourcePack] = []
    findings: list[dict[str, str]] = []
    verified_blob_count = 0
    verified_total_bytes = 0
    for entry in registry.sources:
        try:
            record = _read_record(root / "sources" / f"{entry.source_id}.json")
            if record.record_sha256 != entry.record_sha256:
                _fail("HASH_MISMATCH", entry.source_id)
            records.append(record)
            if entry.pack_root_sha256 is not None:
                pack = _read_pack(root / "packs" / f"{entry.source_id}.json")
                if pack.pack_root_sha256 != entry.pack_root_sha256:
                    _fail("HASH_MISMATCH", entry.source_id)
                stored_receipt = VaultVerificationReceipt.from_dict(
                    _load_json(root / "receipts" / f"{entry.source_id}.json")
                )
                result = vault.verify(pack)
                if stored_receipt.pack_root_sha256 != pack.pack_root_sha256:
                    _fail("HASH_MISMATCH", entry.source_id)
                if result.status != "PASS":
                    findings.extend(
                        {
                            "code": finding.code,
                            "detail": f"{entry.source_id}:{finding.relative_path}",
                        }
                        for finding in result.findings
                    )
                elif stored_receipt != result:
                    findings.append(
                        {
                            "code": "VERIFICATION_RECEIPT_STALE",
                            "detail": entry.source_id,
                        }
                    )
                else:
                    verified_blob_count += result.verified_blob_count
                    verified_total_bytes += result.verified_total_bytes
                packs.append(pack)
        except (ArchitectureSourceValidationError, FileNotFoundError) as exc:
            code = exc.code if isinstance(exc, ArchitectureSourceValidationError) else "TRACKED_ARTIFACT_MISSING"
            findings.append({"code": code, "detail": entry.source_id})
    if not findings:
        try:
            rebuilt = SourceRegistry.create(records=records, packs=packs)
            if rebuilt.registry_snapshot_sha256 != registry.registry_snapshot_sha256:
                findings.append({"code": "REGISTRY_SNAPSHOT_MISMATCH", "detail": "registry.json"})
        except ArchitectureSourceValidationError as exc:
            findings.append({"code": exc.code, "detail": exc.detail})
    findings.extend(_verify_mechanism_cards(root, tuple(records)))
    ordered_findings = sorted(findings, key=lambda value: (value["detail"], value["code"]))
    if ordered_findings:
        return {
            "status": "FAIL",
            "registry_snapshot_sha256": registry_snapshot,
            "source_count": len(registry.sources),
            "ingested_source_count": sum(entry.pack_root_sha256 is not None for entry in registry.sources),
            "verified_blob_count": verified_blob_count,
            "verified_total_bytes": verified_total_bytes,
            "findings": ordered_findings,
        }
    return _success_payload(
        registry=registry,
        records=records,
        verified_blob_count=verified_blob_count,
        verified_total_bytes=verified_total_bytes,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="architecture-source-registry")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("--catalog", type=Path, required=True)
    ingest.add_argument("--staging-root", type=Path, required=True)
    ingest.add_argument("--vault-root", type=Path, required=True)
    ingest.add_argument("--output-root", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--registry", type=Path, required=True)
    verify.add_argument("--vault-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "ingest":
            result = ingest_catalog(
                catalog_path=args.catalog,
                staging_root=args.staging_root,
                vault_root=args.vault_root,
                output_root=args.output_root,
            )
        else:
            result = verify_registry(registry_path=args.registry, vault_root=args.vault_root)
    except ArchitectureSourceValidationError as exc:
        result = {
            "status": "FAIL",
            "registry_snapshot_sha256": None,
            "source_count": 0,
            "ingested_source_count": 0,
            "verified_blob_count": 0,
            "verified_total_bytes": 0,
            "findings": [{"code": exc.code, "detail": exc.detail}],
        }
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        result = {
            "status": "FAIL",
            "registry_snapshot_sha256": None,
            "source_count": 0,
            "ingested_source_count": 0,
            "verified_blob_count": 0,
            "verified_total_bytes": 0,
            "findings": [{"code": "CATALOG_INVALID", "detail": str(exc)}],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
