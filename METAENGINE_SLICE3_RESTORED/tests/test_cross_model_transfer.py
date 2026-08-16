"""Tests for Phase 45 — Cross-Model Mechanism Transfer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.cross_model_transfer_tester import (
    CrossModelTransferTester,
    TransferExperiment,
    TransferSummary,
    TransferResult,
    TRANSFER_VERSION,
)
from metaengine.mechanism_library import (
    MechanismLibrary,
    MechanismCandidate,
    MechanismState,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tester():
    return CrossModelTransferTester(
        transfer_threshold=0.05,
        rejection_threshold=-0.05,
        seed=42,
    )


def make_mechanism_candidate(mechanism_id, status=MechanismState.A0_OBSERVED):
    """Create a minimal MechanismCandidate for testing."""
    return MechanismCandidate.create(
        mechanism_id=mechanism_id,
        semantic_definition="test mechanism",
        origin_source_ids=["engine_16"],
        source_fact_boundary="OWN_LLM_RUN",
        hypothesized_effect="improves quality",
        resource_cost="low",
        complexity_cost="low",
        confidence="LOW",
        status=status,
    )


# ---------------------------------------------------------------------------
# Tests: TransferResult enum
# ---------------------------------------------------------------------------


class TestTransferResult:
    def test_all_values(self):
        assert TransferResult.TRANSFERABLE.value == "TRANSFERABLE"
        assert TransferResult.NOT_TRANSFERRED.value == "NOT_TRANSFERRED"
        assert TransferResult.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"
        assert TransferResult.REJECTED.value == "REJECTED"

    def test_count(self):
        assert len(TransferResult) == 4


# ---------------------------------------------------------------------------
# Tests: TransferExperiment
# ---------------------------------------------------------------------------


class TestTransferExperiment:
    def test_payload_has_required_fields(self):
        e = TransferExperiment(
            experiment_id="test.001",
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="mech.001",
            source_quality=0.8,
            target_quality_baseline=0.5,
            target_quality_with_mechanism=0.7,
            quality_delta=0.2,
            result=TransferResult.TRANSFERABLE,
            experiment_hash="abc",
        )
        p = e.payload()
        assert p["experiment_id"] == "test.001"
        assert p["result"] == "TRANSFERABLE"
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "TRANSFER_EXPERIMENT_IS_EVALUATIVE_NOT_TRUTH"

    def test_as_dict_includes_hash(self):
        e = TransferExperiment(
            experiment_id="t", source_engine="s", target_engine="t",
            mechanism_id="m", source_quality=0.5, target_quality_baseline=0.5,
            target_quality_with_mechanism=0.6, quality_delta=0.1,
            result=TransferResult.TRANSFERABLE, experiment_hash="abc123",
        )
        d = e.as_dict()
        assert d["experiment_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: TransferSummary
# ---------------------------------------------------------------------------


class TestTransferSummary:
    def test_empty_summary(self):
        s = TransferSummary(
            total_experiments=0,
            transferable_count=0,
            not_transferred_count=0,
            insufficient_evidence_count=0,
            rejected_count=0,
            transfer_rate=0.0,
            mean_quality_delta=0.0,
            experiments=(),
            summary_hash="abc",
        )
        p = s.payload()
        assert p["transfer_version"] == TRANSFER_VERSION
        assert p["truth_effect"] == "NONE"

    def test_payload_constitution_compliance(self):
        s = TransferSummary(
            total_experiments=1,
            transferable_count=1,
            not_transferred_count=0,
            insufficient_evidence_count=0,
            rejected_count=0,
            transfer_rate=1.0,
            mean_quality_delta=0.1,
            experiments=(),
            summary_hash="abc",
        )
        p = s.payload()
        assert p["constitution_compliance"]["no_auto_promotion_to_a3"] is True
        assert p["constitution_compliance"]["a2_requires_gate_receipt"] is True


# ---------------------------------------------------------------------------
# Tests: CrossModelTransferTester initialization
# ---------------------------------------------------------------------------


class TestTesterInit:
    def test_initializes_empty(self, tester):
        assert tester.experiments == []
        assert tester.transfer_threshold == 0.05

    def test_transfer_threshold_validation(self):
        with pytest.raises(ValueError, match="TRANSFER_THRESHOLD_MUST_BE_IN"):
            CrossModelTransferTester(transfer_threshold=0.0)

    def test_transfer_threshold_upper_bound(self):
        with pytest.raises(ValueError, match="TRANSFER_THRESHOLD_MUST_BE_IN"):
            CrossModelTransferTester(transfer_threshold=1.5)

    def test_rejection_threshold_validation(self):
        with pytest.raises(ValueError, match="REJECTION_THRESHOLD_MUST_BE_NON_POSITIVE"):
            CrossModelTransferTester(rejection_threshold=0.1)


# ---------------------------------------------------------------------------
# Tests: Single experiment
# ---------------------------------------------------------------------------


class TestSingleExperiment:
    def test_run_experiment_returns_result(self, tester):
        exp = tester.run_experiment(
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="mech.001",
            source_quality=0.8,
            target_quality_baseline=0.5,
            target_quality_with_mechanism=0.7,
        )
        assert isinstance(exp, TransferExperiment)
        assert exp.source_engine == "engine_16"
        assert exp.target_engine == "engine_01"
        assert exp.experiment_hash != ""

    def test_quality_delta_computed(self, tester):
        exp = tester.run_experiment(
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="mech.001",
            source_quality=0.8,
            target_quality_baseline=0.5,
            target_quality_with_mechanism=0.7,
        )
        assert exp.quality_delta == pytest.approx(0.2, abs=0.001)

    def test_transferable_result(self, tester):
        exp = tester.run_experiment(
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="mech.001",
            source_quality=0.8,
            target_quality_baseline=0.5,
            target_quality_with_mechanism=0.7,  # delta=0.2 > threshold=0.05
        )
        assert exp.result == TransferResult.TRANSFERABLE

    def test_not_transferred_result(self, tester):
        exp = tester.run_experiment(
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="mech.001",
            source_quality=0.8,
            target_quality_baseline=0.5,
            target_quality_with_mechanism=0.5,  # delta=0.0
        )
        assert exp.result == TransferResult.NOT_TRANSFERRED

    def test_rejected_result(self, tester):
        exp = tester.run_experiment(
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="mech.001",
            source_quality=0.8,
            target_quality_baseline=0.5,
            target_quality_with_mechanism=0.4,  # delta=-0.1 < rejection_threshold=-0.05
        )
        assert exp.result == TransferResult.REJECTED

    def test_insufficient_evidence_result(self, tester):
        exp = tester.run_experiment(
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="mech.001",
            source_quality=0.8,
            target_quality_baseline=0.5,
            target_quality_with_mechanism=0.52,  # delta=0.02, positive but below threshold=0.05
        )
        assert exp.result == TransferResult.INSUFFICIENT_EVIDENCE

    def test_experiment_added_to_history(self, tester):
        tester.run_experiment(
            source_engine="engine_16",
            target_engine="engine_01",
            mechanism_id="mech.001",
            source_quality=0.8,
            target_quality_baseline=0.5,
            target_quality_with_mechanism=0.7,
        )
        assert len(tester.experiments) == 1

    def test_experiment_deterministic_hash(self, tester):
        e1 = tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="mech.001", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.7,
        )
        tester.experiments.clear()
        e2 = tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="mech.001", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.7,
        )
        assert e1.experiment_hash == e2.experiment_hash


# ---------------------------------------------------------------------------
# Tests: Batch experiments
# ---------------------------------------------------------------------------


class TestBatchExperiments:
    def test_run_batch_multiple_targets(self, tester):
        def quality_fn(target, mech):
            # All targets improve by 0.1
            return (0.5, 0.6)

        results = tester.run_batch(
            source_engine="engine_16",
            target_engines=["engine_01", "engine_02", "engine_03"],
            mechanism_id="mech.001",
            source_quality=0.8,
            quality_fn=quality_fn,
        )
        assert len(results) == 3
        for r in results:
            assert r.result == TransferResult.TRANSFERABLE

    def test_run_batch_varied_results(self, tester):
        def quality_fn(target, mech):
            if target == "engine_01":
                return (0.5, 0.7)  # transferable
            elif target == "engine_02":
                return (0.5, 0.5)  # not transferred
            else:
                return (0.5, 0.4)  # rejected

        results = tester.run_batch(
            source_engine="engine_16",
            target_engines=["engine_01", "engine_02", "engine_03"],
            mechanism_id="mech.001",
            source_quality=0.8,
            quality_fn=quality_fn,
        )
        assert results[0].result == TransferResult.TRANSFERABLE
        assert results[1].result == TransferResult.NOT_TRANSFERRED
        assert results[2].result == TransferResult.REJECTED


# ---------------------------------------------------------------------------
# Tests: Mechanism library integration
# ---------------------------------------------------------------------------


class TestMechanismLibraryIntegration:
    def test_get_transferable_mechanisms(self, tester):
        # Add one transferable, one not
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="mech.good", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.7,
        )
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_02",
            mechanism_id="mech.bad", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.5,
        )
        transferable = tester.get_transferable_mechanisms()
        assert len(transferable) == 1
        assert transferable[0].mechanism_id == "mech.good"

    def test_advance_transferable_to_a1(self, tester):
        # Create library with A0 mechanisms
        c1 = make_mechanism_candidate("mech.good", MechanismState.A0_OBSERVED)
        c2 = make_mechanism_candidate("mech.bad", MechanismState.A0_OBSERVED)
        library = MechanismLibrary.create([c1, c2])

        # Run experiment: mech.good transfers, mech.bad doesn't
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="mech.good", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.7,
        )
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_02",
            mechanism_id="mech.bad", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.5,
        )

        new_library, advanced = tester.advance_transferable_to_a1(library)
        assert "mech.good" in advanced
        assert "mech.bad" not in advanced

        # Check statuses
        for c in new_library.candidates:
            if c.mechanism_id == "mech.good":
                assert c.status == MechanismState.A1_MECHANISM_HYPOTHESIS
            elif c.mechanism_id == "mech.bad":
                assert c.status == MechanismState.A0_OBSERVED  # unchanged

    def test_advance_does_not_reach_a2(self, tester):
        """A1→A2 requires AssimilationGate receipt — constitution guard."""
        c1 = make_mechanism_candidate("mech.good", MechanismState.A0_OBSERVED)
        library = MechanismLibrary.create([c1])

        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="mech.good", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.7,
        )

        new_library, advanced = tester.advance_transferable_to_a1(library)
        # Should be A1, NOT A2
        for c in new_library.candidates:
            if c.mechanism_id == "mech.good":
                assert c.status == MechanismState.A1_MECHANISM_HYPOTHESIS
                assert c.status != MechanismState.A2_TRANSFERABLE


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_empty_summary(self, tester):
        summary = tester.summarize()
        assert summary.total_experiments == 0
        assert summary.transfer_rate == 0.0

    def test_summary_after_experiments(self, tester):
        # 2 transferable, 1 not, 1 rejected
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="m1", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.7,
        )
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_02",
            mechanism_id="m2", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.8,
        )
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_03",
            mechanism_id="m3", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.5,
        )
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_04",
            mechanism_id="m4", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.4,
        )

        summary = tester.summarize()
        assert summary.total_experiments == 4
        assert summary.transferable_count == 2
        assert summary.not_transferred_count == 1
        assert summary.rejected_count == 1
        assert summary.transfer_rate == 0.5  # 2/4
        assert summary.summary_hash != ""

    def test_summary_constitution_compliance(self, tester):
        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="m1", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.7,
        )
        summary = tester.summarize()
        p = summary.payload()
        assert p["constitution_compliance"]["no_auto_promotion_to_a3"] is True
        assert p["constitution_compliance"]["a2_requires_gate_receipt"] is True
        assert p["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_no_a3_promotion(self, tester):
        """Transfer tester never promotes to A3."""
        c1 = make_mechanism_candidate("mech.test", MechanismState.A0_OBSERVED)
        library = MechanismLibrary.create([c1])

        tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="mech.test", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.9,
        )

        new_library, advanced = tester.advance_transferable_to_a1(library)
        for c in new_library.candidates:
            assert c.status != MechanismState.A3_ASSIMILATED

    def test_all_experiments_evaluative(self, tester):
        exp = tester.run_experiment(
            source_engine="engine_16", target_engine="engine_01",
            mechanism_id="m1", source_quality=0.8,
            target_quality_baseline=0.5, target_quality_with_mechanism=0.7,
        )
        assert exp.payload()["truth_effect"] == "NONE"
        assert "EVALUATIVE" in exp.payload()["claim_ceiling"]

    def test_transfer_tester_no_code_modification(self, tester):
        """Transfer tester has no methods to modify code."""
        assert not hasattr(tester, "modify_code")
        assert not hasattr(tester, "execute_code")
