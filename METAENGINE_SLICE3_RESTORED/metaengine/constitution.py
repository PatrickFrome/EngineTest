from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .util import canonical_hash, load_json


CONSTITUTION_KERNEL_VERSION = "METAENGINE-CONSTITUTION-KERNEL-1"

_REQUIRED_K0_IDS = frozenset(
    {
        "PROVENANCE_PRIMARY_EVIDENCE",
        "CANONICAL_NOT_SCIENTIFIC_TRUTH",
        "NO_TRUTH_FROM_RANKING_OR_VOTING",
        "PRESERVE_ABSTENTION",
        "MUTATION_REQUIRES_RECEIPT",
        "SEPARATE_GENERATION_AND_PROMOTION",
        "FROZEN_EVALUATION_CONTRACT",
        "NO_NORMAL_KERNEL_SELF_MUTATION",
        "NO_EXECUTABLE_SELF_MODIFICATION",
        "PRIVACY_PERMISSION_FAIL_CLOSED",
        "IMMUTABLE_HISTORY_WITH_SUPERSESSION",
        "ROLLBACK_RECOVERY_REQUIRED",
    }
)


@dataclass(frozen=True)
class ConstitutionInvariant:
    invariant_id: str
    statement: str
    legacy_guardrail_ids: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.invariant_id,
            "statement": self.statement,
            "legacy_guardrail_ids": list(self.legacy_guardrail_ids),
        }




@dataclass(frozen=True)
class ConstitutionConformanceEntry:
    invariant_id: str
    enforcement_refs: tuple[str, ...]
    test_refs: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "invariant_id": self.invariant_id,
            "enforcement_refs": list(self.enforcement_refs),
            "test_refs": list(self.test_refs),
        }


@dataclass(frozen=True)
class ConstitutionConformanceReport:
    valid: bool
    mapped_invariant_count: int
    unmapped_invariants: tuple[str, ...]
    duplicate_invariants: tuple[str, ...]
    unknown_invariants: tuple[str, ...]
    findings: tuple[str, ...]
    entries: tuple[ConstitutionConformanceEntry, ...]

    @property
    def report_hash(self) -> str:
        return canonical_hash(
            {
                "valid": self.valid,
                "mapped_invariant_count": self.mapped_invariant_count,
                "unmapped_invariants": list(self.unmapped_invariants),
                "duplicate_invariants": list(self.duplicate_invariants),
                "unknown_invariants": list(self.unknown_invariants),
                "findings": list(self.findings),
                "entries": [item.payload() for item in self.entries],
            }
        )


@dataclass(frozen=True)
class ConstitutionAmendmentBoundary:
    ordinary_evolution_allowed: bool
    authority_status: str
    required_process: str

    def payload(self) -> dict[str, Any]:
        return {
            "ordinary_evolution_allowed": self.ordinary_evolution_allowed,
            "authority_status": self.authority_status,
            "required_process": self.required_process,
        }


@dataclass(frozen=True)
class ConstitutionKernel:
    k0_version: str
    k0_invariants: tuple[ConstitutionInvariant, ...]
    k1_version: str
    k1_topics: tuple[str, ...]
    amendment_boundary: ConstitutionAmendmentBoundary

    @property
    def k0_payload(self) -> dict[str, Any]:
        return {
            "k0_version": self.k0_version,
            "invariants": [item.payload() for item in self.k0_invariants],
        }

    @property
    def k1_payload(self) -> dict[str, Any]:
        return {
            "k1_version": self.k1_version,
            "topics": list(self.k1_topics),
            "amendment_boundary": self.amendment_boundary.payload(),
        }

    @property
    def k0_hash(self) -> str:
        return canonical_hash(self.k0_payload)

    @property
    def k1_hash(self) -> str:
        return canonical_hash(self.k1_payload)

    @property
    def constitution_hash(self) -> str:
        return canonical_hash(
            {
                "constitution_kernel_version": CONSTITUTION_KERNEL_VERSION,
                "k0_hash": self.k0_hash,
                "k1_hash": self.k1_hash,
            }
        )

    def require_amendment_authority(self) -> None:
        if self.amendment_boundary.authority_status == "NOT_IMPLEMENTED":
            raise RuntimeError("CONSTITUTION_AMENDMENT_AUTHORITY_NOT_IMPLEMENTED")
        if not self.amendment_boundary.ordinary_evolution_allowed:
            raise RuntimeError("CONSTITUTION_AMENDMENT_REQUIRES_EXTERNAL_GATED_PROCESS")


def _nonempty_text(value: Any, code: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(code)
    return text


def _load_k0(path: Path) -> tuple[str, tuple[ConstitutionInvariant, ...]]:
    value = load_json(path)
    version = _nonempty_text(value.get("k0_version", ""), "CONSTITUTION_K0_VERSION_REQUIRED")
    raw_items = tuple(value.get("invariants", ()))
    ids = [str(item.get("id", "")).strip() for item in raw_items]
    if len(ids) != len(set(ids)):
        raise ValueError("CONSTITUTION_K0_DUPLICATE_INVARIANT")
    if set(ids) != set(_REQUIRED_K0_IDS):
        raise ValueError("CONSTITUTION_K0_SET_MISMATCH")
    items = []
    for item in raw_items:
        invariant_id = _nonempty_text(item.get("id", ""), "CONSTITUTION_K0_ID_REQUIRED")
        statement = _nonempty_text(item.get("statement", ""), "CONSTITUTION_K0_STATEMENT_REQUIRED")
        legacy = tuple(sorted({str(x).strip() for x in item.get("legacy_guardrail_ids", ()) if str(x).strip()}))
        items.append(
            ConstitutionInvariant(
                invariant_id=invariant_id,
                statement=statement,
                legacy_guardrail_ids=legacy,
            )
        )
    return version, tuple(sorted(items, key=lambda item: item.invariant_id))


def _load_k1(path: Path) -> tuple[str, tuple[str, ...], ConstitutionAmendmentBoundary]:
    value = load_json(path)
    version = _nonempty_text(value.get("k1_version", ""), "CONSTITUTION_K1_VERSION_REQUIRED")
    raw_topics = tuple(value.get("topics", ()))
    topics = tuple(str(item).strip() for item in raw_topics)
    if not topics or any(not item for item in topics):
        raise ValueError("CONSTITUTION_K1_TOPIC_INVALID")
    if len(topics) != len(set(topics)):
        raise ValueError("CONSTITUTION_K1_TOPIC_DUPLICATE")
    boundary_value = value.get("amendment_boundary", {})
    boundary = ConstitutionAmendmentBoundary(
        ordinary_evolution_allowed=bool(boundary_value.get("ordinary_evolution_allowed", False)),
        authority_status=_nonempty_text(
            boundary_value.get("authority_status", ""),
            "CONSTITUTION_AMENDMENT_AUTHORITY_STATUS_REQUIRED",
        ),
        required_process=_nonempty_text(
            boundary_value.get("required_process", ""),
            "CONSTITUTION_AMENDMENT_PROCESS_REQUIRED",
        ),
    )
    if boundary.ordinary_evolution_allowed:
        raise ValueError("CONSTITUTION_NORMAL_EVOLUTION_AMENDMENT_FORBIDDEN")
    if boundary.authority_status != "NOT_IMPLEMENTED":
        raise ValueError("CONSTITUTION_AMENDMENT_AUTHORITY_MUST_REMAIN_UNIMPLEMENTED")
    return version, tuple(sorted(topics)), boundary


def load_constitution_kernel(root: str | Path) -> ConstitutionKernel:
    root = Path(root).resolve()
    config_dir = root / "config" / "constitution"
    k0_version, invariants = _load_k0(config_dir / "k0_v1.json")
    k1_version, topics, amendment_boundary = _load_k1(config_dir / "k1_v1.json")
    return ConstitutionKernel(
        k0_version=k0_version,
        k0_invariants=invariants,
        k1_version=k1_version,
        k1_topics=topics,
        amendment_boundary=amendment_boundary,
    )


def constitution_hash(root: str | Path) -> str:
    return load_constitution_kernel(root).constitution_hash


def _ref_path(root: Path, ref: str) -> Path | None:
    raw_path = str(ref).split("#", 1)[0].strip()
    if not raw_path:
        return None
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def verify_constitution_conformance(root: str | Path) -> ConstitutionConformanceReport:
    root = Path(root).resolve()
    kernel = load_constitution_kernel(root)
    value = load_json(root / "config" / "constitution" / "conformance_matrix_v1.json")
    raw_entries = tuple(value.get("entries", ()))
    entries: list[ConstitutionConformanceEntry] = []
    findings: set[str] = set()
    ids: list[str] = []
    for raw in raw_entries:
        invariant_id = str(raw.get("invariant_id", "")).strip()
        ids.append(invariant_id)
        enforcement_refs = tuple(sorted({str(x).strip() for x in raw.get("enforcement_refs", ()) if str(x).strip()}))
        test_refs = tuple(sorted({str(x).strip() for x in raw.get("test_refs", ()) if str(x).strip()}))
        if not enforcement_refs:
            findings.add("CONSTITUTION_CONFORMANCE_ENFORCEMENT_REF_REQUIRED")
        if not test_refs:
            findings.add("CONSTITUTION_CONFORMANCE_TEST_REF_REQUIRED")
        for ref in enforcement_refs + test_refs:
            path = _ref_path(root, ref)
            if path is None or not path.is_file():
                findings.add("CONSTITUTION_CONFORMANCE_REF_PATH_MISSING")
        entries.append(
            ConstitutionConformanceEntry(
                invariant_id=invariant_id,
                enforcement_refs=enforcement_refs,
                test_refs=test_refs,
            )
        )

    counts = {item: ids.count(item) for item in set(ids)}
    duplicate = tuple(sorted(item for item, count in counts.items() if item and count > 1))
    expected = {item.invariant_id for item in kernel.k0_invariants}
    present = {item for item in ids if item}
    unmapped = tuple(sorted(expected - present))
    unknown = tuple(sorted(present - expected))
    if duplicate:
        findings.add("CONSTITUTION_CONFORMANCE_DUPLICATE_INVARIANT")
    if unmapped:
        findings.add("CONSTITUTION_CONFORMANCE_INVARIANT_UNMAPPED")
    if unknown:
        findings.add("CONSTITUTION_CONFORMANCE_UNKNOWN_INVARIANT")
    if any(not item for item in ids):
        findings.add("CONSTITUTION_CONFORMANCE_INVARIANT_ID_REQUIRED")

    ordered_entries = tuple(sorted(entries, key=lambda item: (item.invariant_id, item.enforcement_refs, item.test_refs)))
    ordered_findings = tuple(sorted(findings))
    return ConstitutionConformanceReport(
        valid=not ordered_findings,
        mapped_invariant_count=len(expected & present),
        unmapped_invariants=unmapped,
        duplicate_invariants=duplicate,
        unknown_invariants=unknown,
        findings=ordered_findings,
        entries=ordered_entries,
    )
