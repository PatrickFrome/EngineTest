from __future__ import annotations

import hashlib
import json
import string
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .codec import canonical_digest


class DevelopmentReviewDecision(str, Enum):
    ACCEPT_CONTINUE = "ACCEPT_CONTINUE"
    ACCEPT_WITH_FOLLOWUP_EXPERIMENT = "ACCEPT_WITH_FOLLOWUP_EXPERIMENT"
    REVISE_BEFORE_CONTINUE = "REVISE_BEFORE_CONTINUE"
    REVERT_BEFORE_CONTINUE = "REVERT_BEFORE_CONTINUE"
    DEFER_EXPERIMENT_REQUIRED = "DEFER_EXPERIMENT_REQUIRED"
    BLOCK_CONSTITUTIONAL_CONFLICT = "BLOCK_CONSTITUTIONAL_CONFLICT"


class DevelopmentAlternativeKind(str, Enum):
    CURRENT = "CURRENT"
    MINIMAL = "MINIMAL"
    LIBRARY = "LIBRARY"
    SYNTHESIS = "SYNTHESIS"


_ADMISSIBLE_DECISIONS = frozenset(
    {
        DevelopmentReviewDecision.ACCEPT_CONTINUE,
        DevelopmentReviewDecision.ACCEPT_WITH_FOLLOWUP_EXPERIMENT,
    }
)


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(char in string.hexdigits for char in value)


def _require_text(value: str, error: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(error)
    return text


def _canonical_hashes(values: Iterable[str], *, error: str) -> tuple[str, ...]:
    result = tuple(sorted({str(value) for value in values}))
    if not result or any(not _is_hex(value, 64) for value in result):
        raise ValueError(error)
    return result


@dataclass(frozen=True)
class DevelopmentAlternative:
    kind: DevelopmentAlternativeKind
    summary: str
    evidence_hashes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "summary": self.summary,
            "evidence_hashes": list(self.evidence_hashes),
        }

    @classmethod
    def create(
        cls,
        *,
        kind: DevelopmentAlternativeKind,
        summary: str,
        evidence_hashes: Iterable[str],
    ) -> "DevelopmentAlternative":
        return cls(
            kind=DevelopmentAlternativeKind(kind),
            summary=_require_text(summary, "DEVELOPMENT_REVIEW_ALTERNATIVE_SUMMARY_REQUIRED"),
            evidence_hashes=_canonical_hashes(
                evidence_hashes,
                error="DEVELOPMENT_REVIEW_ALTERNATIVE_EVIDENCE_INVALID",
            ),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DevelopmentAlternative":
        return cls.create(
            kind=DevelopmentAlternativeKind(value["kind"]),
            summary=str(value["summary"]),
            evidence_hashes=tuple(value.get("evidence_hashes", ())),
        )


@dataclass(frozen=True)
class DevelopmentReceiptVerification:
    valid: bool
    reason: str


@dataclass(frozen=True)
class DevelopmentEvolutionReviewReceipt:
    review_protocol_version: str
    completed_step_id: str
    completed_step_commit: str
    completed_step_evidence_hashes: tuple[str, ...]
    constitution_hash: str
    architecture_library_snapshot_hash: str
    policy_snapshot_hash: str
    relevant_mechanism_ids: tuple[str, ...]
    alternatives_considered: tuple[DevelopmentAlternative, ...]
    decision: DevelopmentReviewDecision
    rationale: str
    complexity_delta: str
    capability_hypothesis: str
    required_followup_experiment: str
    constitutional_findings: tuple[str, ...]
    library_findings: tuple[str, ...]
    policy_findings: tuple[str, ...]
    next_step_allowed: bool
    receipt_hash: str

    @staticmethod
    def _payload(
        *,
        review_protocol_version: str,
        completed_step_id: str,
        completed_step_commit: str,
        completed_step_evidence_hashes: tuple[str, ...],
        constitution_hash: str,
        architecture_library_snapshot_hash: str,
        policy_snapshot_hash: str,
        relevant_mechanism_ids: tuple[str, ...],
        alternatives_considered: tuple[DevelopmentAlternative, ...],
        decision: DevelopmentReviewDecision,
        rationale: str,
        complexity_delta: str,
        capability_hypothesis: str,
        required_followup_experiment: str,
        constitutional_findings: tuple[str, ...],
        library_findings: tuple[str, ...],
        policy_findings: tuple[str, ...],
        next_step_allowed: bool,
    ) -> dict[str, Any]:
        return {
            "review_protocol_version": review_protocol_version,
            "completed_step_id": completed_step_id,
            "completed_step_commit": completed_step_commit,
            "completed_step_evidence_hashes": list(completed_step_evidence_hashes),
            "constitution_hash": constitution_hash,
            "architecture_library_snapshot_hash": architecture_library_snapshot_hash,
            "policy_snapshot_hash": policy_snapshot_hash,
            "relevant_mechanism_ids": list(relevant_mechanism_ids),
            "alternatives_considered": [alternative.as_dict() for alternative in alternatives_considered],
            "decision": decision.value,
            "rationale": rationale,
            "complexity_delta": complexity_delta,
            "capability_hypothesis": capability_hypothesis,
            "required_followup_experiment": required_followup_experiment,
            "constitutional_findings": list(constitutional_findings),
            "library_findings": list(library_findings),
            "policy_findings": list(policy_findings),
            "next_step_allowed": next_step_allowed,
        }

    @classmethod
    def create(
        cls,
        *,
        completed_step_id: str,
        completed_step_commit: str,
        completed_step_evidence_hashes: Iterable[str],
        constitution_hash: str,
        architecture_library_snapshot_hash: str,
        policy_snapshot_hash: str,
        relevant_mechanism_ids: Iterable[str],
        alternatives_considered: Iterable[DevelopmentAlternative],
        decision: DevelopmentReviewDecision,
        rationale: str,
        complexity_delta: str,
        capability_hypothesis: str,
        required_followup_experiment: str,
        constitutional_findings: Iterable[str],
        library_findings: Iterable[str],
        policy_findings: Iterable[str],
        review_protocol_version: str = "METAENGINE-DEVELOPMENT-EVOLUTION-REVIEW-1",
    ) -> "DevelopmentEvolutionReviewReceipt":
        completed_step_id = _require_text(completed_step_id, "DEVELOPMENT_REVIEW_STEP_ID_REQUIRED")
        completed_step_commit = str(completed_step_commit)
        if not _is_hex(completed_step_commit, 40):
            raise ValueError("DEVELOPMENT_REVIEW_COMMIT_INVALID")
        completed_step_evidence_hashes = _canonical_hashes(
            completed_step_evidence_hashes,
            error="DEVELOPMENT_REVIEW_EVIDENCE_INVALID",
        )
        for value, error in (
            (constitution_hash, "DEVELOPMENT_REVIEW_CONSTITUTION_HASH_INVALID"),
            (architecture_library_snapshot_hash, "DEVELOPMENT_REVIEW_LIBRARY_HASH_INVALID"),
            (policy_snapshot_hash, "DEVELOPMENT_REVIEW_POLICY_HASH_INVALID"),
        ):
            if not _is_hex(str(value), 64):
                raise ValueError(error)

        mechanisms = tuple(sorted({str(value).strip() for value in relevant_mechanism_ids if str(value).strip()}))
        alternatives = tuple(alternatives_considered)
        kinds = tuple(alternative.kind for alternative in alternatives)
        if len(alternatives) != len(DevelopmentAlternativeKind) or set(kinds) != set(DevelopmentAlternativeKind):
            raise ValueError("DEVELOPMENT_REVIEW_ALTERNATIVES_INCOMPLETE")
        if len(set(kinds)) != len(kinds):
            raise ValueError("DEVELOPMENT_REVIEW_ALTERNATIVES_DUPLICATE")
        normalized_alternatives = tuple(
            DevelopmentAlternative.create(
                kind=alternative.kind,
                summary=alternative.summary,
                evidence_hashes=alternative.evidence_hashes,
            )
            for alternative in sorted(alternatives, key=lambda item: item.kind.value)
        )

        constitutional_findings = tuple(str(value).strip() for value in constitutional_findings if str(value).strip())
        library_findings = tuple(str(value).strip() for value in library_findings if str(value).strip())
        policy_findings = tuple(str(value).strip() for value in policy_findings if str(value).strip())
        if not constitutional_findings:
            raise ValueError("DEVELOPMENT_REVIEW_CONSTITUTION_FINDINGS_REQUIRED")
        if not library_findings:
            raise ValueError("DEVELOPMENT_REVIEW_LIBRARY_FINDINGS_REQUIRED")
        if not policy_findings:
            raise ValueError("DEVELOPMENT_REVIEW_POLICY_FINDINGS_REQUIRED")

        decision = DevelopmentReviewDecision(decision)
        next_step_allowed = decision in _ADMISSIBLE_DECISIONS
        fields = {
            "review_protocol_version": _require_text(
                review_protocol_version,
                "DEVELOPMENT_REVIEW_PROTOCOL_VERSION_REQUIRED",
            ),
            "completed_step_id": completed_step_id,
            "completed_step_commit": completed_step_commit,
            "completed_step_evidence_hashes": completed_step_evidence_hashes,
            "constitution_hash": str(constitution_hash),
            "architecture_library_snapshot_hash": str(architecture_library_snapshot_hash),
            "policy_snapshot_hash": str(policy_snapshot_hash),
            "relevant_mechanism_ids": mechanisms,
            "alternatives_considered": normalized_alternatives,
            "decision": decision,
            "rationale": _require_text(rationale, "DEVELOPMENT_REVIEW_RATIONALE_REQUIRED"),
            "complexity_delta": _require_text(complexity_delta, "DEVELOPMENT_REVIEW_COMPLEXITY_DELTA_REQUIRED"),
            "capability_hypothesis": _require_text(
                capability_hypothesis,
                "DEVELOPMENT_REVIEW_CAPABILITY_HYPOTHESIS_REQUIRED",
            ),
            "required_followup_experiment": _require_text(
                required_followup_experiment,
                "DEVELOPMENT_REVIEW_FOLLOWUP_REQUIRED",
            ),
            "constitutional_findings": constitutional_findings,
            "library_findings": library_findings,
            "policy_findings": policy_findings,
            "next_step_allowed": next_step_allowed,
        }
        receipt_hash = canonical_digest(cls._payload(**fields))
        return cls(**fields, receipt_hash=receipt_hash)

    def payload(self) -> dict[str, Any]:
        return self._payload(
            review_protocol_version=self.review_protocol_version,
            completed_step_id=self.completed_step_id,
            completed_step_commit=self.completed_step_commit,
            completed_step_evidence_hashes=self.completed_step_evidence_hashes,
            constitution_hash=self.constitution_hash,
            architecture_library_snapshot_hash=self.architecture_library_snapshot_hash,
            policy_snapshot_hash=self.policy_snapshot_hash,
            relevant_mechanism_ids=self.relevant_mechanism_ids,
            alternatives_considered=self.alternatives_considered,
            decision=self.decision,
            rationale=self.rationale,
            complexity_delta=self.complexity_delta,
            capability_hypothesis=self.capability_hypothesis,
            required_followup_experiment=self.required_followup_experiment,
            constitutional_findings=self.constitutional_findings,
            library_findings=self.library_findings,
            policy_findings=self.policy_findings,
            next_step_allowed=self.next_step_allowed,
        )

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_hash": self.receipt_hash}

    def creation_fields(self) -> dict[str, Any]:
        return {
            "review_protocol_version": self.review_protocol_version,
            "completed_step_id": self.completed_step_id,
            "completed_step_commit": self.completed_step_commit,
            "completed_step_evidence_hashes": self.completed_step_evidence_hashes,
            "constitution_hash": self.constitution_hash,
            "architecture_library_snapshot_hash": self.architecture_library_snapshot_hash,
            "policy_snapshot_hash": self.policy_snapshot_hash,
            "relevant_mechanism_ids": self.relevant_mechanism_ids,
            "alternatives_considered": self.alternatives_considered,
            "decision": self.decision,
            "rationale": self.rationale,
            "complexity_delta": self.complexity_delta,
            "capability_hypothesis": self.capability_hypothesis,
            "required_followup_experiment": self.required_followup_experiment,
            "constitutional_findings": self.constitutional_findings,
            "library_findings": self.library_findings,
            "policy_findings": self.policy_findings,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DevelopmentEvolutionReviewReceipt":
        alternatives = tuple(
            DevelopmentAlternative.from_dict(item)
            for item in value.get("alternatives_considered", ())
        )
        receipt = cls(
            review_protocol_version=str(value["review_protocol_version"]),
            completed_step_id=str(value["completed_step_id"]),
            completed_step_commit=str(value["completed_step_commit"]),
            completed_step_evidence_hashes=tuple(value.get("completed_step_evidence_hashes", ())),
            constitution_hash=str(value["constitution_hash"]),
            architecture_library_snapshot_hash=str(value["architecture_library_snapshot_hash"]),
            policy_snapshot_hash=str(value["policy_snapshot_hash"]),
            relevant_mechanism_ids=tuple(value.get("relevant_mechanism_ids", ())),
            alternatives_considered=alternatives,
            decision=DevelopmentReviewDecision(value["decision"]),
            rationale=str(value["rationale"]),
            complexity_delta=str(value["complexity_delta"]),
            capability_hypothesis=str(value["capability_hypothesis"]),
            required_followup_experiment=str(value["required_followup_experiment"]),
            constitutional_findings=tuple(value.get("constitutional_findings", ())),
            library_findings=tuple(value.get("library_findings", ())),
            policy_findings=tuple(value.get("policy_findings", ())),
            next_step_allowed=bool(value["next_step_allowed"]),
            receipt_hash=str(value["receipt_hash"]),
        )
        return receipt


def verify_receipt_integrity(receipt: DevelopmentEvolutionReviewReceipt) -> DevelopmentReceiptVerification:
    actual = canonical_digest(receipt.payload())
    if actual != receipt.receipt_hash:
        return DevelopmentReceiptVerification(False, "DEVELOPMENT_REVIEW_RECEIPT_HASH_MISMATCH")
    expected_allowed = receipt.decision in _ADMISSIBLE_DECISIONS
    if receipt.next_step_allowed is not expected_allowed:
        return DevelopmentReceiptVerification(False, "DEVELOPMENT_REVIEW_DECISION_ALLOWANCE_MISMATCH")
    return DevelopmentReceiptVerification(True, "DEVELOPMENT_REVIEW_RECEIPT_VALID")


@dataclass(frozen=True)
class ContentSnapshot:
    snapshot_version: str
    files: tuple[dict[str, str], ...]
    snapshot_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_version": self.snapshot_version,
            "files": [dict(row) for row in self.files],
            "snapshot_hash": self.snapshot_hash,
        }


@dataclass(frozen=True)
class DevelopmentReviewContext:
    review_context_version: str
    constitution: ContentSnapshot
    architecture_library: ContentSnapshot
    policy: ContentSnapshot


def snapshot_paths(
    root: str | Path,
    paths: Iterable[str],
    *,
    snapshot_version: str = "METAENGINE-DEVELOPMENT-REVIEW-CONTENT-SNAPSHOT-1",
) -> ContentSnapshot:
    root = Path(root).resolve()
    rows: list[dict[str, str]] = []
    normalized_paths: set[str] = set()
    for raw in paths:
        pure = PurePosixPath(str(raw))
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise ValueError(f"DEVELOPMENT_REVIEW_SNAPSHOT_PATH_INVALID:{raw}")
        rel = pure.as_posix()
        if rel in normalized_paths:
            continue
        normalized_paths.add(rel)
        absolute = (root / Path(*pure.parts)).resolve()
        try:
            absolute.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"DEVELOPMENT_REVIEW_SNAPSHOT_PATH_INVALID:{raw}") from exc
        if not absolute.is_file():
            raise FileNotFoundError(f"DEVELOPMENT_REVIEW_SNAPSHOT_FILE_MISSING:{rel}")
        rows.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(absolute.read_bytes()).hexdigest(),
            }
        )
    if not rows:
        raise ValueError("DEVELOPMENT_REVIEW_SNAPSHOT_EMPTY")
    ordered = tuple(sorted(rows, key=lambda row: row["path"]))
    payload = {
        "snapshot_version": snapshot_version,
        "files": ordered,
    }
    return ContentSnapshot(
        snapshot_version=snapshot_version,
        files=ordered,
        snapshot_hash=canonical_digest(payload),
    )


def load_bootstrap_review_context(root: str | Path) -> DevelopmentReviewContext:
    root = Path(root).resolve()
    config_path = root / "config" / "development_review_bootstrap_v1.json"
    value = json.loads(config_path.read_text(encoding="utf-8"))
    version = _require_text(
        str(value.get("review_context_version", "")),
        "DEVELOPMENT_REVIEW_CONTEXT_VERSION_REQUIRED",
    )
    return DevelopmentReviewContext(
        review_context_version=version,
        constitution=snapshot_paths(
            root,
            value.get("constitution_paths", ()),
            snapshot_version=f"{version}:CONSTITUTION",
        ),
        architecture_library=snapshot_paths(
            root,
            value.get("architecture_library_paths", ()),
            snapshot_version=f"{version}:ARCHITECTURE_LIBRARY",
        ),
        policy=snapshot_paths(
            root,
            value.get("policy_paths", ()),
            snapshot_version=f"{version}:POLICY",
        ),
    )
