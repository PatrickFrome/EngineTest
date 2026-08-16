"""METAENGINE Phase 6 — Architectural Assimilation Loop.

Implements the closed loop from the chat-export vision:

EXTERNAL SYSTEM → CHARACTERIZATION → BEHAVIORAL FINGERPRINT →
MECHANISM HYPOTHESES → ABSTRACT MECHANISM → METAENGINE IMPLEMENTATION →
ABLATION → TRANSFER TEST → ORGANIZATION TOURNAMENT →
ASSIMILATE / REJECT / RETAIN AS CONTEXTUAL

This is the loop that lets MetaEngine learn from external systems without
copying them — extracting transferable mechanisms, not implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .util import canonical_hash
from .mechanism_library import MechanismCandidate, MechanismState
from .assimilation import AssimilationGate, TransferReceipt, TransferRegime


ASSIMILATION_LOOP_VERSION = "METAENGINE-ARCHITECTURAL-ASSIMILATION-1"


class AssimilationDecision(str, Enum):
    REJECTED = "REJECTED"
    CONTEXTUAL = "CONTEXTUAL"
    TRANSFERABLE = "TRANSFERABLE"
    ASSIMILATED = "ASSIMILATED"


class FingerprintKind(str, Enum):
    BEHAVIORAL = "BEHAVIORAL"
    STRUCTURAL = "STRUCTURAL"
    PERFORMANCE = "PERFORMANCE"


@dataclass(frozen=True)
class BehavioralFingerprint:
    """Observable behavior of an external system."""
    system_id: str
    fingerprint_kind: FingerprintKind
    observations: tuple[tuple[str, str], ...]  # (metric, value) pairs

    def payload(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "fingerprint_kind": self.fingerprint_kind.value,
            "observations": [list(item) for item in self.observations],
        }

    @property
    def fingerprint_hash(self) -> str:
        return canonical_hash(self.payload())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BehavioralFingerprint":
        return cls(
            system_id=str(value["system_id"]),
            fingerprint_kind=FingerprintKind(str(value["fingerprint_kind"])),
            observations=tuple(tuple(item) for item in value.get("observations", ())),
        )


@dataclass(frozen=True)
class MechanismHypothesis:
    """A competing explanation for an observed behavior."""
    hypothesis_id: str
    mechanism_description: str
    expected_effect: str
    falsification_test: str
    source_system_id: str

    def payload(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "mechanism_description": self.mechanism_description,
            "expected_effect": self.expected_effect,
            "falsification_test": self.falsification_test,
            "source_system_id": self.source_system_id,
        }

    @property
    def hypothesis_hash(self) -> str:
        return canonical_hash(self.payload())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MechanismHypothesis":
        return cls(
            hypothesis_id=str(value["hypothesis_id"]),
            mechanism_description=str(value["mechanism_description"]),
            expected_effect=str(value["expected_effect"]),
            falsification_test=str(value["falsification_test"]),
            source_system_id=str(value["source_system_id"]),
        )


@dataclass(frozen=True)
class TransferExperiment:
    """A transfer test: does the mechanism work on a different resource/model?"""
    experiment_id: str
    mechanism_hypothesis_hash: str
    source_resource_id: str
    target_resource_id: str
    result: str  # TRANSFERRED / NOT_TRANSFERRED / PARTIAL_TRANSFER
    evidence_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "mechanism_hypothesis_hash": self.mechanism_hypothesis_hash,
            "source_resource_id": self.source_resource_id,
            "target_resource_id": self.target_resource_id,
            "result": self.result,
            "evidence_hash": self.evidence_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferExperiment":
        return cls(
            experiment_id=str(value["experiment_id"]),
            mechanism_hypothesis_hash=str(value["mechanism_hypothesis_hash"]),
            source_resource_id=str(value["source_resource_id"]),
            target_resource_id=str(value["target_resource_id"]),
            result=str(value["result"]),
            evidence_hash=str(value["evidence_hash"]),
        )


@dataclass(frozen=True)
class AssimilationResult:
    """Final result of the assimilation loop for one mechanism."""
    loop_version: str
    system_id: str
    fingerprint_hash: str
    hypotheses: tuple[MechanismHypothesis, ...]
    transfer_experiments: tuple[TransferExperiment, ...]
    decision: AssimilationDecision
    mechanism_candidate_id: str | None
    truth_effect: str
    assimilation_effect: str
    result_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "loop_version": self.loop_version,
            "system_id": self.system_id,
            "fingerprint_hash": self.fingerprint_hash,
            "hypotheses": [h.payload() for h in self.hypotheses],
            "transfer_experiments": [e.payload() for e in self.transfer_experiments],
            "decision": self.decision.value,
            "mechanism_candidate_id": self.mechanism_candidate_id,
            "truth_effect": self.truth_effect,
            "assimilation_effect": self.assimilation_effect,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "result_hash": self.result_hash}


def run_assimilation_loop(
    fingerprint: BehavioralFingerprint,
    hypotheses: Iterable[MechanismHypothesis],
    transfer_experiments: Iterable[TransferExperiment] = (),
) -> AssimilationResult:
    """Run the assimilation loop for one external system.

    Decision logic:
    - If any transfer experiment returns TRANSFERRED → TRANSFERABLE
    - If all return NOT_TRANSFERRED → REJECTED
    - If some PARTIAL_TRANSFER → CONTEXTUAL
    - ASSIMILATED only when a separate promotion gate authorizes it
      (not automatic — requires separate authorized gate per constitution)
    """
    hyps = tuple(sorted(hypotheses, key=lambda h: h.hypothesis_id))
    experiments = tuple(sorted(transfer_experiments, key=lambda e: e.experiment_id))

    if not experiments:
        decision = AssimilationDecision.REJECTED
    elif all(e.result == "TRANSFERRED" for e in experiments):
        decision = AssimilationDecision.TRANSFERABLE
    elif any(e.result == "TRANSFERRED" for e in experiments):
        decision = AssimilationDecision.CONTEXTUAL
    elif any(e.result == "PARTIAL_TRANSFER" for e in experiments):
        decision = AssimilationDecision.CONTEXTUAL
    else:
        decision = AssimilationDecision.REJECTED

    # Mechanism candidate only for TRANSFERABLE (not ASSIMILATED — that needs separate gate)
    mech_id = None
    if decision == AssimilationDecision.TRANSFERABLE:
        mech_id = f"mec.assimilated.{fingerprint.system_id[:16]}"

    result = AssimilationResult(
        loop_version=ASSIMILATION_LOOP_VERSION,
        system_id=fingerprint.system_id,
        fingerprint_hash=fingerprint.fingerprint_hash,
        hypotheses=hyps,
        transfer_experiments=experiments,
        decision=decision,
        mechanism_candidate_id=mech_id,
        truth_effect="NONE",
        assimilation_effect="NONE",  # assimilation_effect stays NONE until separate gate authorizes
        result_hash="",
    )
    h = canonical_hash(result.payload())
    return AssimilationResult(**{**result.__dict__, "result_hash": h})
