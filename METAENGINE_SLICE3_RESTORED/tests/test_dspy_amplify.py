"""Step 9: Tests for DSPy-powered amplifier."""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.dspy_amplify import (
    DSPyAmplifier,
    DSPyAmplifyResult,
    DSPY_AMPLIFY_VERSION,
    DSPY_AVAILABLE,
)


class TestDSPyAvailability:
    def test_dspy_available(self):
        """DSPy package is installed."""
        assert DSPY_AVAILABLE is True

    def test_dspy_import(self):
        import dspy
        assert dspy is not None


class TestDSPyAmplifier:
    def test_init(self):
        amp = DSPyAmplifier()
        assert amp._examples == []
        assert amp._compiled_module is None

    def test_add_example(self):
        amp = DSPyAmplifier()
        amp.add_example(
            metrics={"rlaif_reward": 0.3},
            config_changes={"llm_temperature": 0.48},
            fitness=0.6,
        )
        assert len(amp._examples) == 1

    def test_amplify_without_dspy_uses_heuristic(self):
        """With use_dspy=False, falls back to heuristic rules."""
        amp = DSPyAmplifier(use_dspy=False)
        metrics = {"rlaif_reward": 0.2, "pbt_best_fitness": 0.3, "es_converged": False}
        result = amp.amplify(metrics, {"llm_temperature": 0.4, "exploration_rate": 0.15})
        assert result.using_dspy is False
        assert len(result.config_changes) > 0  # At least one rule fired

    def test_amplify_rlaif_low_rule(self):
        """RLAIF reward < 0.4 triggers temperature increase."""
        amp = DSPyAmplifier(use_dspy=False)
        result = amp.amplify({"rlaif_reward": 0.2}, {"llm_temperature": 0.4})
        assert "llm_temperature" in result.config_changes
        assert result.config_changes["llm_temperature"] > 0.4

    def test_amplify_pbt_plateau_rule(self):
        """PBT fitness < 0.7 triggers exploration increase."""
        amp = DSPyAmplifier(use_dspy=False)
        result = amp.amplify({"pbt_best_fitness": 0.5}, {"exploration_rate": 0.15})
        assert "exploration_rate" in result.config_changes

    def test_amplify_faithfulness_low_rule(self):
        """Faithfulness < 0.5 triggers provenance weight increase."""
        amp = DSPyAmplifier(use_dspy=False)
        result = amp.amplify({"faithfulness_mean": 0.3}, {"rlaif_weight_provenance": 0.15})
        assert "rlaif_weight_provenance" in result.config_changes

    def test_amplify_redteam_violations_rule(self):
        """RedTeam violations > 0 triggers no_truth weight increase."""
        amp = DSPyAmplifier(use_dspy=False)
        result = amp.amplify({"redteam_violation_rate": 0.1}, {"rlaif_weight_no_truth": 0.15})
        assert "rlaif_weight_no_truth" in result.config_changes

    def test_amplify_es_not_converged_rule(self):
        """ES not converged triggers sigma increase."""
        amp = DSPyAmplifier(use_dspy=False)
        result = amp.amplify({"es_converged": False}, {"es_sigma": 0.3})
        assert "es_sigma" in result.config_changes

    def test_amplify_no_rules_when_metrics_good(self):
        """No changes when all metrics are good."""
        amp = DSPyAmplifier(use_dspy=False)
        result = amp.amplify(
            {"rlaif_reward": 0.8, "pbt_best_fitness": 0.9, "es_converged": True,
             "faithfulness_mean": 0.7, "redteam_violation_rate": 0.0,
             "marl_foe_mean": 0.1, "transfer_rate": 0.5},
            {"llm_temperature": 0.4, "exploration_rate": 0.15},
        )
        assert len(result.config_changes) == 0

    def test_amplify_transfer_low_rule(self):
        """Transfer rate < 0.3 triggers max_rounds increase."""
        amp = DSPyAmplifier(use_dspy=False)
        result = amp.amplify({"transfer_rate": 0.1}, {"max_rounds": 4})
        assert "max_rounds" in result.config_changes
        assert result.config_changes["max_rounds"] == 5

    def test_rolling_window(self):
        """Examples beyond MAX_EXAMPLES are evicted."""
        amp = DSPyAmplifier()
        for i in range(110):
            amp.add_example({"rlaif_reward": 0.1 * i}, {"temperature": 0.4}, 0.5)
        assert len(amp._examples) == 100  # MAX_EXAMPLES

    def test_compile_without_examples(self):
        """Compile returns False when < 5 examples."""
        amp = DSPyAmplifier()
        amp.add_example({"r": 0.1}, {"temp": 0.4}, 0.3)
        result = amp.compile()
        assert result is False

    def test_compile_invalidates_module(self):
        """Adding new examples invalidates compiled module."""
        amp = DSPyAmplifier()
        amp._compiled_module = "fake"
        amp.add_example({"r": 0.1}, {"temp": 0.4}, 0.3)
        assert amp._compiled_module is None

    def test_state(self):
        amp = DSPyAmplifier()
        s = amp.state()
        assert s["dspy_amplify_version"] == DSPY_AMPLIFY_VERSION
        assert s["dspy_available"] is True
        assert s["example_count"] == 0
        assert s["heuristic_rules"] == 7
        assert s["truth_effect"] == "NONE"

    def test_truth_effect_none(self):
        amp = DSPyAmplifier()
        assert amp.state()["truth_effect"] == "NONE"

    def test_amplify_returns_result(self):
        """amplify() returns DSPyAmplifyResult."""
        amp = DSPyAmplifier(use_dspy=False)
        result = amp.amplify({"rlaif_reward": 0.2}, {})
        assert isinstance(result, DSPyAmplifyResult)
        assert isinstance(result.config_changes, dict)
        assert isinstance(result.rationale, str)
        assert isinstance(result.using_dspy, bool)
