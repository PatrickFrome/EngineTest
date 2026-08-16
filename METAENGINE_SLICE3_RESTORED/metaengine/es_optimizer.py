"""METAENGINE Phase 39 — Evolution Strategies (ES) Hyperparameter Optimizer.

Implements gradient-free optimization using antithetic sampling (Salimans et al
2017, OpenAI). For each hyperparameter vector θ:
  1. Sample noise ε ~ N(0, σ²I)
  2. Evaluate fitness(θ + ε) and fitness(θ - ε)  [antithetic pair]
  3. Estimate gradient: ∇f ≈ (f(θ+ε) - f(θ-ε)) / (2σ) * ε  [finite differences]
  4. Update: θ ← θ + α * ∇f
  5. Decay σ and α over generations

Works on NON-DIFFERENTIABLE objectives (e.g., quality = token overlap).
Complements PBT: PBT = coarse discrete search, ES = fine continuous optimization.

Constitution compliance:
  - ES does NOT modify code — only optimizes hyperparameter values
  - All policies remain SHADOW
  - Fitness is from RLAIF (constitutional compliance, not truth)
  - No auto-promotion
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from .util import canonical_hash


ES_VERSION = "METAENGINE-ES-HYPERPARAMETER-OPTIMIZER-1"


# ---------------------------------------------------------------------------
# Hyperparameter spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HyperparameterSpec:
    """Specification of a single hyperparameter to optimize."""
    name: str
    min_value: float
    max_value: float
    initial_value: float
    is_integer: bool = False

    def clamp(self, value: float) -> float:
        """Clamp value to valid range, round if integer."""
        v = max(self.min_value, min(self.max_value, value))
        if self.is_integer:
            v = round(v)
        return v

    def payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "min": self.min_value,
            "max": self.max_value,
            "initial": self.initial_value,
            "is_integer": self.is_integer,
        }


# Default hyperparameters to optimize for an ArchitecturePolicy
DEFAULT_POLICY_HYPERPARAMS: tuple[HyperparameterSpec, ...] = (
    HyperparameterSpec("max_rounds", 1, 8, 4, is_integer=True),
    HyperparameterSpec("max_deep_engines", 1, 16, 8, is_integer=True),
    HyperparameterSpec("exploration_rate", 0.0, 0.30, 0.15, is_integer=False),
    HyperparameterSpec("temperature", 0.0, 2.0, 0.4, is_integer=False),
)


# ---------------------------------------------------------------------------
# ES optimization state
# ---------------------------------------------------------------------------


@dataclass
class ESState:
    """Current state of ES optimization."""
    theta: dict[str, float]  # current hyperparameter values
    sigma: float  # noise standard deviation
    alpha: float  # learning rate
    generation: int = 0
    best_fitness: float = 0.0
    best_theta: dict[str, float] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {
            "theta": dict(self.theta),
            "sigma": round(self.sigma, 6),
            "alpha": round(self.alpha, 6),
            "generation": self.generation,
            "best_fitness": round(self.best_fitness, 6),
            "best_theta": dict(self.best_theta),
            "history_count": len(self.history),
            "truth_effect": "NONE",
            "claim_ceiling": "ES_STATE_IS_OPTIMIZATION_NOT_TRUTH",
        }


# ---------------------------------------------------------------------------
# ES Optimizer
# ---------------------------------------------------------------------------


class ESHyperparameterOptimizer:
    """Evolution Strategies optimizer using antithetic sampling.

    The optimizer maintains a theta vector (hyperparameter values) and
    iteratively improves it using gradient estimates from antithetic pairs.

    Usage:
        optimizer = ESHyperparameterOptimizer(specs=DEFAULT_POLICY_HYPERPARAMS)
        for gen in range(num_generations):
            state = optimizer.step(fitness_fn)
        best = optimizer.state.best_theta
    """

    def __init__(
        self,
        *,
        specs: tuple[HyperparameterSpec, ...] = DEFAULT_POLICY_HYPERPARAMS,
        population_size: int = 8,  # number of antithetic pairs per generation
        initial_sigma: float = 0.3,
        initial_alpha: float = 0.1,
        sigma_decay: float = 0.95,  # sigma *= decay each generation
        alpha_decay: float = 0.97,  # alpha *= decay each generation
        min_sigma: float = 0.01,
        min_alpha: float = 0.001,
        seed: int = 42,
    ):
        if population_size < 2:
            raise ValueError("POPULATION_SIZE_MUST_BE_AT_LEAST_2 (need antithetic pairs)")
        if not 0 < sigma_decay <= 1.0:
            raise ValueError("SIGMA_DECAY_MUST_BE_IN_(0, 1]")
        self.specs = specs
        self.population_size = population_size
        self.initial_sigma = initial_sigma
        self.initial_alpha = initial_alpha
        self.sigma_decay = sigma_decay
        self.alpha_decay = alpha_decay
        self.min_sigma = min_sigma
        self.min_alpha = min_alpha
        self._rng = random.Random(seed)

        # Initialize state
        theta = {spec.name: spec.initial_value for spec in specs}
        self.state = ESState(
            theta=theta,
            sigma=initial_sigma,
            alpha=initial_alpha,
            best_fitness=0.0,
            best_theta=dict(theta),
        )

    # ------------------------------------------------------------------
    # Noise sampling
    # ------------------------------------------------------------------

    def _sample_noise(self) -> dict[str, float]:
        """Sample Gaussian noise for each hyperparameter."""
        return {
            spec.name: self._rng.gauss(0, 1) * self.state.sigma
            for spec in self.specs
        }

    def _perturb_theta(self, theta: dict[str, float], noise: dict[str, float], direction: int = 1) -> dict[str, float]:
        """Apply noise to theta (direction=+1 or -1 for antithetic)."""
        result = {}
        for spec in self.specs:
            raw = theta[spec.name] + direction * noise[spec.name]
            result[spec.name] = spec.clamp(raw)
        return result

    # ------------------------------------------------------------------
    # Gradient estimation
    # ------------------------------------------------------------------

    def _estimate_gradient(
        self,
        fitness_fn: Callable[[dict[str, float]], float],
    ) -> tuple[dict[str, float], float]:
        """Estimate gradient using antithetic sampling.

        Returns (gradient_vector, mean_fitness).
        """
        gradient_sum = {spec.name: 0.0 for spec in self.specs}
        fitness_sum = 0.0

        for _ in range(self.population_size):
            noise = self._sample_noise()
            theta_plus = self._perturb_theta(self.state.theta, noise, direction=+1)
            theta_minus = self._perturb_theta(self.state.theta, noise, direction=-1)

            f_plus = fitness_fn(theta_plus)
            f_minus = fitness_fn(theta_minus)
            fitness_sum += (f_plus + f_minus) / 2

            # Gradient estimate: (f+ - f-) / (2 * sigma * noise_i)
            # Using Salimans et al 2017 formula: ∇f ≈ (1/n) * Σ (f(θ+ε) - f(θ-ε)) * ε / (2σ²)
            diff = f_plus - f_minus
            for spec in self.specs:
                n = noise[spec.name]
                if abs(n) > 1e-10 and self.state.sigma > 1e-10:
                    # Contribution to gradient for this parameter
                    gradient_sum[spec.name] += diff * n / (self.state.sigma ** 2)

        # Average
        n_pairs = self.population_size
        gradient = {k: v / n_pairs for k, v in gradient_sum.items()}
        mean_fitness = fitness_sum / n_pairs

        return gradient, mean_fitness

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(self, fitness_fn: Callable[[dict[str, float]], float]) -> dict[str, Any]:
        """Perform one ES optimization step.

        Args:
            fitness_fn: takes a theta dict {param_name: value}, returns fitness 0-1.

        Returns:
            Step summary dict.
        """
        gradient, mean_fitness = self._estimate_gradient(fitness_fn)

        # Update theta using gradient
        new_theta = {}
        for spec in self.specs:
            old_val = self.state.theta[spec.name]
            grad = gradient[spec.name]
            new_val = spec.clamp(old_val + self.state.alpha * grad)
            new_theta[spec.name] = new_val

        # Evaluate new theta
        new_fitness = fitness_fn(new_theta)

        # Track best
        improved = new_fitness > self.state.best_fitness
        if improved:
            self.state.best_fitness = new_fitness
            self.state.best_theta = dict(new_theta)

        # Record history
        step_record = {
            "generation": self.state.generation,
            "mean_fitness": round(mean_fitness, 6),
            "new_fitness": round(new_fitness, 6),
            "best_fitness": round(self.state.best_fitness, 6),
            "sigma": round(self.state.sigma, 6),
            "alpha": round(self.state.alpha, 6),
            "improved": improved,
            "theta_before": {k: round(v, 4) for k, v in self.state.theta.items()},
            "theta_after": {k: round(v, 4) for k, v in new_theta.items()},
            "gradient": {k: round(v, 6) for k, v in gradient.items()},
            "truth_effect": "NONE",
        }
        step_record["record_hash"] = canonical_hash({k: v for k, v in step_record.items() if k != "record_hash"})
        self.state.history.append(step_record)

        # Update state
        self.state.theta = new_theta
        self.state.generation += 1

        # Decay sigma and alpha
        self.state.sigma = max(self.min_sigma, self.state.sigma * self.sigma_decay)
        self.state.alpha = max(self.min_alpha, self.state.alpha * self.alpha_decay)

        return step_record

    # ------------------------------------------------------------------
    # Run multiple steps
    # ------------------------------------------------------------------

    def run(
        self,
        fitness_fn: Callable[[dict[str, float]], float],
        num_generations: int = 10,
    ) -> dict[str, Any]:
        """Run ES for multiple generations.

        Returns:
            Summary with best theta, fitness history, convergence info.
        """
        for _ in range(num_generations):
            self.step(fitness_fn)

        return self.summary()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return optimization summary."""
        if not self.state.history:
            return {
                "es_version": ES_VERSION,
                "generations_run": 0,
                "truth_effect": "NONE",
            }

        fitness_history = [h["new_fitness"] for h in self.state.history]
        first_fitness = fitness_history[0]
        last_fitness = fitness_history[-1]
        max_fitness = max(fitness_history)
        min_fitness = min(fitness_history)

        # Convergence: did fitness stabilize in last 3 generations?
        last_3 = fitness_history[-3:] if len(fitness_history) >= 3 else fitness_history
        converged = max(last_3) - min(last_3) < 0.01

        return {
            "es_version": ES_VERSION,
            "generations_run": len(self.state.history),
            "specs": [s.payload() for s in self.specs],
            "population_size": self.population_size,
            "initial_sigma": self.initial_sigma,
            "initial_alpha": self.initial_alpha,
            "sigma_decay": self.sigma_decay,
            "alpha_decay": self.alpha_decay,
            "final_theta": dict(self.state.theta),
            "best_theta": dict(self.state.best_theta),
            "best_fitness": round(self.state.best_fitness, 6),
            "first_fitness": round(first_fitness, 6),
            "last_fitness": round(last_fitness, 6),
            "max_fitness": round(max_fitness, 6),
            "min_fitness": round(min_fitness, 6),
            "improvement": round(last_fitness - first_fitness, 6),
            "converged": converged,
            "final_sigma": round(self.state.sigma, 6),
            "final_alpha": round(self.state.alpha, 6),
            "history": self.state.history,
            "truth_effect": "NONE",
            "claim_ceiling": "ES_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "no_code_modification": True,
                "all_policies_remain_shadow": True,
                "fitness_is_evaluative": True,
                "no_auto_promotion": True,
            },
        }


# ---------------------------------------------------------------------------
# Fitness function factory
# ---------------------------------------------------------------------------


def make_policy_fitness_fn(
    base_policy_fitness_fn: Callable,
) -> Callable[[dict[str, float]], float]:
    """Wrap a policy fitness function to accept a theta dict.

    The base_policy_fitness_fn takes an ArchitecturePolicy and returns fitness.
    This wrapper takes a theta dict, applies it to a policy, and calls the base fn.

    Args:
        base_policy_fitness_fn: fn(ArchitecturePolicy) -> float

    Returns:
        fn(theta: dict[str, float]) -> float
    """
    def fitness_fn(theta: dict[str, float]) -> float:
        # theta contains: max_rounds, max_deep_engines, exploration_rate, temperature
        # The base function should handle creating a policy from these
        return base_policy_fitness_fn(theta)
    return fitness_fn
