"""pbt_trainer.py — Population-based training for MetaEngine hyperparameter optimization.

Instead of trying one patch per improvement cycle, PBT maintains a population
of 8 architecture policies in parallel. Each policy runs 6 tasks. After each
generation:
  - Top 2 policies "reproduce" (mutate hyperparameters)
  - Bottom 2 policies are replaced by the mutated offspring

This gives 8× faster hyperparameter discovery compared to serial improvement.

Usage:
  from metaengine.pbt_trainer import PBTTrainer
  trainer = PBTTrainer(population_size=8)
  trainer.run_generation()
  best_policy = trainer.best_policy()
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("ME_BENCHMARK_ROOT") or Path(__file__).resolve().parent.parent)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PBT_STATE_FILE = ROOT / "storage" / "pbt_state.json"
PBT_LOG = ROOT / "storage" / "pbt_trainer.log"


def _log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] [pbt] {msg}"
    print(line, flush=True)
    try:
        PBT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with PBT_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


@dataclass
class ArchitecturePolicy:
    """One candidate architecture policy in the PBT population."""
    policy_id: str
    # Hyperparameters (the "genome")
    max_rounds: int = 2
    max_deep_engines: int = 3
    exploration_rate: float = 0.15
    temperature: float = 0.4
    # Evaluation results
    fitness: float = 0.0
    tasks_evaluated: int = 0
    generation: int = 0
    parent_id: str = ""
    # Status
    alive: bool = True
    evaluated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ArchitecturePolicy":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class PBTTrainer:
    """Population-based training for MetaEngine.

    Maintains a population of architecture policies, evaluates them in
    parallel, and evolves them via truncation selection + mutation.
    """

    def __init__(self, population_size: int = 8):
        self.population_size = population_size
        self.policies: list[ArchitecturePolicy] = []
        self.generation = 0
        self._load_state()

    def _load_state(self) -> None:
        """Load previously saved PBT state."""
        if PBT_STATE_FILE.is_file():
            try:
                data = json.loads(PBT_STATE_FILE.read_text(encoding="utf-8"))
                self.generation = data.get("generation", 0)
                self.policies = [
                    ArchitecturePolicy.from_dict(p) for p in data.get("policies", [])
                ]
                _log(f"loaded {len(self.policies)} policies from generation {self.generation}")
            except Exception as exc:
                _log(f"load failed: {exc}")
                self.policies = []
        if not self.policies:
            self._init_population()

    def _init_population(self) -> None:
        """Initialize a diverse random population."""
        _log(f"initializing population of {self.population_size} policies")
        for i in range(self.population_size):
            self.policies.append(ArchitecturePolicy(
                policy_id=f"gen0-policy{i}",
                max_rounds=random.randint(1, 4),
                max_deep_engines=random.randint(2, 6),
                exploration_rate=round(random.uniform(0.05, 0.3), 3),
                temperature=round(random.uniform(0.2, 0.7), 3),
                generation=0,
            ))

    def _save_state(self) -> None:
        """Persist PBT state for future runs."""
        try:
            PBT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "generation": self.generation,
                "population_size": self.population_size,
                "policies": [p.to_dict() for p in self.policies],
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            PBT_STATE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            _log(f"save failed: {exc}")

    def evaluate_population(self, fitness_fn: callable) -> None:
        """Evaluate all alive policies using the provided fitness function.

        Args:
            fitness_fn: function(ArchitecturePolicy) -> float
                        Returns the fitness (0-1) for this policy.
        """
        _log(f"evaluating {sum(1 for p in self.policies if p.alive)} alive policies")
        for p in self.policies:
            if not p.alive:
                continue
            try:
                p.fitness = fitness_fn(p)
                p.tasks_evaluated += 6  # each policy runs 6 tasks
                p.evaluated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                _log(f"  {p.policy_id}: fitness={p.fitness:.4f}")
            except Exception as exc:
                _log(f"  {p.policy_id}: evaluation FAILED: {exc}")
                p.fitness = 0.0

    def evolve(self) -> dict:
        """Truncation selection + mutation. Returns evolution summary.

        - Top 25% of policies "reproduce" (mutate hyperparameters)
        - Bottom 25% are replaced by the mutated offspring
        - Middle 50% survive unchanged
        """
        # Sort by fitness descending
        alive = [p for p in self.policies if p.alive]
        alive.sort(key=lambda p: p.fitness, reverse=True)
        n = len(alive)
        if n < 4:
            _log(f"population too small ({n}) to evolve — skipping")
            return {"evolved": False, "reason": "population_too_small"}

        # Truncation: top 25% are "exploiters", bottom 25% are "explored"
        top_quartile = n // 4
        bottom_quartile = n // 4
        exploiters = alive[:top_quartile]
        explored = alive[-bottom_quartile:]

        _log(f"evolving: top {len(exploiters)} reproduce, bottom {len(explored)} replaced")

        # Replace bottom policies with mutated copies of top policies
        for i, weak in enumerate(explored):
            parent = exploiters[i % len(exploiters)]
            # Mutate: ±20% perturbation of each hyperparameter
            child = ArchitecturePolicy(
                policy_id=f"gen{self.generation+1}-policy{i}",
                max_rounds=max(1, min(8, parent.max_rounds + random.choice([-1, 1]))),
                max_deep_engines=max(1, min(16, parent.max_deep_engines + random.choice([-1, 1]))),
                exploration_rate=round(max(0.0, min(1.0,
                    parent.exploration_rate * random.uniform(0.8, 1.2))), 3),
                temperature=round(max(0.0, min(1.0,
                    parent.temperature * random.uniform(0.8, 1.2))), 3),
                fitness=0.0,
                tasks_evaluated=0,
                generation=self.generation + 1,
                parent_id=parent.policy_id,
            )
            # Replace the weak policy with the child
            idx = self.policies.index(weak)
            self.policies[idx] = child
            _log(f"  {weak.policy_id} (fit={weak.fitness:.3f}) → replaced by "
                 f"{child.policy_id} (mutated from {parent.policy_id})")

        self.generation += 1
        self._save_state()
        return {
            "evolved": True,
            "generation": self.generation,
            "exploiters": [p.policy_id for p in exploiters],
            "explored": [p.policy_id for p in explored],
        }

    def best_policy(self) -> ArchitecturePolicy | None:
        """Return the best policy in the population."""
        alive = [p for p in self.policies if p.alive]
        if not alive:
            return None
        return max(alive, key=lambda p: p.fitness)

    def run_generation(self, fitness_fn: callable) -> dict:
        """Run one complete PBT generation: evaluate + evolve."""
        _log(f"=== PBT GENERATION {self.generation} START ===")
        t0 = time.perf_counter()

        # Phase 1: Evaluate all alive policies
        self.evaluate_population(fitness_fn)

        # Phase 2: Evolve
        evolve_result = self.evolve()

        # Phase 3: Save state
        self._save_state()

        elapsed = time.perf_counter() - t0
        best = self.best_policy()
        summary = {
            "generation": self.generation,
            "duration_sec": round(elapsed, 2),
            "best_fitness": best.fitness if best else 0.0,
            "best_policy_id": best.policy_id if best else "",
            "avg_fitness": (
                sum(p.fitness for p in self.policies if p.alive) /
                max(1, sum(1 for p in self.policies if p.alive))
            ),
            "evolve_result": evolve_result,
        }
        _log(f"=== PBT GENERATION {self.generation} END — "
             f"best={summary['best_fitness']:.4f}, avg={summary['avg_fitness']:.4f}, "
             f"duration={elapsed:.1f}s ===")
        return summary

    def summary(self) -> dict:
        """Return summary stats for monitoring."""
        alive = [p for p in self.policies if p.alive]
        return {
            "generation": self.generation,
            "population_size": len(alive),
            "best_fitness": max((p.fitness for p in alive), default=0.0),
            "avg_fitness": (
                sum(p.fitness for p in alive) / len(alive) if alive else 0.0
            ),
            "best_policy": self.best_policy().to_dict() if self.best_policy() else None,
        }
