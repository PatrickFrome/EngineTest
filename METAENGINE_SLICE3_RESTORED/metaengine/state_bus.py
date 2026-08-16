"""METAENGINE Phase 49 — Shared State Bus.

Connects all trainers via a shared state object. Trainers publish their
results to the bus, and other trainers can consume them.

Architecture:
  TrainingStateBus holds:
    - rlaif_rewards: dict[engine_id → reward] (from RLAIF)
    - pbt_champions: list[ArchitecturePolicy] (from PBT)
    - alphazero_mechanisms: list[str] (mechanism_ids from AlphaZero)
    - marl_agent_rewards: dict[engine_id → total_reward] (from MARL)
    - redteam_vulnerabilities: list[dict] (from RedTeam)
    - faithfulness_scores: dict[engine_id → score] (from Faithfulness)
    - trace_mechanisms: list[str] (from TraceExtractor)
    - transferable_mechanisms: list[str] (from CrossModelTransferTester)

Flow:
  1. RLAIF publishes rewards → PBT subscribes as fitness
  2. PBT publishes champions → AlphaZero subscribes as tournament participants
  3. AlphaZero publishes mechanisms → ES subscribes as optimization targets
  4. TraceExtractor publishes traces → CrossModelTransferTester subscribes
  5. RedTeam publishes vulnerabilities → all trainers see vulnerabilities

Constitution compliance:
  - State bus is evaluative (truth_effect=NONE)
  - No auto-promotion (bus is a data structure, not an authority)
  - No code modification
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .util import canonical_hash, write_json


BUS_VERSION = "METAENGINE-TRAINING-STATE-BUS-2"  # Step 2: bumped for thread safety


@dataclass
class TrainingStateBus:
    """Shared state between all trainers.

    Trainers publish their results here. Other trainers can read them.

    Step 2: Thread-safe — all publish methods acquire _lock to prevent data races
    when multiple trainers (PBT with max_workers=4, MARL, orchestrator) call
    publish concurrently.
    """
    # RLAIF rewards (Phase 36)
    rlaif_rewards: dict[str, float] = field(default_factory=dict)
    rlaif_confidence: dict[str, float] = field(default_factory=dict)

    # PBT champions (Phase 37)
    pbt_champions: list[dict] = field(default_factory=list)  # policy payloads
    pbt_best_fitness: float = 0.0
    pbt_generation: int = 0

    # AlphaZero mechanisms (Phase 38)
    alphazero_mechanisms: list[str] = field(default_factory=list)
    alphazero_architectures: list[dict] = field(default_factory=list)

    # ES optimization (Phase 39)
    es_best_fitness: float = 0.0
    es_converged: bool = False
    es_best_theta: dict[str, float] = field(default_factory=dict)

    # MARL agent rewards (Phase 40)
    marl_agent_rewards: dict[str, float] = field(default_factory=dict)
    marl_friend_mean: float = 0.0
    marl_foe_mean: float = 0.0

    # RedTeam vulnerabilities (Phase 41+47)
    redteam_vulnerabilities: list[dict] = field(default_factory=list)
    redteam_violation_rate: float = 0.0

    # Faithfulness scores (Phase 46)
    faithfulness_scores: dict[str, float] = field(default_factory=dict)
    faithfulness_mean: float = 0.0

    # Trace mechanisms (Phase 44)
    trace_mechanisms: list[str] = field(default_factory=list)

    # Transferable mechanisms (Phase 45)
    transferable_mechanisms: list[str] = field(default_factory=list)
    transfer_rate: float = 0.0

    # Tiered fitness (Phase 67 / I3: PBT publishes tiered fitness results here)
    tiered_fitness_best: float = 0.0
    tiered_fitness_mean: float = 0.0
    tiered_fitness_generation: int = 0
    tiered_fitness_l2_calls: int = 0
    tiered_fitness_tier_distribution: dict[str, int] = field(default_factory=dict)
    tiered_fitness_last_theta: dict[str, float] = field(default_factory=dict)

    # Metadata
    last_updated: str = ""
    bus_hash: str = ""

    # Step 2: Thread safety lock
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        """Step 2: Ensure lock is always a fresh RLock (not shared across instances)."""
        object.__setattr__(self, '_lock', threading.RLock())

    # ------------------------------------------------------------------
    # Publish methods (called by trainers)
    # ------------------------------------------------------------------

    def publish_rlaif(self, engine_id: str, reward: float, confidence: float) -> None:
        """RLAIF trainer publishes reward for an engine."""
        with self._lock:
            self.rlaif_rewards[engine_id] = reward
            self.rlaif_confidence[engine_id] = confidence
            self._touch()

    def publish_pbt(self, champions: list[dict], best_fitness: float, generation: int) -> None:
        """PBT trainer publishes champions."""
        with self._lock:
            self.pbt_champions = champions
            self.pbt_best_fitness = best_fitness
            self.pbt_generation = generation
            self._touch()

    def publish_alphazero(self, mechanisms: list[str], architectures: list[dict]) -> None:
        """AlphaZero trainer publishes extracted mechanisms."""
        with self._lock:
            self.alphazero_mechanisms = mechanisms
            self.alphazero_architectures = architectures
            self._touch()

    def publish_es(self, best_fitness: float, converged: bool, best_theta: dict) -> None:
        """ES optimizer publishes results."""
        with self._lock:
            self.es_best_fitness = best_fitness
            self.es_converged = converged
            self.es_best_theta = best_theta
            self._touch()

    def publish_marl(self, agent_rewards: dict[str, float], friend_mean: float, foe_mean: float) -> None:
        """MARL trainer publishes agent rewards."""
        with self._lock:
            self.marl_agent_rewards = agent_rewards
            self.marl_friend_mean = friend_mean
            self.marl_foe_mean = foe_mean
            self._touch()

    def publish_redteam(self, vulnerabilities: list[dict], violation_rate: float) -> None:
        """RedTeam adversary publishes found vulnerabilities."""
        with self._lock:
            self.redteam_vulnerabilities = vulnerabilities
            self.redteam_violation_rate = violation_rate
            self._touch()

    def publish_faithfulness(self, scores: dict[str, float], mean: float) -> None:
        """Faithfulness tester publishes scores."""
        with self._lock:
            self.faithfulness_scores = scores
            self.faithfulness_mean = mean
            self._touch()

    def publish_traces(self, mechanism_ids: list[str]) -> None:
        """Trace extractor publishes extracted mechanism IDs."""
        with self._lock:
            self.trace_mechanisms = mechanism_ids
            self._touch()

    def publish_transfer(self, transferable: list[str], transfer_rate: float) -> None:
        """Cross-model transfer tester publishes results."""
        with self._lock:
            self.transferable_mechanisms = transferable
            self.transfer_rate = transfer_rate
            self._touch()

    def publish_tiered_fitness(
        self,
        *,
        best_fitness: float,
        mean_fitness: float,
        generation: int,
        l2_calls: int,
        tier_distribution: dict[str, int] | None = None,
        last_theta: dict[str, float] | None = None,
    ) -> None:
        """I3: Tiered fitness adapter publishes its evaluation summary."""
        with self._lock:
            self.tiered_fitness_best = best_fitness
            self.tiered_fitness_mean = mean_fitness
            self.tiered_fitness_generation = generation
            self.tiered_fitness_l2_calls = l2_calls
            self.tiered_fitness_tier_distribution = dict(tier_distribution or {})
            self.tiered_fitness_last_theta = dict(last_theta or {})
            self._touch()

    # ------------------------------------------------------------------
    # Subscribe methods (called by trainers to read state)
    # ------------------------------------------------------------------

    def get_rlaif_reward(self, engine_id: str) -> float | None:
        """Get RLAIF reward for an engine (for PBT fitness)."""
        return self.rlaif_rewards.get(engine_id)

    def get_pbt_champions(self) -> list[dict]:
        """Get PBT champions (for AlphaZero tournament)."""
        return self.pbt_champions

    def get_alphazero_mechanisms(self) -> list[str]:
        """Get AlphaZero mechanisms (for ES optimization targets)."""
        return self.alphazero_mechanisms

    def get_trace_mechanisms(self) -> list[str]:
        """Get trace mechanisms (for CrossModelTransferTester)."""
        return self.trace_mechanisms

    def get_redteam_vulnerabilities(self) -> list[dict]:
        """Get red team vulnerabilities (for all trainers to see)."""
        return self.redteam_vulnerabilities

    def get_faithfulness_score(self, engine_id: str) -> float | None:
        """Get faithfulness score for an engine."""
        return self.faithfulness_scores.get(engine_id)

    def get_tiered_fitness_summary(self) -> dict[str, Any]:
        """I3: Get tiered fitness summary (for downstream subscribers like ES, recursive)."""
        return {
            "best_fitness": self.tiered_fitness_best,
            "mean_fitness": self.tiered_fitness_mean,
            "generation": self.tiered_fitness_generation,
            "l2_calls": self.tiered_fitness_l2_calls,
            "tier_distribution": dict(self.tiered_fitness_tier_distribution),
            "last_theta": dict(self.tiered_fitness_last_theta),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _touch(self) -> None:
        """Update last_updated timestamp."""
        self.last_updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def compute_hash(self) -> str:
        """Compute content hash of the bus state.

        Step 2: Now includes all fields that were previously missing:
        - marl_foe_mean (was missing)
        - pbt_generation (was missing)
        - es_converged (was missing)
        - faithfulness_scores count (was missing)
        - tiered_fitness_mean (was missing)
        - tiered_fitness_l2_calls (was missing)
        """
        with self._lock:
            payload = {
                "bus_version": BUS_VERSION,
                "rlaif_rewards": dict(self.rlaif_rewards),
                "rlaif_confidence_count": len(self.rlaif_confidence),
                "pbt_best_fitness": self.pbt_best_fitness,
                "pbt_generation": self.pbt_generation,  # Step 2: was missing
                "pbt_champions_count": len(self.pbt_champions),  # Step 2: was missing
                "es_best_fitness": self.es_best_fitness,
                "es_converged": self.es_converged,  # Step 2: was missing
                "es_best_theta": dict(self.es_best_theta),
                "marl_friend_mean": self.marl_friend_mean,
                "marl_foe_mean": self.marl_foe_mean,  # Step 2: was missing
                "marl_agent_rewards_count": len(self.marl_agent_rewards),  # Step 2: was missing
                "redteam_violation_rate": self.redteam_violation_rate,
                "redteam_vulnerabilities_count": len(self.redteam_vulnerabilities),  # Step 2: was missing
                "faithfulness_mean": self.faithfulness_mean,
                "faithfulness_scores_count": len(self.faithfulness_scores),  # Step 2: was missing
                "transfer_rate": self.transfer_rate,
                "transferable_count": len(self.transferable_mechanisms),  # Step 2: was missing
                "alphazero_mechanisms_count": len(self.alphazero_mechanisms),
                "trace_mechanisms_count": len(self.trace_mechanisms),
                "tiered_fitness_best": self.tiered_fitness_best,
                "tiered_fitness_mean": self.tiered_fitness_mean,  # Step 2: was missing
                "tiered_fitness_generation": self.tiered_fitness_generation,
                "tiered_fitness_l2_calls": self.tiered_fitness_l2_calls,  # Step 2: was missing
                "tiered_fitness_tier_distribution": dict(self.tiered_fitness_tier_distribution),  # Step 2: was missing
            }
            return canonical_hash(payload)

    def payload(self) -> dict[str, Any]:
        """Full payload for serialization.

        Step 2: Now includes full lists (pbt_champions, alphazero_architectures,
        redteam_vulnerabilities) instead of just counts — so load() can restore them.
        """
        return {
            "bus_version": BUS_VERSION,
            "rlaif_rewards": dict(self.rlaif_rewards),
            "rlaif_confidence": dict(self.rlaif_confidence),
            # Step 2: Full list (was: pbt_champions_count only)
            "pbt_champions": list(self.pbt_champions),
            "pbt_champions_count": len(self.pbt_champions),
            "pbt_best_fitness": self.pbt_best_fitness,
            "pbt_generation": self.pbt_generation,
            "alphazero_mechanisms": list(self.alphazero_mechanisms),
            # Step 2: Full list (was: alphazero_architectures_count only)
            "alphazero_architectures": list(self.alphazero_architectures),
            "alphazero_architectures_count": len(self.alphazero_architectures),
            "es_best_fitness": self.es_best_fitness,
            "es_converged": self.es_converged,
            "es_best_theta": dict(self.es_best_theta),
            "marl_agent_rewards": dict(self.marl_agent_rewards),
            "marl_friend_mean": self.marl_friend_mean,
            "marl_foe_mean": self.marl_foe_mean,
            # Step 2: Full list (was: redteam_vulnerabilities_count only)
            "redteam_vulnerabilities": list(self.redteam_vulnerabilities),
            "redteam_vulnerabilities_count": len(self.redteam_vulnerabilities),
            "redteam_violation_rate": self.redteam_violation_rate,
            "faithfulness_scores": dict(self.faithfulness_scores),
            "faithfulness_mean": self.faithfulness_mean,
            "trace_mechanisms": list(self.trace_mechanisms),
            "transferable_mechanisms": list(self.transferable_mechanisms),
            "transfer_rate": self.transfer_rate,
            # I3: tiered fitness publication
            "tiered_fitness_best": self.tiered_fitness_best,
            "tiered_fitness_mean": self.tiered_fitness_mean,
            "tiered_fitness_generation": self.tiered_fitness_generation,
            "tiered_fitness_l2_calls": self.tiered_fitness_l2_calls,
            "tiered_fitness_tier_distribution": dict(self.tiered_fitness_tier_distribution),
            "tiered_fitness_last_theta": dict(self.tiered_fitness_last_theta),
            "last_updated": self.last_updated,
            "bus_hash": self.compute_hash(),
            "truth_effect": "NONE",
            "claim_ceiling": "STATE_BUS_IS_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "no_auto_promotion": True,
                "no_code_modification": True,
                "evaluative_not_truth": True,
                "shared_state_idempotent": True,
                # Step 2: thread safety
                "thread_safe": True,
            },
        }

    def save(self, path: str | Path) -> None:
        """Persist bus state to file."""
        write_json(path, self.payload())

    @classmethod
    def load(cls, path: str | Path) -> "TrainingStateBus":
        """Load bus state from file.

        Step 2: Fixed lossy deserialization — now restores ALL fields that
        were previously dropped:
        - pbt_champions (was: only pbt_best_fitness + pbt_generation)
        - alphazero_architectures (was: only alphazero_mechanisms)
        - redteam_vulnerabilities (was: only violation_rate)
        - rlaif_confidence (was: only rlaif_rewards)
        - tiered_fitness_tier_distribution (was: dropped)
        - tiered_fitness_last_theta (was: dropped)
        - tiered_fitness_mean (was: dropped)
        - tiered_fitness_l2_calls (was: dropped)
        """
        p = Path(path)
        if not p.is_file():
            return cls()
        data = json.loads(p.read_text())
        bus = cls()
        bus.rlaif_rewards = data.get("rlaif_rewards", {})
        bus.rlaif_confidence = data.get("rlaif_confidence", {})
        # Step 2: Restore pbt_champions (was dropped)
        bus.pbt_champions = data.get("pbt_champions", [])
        bus.pbt_best_fitness = data.get("pbt_best_fitness", 0.0)
        bus.pbt_generation = data.get("pbt_generation", 0)
        bus.alphazero_mechanisms = data.get("alphazero_mechanisms", [])
        # Step 2: Restore alphazero_architectures (was dropped)
        bus.alphazero_architectures = data.get("alphazero_architectures", [])
        bus.es_best_fitness = data.get("es_best_fitness", 0.0)
        bus.es_converged = data.get("es_converged", False)
        bus.es_best_theta = data.get("es_best_theta", {})
        bus.marl_agent_rewards = data.get("marl_agent_rewards", {})
        bus.marl_friend_mean = data.get("marl_friend_mean", 0.0)
        bus.marl_foe_mean = data.get("marl_foe_mean", 0.0)
        # Step 2: Restore redteam_vulnerabilities (was dropped)
        bus.redteam_vulnerabilities = data.get("redteam_vulnerabilities", [])
        bus.redteam_violation_rate = data.get("redteam_violation_rate", 0.0)
        bus.faithfulness_scores = data.get("faithfulness_scores", {})
        bus.faithfulness_mean = data.get("faithfulness_mean", 0.0)
        bus.trace_mechanisms = data.get("trace_mechanisms", [])
        bus.transferable_mechanisms = data.get("transferable_mechanisms", [])
        bus.transfer_rate = data.get("transfer_rate", 0.0)
        bus.tiered_fitness_best = data.get("tiered_fitness_best", 0.0)
        # Step 2: Restore tiered_fitness_mean (was dropped)
        bus.tiered_fitness_mean = data.get("tiered_fitness_mean", 0.0)
        bus.tiered_fitness_generation = data.get("tiered_fitness_generation", 0)
        # Step 2: Restore tiered_fitness_l2_calls (was dropped)
        bus.tiered_fitness_l2_calls = data.get("tiered_fitness_l2_calls", 0)
        # Step 2: Restore tiered_fitness_tier_distribution (was dropped)
        bus.tiered_fitness_tier_distribution = data.get("tiered_fitness_tier_distribution", {})
        # Step 2: Restore tiered_fitness_last_theta (was dropped)
        bus.tiered_fitness_last_theta = data.get("tiered_fitness_last_theta", {})
        bus.last_updated = data.get("last_updated", "")
        return bus

    def summary(self) -> dict[str, Any]:
        """Compact summary of bus state."""
        return {
            "bus_version": BUS_VERSION,
            "publishers": {
                "rlaif": len(self.rlaif_rewards),
                "pbt": len(self.pbt_champions),
                "alphazero": len(self.alphazero_mechanisms),
                "es": 1 if self.es_best_fitness > 0 else 0,
                "marl": len(self.marl_agent_rewards),
                "redteam": len(self.redteam_vulnerabilities),
                "faithfulness": len(self.faithfulness_scores),
                "traces": len(self.trace_mechanisms),
                "transfer": len(self.transferable_mechanisms),
                # I3: tiered fitness publisher status
                "tiered_fitness": 1 if self.tiered_fitness_best > 0 else 0,
            },
            "key_metrics": {
                "rlaif_mean_reward": sum(self.rlaif_rewards.values()) / max(1, len(self.rlaif_rewards)) if self.rlaif_rewards else 0.0,
                "pbt_best_fitness": self.pbt_best_fitness,
                "es_best_fitness": self.es_best_fitness,
                "es_converged": self.es_converged,
                "marl_foe_mean": self.marl_foe_mean,
                "redteam_violation_rate": self.redteam_violation_rate,
                "faithfulness_mean": self.faithfulness_mean,
                "transfer_rate": self.transfer_rate,
                # I3: tiered fitness metrics
                "tiered_fitness_best": self.tiered_fitness_best,
                "tiered_fitness_mean": self.tiered_fitness_mean,
                "tiered_fitness_generation": self.tiered_fitness_generation,
                "tiered_fitness_l2_calls": self.tiered_fitness_l2_calls,
            },
            "bus_hash": self.compute_hash()[:32],
            "last_updated": self.last_updated,
            "truth_effect": "NONE",
        }
