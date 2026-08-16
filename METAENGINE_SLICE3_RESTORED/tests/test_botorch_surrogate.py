"""Step 6: Tests for BoTorch GP surrogate."""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.botorch_surrogate import (
    BotorchSurrogate,
    SurrogatePrediction,
    BOTORCH_AVAILABLE,
    SURROGATE_VERSION,
    normalize_theta,
)


class TestBotorchAvailability:
    def test_botorch_available(self):
        """BoTorch + torch + gpytorch are installed."""
        assert BOTORCH_AVAILABLE is True

    def test_botorch_imports(self):
        import torch
        import botorch
        import gpytorch
        assert torch is not None
        assert botorch is not None
        assert gpytorch is not None


class TestNormalize:
    def test_normalize_theta_returns_list(self):
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        result = normalize_theta(theta)
        assert isinstance(result, list)
        assert len(result) == 4

    def test_normalize_theta_range(self):
        theta = {"max_rounds": 1, "max_deep_engines": 1, "exploration_rate": 0.0, "temperature": 0.0}
        result = normalize_theta(theta)
        assert all(0.0 <= x <= 1.0 for x in result)

    def test_normalize_theta_max(self):
        theta = {"max_rounds": 8, "max_deep_engines": 16, "exploration_rate": 0.30, "temperature": 2.0}
        result = normalize_theta(theta)
        assert all(abs(x - 1.0) < 0.01 for x in result)

    def test_normalize_theta_mid(self):
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        result = normalize_theta(theta)
        assert 0.4 < result[0] < 0.6  # mid-range


class TestBotorchSurrogate:
    def test_init(self):
        s = BotorchSurrogate()
        assert s._observations == []
        assert s._gp_model is None
        assert s.ucb_beta == 2.0

    def test_add_observation(self):
        s = BotorchSurrogate()
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        s.add_observation(theta, 0.85)
        assert len(s._observations) == 1

    def test_predict_without_gp(self):
        """With < 3 observations, falls back to heuristic."""
        s = BotorchSurrogate()
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        s.add_observation(theta, 0.85)
        pred = s.predict(theta)
        assert pred.using_gp is False
        assert pred.mean == 0.85  # mean of 1 observation
        assert pred.variance == 0.25  # default uncertainty

    def test_predict_with_gp(self):
        """With >= 3 observations, uses GP."""
        s = BotorchSurrogate()
        thetas = [
            {"max_rounds": 2, "max_deep_engines": 4, "exploration_rate": 0.10, "temperature": 0.3},
            {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4},
            {"max_rounds": 6, "max_deep_engines": 12, "exploration_rate": 0.20, "temperature": 0.6},
        ]
        scores = [0.5, 0.8, 0.6]
        for t, s_val in zip(thetas, scores):
            s.add_observation(t, s_val)
        pred = s.predict(thetas[1])
        assert pred.using_gp is True
        assert 0.0 <= pred.mean <= 1.0
        assert pred.variance >= 0.0

    def test_prediction_range(self):
        """All predictions are in [0, 1]."""
        s = BotorchSurrogate()
        for i in range(10):
            theta = {"max_rounds": i+1, "max_deep_engines": 2*(i+1), "exploration_rate": 0.01*(i+1), "temperature": 0.1*(i+1)}
            s.add_observation(theta, 0.5 + 0.03 * i)
        for i in range(20):
            theta = {"max_rounds": 1+i, "max_deep_engines": 1+2*i, "exploration_rate": 0.01*i, "temperature": 0.05*i}
            pred = s.predict(theta)
            assert 0.0 <= pred.mean <= 1.0

    def test_acquisition_score(self):
        """UCB acquisition combines mean + exploration."""
        s = BotorchSurrogate(ucb_beta=2.0)
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        s.add_observation(theta, 0.8)
        score = s.acquisition_score(theta)
        assert score > 0.8  # UCB > mean

    def test_state(self):
        s = BotorchSurrogate()
        state = s.state()
        assert state["surrogate_version"] == SURROGATE_VERSION
        assert state["botorch_available"] is True
        assert state["observation_count"] == 0
        assert state["gp_fitted"] is False
        assert state["truth_effect"] == "NONE"

    def test_rolling_window(self):
        """Observations beyond max_observations are evicted."""
        s = BotorchSurrogate(max_observations=5)
        for i in range(10):
            theta = {"max_rounds": i+1, "max_deep_engines": 2*(i+1), "exploration_rate": 0.01*(i+1), "temperature": 0.1*(i+1)}
            s.add_observation(theta, 0.5)
        assert len(s._observations) == 5

    def test_gp_fit_after_observations(self):
        """GP is fitted after 3+ observations."""
        s = BotorchSurrogate()
        for i in range(5):
            theta = {"max_rounds": i+1, "max_deep_engines": 2*(i+1), "exploration_rate": 0.01*(i+1), "temperature": 0.1*(i+1)}
            s.add_observation(theta, 0.5 + 0.05 * i)
        pred = s.predict(theta)
        assert pred.using_gp is True
        state = s.state()
        assert state["gp_fitted"] is True
        assert state["observation_count"] == 5

    def test_truth_effect_none(self):
        s = BotorchSurrogate()
        assert s.state()["truth_effect"] == "NONE"


class TestTieredFitnessBoTorchIntegration:
    """Test that tiered_fitness.py correctly uses BoTorch surrogate."""

    def test_adapter_has_botorch(self):
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=2, use_botorch=True)
        assert adapter._botorch_surrogate is not None

    def test_adapter_can_disable_botorch(self):
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=2, use_botorch=False)
        assert adapter._botorch_surrogate is None

    def test_summary_includes_botorch(self):
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=2, use_botorch=True)
        s = adapter.summary()
        assert "botorch" in s
        assert s["botorch"]["botorch_available"] is True

    def test_l0_uses_botorch_after_observations(self):
        """After 3+ L2 observations, L0 uses GP posterior mean."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=0, use_botorch=True)
        # Simulate 3 L2 observations
        thetas = [
            {"max_rounds": 2, "max_deep_engines": 4, "exploration_rate": 0.10, "temperature": 0.3},
            {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4},
            {"max_rounds": 6, "max_deep_engines": 12, "exploration_rate": 0.20, "temperature": 0.6},
        ]
        for t in thetas:
            adapter._botorch_surrogate.add_observation(t, 0.8)
        # Now L0 should use GP
        score = adapter._evaluate_l0(thetas[1])
        assert 0.0 <= score <= 1.0
        # GP state should show fitted
        assert adapter._botorch_surrogate.state()["gp_fitted"] is True
