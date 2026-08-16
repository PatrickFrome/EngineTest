"""Step 6: BoTorch-powered GP surrogate for tiered fitness L0 evaluation.

Replaces the hand-coded weighted-sum heuristic in tiered_fitness.py with a
fitted Gaussian Process (GP) surrogate model. The GP learns from observed
(theta, L2_score) pairs and provides:
  - Posterior mean (predicted fitness)
  - Posterior variance (uncertainty estimate)
  - Acquisition function values (for UCB-based candidate selection)

Architecture:
  - BotorchSurrogate wraps a SingleTaskGP model
  - Trains on observed (theta, fitness) pairs from L2 evaluations
  - Falls back to heuristic when insufficient data (< 3 observations)
  - Provides predict() → (mean, variance) for any theta
  - Provides acquisition_score() → UCB for exploration/exploitation

Constitution compliance:
  - Surrogate is evaluative (truth_effect=NONE)
  - No auto-promotion (surrogate only predicts, doesn't decide)
  - No code modification
  - Predictions are bounded [0, 1]
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

# Step 6: BoTorch imports (graceful degradation if not available)
try:
    import torch
    from botorch.models import SingleTaskGP
    from botorch.fit import fit_gpytorch_mll
    from gpytorch.mlls import ExactMarginalLogLikelihood
    from botorch.acquisition import UpperConfidenceBound
    BOTORCH_AVAILABLE = True
except ImportError:
    BOTORCH_AVAILABLE = False


SURROGATE_VERSION = "METAENGINE-BOTORCH-SURROGATE-1"

# Theta feature names (must match tiered_fitness.py SURROGATE_FEATURE_NAMES)
THETA_KEYS = ("max_rounds", "max_deep_engines", "exploration_rate", "temperature")

# Normalization ranges (must match _surrogate_features in tiered_fitness.py)
THETA_RANGES = {
    "max_rounds": (1.0, 8.0),
    "max_deep_engines": (1.0, 16.0),
    "exploration_rate": (0.0, 0.30),
    "temperature": (0.0, 2.0),
}


def normalize_theta(theta: dict[str, float]) -> list[float]:
    """Normalize theta to [0, 1] range for GP input."""
    result = []
    for key in THETA_KEYS:
        lo, hi = THETA_RANGES[key]
        val = float(theta.get(key, (lo + hi) / 2))
        result.append(max(0.0, min(1.0, (val - lo) / (hi - lo))))
    return result


@dataclass
class SurrogatePrediction:
    """Prediction from the GP surrogate."""
    mean: float  # predicted fitness [0, 1]
    variance: float  # prediction uncertainty [0, 1]
    ucb_score: float  # upper confidence bound (mean + beta * sqrt(variance))
    using_gp: bool  # True if GP was used, False if heuristic fallback
    observation_count: int  # number of training observations


class BotorchSurrogate:
    """BoTorch GP surrogate for L0 fitness prediction.

    Usage:
        surrogate = BotorchSurrogate()
        # Add observations (from L2 evaluations)
        surrogate.add_observation(theta, l2_score)
        # Predict fitness for new theta
        pred = surrogate.predict(theta)
        print(f"Predicted: {pred.mean:.4f} ± {pred.variance:.4f}")

    When < 3 observations: falls back to heuristic (same as old L0)
    When >= 3 observations: fits GP and uses posterior mean
    When >= 10 observations: uses UCB acquisition for exploration
    """

    MIN_OBSERVATIONS_FOR_GP = 3  # Need at least 3 points to fit a GP
    MIN_OBSERVATIONS_FOR_UCB = 10  # UCB only useful with enough data
    UCB_BETA = 2.0  # Exploration parameter (higher = more exploration)
    MAX_OBSERVATIONS = 200  # Rolling window size

    def __init__(
        self,
        *,
        ucb_beta: float = 2.0,
        max_observations: int = 200,
    ):
        self.ucb_beta = float(ucb_beta)
        self.max_observations = int(max_observations)
        self._observations: list[tuple[list[float], float]] = []  # (normalized_theta, fitness)
        self._gp_model: Any = None
        self._mll: Any = None
        self._train_x: Any = None
        self._train_y: Any = None
        self._last_fit_count: int = 0
        self._fit_time_ms: float = 0.0

    def add_observation(self, theta: dict[str, float], fitness: float) -> None:
        """Add an (theta, fitness) observation to the training set."""
        norm = normalize_theta(theta)
        fitness = max(0.0, min(1.0, float(fitness)))
        self._observations.append((norm, fitness))
        # Rolling window
        if len(self._observations) > self.max_observations:
            self._observations = self._observations[-self.max_observations:]
        # Invalidate GP model (will refit on next predict)
        self._gp_model = None

    def _fit_gp(self) -> bool:
        """Fit the GP model on current observations. Returns True if successful."""
        if not BOTORCH_AVAILABLE or len(self._observations) < self.MIN_OBSERVATIONS_FOR_GP:
            return False

        try:
            started = time.perf_counter()
            # Prepare training data — BoTorch expects X shape (n, d) and Y shape (n, 1)
            X = torch.tensor(
                [obs[0] for obs in self._observations],
                dtype=torch.float64,
            )  # (n, d)
            Y = torch.tensor(
                [[obs[1]] for obs in self._observations],
                dtype=torch.float64,
            )  # (n, 1)

            # Create and fit GP
            self._gp_model = SingleTaskGP(X, Y)
            self._mll = ExactMarginalLogLikelihood(self._gp_model.likelihood, self._gp_model)
            fit_gpytorch_mll(self._mll)

            self._train_x = X
            self._train_y = Y
            self._last_fit_count = len(self._observations)
            self._fit_time_ms = (time.perf_counter() - started) * 1000
            return True
        except Exception:
            self._gp_model = None
            return False

    def predict(self, theta: dict[str, float]) -> SurrogatePrediction:
        """Predict fitness for a given theta.

        Returns SurrogatePrediction with mean, variance, ucb_score.
        Falls back to heuristic when insufficient data.
        """
        norm = normalize_theta(theta)
        n_obs = len(self._observations)

        # Need to refit if observations changed
        if self._gp_model is not None and self._last_fit_count != n_obs:
            self._gp_model = None

        if n_obs < self.MIN_OBSERVATIONS_FOR_GP or not BOTORCH_AVAILABLE:
            # Fallback to simple heuristic (mean of observations)
            if n_obs > 0:
                mean = sum(obs[1] for obs in self._observations) / n_obs
                variance = 0.25  # High uncertainty when using fallback
            else:
                mean = 0.5  # Neutral prediction
                variance = 0.25
            ucb = mean + self.ucb_beta * math.sqrt(variance)
            return SurrogatePrediction(
                mean=mean, variance=variance, ucb_score=ucb,
                using_gp=False, observation_count=n_obs,
            )

        # Fit GP if needed
        if self._gp_model is None:
            if not self._fit_gp():
                # Fit failed — fallback
                mean = sum(obs[1] for obs in self._observations) / n_obs
                variance = 0.25
                ucb = mean + self.ucb_beta * math.sqrt(variance)
                return SurrogatePrediction(
                    mean=mean, variance=variance, ucb_score=ucb,
                    using_gp=False, observation_count=n_obs,
                )

        try:
            # Predict using GP — x_test shape (1, d)
            x_test = torch.tensor([norm], dtype=torch.float64)
            with torch.no_grad():
                posterior = self._gp_model.posterior(x_test)
                mean_t = posterior.mean.squeeze()
                var_t = posterior.variance.squeeze()

            mean = float(max(0.0, min(1.0, mean_t.item())))
            variance = float(max(0.0, min(1.0, var_t.item())))
            ucb = mean + self.ucb_beta * math.sqrt(variance)

            return SurrogatePrediction(
                mean=mean, variance=variance, ucb_score=ucb,
                using_gp=True, observation_count=n_obs,
            )
        except Exception:
            # Prediction failed — fallback
            mean = sum(obs[1] for obs in self._observations) / n_obs
            variance = 0.25
            ucb = mean + self.ucb_beta * math.sqrt(variance)
            return SurrogatePrediction(
                mean=mean, variance=variance, ucb_score=ucb,
                using_gp=False, observation_count=n_obs,
            )

    def acquisition_score(self, theta: dict[str, float]) -> float:
        """UCB acquisition score for candidate selection.

        Higher = more promising candidate for L2 evaluation.
        Combines exploitation (mean) with exploration (variance).
        """
        pred = self.predict(theta)
        return pred.ucb_score

    def state(self) -> dict[str, Any]:
        """Return surrogate state for inspection."""
        return {
            "surrogate_version": SURROGATE_VERSION,
            "botorch_available": BOTORCH_AVAILABLE,
            "observation_count": len(self._observations),
            "gp_fitted": self._gp_model is not None,
            "last_fit_count": self._last_fit_count,
            "last_fit_time_ms": round(self._fit_time_ms, 2),
            "ucb_beta": self.ucb_beta,
            "using_gp": self._gp_model is not None and len(self._observations) >= self.MIN_OBSERVATIONS_FOR_GP,
            "truth_effect": "NONE",
        }
