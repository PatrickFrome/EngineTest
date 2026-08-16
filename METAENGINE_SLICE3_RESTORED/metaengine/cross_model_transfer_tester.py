"""METAENGINE Phase 45 — Cross-Model Mechanism Transfer Tester.

Tests whether mechanisms extracted from one engine (e.g., engine_16 LLM)
transfer to other engines (e.g., engine_01-04 native, engine_05-15 reference).

Transfer test loop:
  1. Source mechanism: A0_OBSERVED from source engine (e.g., engine_16)
  2. Hypothesis: mechanism will improve target engine's quality
  3. Experiment: apply mechanism to target engine, measure quality delta
  4. Decision:
     - quality delta > threshold → TRANSFERABLE (A1_MECHANISM_HYPOTHESIS → A2_TRANSFERABLE)
     - quality delta <= 0 → NOT_TRANSFERRED (stays A1)
     - ambiguous → INSUFFICIENT_EVIDENCE

Constitution compliance:
  - Transfer test is an experiment, not truth promotion
  - A2 requires AssimilationGate receipt (constitution guard)
  - No auto-promotion to A3 (external authority required)
  - Mechanisms remain generative (claim_ceiling)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

from .util import canonical_hash


TRANSFER_VERSION = "METAENGINE-CROSS-MODEL-TRANSFER-1"


# ---------------------------------------------------------------------------
# Transfer result enum
# ---------------------------------------------------------------------------


class TransferResult(str, Enum):
    TRANSFERABLE = "TRANSFERABLE"  # quality improved, A1→A2 candidate
    NOT_TRANSFERRED = "NOT_TRANSFERRED"  # quality didn't improve
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # ambiguous
    REJECTED = "REJECTED"  # quality decreased


# ---------------------------------------------------------------------------
# Transfer experiment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferExperiment:
    """A single cross-model transfer experiment."""
    experiment_id: str
    source_engine: str
    target_engine: str
    mechanism_id: str
    source_quality: float  # quality with source engine
    target_quality_baseline: float  # quality of target without mechanism
    target_quality_with_mechanism: float  # quality of target with mechanism
    quality_delta: float  # target_quality_with - target_quality_baseline
    result: TransferResult
    experiment_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "source_engine": self.source_engine,
            "target_engine": self.target_engine,
            "mechanism_id": self.mechanism_id,
            "source_quality": round(self.source_quality, 6),
            "target_quality_baseline": round(self.target_quality_baseline, 6),
            "target_quality_with_mechanism": round(self.target_quality_with_mechanism, 6),
            "quality_delta": round(self.quality_delta, 6),
            "result": self.result.value,
            "truth_effect": "NONE",
            "claim_ceiling": "TRANSFER_EXPERIMENT_IS_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "experiment_hash": self.experiment_hash}


# ---------------------------------------------------------------------------
# Transfer summary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferSummary:
    """Summary of all transfer experiments."""
    total_experiments: int
    transferable_count: int
    not_transferred_count: int
    insufficient_evidence_count: int
    rejected_count: int
    transfer_rate: float  # transferable / total
    mean_quality_delta: float
    experiments: tuple[TransferExperiment, ...]
    summary_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "transfer_version": TRANSFER_VERSION,
            "total_experiments": self.total_experiments,
            "transferable_count": self.transferable_count,
            "not_transferred_count": self.not_transferred_count,
            "insufficient_evidence_count": self.insufficient_evidence_count,
            "rejected_count": self.rejected_count,
            "transfer_rate": round(self.transfer_rate, 6),
            "mean_quality_delta": round(self.mean_quality_delta, 6),
            "experiments": [e.payload() for e in self.experiments],
            "truth_effect": "NONE",
            "claim_ceiling": "TRANSFER_SUMMARY_IS_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "no_auto_promotion_to_a3": True,
                "a2_requires_gate_receipt": True,
                "mechanisms_remain_generative": True,
                "experiments_are_evaluative": True,
            },
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "summary_hash": self.summary_hash}


# ---------------------------------------------------------------------------
# Cross-Model Transfer Tester
# ---------------------------------------------------------------------------


class CrossModelTransferTester:
    """Tests whether mechanisms transfer across engines.

    Usage:
        tester = CrossModelTransferTester(transfer_threshold=0.05)
        experiment = tester.run_experiment(
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="trace_mech.engine_16.abc123",
            source_quality=0.8,
            target_quality_fn=lambda engine_id, mechanism_id: 0.6,  # baseline
            target_quality_with_mechanism_fn=lambda engine_id, mechanism_id: 0.7,  # with mech
        )
        summary = tester.summarize()
    """

    def __init__(
        self,
        *,
        transfer_threshold: float = 0.05,  # min quality delta for TRANSFERABLE
        rejection_threshold: float = -0.05,  # quality delta below this → REJECTED
        seed: int = 42,
    ):
        if not 0.0 < transfer_threshold <= 1.0:
            raise ValueError("TRANSFER_THRESHOLD_MUST_BE_IN_(0, 1]")
        if rejection_threshold > 0.0:
            raise ValueError("REJECTION_THRESHOLD_MUST_BE_NON_POSITIVE")
        self.transfer_threshold = transfer_threshold
        self.rejection_threshold = rejection_threshold
        self.experiments: list[TransferExperiment] = []

    # ------------------------------------------------------------------
    # Single experiment
    # ------------------------------------------------------------------

    def run_experiment(
        self,
        *,
        source_engine: str,
        target_engine: str,
        mechanism_id: str,
        source_quality: float,
        target_quality_baseline: float,
        target_quality_with_mechanism: float,
    ) -> TransferExperiment:
        """Run one transfer experiment.

        Args:
            source_engine: engine that produced the mechanism.
            target_engine: engine to test transfer to.
            mechanism_id: the mechanism being transferred.
            source_quality: quality achieved by source engine.
            target_quality_baseline: quality of target without mechanism.
            target_quality_with_mechanism: quality of target with mechanism.

        Returns:
            TransferExperiment with result.
        """
        delta = target_quality_with_mechanism - target_quality_baseline

        # Determine result
        if delta >= self.transfer_threshold:
            result = TransferResult.TRANSFERABLE
        elif delta <= self.rejection_threshold:
            result = TransferResult.REJECTED
        elif delta > 0:
            result = TransferResult.INSUFFICIENT_EVIDENCE  # positive but below threshold
        else:
            result = TransferResult.NOT_TRANSFERRED  # no improvement

        experiment_id = f"transfer.{source_engine}.{target_engine}.{mechanism_id[-12:]}"

        experiment = TransferExperiment(
            experiment_id=experiment_id,
            source_engine=source_engine,
            target_engine=target_engine,
            mechanism_id=mechanism_id,
            source_quality=source_quality,
            target_quality_baseline=target_quality_baseline,
            target_quality_with_mechanism=target_quality_with_mechanism,
            quality_delta=delta,
            result=result,
            experiment_hash="",
        )
        h = canonical_hash(experiment.payload())
        experiment = TransferExperiment(**{**experiment.__dict__, "experiment_hash": h})
        self.experiments.append(experiment)
        return experiment

    # ------------------------------------------------------------------
    # Batch experiments
    # ------------------------------------------------------------------

    def run_batch(
        self,
        *,
        source_engine: str,
        target_engines: list[str],
        mechanism_id: str,
        source_quality: float,
        quality_fn: Callable[[str, str], tuple[float, float]],
    ) -> list[TransferExperiment]:
        """Run transfer experiments from one source to multiple targets.

        Args:
            source_engine: source engine.
            target_engines: list of target engines.
            mechanism_id: mechanism to transfer.
            source_quality: source engine quality.
            quality_fn: fn(target_engine, mechanism_id) → (baseline, with_mechanism).

        Returns:
            List of TransferExperiment.
        """
        results = []
        for target in target_engines:
            baseline, with_mech = quality_fn(target, mechanism_id)
            exp = self.run_experiment(
                source_engine=source_engine,
                target_engine=target,
                mechanism_id=mechanism_id,
                source_quality=source_quality,
                target_quality_baseline=baseline,
                target_quality_with_mechanism=with_mech,
            )
            results.append(exp)
        return results

    # ------------------------------------------------------------------
    # Mechanism library integration
    # ------------------------------------------------------------------

    def get_transferable_mechanisms(self) -> list[TransferExperiment]:
        """Return experiments where mechanism is TRANSFERABLE."""
        return [e for e in self.experiments if e.result == TransferResult.TRANSFERABLE]

    def advance_transferable_to_a1(
        self,
        library,
    ) -> list:
        """Advance TRANSFERABLE mechanisms from A0 to A1_MECHANISM_HYPOTHESIS.

        Note: A1→A2 requires AssimilationGate receipt (constitution guard).
        This method only does A0→A1, which is always allowed for observed mechanisms.

        Args:
            library: the MechanismLibrary to update.

        Returns:
            List of advanced mechanism IDs.
        """
        from .mechanism_library import MechanismState
        import dataclasses

        transferable = self.get_transferable_mechanisms()
        transferable_ids = {e.mechanism_id for e in transferable}

        advanced = []
        new_candidates = []
        for candidate in library.candidates:
            if candidate.mechanism_id in transferable_ids and candidate.status == MechanismState.A0_OBSERVED:
                # Advance A0 → A1
                updated = dataclasses.replace(candidate, status=MechanismState.A1_MECHANISM_HYPOTHESIS)
                new_candidates.append(updated)
                advanced.append(candidate.mechanism_id)
            else:
                new_candidates.append(candidate)

        # Rebuild library
        new_candidates_sorted = tuple(sorted(new_candidates, key=lambda c: c.mechanism_id))
        new_library = type(library)(
            library_version=library.library_version,
            candidates=new_candidates_sorted,
        )
        return new_library, advanced

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summarize(self) -> TransferSummary:
        """Summarize all transfer experiments."""
        if not self.experiments:
            return TransferSummary(
                total_experiments=0,
                transferable_count=0,
                not_transferred_count=0,
                insufficient_evidence_count=0,
                rejected_count=0,
                transfer_rate=0.0,
                mean_quality_delta=0.0,
                experiments=(),
                summary_hash="",
            )

        total = len(self.experiments)
        transferable = sum(1 for e in self.experiments if e.result == TransferResult.TRANSFERABLE)
        not_transferred = sum(1 for e in self.experiments if e.result == TransferResult.NOT_TRANSFERRED)
        insufficient = sum(1 for e in self.experiments if e.result == TransferResult.INSUFFICIENT_EVIDENCE)
        rejected = sum(1 for e in self.experiments if e.result == TransferResult.REJECTED)

        mean_delta = sum(e.quality_delta for e in self.experiments) / total

        summary = TransferSummary(
            total_experiments=total,
            transferable_count=transferable,
            not_transferred_count=not_transferred,
            insufficient_evidence_count=insufficient,
            rejected_count=rejected,
            transfer_rate=transferable / total if total > 0 else 0.0,
            mean_quality_delta=mean_delta,
            experiments=tuple(self.experiments),
            summary_hash="",
        )
        h = canonical_hash(summary.payload())
        return TransferSummary(**{**summary.__dict__, "summary_hash": h})
