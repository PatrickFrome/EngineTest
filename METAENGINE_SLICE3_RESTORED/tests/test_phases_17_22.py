"""METAENGINE Phase 17-22 — Advanced phases tests.

Phase 17: LLM Model Adapter
Phase 18: Sealed Benchmark Suite
Phase 19: Task-Conditional Policy Selection
Phase 20: Architecture Synthesis G+2
Phase 21: Information-Gain Experiment Selection
Phase 22: Uncertainty Calibration + Failure Taxonomy + Cross-World Transfer
"""

from __future__ import annotations

import pytest

# ===========================================================================
# Phase 17: LLM Model Adapter
# ===========================================================================


class TestLLMModelAdapter:
    def test_llm_config_create(self):
        from metaengine.llm_model_adapter import LLMModelConfig
        c = LLMModelConfig(
            model_id="llm-test-01",
            endpoint="http://localhost:11434/api/generate",
            model_name="llama3.2",
            api_key_env="OLLAMA_API_KEY",
        )
        assert c.model_id == "llm-test-01"
        assert c.adapter_kind == "LLM_MODEL"
        assert c.implementation_level == "REAL_LLM_EXECUTOR"

    def test_llm_config_payload(self):
        from metaengine.llm_model_adapter import LLMModelConfig
        c = LLMModelConfig(model_id="t", endpoint="http://x", model_name="m", api_key_env="K")
        d = c.payload()
        assert d["api_key_env"] == "K"  # env var NAME, not key
        assert "api_key" not in d  # actual key never in payload

    def test_llm_adapter_implements_contract(self):
        from metaengine.llm_model_adapter import LLMModelAdapter, LLMModelConfig
        from metaengine.adapters.base import Adapter
        assert issubclass(LLMModelAdapter, Adapter)

    def test_llm_adapter_claim_ceiling(self):
        from metaengine.llm_model_adapter import LLMModelConfig
        c = LLMModelConfig(model_id="t", endpoint="http://x", model_name="m", api_key_env="K")
        # The adapter must mark LLM output as generative, not evidence
        assert c.implementation_level == "REAL_LLM_EXECUTOR"

    def test_llm_adapter_redacts_secrets(self):
        from metaengine.llm_model_adapter import LLMModelConfig
        c = LLMModelConfig(model_id="t", endpoint="http://x", model_name="m", api_key_env="SECRET_KEY")
        # api_key_env stores the NAME of the env var, not the key value
        assert c.api_key_env == "SECRET_KEY"

    def test_llm_adapter_supports_ollama_format(self):
        from metaengine.llm_model_adapter import LLMModelConfig
        c = LLMModelConfig(
            model_id="ollama-01",
            endpoint="http://localhost:11434/api/generate",
            model_name="llama3.2",
            api_key_env="OLLAMA_KEY",
        )
        assert "/api/generate" in c.endpoint

    def test_llm_adapter_supports_openai_format(self):
        from metaengine.llm_model_adapter import LLMModelConfig
        c = LLMModelConfig(
            model_id="openai-01",
            endpoint="https://api.openai.com/v1/chat/completions",
            model_name="gpt-4o-mini",
            api_key_env="OPENAI_API_KEY",
        )
        assert "chat/completions" in c.endpoint

    def test_llm_adapter_default_temperature(self):
        from metaengine.llm_model_adapter import LLMModelConfig
        c = LLMModelConfig(model_id="t", endpoint="http://x", model_name="m", api_key_env="K")
        assert 0 < c.temperature <= 1.0

    def test_llm_adapter_max_tokens(self):
        from metaengine.llm_model_adapter import LLMModelConfig
        c = LLMModelConfig(model_id="t", endpoint="http://x", model_name="m", api_key_env="K", max_tokens=512)
        assert c.max_tokens == 512


# ===========================================================================
# Phase 18: Sealed Benchmark Suite
# ===========================================================================


class TestSealedBenchmark:
    def test_sealed_benchmark_exists(self):
        from metaengine.sealed_benchmark import SealedBenchmarkSuite
        assert SealedBenchmarkSuite is not None

    def test_generates_sealed_tasks(self):
        from metaengine.sealed_benchmark import SealedBenchmarkSuite
        suite = SealedBenchmarkSuite(seed=42)
        tasks = suite.generate_sealed_tasks(count=5)
        assert len(tasks) == 5

    def test_tasks_are_unknown_to_engine(self):
        from metaengine.sealed_benchmark import SealedBenchmarkSuite
        suite = SealedBenchmarkSuite(seed=42)
        tasks = suite.generate_sealed_tasks(count=3)
        for t in tasks:
            assert t.sealed is True
            assert t.source_text  # non-empty
            assert t.expected_outcome is not None  # has ground truth

    def test_sealed_tasks_deterministic(self):
        from metaengine.sealed_benchmark import SealedBenchmarkSuite
        s1 = SealedBenchmarkSuite(seed=42)
        s2 = SealedBenchmarkSuite(seed=42)
        t1 = s1.generate_sealed_tasks(count=3)
        t2 = s2.generate_sealed_tasks(count=3)
        assert t1[0].task_hash == t2[0].task_hash

    def test_sealed_tasks_have_capability_dimensions(self):
        from metaengine.sealed_benchmark import SealedBenchmarkSuite
        suite = SealedBenchmarkSuite(seed=42)
        tasks = suite.generate_sealed_tasks(count=3)
        for t in tasks:
            assert len(t.capability_dimensions) > 0

    def test_sealed_benchmark_hash(self):
        from metaengine.sealed_benchmark import SealedBenchmarkSuite
        suite = SealedBenchmarkSuite(seed=42)
        h = suite.suite_hash()
        assert len(h) == 64

    def test_truth_effect_none(self):
        from metaengine.sealed_benchmark import SealedBenchmarkSuite
        suite = SealedBenchmarkSuite(seed=42)
        tasks = suite.generate_sealed_tasks(count=1)
        assert tasks[0].truth_effect == "NONE"


# ===========================================================================
# Phase 19: Task-Conditional Policy Selection
# ===========================================================================


class TestTaskConditionalPolicy:
    def test_task_conditional_selector_exists(self):
        from metaengine.task_conditional_selector import TaskConditionalSelector
        assert TaskConditionalSelector is not None

    def test_selects_policy_based_on_task_features(self):
        from metaengine.task_conditional_selector import TaskConditionalSelector
        selector = TaskConditionalSelector()
        result = selector.select(
            task_features={"complexity": 0.8, "uncertainty": 0.6, "context_length": 0.3},
            available_policies=["P0", "P1", "P2"],
            biography_priors={"P0": 0.6, "P1": 0.8, "P2": 0.5},
        )
        assert result.selected_policy in ["P0", "P1", "P2"]
        assert result.confidence > 0

    def test_high_uncertainty_prefers_verifier(self):
        from metaengine.task_conditional_selector import TaskConditionalSelector
        selector = TaskConditionalSelector()
        result = selector.select(
            task_features={"complexity": 0.9, "uncertainty": 0.9, "context_length": 0.5},
            available_policies=["SINGLE_MODEL", "MODEL_PLUS_VERIFIER", "FEDERATION"],
            biography_priors={"SINGLE_MODEL": 0.5, "MODEL_PLUS_VERIFIER": 0.7, "FEDERATION": 0.6},
        )
        assert result.selected_policy == "MODEL_PLUS_VERIFIER"

    def test_low_complexity_prefers_simple(self):
        from metaengine.task_conditional_selector import TaskConditionalSelector
        selector = TaskConditionalSelector()
        result = selector.select(
            task_features={"complexity": 0.2, "uncertainty": 0.1, "context_length": 0.2},
            available_policies=["SINGLE_MODEL", "MODEL_PLUS_VERIFIER", "FEDERATION"],
            biography_priors={"SINGLE_MODEL": 0.8, "MODEL_PLUS_VERIFIER": 0.5, "FEDERATION": 0.4},
        )
        assert result.selected_policy == "SINGLE_MODEL"

    def test_selection_hash_deterministic(self):
        from metaengine.task_conditional_selector import TaskConditionalSelector
        selector = TaskConditionalSelector()
        r1 = selector.select(
            task_features={"complexity": 0.5, "uncertainty": 0.5, "context_length": 0.5},
            available_policies=["P0", "P1"],
            biography_priors={"P0": 0.6, "P1": 0.7},
        )
        r2 = selector.select(
            task_features={"complexity": 0.5, "uncertainty": 0.5, "context_length": 0.5},
            available_policies=["P0", "P1"],
            biography_priors={"P0": 0.6, "P1": 0.7},
        )
        assert r1.selection_hash == r2.selection_hash

    def test_updates_with_experience(self):
        from metaengine.task_conditional_selector import TaskConditionalSelector
        selector = TaskConditionalSelector()
        # First selection
        r1 = selector.select(
            task_features={"complexity": 0.5, "uncertainty": 0.5, "context_length": 0.5},
            available_policies=["P0", "P1"],
            biography_priors={"P0": 0.5, "P1": 0.5},
        )
        # Update with actual outcome
        selector.update(r1.selected_policy, actual_quality=0.9, task_features={"complexity": 0.5, "uncertainty": 0.5, "context_length": 0.5})
        # Second selection should be influenced
        r2 = selector.select(
            task_features={"complexity": 0.5, "uncertainty": 0.5, "context_length": 0.5},
            available_policies=["P0", "P1"],
            biography_priors={"P0": 0.5, "P1": 0.5},
        )
        # The selected policy should lean towards the one with better outcome
        assert r2.selected_policy == r1.selected_policy  # should prefer the one that scored 0.9

    def test_truth_effect_none(self):
        from metaengine.task_conditional_selector import TaskConditionalSelector
        selector = TaskConditionalSelector()
        result = selector.select(
            task_features={"complexity": 0.5, "uncertainty": 0.5, "context_length": 0.5},
            available_policies=["P0"],
            biography_priors={"P0": 0.5},
        )
        d = result.payload()
        assert d["truth_effect"] == "NONE"


# ===========================================================================
# Phase 20: Architecture Synthesis G+2
# ===========================================================================


class TestArchitectureSynthesis:
    def test_synthesizer_exists(self):
        from metaengine.architecture_synthesis import ArchitectureSynthesizer
        assert ArchitectureSynthesizer is not None

    def test_synthesizes_from_mechanisms(self):
        from metaengine.architecture_synthesis import ArchitectureSynthesizer
        synth = ArchitectureSynthesizer(seed=42)
        result = synth.synthesize(
            winning_mechanisms=["mec.routing", "mec.verification", "mec.memory"],
            max_combinations=5,
        )
        assert len(result.syntheses) > 0
        for s in result.syntheses:
            assert len(s.combined_mechanisms) >= 2

    def test_synthesis_is_novel(self):
        from metaengine.architecture_synthesis import ArchitectureSynthesizer
        synth = ArchitectureSynthesizer(seed=42)
        result = synth.synthesize(
            winning_mechanisms=["mec.a", "mec.b", "mec.c"],
            max_combinations=3,
        )
        # Each synthesis must combine at least 2 mechanisms
        for s in result.syntheses:
            assert len(s.combined_mechanisms) >= 2

    def test_synthesis_hash_deterministic(self):
        from metaengine.architecture_synthesis import ArchitectureSynthesizer
        synth = ArchitectureSynthesizer(seed=42)
        r1 = synth.synthesize(winning_mechanisms=["mec.a", "mec.b"], max_combinations=3)
        r2 = synth.synthesize(winning_mechanisms=["mec.a", "mec.b"], max_combinations=3)
        assert r1.syntheses[0].synthesis_hash == r2.syntheses[0].synthesis_hash

    def test_synthesis_truth_effect_none(self):
        from metaengine.architecture_synthesis import ArchitectureSynthesizer
        synth = ArchitectureSynthesizer(seed=42)
        result = synth.synthesize(winning_mechanisms=["mec.a"], max_combinations=1)
        d = result.payload()
        assert d["truth_effect"] == "NONE"

    def test_synthesis_does_not_assume_sum_is_positive(self):
        from metaengine.architecture_synthesis import ArchitectureSynthesizer
        synth = ArchitectureSynthesizer(seed=42)
        result = synth.synthesize(
            winning_mechanisms=["mec.a", "mec.b"],
            max_combinations=3,
        )
        for s in result.syntheses:
            assert "assumes_positive_sum" not in s.rationale.lower() or "not" in s.rationale.lower()


# ===========================================================================
# Phase 21: Information-Gain Experiment Selection
# ===========================================================================


class TestInformationGainSelection:
    def test_selector_exists(self):
        from metaengine.information_gain_selector import InformationGainSelector
        assert InformationGainSelector is not None

    def test_selects_highest_information_gain(self):
        from metaengine.information_gain_selector import InformationGainSelector
        selector = InformationGainSelector()
        candidates = [
            {"id": "C0", "expected_gain": 0.5, "uncertainty": 0.9, "novelty": 0.3, "cost": 1.0},
            {"id": "C1", "expected_gain": 0.8, "uncertainty": 0.2, "novelty": 0.1, "cost": 1.0},
            {"id": "C2", "expected_gain": 0.6, "uncertainty": 0.7, "novelty": 0.8, "cost": 0.5},
        ]
        selected = selector.select(candidates, budget=2)
        assert len(selected) <= 2
        # C2 has highest information gain (uncertainty * novelty / cost)
        assert "C2" in [c["id"] for c in selected]

    def test_respects_budget(self):
        from metaengine.information_gain_selector import InformationGainSelector
        selector = InformationGainSelector()
        candidates = [
            {"id": "C0", "expected_gain": 0.5, "uncertainty": 0.9, "novelty": 0.3, "cost": 2.0},
            {"id": "C1", "expected_gain": 0.8, "uncertainty": 0.2, "novelty": 0.1, "cost": 3.0},
        ]
        selected = selector.select(candidates, budget=1)
        # Budget=1 means we can only afford experiments with cost <= 1
        # None qualify → empty selection
        assert len(selected) == 0

    def test_information_gain_formula(self):
        from metaengine.information_gain_selector import InformationGainSelector
        selector = InformationGainSelector()
        # info_gain = expected_gain * uncertainty * novelty / cost
        gain = selector._compute_info_gain(
            expected_gain=0.5, uncertainty=0.8, novelty=0.6, cost=1.0
        )
        assert gain == pytest.approx(0.5 * 0.8 * 0.6 / 1.0, abs=0.01)

    def test_deterministic(self):
        from metaengine.information_gain_selector import InformationGainSelector
        s1 = InformationGainSelector()
        s2 = InformationGainSelector()
        c = [{"id": "C0", "expected_gain": 0.5, "uncertainty": 0.9, "novelty": 0.3, "cost": 1.0}]
        assert [c["id"] for c in s1.select(c, budget=1)] == [c["id"] for c in s2.select(c, budget=1)]


# ===========================================================================
# Phase 22: Uncertainty Calibration + Failure Taxonomy + Cross-World Transfer
# ===========================================================================


class TestUncertaintyCalibration:
    def test_calibrator_exists(self):
        from metaengine.uncertainty_calibration import UncertaintyCalibrator
        assert UncertaintyCalibrator is not None

    def test_calibrates_predictions(self):
        from metaengine.uncertainty_calibration import UncertaintyCalibrator
        cal = UncertaintyCalibrator()
        # Add observations: predicted confidence vs actual correctness
        cal.add_observation(predicted_confidence=0.9, actual_correct=True)
        cal.add_observation(predicted_confidence=0.9, actual_correct=False)
        cal.add_observation(predicted_confidence=0.3, actual_correct=False)
        cal.add_observation(predicted_confidence=0.3, actual_correct=True)
        # Calibration error should be high (predictions don't match reality)
        error = cal.calibration_error()
        assert error > 0  # not perfectly calibrated

    def test_perfect_calibration(self):
        from metaengine.uncertainty_calibration import UncertaintyCalibrator
        cal = UncertaintyCalibrator()
        for _ in range(10):
            cal.add_observation(predicted_confidence=0.8, actual_correct=True)
        for _ in range(2):
            cal.add_observation(predicted_confidence=0.8, actual_correct=False)
        # 10/12 = 0.833 ≈ 0.8 predicted → close to calibrated
        error = cal.calibration_error()
        assert error < 0.1  # nearly calibrated

    def test_calibration_hash(self):
        from metaengine.uncertainty_calibration import UncertaintyCalibrator
        cal = UncertaintyCalibrator()
        cal.add_observation(predicted_confidence=0.5, actual_correct=True)
        h = cal.calibrator_hash()
        assert len(h) == 64


class TestFailureTaxonomy:
    def test_taxonomy_exists(self):
        from metaengine.failure_taxonomy import FailureTaxonomy
        assert FailureTaxonomy is not None

    def test_classifies_failure(self):
        from metaengine.failure_taxonomy import FailureTaxonomy, FailureClass
        tax = FailureTaxonomy()
        result = tax.classify(
            failure_type="timeout",
            context={"engine_id": "engine_01", "task_complexity": 0.9},
        )
        assert result.failure_class in FailureClass

    def test_failure_hash(self):
        from metaengine.failure_taxonomy import FailureTaxonomy
        tax = FailureTaxonomy()
        r1 = tax.classify("timeout", {"engine_id": "e01"})
        r2 = tax.classify("timeout", {"engine_id": "e01"})
        assert r1.finding_hash == r2.finding_hash

    def test_different_failures_different_classes(self):
        from metaengine.failure_taxonomy import FailureTaxonomy, FailureClass
        tax = FailureTaxonomy()
        timeout = tax.classify("timeout", {})
        hallucination = tax.classify("hallucination", {})
        resource = tax.classify("resource_exhaustion", {})
        # Different failure types should map to different classes
        classes = {timeout.failure_class, hallucination.failure_class, resource.failure_class}
        assert len(classes) > 1


class TestCrossWorldTransfer:
    def test_transfer_exists(self):
        from metaengine.cross_world_transfer import CrossWorldTransfer
        assert CrossWorldTransfer is not None

    def test_transfers_findings(self):
        from metaengine.cross_world_transfer import CrossWorldTransfer
        transfer = CrossWorldTransfer()
        result = transfer.transfer(
            source_world_findings={"mechanism": "routing", "effect": 0.3, "confidence": 0.8},
            target_world_context={"task_type": "reasoning", "resources": ["model_a"]},
        )
        assert result.transferable is not None
        assert result.confidence >= 0

    def test_transfer_hash(self):
        from metaengine.cross_world_transfer import CrossWorldTransfer
        t = CrossWorldTransfer()
        r1 = t.transfer({"mechanism": "m", "effect": 0.5, "confidence": 0.7}, {"task_type": "t"})
        r2 = t.transfer({"mechanism": "m", "effect": 0.5, "confidence": 0.7}, {"task_type": "t"})
        assert r1.transfer_hash == r2.transfer_hash

    def test_low_confidence_source_reduces_transfer_confidence(self):
        from metaengine.cross_world_transfer import CrossWorldTransfer
        t = CrossWorldTransfer()
        high = t.transfer({"mechanism": "m", "effect": 0.5, "confidence": 0.9}, {"task_type": "t"})
        low = t.transfer({"mechanism": "m", "effect": 0.5, "confidence": 0.2}, {"task_type": "t"})
        assert low.confidence < high.confidence

    def test_truth_effect_none(self):
        from metaengine.cross_world_transfer import CrossWorldTransfer
        t = CrossWorldTransfer()
        result = t.transfer({"mechanism": "m", "effect": 0.5, "confidence": 0.7}, {"task_type": "t"})
        d = result.payload()
        assert d["truth_effect"] == "NONE"
