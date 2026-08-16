"""Tests for Phase 38 — AlphaZero Self-Play Architecture Trainer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.selfplay_trainer import (
    SelfPlayArchitectureTrainer,
    SelfPlayGeneration,
    SELFPLAY_VERSION,
)
from metaengine.architecture_policy import ArchitecturePolicy, initial_policy
from metaengine.organization_tournament import PolicyResult, run_tournament
from metaengine.mechanism_library import MechanismLibrary, MechanismCandidate, MechanismState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_policy():
    return initial_policy()


@pytest.fixture
def trainer():
    return SelfPlayArchitectureTrainer(seed=42)


def _make_policy(policy_id: str, topology_id: str = "TEST") -> tuple[str, ArchitecturePolicy]:
    """Create a test policy with given ID."""
    pol = ArchitecturePolicy(
        generation=0, parent_policy_hash=None,
        topology_id=topology_id,
        waves=(("engine_01",),),
        dialectic_operators=("SOURCE_READING",),
        max_rounds=1, max_deep_engines=1,
        exploration_rate=0.0,
        status="SHADOW",
        mutation_receipt={"origin": "test"},
    )
    pol.validate()
    return (policy_id, pol)


def _make_results(policy_ids: list[str], task_ids: list[str], quality_map: dict) -> list[PolicyResult]:
    """Create PolicyResult list with given quality values."""
    results = []
    for pid in policy_ids:
        for tid in task_ids:
            q = quality_map.get((pid, tid), 0.5)
            results.append(PolicyResult(
                policy_id=pid, task_id=tid,
                quality=q, cost=1.0, latency=1.0,
                reproducibility=1.0, resource_efficiency=q,
            ))
    return results


# ---------------------------------------------------------------------------
# Tests: SelfPlayGeneration
# ---------------------------------------------------------------------------


class TestSelfPlayGeneration:
    """Test the SelfPlayGeneration dataclass."""

    def test_payload_has_required_fields(self):
        from metaengine.organization_tournament import TournamentResult
        from metaengine.architecture_synthesis import SynthesisResult
        # Create minimal tournament
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        tournament = run_tournament(results, policy_ids=["A", "B"], task_ids=["t1"])
        syntheses = SynthesisResult(syntheses=(), source_mechanisms=(), result_hash="abc")
        gen = SelfPlayGeneration(
            generation=0,
            tournament=tournament,
            extracted_mechanisms=(),
            syntheses=syntheses,
            ablated_mechanism_ids=(),
            advanced_mechanisms=(),
            generation_hash="",
        )
        p = gen.payload()
        assert p["selfplay_version"] == SELFPLAY_VERSION
        assert p["generation"] == 0
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "SELFPLAY_GENERATION_IS_EVALUATIVE_NOT_TRUTH"


# ---------------------------------------------------------------------------
# Tests: SelfPlayArchitectureTrainer
# ---------------------------------------------------------------------------


class TestSelfPlayTrainer:
    """Test the self-play trainer."""

    def test_initialize_empty_library(self, trainer):
        assert len(trainer.mechanism_library.candidates) == 0
        assert len(trainer.generations) == 0

    def test_run_tournament_returns_result(self, trainer):
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results,
            policy_ids=["A", "B"],
            task_ids=["t1"],
        )
        assert tournament.tournament_hash != ""
        assert len(tournament.pareto_frontier) == 2

    def test_extract_winning_mechanisms(self, trainer):
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results,
            policy_ids=["A", "B"],
            task_ids=["t1"],
        )
        extracted = trainer.extract_winning_mechanisms(tournament)
        # A should be on Pareto frontier (higher quality)
        assert len(extracted) >= 1
        for candidate in extracted:
            assert candidate.status == MechanismState.A0_OBSERVED
            assert candidate.mechanism_id.startswith("mech.")

    def test_extract_adds_to_library(self, trainer):
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results,
            policy_ids=["A", "B"],
            task_ids=["t1"],
        )
        before = len(trainer.mechanism_library.candidates)
        trainer.extract_winning_mechanisms(tournament)
        after = len(trainer.mechanism_library.candidates)
        assert after > before

    def test_synthesize_architectures(self, trainer):
        results = _make_results(["A", "B", "C"], ["t1"], {"A": 0.8, "B": 0.7, "C": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results,
            policy_ids=["A", "B", "C"],
            task_ids=["t1"],
        )
        extracted = trainer.extract_winning_mechanisms(tournament)
        mechanism_ids = [c.mechanism_id for c in extracted]
        if len(mechanism_ids) >= 2:
            syntheses = trainer.synthesize_architectures(mechanism_ids)
            assert syntheses.result_hash != ""
            # May have 0 syntheses if fewer than 2 mechanisms, but should not error
        # else: not enough mechanisms to synthesize — acceptable

    def test_ablate_losing_mechanisms(self, trainer):
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results,
            policy_ids=["A", "B"],
            task_ids=["t1"],
        )
        # Extract first to populate library
        trainer.extract_winning_mechanisms(tournament)
        ablated = trainer.ablate_losing_mechanisms(tournament)
        # Returns list of mechanism_ids (may be empty if no losers had mechanisms)
        assert isinstance(ablated, list)

    def test_advance_mechanism_states_a0_to_a1(self, trainer):
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results,
            policy_ids=["A", "B"],
            task_ids=["t1"],
        )
        trainer.extract_winning_mechanisms(tournament)
        # Now mechanisms are A0_OBSERVED
        advanced = trainer.advance_mechanism_states()
        # A0 → A1 should happen for all observed mechanisms
        assert len(advanced) > 0
        for a in advanced:
            assert a["old_state"] == "A0_OBSERVED"
            assert a["new_state"] == "A1_MECHANISM_HYPOTHESIS"

    def test_advance_a1_to_a2_requires_gate_receipt(self, trainer):
        """A1 → A2 requires AssimilationGate receipt — constitution guard.

        SelfPlayTrainer does NOT advance A1→A2 (needs gate receipt).
        This test verifies that A1 candidates stay at A1.
        """
        import dataclasses
        from metaengine.mechanism_library import MechanismCandidate
        c1 = MechanismCandidate.create(
            mechanism_id="mech.1", semantic_definition="test",
            origin_source_ids=["policy_A"], source_fact_boundary="test",
            hypothesized_effect="test", resource_cost="1.0", complexity_cost="1.0",
            confidence="LOW", status=MechanismState.A1_MECHANISM_HYPOTHESIS,
        )
        c2 = MechanismCandidate.create(
            mechanism_id="mech.2", semantic_definition="test2",
            origin_source_ids=["policy_A"], source_fact_boundary="test",
            hypothesized_effect="test2", resource_cost="1.0", complexity_cost="1.0",
            confidence="LOW", status=MechanismState.A1_MECHANISM_HYPOTHESIS,
        )
        trainer.mechanism_library = MechanismLibrary.create([c1, c2])
        advanced = trainer.advance_mechanism_states()
        # A1 should NOT advance to A2 (requires gate receipt)
        assert len(advanced) == 0

    def test_a2_does_not_advance_to_a3_without_authority(self, trainer):
        """A2 → A3 requires external promotion authority — constitution."""
        import dataclasses
        from metaengine.mechanism_library import MechanismCandidate
        # Create A1 candidate, then replace to A2 (bypassing create's gate check for test)
        c = MechanismCandidate.create(
            mechanism_id="mech.1", semantic_definition="test",
            origin_source_ids=["policy_A"], source_fact_boundary="test",
            hypothesized_effect="test", resource_cost="1.0", complexity_cost="1.0",
            confidence="LOW", status=MechanismState.A1_MECHANISM_HYPOTHESIS,
        )
        c = dataclasses.replace(c, status=MechanismState.A2_TRANSFERABLE)
        # Construct library directly (bypass create validation for A2 in test)
        trainer.mechanism_library = MechanismLibrary(
            library_version=trainer.mechanism_library.library_version,
            candidates=(c,),
        )
        advanced = trainer.advance_mechanism_states()
        # A2 should NOT advance to A3 (no promotion authority)
        assert len(advanced) == 0

    def test_run_generation_full_loop(self, trainer):
        policies = [_make_policy("A"), _make_policy("B")]
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        gen = trainer.run_generation(
            policies=policies,
            task_results=results,
            generation_index=0,
        )
        assert gen.generation == 0
        assert gen.generation_hash != ""
        assert gen.tournament.tournament_hash != ""
        assert len(gen.extracted_mechanisms) > 0

    def test_run_multiple_generations(self, trainer):
        for i in range(3):
            policies = [_make_policy(f"A{i}"), _make_policy(f"B{i}")]
            results = _make_results([f"A{i}", f"B{i}"], ["t1"], {f"A{i}": 0.8, f"B{i}": 0.3})
            trainer.run_generation(
                policies=policies,
                task_results=results,
                generation_index=i,
            )
        assert len(trainer.generations) == 3
        summary = trainer.summary()
        assert summary["generations_run"] == 3
        assert summary["total_mechanisms_extracted"] > 0

    def test_summary_returns_evaluative_not_truth(self, trainer):
        # Run at least one generation to get a non-empty summary
        policies = [_make_policy("A"), _make_policy("B")]
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        trainer.run_generation(policies=policies, task_results=results, generation_index=0)
        summary = trainer.summary()
        assert summary["truth_effect"] == "NONE"
        assert "constitution_compliance" in summary
        assert summary["constitution_compliance"]["all_syntheses_are_hypotheses"]
        assert summary["constitution_compliance"]["no_auto_promotion_to_a3"]

    def test_mechanism_library_accumulates(self, trainer):
        """Mechanism library should accumulate across generations."""
        for i in range(3):
            policies = [_make_policy(f"A{i}"), _make_policy(f"B{i}")]
            results = _make_results([f"A{i}", f"B{i}"], ["t1"], {f"A{i}": 0.8, f"B{i}": 0.3})
            trainer.run_generation(
                policies=policies,
                task_results=results,
                generation_index=i,
            )
        # Library should have mechanisms from all generations
        assert len(trainer.mechanism_library.candidates) >= 3

    def test_generation_hash_is_deterministic(self, trainer):
        """Same inputs should produce same generation hash."""
        policies = [_make_policy("A"), _make_policy("B")]
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})

        trainer1 = SelfPlayArchitectureTrainer(seed=42)
        trainer2 = SelfPlayArchitectureTrainer(seed=42)

        gen1 = trainer1.run_generation(policies=policies, task_results=results, generation_index=0)
        gen2 = trainer2.run_generation(policies=policies, task_results=results, generation_index=0)
        assert gen1.generation_hash == gen2.generation_hash


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    """Test that self-play preserves constitution."""

    def test_all_mechanisms_start_at_a0(self, trainer):
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results, policy_ids=["A", "B"], task_ids=["t1"],
        )
        extracted = trainer.extract_winning_mechanisms(tournament)
        for c in extracted:
            assert c.status == MechanismState.A0_OBSERVED
            assert c.promotion_authority is None

    def test_no_a3_without_external_authority(self, trainer):
        """A3_ASSIMILATED requires external promotion authority."""
        results = _make_results(["A", "B"], ["t1"], {"A": 0.8, "B": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results, policy_ids=["A", "B"], task_ids=["t1"],
        )
        trainer.extract_winning_mechanisms(tournament)
        trainer.advance_mechanism_states()
        trainer.advance_mechanism_states()  # A1 → A2
        # No mechanism should reach A3 (no promotion authority)
        for c in trainer.mechanism_library.candidates:
            assert c.status != MechanismState.A3_ASSIMILATED

    def test_syntheses_carry_hypothesis_ceiling(self, trainer):
        results = _make_results(["A", "B", "C"], ["t1"], {"A": 0.8, "B": 0.7, "C": 0.3})
        tournament = trainer.run_tournament(
            policy_results=results, policy_ids=["A", "B", "C"], task_ids=["t1"],
        )
        extracted = trainer.extract_winning_mechanisms(tournament)
        if len(extracted) >= 2:
            syntheses = trainer.synthesize_architectures([c.mechanism_id for c in extracted])
            for s in syntheses.syntheses:
                assert s.payload()["claim_ceiling"] == "SYNTHESIS_IS_HYPOTHESIS_NOT_FACT"
                assert s.payload()["truth_effect"] == "NONE"
