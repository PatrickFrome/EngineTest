"""METAENGINE Phase 24-30 — Advanced integration tests.

Phase 24: LLM adapter registered in AdapterRegistry
Phase 25: Sealed Organization Tournament end-to-end
Phase 26: Recursive Self-Improvement measurement
Phase 27: Architecture Assimilation from external system
Phase 28: Autonomous Experiment Loop
Phase 29: Cross-Model Validation
Phase 30: Meta-Learning (learning to learn)
"""

from __future__ import annotations

import json
import pytest

from metaengine.adapters.registry import AdapterRegistry


# ===========================================================================
# Phase 24: LLM Adapter Registration
# ===========================================================================


class TestLLMAdapterRegistration:
    def test_llm_model_mode_in_registry(self):
        assert "LLM_MODEL" in AdapterRegistry.MODES

    def test_llm_disclosure(self):
        reg = AdapterRegistry()
        d = reg.disclosure({"execution_mode": "LLM_MODEL"})
        assert d["adapter_kind"] == "LLM_MODEL"
        assert d["implementation_level"] == "REAL_LLM_EXECUTOR"
        assert d["silent_fallback_allowed"] is False

    def test_llm_adapter_created_with_config(self):
        from metaengine.llm_model_adapter import LLMModelAdapter, LLMModelConfig
        reg = AdapterRegistry()
        record = {
            "engine_id": "engine_llm_01",
            "execution_mode": "LLM_MODEL",
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model_name": "llama3.2",
            "llm_api_key_env": "OLLAMA_API_KEY",
        }
        adapter = reg.create(record, "/tmp")
        assert isinstance(adapter, LLMModelAdapter)
        assert adapter.config.model_name == "llama3.2"
        assert adapter.config.endpoint == "http://localhost:11434/api/generate"

    def test_llm_adapter_uses_env_var_name_not_key(self):
        reg = AdapterRegistry()
        record = {
            "engine_id": "test",
            "execution_mode": "LLM_MODEL",
            "llm_api_key_env": "MY_SECRET_KEY",
        }
        adapter = reg.create(record, "/tmp")
        assert adapter.config.api_key_env == "MY_SECRET_KEY"

    def test_llm_adapter_default_config(self):
        reg = AdapterRegistry()
        adapter = reg.create({"engine_id": "t", "execution_mode": "LLM_MODEL"}, "/tmp")
        assert adapter.config.max_tokens == 2048
        assert adapter.config.temperature == 0.7

    def test_llm_adapter_no_silent_fallback(self):
        """If LLM endpoint is unreachable, adapter must FAILED — not silently simulate."""
        reg = AdapterRegistry()
        adapter = reg.create({"engine_id": "t", "execution_mode": "LLM_MODEL"}, "/tmp")
        # Run with no input file → should fail, not simulate
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test")
            f.flush()
            result = adapter.run(f.name, "/tmp/llm_test_out", {"meta_run_id": "test"})
        # Should be FAILED (no Ollama running) — NOT REFERENCE_SIMULATION_COMPLETE
        assert result.status in ("FAILED", "COMPLETE")  # COMPLETE if Ollama is running
        assert result.adapter_kind == "LLM_MODEL"
        assert result.implementation_level == "REAL_LLM_EXECUTOR"

    def test_unknown_mode_still_rejected(self):
        reg = AdapterRegistry()
        with pytest.raises(ValueError, match="UNKNOWN_ADAPTER_MODE"):
            reg.create({"execution_mode": "BOGUS"}, "/tmp")

    def test_existing_modes_preserved(self):
        assert "NODE_NATIVE" in AdapterRegistry.MODES
        assert "PYTHON_REFERENCE_CONTRACT" in AdapterRegistry.MODES


# ===========================================================================
# Phase 25: Sealed Organization Tournament end-to-end
# ===========================================================================


class TestSealedOrganizationTournament:
    def test_tournament_runs_on_sealed_tasks(self):
        from metaengine.sealed_benchmark import SealedBenchmarkSuite
        from metaengine.organization_tournament import run_tournament, PolicyResult

        suite = SealedBenchmarkSuite(seed=42)
        tasks = suite.generate_sealed_tasks(count=3)

        # 4 organization policies
        policies = ["SINGLE_MODEL", "MODEL_PLUS_VERIFIER", "TWO_MODELS_SYNTHESIS", "FEDERATION"]

        # Synthetic results: each policy on each task
        results = []
        for pol in policies:
            for task in tasks:
                # Give each policy different quality per task
                q = {"SINGLE_MODEL": 0.6, "MODEL_PLUS_VERIFIER": 0.8,
                     "TWO_MODELS_SYNTHESIS": 0.7, "FEDERATION": 0.75}[pol]
                results.append(PolicyResult(
                    policy_id=pol, task_id=task.task_id,
                    quality=q, cost=1.0, latency=0.5,
                    reproducibility=1.0, resource_efficiency=0.5,
                ))

        tour = run_tournament(results, policy_ids=policies, task_ids=[t.task_id for t in tasks])

        assert len(tour.pairwise) > 0
        assert len(tour.pareto_frontier) == 4
        # MODEL_PLUS_VERIFIER should be non-dominated (highest quality, same cost)
        non_dom = [e for e in tour.pareto_frontier if not e.dominated]
        assert "MODEL_PLUS_VERIFIER" in [e.policy_id for e in non_dom]

    def test_tournament_produces_dominance(self):
        from metaengine.organization_tournament import run_tournament, PolicyResult
        results = [
            PolicyResult("P0", "T0", 0.9, 0.5, 0.3, 1.0, 0.5),
            PolicyResult("P1", "T0", 0.5, 1.0, 0.8, 1.0, 0.5),
        ]
        tour = run_tournament(results, policy_ids=["P0", "P1"], task_ids=["T0"])
        assert "P1" in tour.dominance.get("P0", [])

    def test_tournament_truth_effect_none(self):
        from metaengine.organization_tournament import run_tournament, PolicyResult
        results = [PolicyResult("P0", "T0", 0.8, 1.0, 0.5, 1.0, 0.5)]
        tour = run_tournament(results, policy_ids=["P0"], task_ids=["T0"])
        assert tour.payload()["truth_effect"] == "NONE"

    def test_tournament_hash_deterministic(self):
        from metaengine.organization_tournament import run_tournament, PolicyResult
        r = [PolicyResult("P0", "T0", 0.8, 1.0, 0.5, 1.0, 0.5),
             PolicyResult("P1", "T0", 0.7, 0.8, 0.4, 1.0, 0.5)]
        t1 = run_tournament(r, policy_ids=["P0", "P1"], task_ids=["T0"])
        t2 = run_tournament(r, policy_ids=["P0", "P1"], task_ids=["T0"])
        assert t1.tournament_hash == t2.tournament_hash


# ===========================================================================
# Phase 26: Recursive Self-Improvement
# ===========================================================================


class TestRecursiveSelfImprovement:
    def test_g1_better_than_g0(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        result = comp.compare(
            g0_experiments=20, g0_correct_predictions=8,
            g1_experiments=10, g1_correct_predictions=7,
        )
        assert result.g1_better is True
        assert result.improvement_ratio > 1.0
        assert result.efficiency_improved is True

    def test_g0_better_than_g1(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        result = comp.compare(
            g0_experiments=10, g0_correct_predictions=8,
            g1_experiments=10, g1_correct_predictions=5,
        )
        assert result.g1_better is False
        assert result.improvement_ratio < 1.0

    def test_efficiency_measurement(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        result = comp.compare(
            g0_experiments=20, g0_correct_predictions=10,
            g1_experiments=5, g1_correct_predictions=4,
        )
        assert result.experiment_reduction == 15
        assert result.efficiency_improved is True

    def test_result_hash_deterministic(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        r1 = comp.compare(g0_experiments=10, g0_correct_predictions=5, g1_experiments=8, g1_correct_predictions=6)
        r2 = comp.compare(g0_experiments=10, g0_correct_predictions=5, g1_experiments=8, g1_correct_predictions=6)
        assert r1.result_hash == r2.result_hash

    def test_truth_effect_none(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        result = comp.compare(g0_experiments=10, g0_correct_predictions=5, g1_experiments=8, g1_correct_predictions=6)
        assert result.payload()["truth_effect"] == "NONE"


# ===========================================================================
# Phase 27: Architecture Assimilation from external system
# ===========================================================================


class TestArchitectureAssimilation:
    def test_full_assimilation_loop(self):
        from metaengine.assimilation_loop import (
            BehavioralFingerprint, FingerprintKind, MechanismHypothesis,
            TransferExperiment, run_assimilation_loop, AssimilationDecision,
        )
        fp = BehavioralFingerprint(
            system_id="external-gpt5",
            fingerprint_kind=FingerprintKind.BEHAVIORAL,
            observations=(("quality", "0.92"), ("long_context", "superior")),
        )
        h = MechanismHypothesis(
            hypothesis_id="H1",
            mechanism_description="multi_stage_verification",
            expected_effect="reduces critical errors on high-uncertainty tasks",
            falsification_test="remove verification → quality drops",
            source_system_id="external-gpt5",
        )
        te = TransferExperiment(
            experiment_id="TE1",
            mechanism_hypothesis_hash=h.hypothesis_hash,
            source_resource_id="gpt5",
            target_resource_id="llama3.2",
            result="TRANSFERRED",
            evidence_hash="a" * 64,
        )
        result = run_assimilation_loop(fp, [h], [te])
        assert result.decision == AssimilationDecision.TRANSFERABLE
        assert result.mechanism_candidate_id is not None
        assert result.truth_effect == "NONE"
        assert result.assimilation_effect == "NONE"

    def test_rejected_assimilation(self):
        from metaengine.assimilation_loop import (
            BehavioralFingerprint, FingerprintKind, MechanismHypothesis,
            TransferExperiment, run_assimilation_loop, AssimilationDecision,
        )
        fp = BehavioralFingerprint(system_id="ext", fingerprint_kind=FingerprintKind.BEHAVIORAL, observations=())
        h = MechanismHypothesis(hypothesis_id="H1", mechanism_description="m", expected_effect="e",
                                falsification_test="f", source_system_id="ext")
        te = TransferExperiment(experiment_id="TE1", mechanism_hypothesis_hash=h.hypothesis_hash,
                                source_resource_id="a", target_resource_id="b", result="NOT_TRANSFERRED",
                                evidence_hash="b" * 64)
        result = run_assimilation_loop(fp, [h], [te])
        assert result.decision == AssimilationDecision.REJECTED

    def test_assimilation_never_automatic(self):
        """ASSIMILATED requires separate gate — never automatic."""
        from metaengine.assimilation_loop import (
            BehavioralFingerprint, FingerprintKind, MechanismHypothesis,
            TransferExperiment, run_assimilation_loop, AssimilationDecision,
        )
        fp = BehavioralFingerprint(system_id="ext", fingerprint_kind=FingerprintKind.BEHAVIORAL, observations=())
        h = MechanismHypothesis(hypothesis_id="H1", mechanism_description="m", expected_effect="e",
                                falsification_test="f", source_system_id="ext")
        te = TransferExperiment(experiment_id="TE1", mechanism_hypothesis_hash=h.hypothesis_hash,
                                source_resource_id="a", target_resource_id="b", result="TRANSFERRED",
                                evidence_hash="a" * 64)
        result = run_assimilation_loop(fp, [h], [te])
        assert result.decision != AssimilationDecision.ASSIMILATED


# ===========================================================================
# Phase 28: Autonomous Experiment Loop
# ===========================================================================


class TestAutonomousExperimentLoop:
    def test_loop_exists(self):
        from metaengine.autonomous_loop import AutonomousExperimentLoop
        assert AutonomousExperimentLoop is not None

    def test_loop_generates_hypothesis(self):
        from metaengine.autonomous_loop import AutonomousExperimentLoop
        loop = AutonomousExperimentLoop(seed=42)
        hypothesis = loop.generate_hypothesis(
            mechanism_library_ids=["mec.a", "mec.b"],
            task_features={"complexity": 0.7, "uncertainty": 0.5},
        )
        assert hypothesis is not None
        assert hypothesis.hypothesis_id
        assert hypothesis.rationale

    def test_loop_selects_experiment(self):
        from metaengine.autonomous_loop import AutonomousExperimentLoop
        loop = AutonomousExperimentLoop(seed=42)
        candidates = [
            {"id": "E1", "expected_gain": 0.7, "uncertainty": 0.8, "novelty": 0.6, "cost": 1.0},
            {"id": "E2", "expected_gain": 0.5, "uncertainty": 0.3, "novelty": 0.2, "cost": 0.5},
        ]
        selected = loop.select_experiment(candidates, budget=2)
        assert len(selected) > 0
        assert selected[0]["id"] == "E1"  # higher info gain

    def test_loop_records_outcome(self):
        from metaengine.autonomous_loop import AutonomousExperimentLoop
        loop = AutonomousExperimentLoop(seed=42)
        loop.record_outcome(experiment_id="E1", quality=0.8, success=True)
        assert len(loop._outcomes) == 1

    def test_loop_improves_selection(self):
        """After recording outcomes, the loop should adjust selection."""
        from metaengine.autonomous_loop import AutonomousExperimentLoop
        loop = AutonomousExperimentLoop(seed=42)
        # Record: E1 was great, E2 was bad
        loop.record_outcome(experiment_id="E1", quality=0.9, success=True)
        loop.record_outcome(experiment_id="E2", quality=0.2, success=False)
        # Next selection should prefer E1-like candidates
        candidates = [
            {"id": "E1_like", "expected_gain": 0.7, "uncertainty": 0.8, "novelty": 0.6, "cost": 1.0},
            {"id": "E2_like", "expected_gain": 0.5, "uncertainty": 0.3, "novelty": 0.2, "cost": 0.5},
        ]
        selected = loop.select_experiment(candidates, budget=1)
        assert "E1_like" in [c["id"] for c in selected]

    def test_loop_hash(self):
        from metaengine.autonomous_loop import AutonomousExperimentLoop
        loop = AutonomousExperimentLoop(seed=42)
        h = loop.loop_hash()
        assert len(h) == 64

    def test_truth_effect_none(self):
        from metaengine.autonomous_loop import AutonomousExperimentLoop
        loop = AutonomousExperimentLoop(seed=42)
        d = loop.payload()
        assert d["truth_effect"] == "NONE"


# ===========================================================================
# Phase 29: Cross-Model Validation
# ===========================================================================


class TestCrossModelValidation:
    def test_validator_exists(self):
        from metaengine.cross_model_validation import CrossModelValidator
        assert CrossModelValidator is not None

    def test_validates_model_independence(self):
        from metaengine.cross_model_validation import CrossModelValidator
        validator = CrossModelValidator()
        result = validator.validate(
            mechanism_id="mec.routing",
            model_a_results={"quality": 0.8, "cost": 1.0},
            model_b_results={"quality": 0.75, "cost": 1.0},
        )
        assert result.model_independent is not None
        assert result.quality_delta is not None

    def test_model_independence_passes_when_similar(self):
        from metaengine.cross_model_validation import CrossModelValidator
        validator = CrossModelValidator()
        result = validator.validate(
            mechanism_id="mec.test",
            model_a_results={"quality": 0.8, "cost": 1.0},
            model_b_results={"quality": 0.78, "cost": 1.0},
        )
        assert result.model_independent is True  # small delta → independent

    def test_model_independence_fails_when_divergent(self):
        from metaengine.cross_model_validation import CrossModelValidator
        validator = CrossModelValidator()
        result = validator.validate(
            mechanism_id="mec.test",
            model_a_results={"quality": 0.9, "cost": 1.0},
            model_b_results={"quality": 0.3, "cost": 1.0},
        )
        assert result.model_independent is False  # large delta → model-dependent

    def test_result_hash(self):
        from metaengine.cross_model_validation import CrossModelValidator
        v = CrossModelValidator()
        r1 = v.validate(mechanism_id="m", model_a_results={"quality": 0.8}, model_b_results={"quality": 0.7})
        r2 = v.validate(mechanism_id="m", model_a_results={"quality": 0.8}, model_b_results={"quality": 0.7})
        assert r1.validation_hash == r2.validation_hash

    def test_truth_effect_none(self):
        from metaengine.cross_model_validation import CrossModelValidator
        v = CrossModelValidator()
        result = v.validate(mechanism_id="m", model_a_results={"quality": 0.8}, model_b_results={"quality": 0.7})
        d = result.payload()
        assert d["truth_effect"] == "NONE"


# ===========================================================================
# Phase 30: Meta-Learning (learning to learn)
# ===========================================================================


class TestMetaLearning:
    def test_meta_learner_exists(self):
        from metaengine.meta_learning import MetaLearner
        assert MetaLearner is not None

    def test_records_experiment_strategy(self):
        from metaengine.meta_learning import MetaLearner
        learner = MetaLearner()
        learner.record_strategy(
            strategy_id="random_search",
            experiments_run=20,
            correct_predictions=8,
            compute_cost=10.0,
        )
        assert len(learner._strategies) == 1

    def test_compares_strategies(self):
        from metaengine.meta_learning import MetaLearner
        learner = MetaLearner()
        learner.record_strategy("random", 20, 8, 10.0)
        learner.record_strategy("info_gain", 10, 7, 5.0)
        result = learner.compare_strategies()
        assert result.best_strategy in ("random", "info_gain")
        assert result.improvement_ratio is not None

    def test_info_gain_better_than_random(self):
        from metaengine.meta_learning import MetaLearner
        learner = MetaLearner()
        # Random: 8/20 = 0.4 accuracy, cost 10
        learner.record_strategy("random", 20, 8, 10.0)
        # Info-gain: 7/10 = 0.7 accuracy, cost 5 → better
        learner.record_strategy("info_gain", 10, 7, 5.0)
        result = learner.compare_strategies()
        assert result.best_strategy == "info_gain"

    def test_result_hash(self):
        from metaengine.meta_learning import MetaLearner
        learner = MetaLearner()
        learner.record_strategy("s1", 10, 5, 5.0)
        r1 = learner.compare_strategies()
        r2 = learner.compare_strategies()
        assert r1.result_hash == r2.result_hash

    def test_truth_effect_none(self):
        from metaengine.meta_learning import MetaLearner
        learner = MetaLearner()
        learner.record_strategy("s1", 10, 5, 5.0)
        result = learner.compare_strategies()
        d = result.payload()
        assert d["truth_effect"] == "NONE"
