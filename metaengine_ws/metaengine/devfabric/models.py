from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .codec import canonical_digest


class PrivacyClass(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class RiskClass(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    RELEASE = "RELEASE"


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    INCONCLUSIVE_SECURITY_FEED = "INCONCLUSIVE_SECURITY_FEED"


def _tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    task_hash: str
    source_checkpoint_id: str
    source_tree_hash: str
    objective: str
    acceptance_tests: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    capabilities_required: tuple[str, ...]
    risk_class: RiskClass
    privacy_class: PrivacyClass
    zero_spend: bool = True

    @classmethod
    def create(
        cls,
        *,
        source_checkpoint_id: str,
        source_tree_hash: str,
        objective: str,
        acceptance_tests: Iterable[str],
        allowed_paths: Iterable[str],
        forbidden_paths: Iterable[str],
        capabilities_required: Iterable[str],
        risk_class: RiskClass,
        privacy_class: PrivacyClass,
        zero_spend: bool = True,
    ) -> "TaskEnvelope":
        payload = {
            "source_checkpoint_id": source_checkpoint_id,
            "source_tree_hash": source_tree_hash,
            "objective": objective,
            "acceptance_tests": _tuple(acceptance_tests),
            "allowed_paths": _tuple(allowed_paths),
            "forbidden_paths": _tuple(forbidden_paths),
            "capabilities_required": _tuple(capabilities_required),
            "risk_class": risk_class,
            "privacy_class": privacy_class,
            "zero_spend": bool(zero_spend),
        }
        digest = canonical_digest(payload)
        return cls(task_id=f"task-{digest[:20]}", task_hash=digest, **payload)


@dataclass(frozen=True)
class CandidateReceipt:
    candidate_hash: str
    task_id: str
    provider_id: str
    base_tree_hash: str
    patch_hash: str
    changed_paths: tuple[str, ...]
    metadata: tuple[tuple[str, str], ...]

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        provider_id: str,
        base_tree_hash: str,
        patch_hash: str,
        changed_paths: Iterable[str],
        metadata: Mapping[str, str] | None = None,
    ) -> "CandidateReceipt":
        payload = {
            "task_id": task_id,
            "provider_id": provider_id,
            "base_tree_hash": base_tree_hash,
            "patch_hash": patch_hash,
            "changed_paths": tuple(sorted(set(changed_paths))),
            "metadata": tuple(sorted((str(k), str(v)) for k, v in (metadata or {}).items())),
        }
        return cls(candidate_hash=canonical_digest(payload), **payload)


@dataclass(frozen=True)
class VerificationReceipt:
    verification_hash: str
    candidate_hash: str
    verifier_id: str
    verifier_version: str
    commands: tuple[str, ...]
    exit_statuses: tuple[int, ...]
    verdict: Verdict
    evidence_hashes: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        candidate_hash: str,
        verifier_id: str,
        verifier_version: str,
        commands: Iterable[str],
        exit_statuses: Iterable[int],
        verdict: Verdict,
        evidence_hashes: Iterable[str] = (),
    ) -> "VerificationReceipt":
        payload = {
            "candidate_hash": candidate_hash,
            "verifier_id": verifier_id,
            "verifier_version": verifier_version,
            "commands": tuple(commands),
            "exit_statuses": tuple(int(x) for x in exit_statuses),
            "verdict": verdict,
            "evidence_hashes": tuple(evidence_hashes),
        }
        return cls(verification_hash=canonical_digest(payload), **payload)


@dataclass(frozen=True)
class PromotionProposal:
    proposal_hash: str
    task_hash: str
    candidate_hash: str
    verification_hashes: tuple[str, ...]
    target_checkpoint_parent: str
    auto_promote: bool = False

    @classmethod
    def create(
        cls,
        *,
        task_hash: str,
        candidate_hash: str,
        verification_hashes: Iterable[str],
        target_checkpoint_parent: str,
    ) -> "PromotionProposal":
        payload = {
            "task_hash": task_hash,
            "candidate_hash": candidate_hash,
            "verification_hashes": tuple(sorted(verification_hashes)),
            "target_checkpoint_parent": target_checkpoint_parent,
            "auto_promote": False,
        }
        return cls(proposal_hash=canonical_digest(payload), **payload)
