"""METAENGINE Phase 40 — MARL Friend-or-Foe Trainer.

Multi-Agent Reinforcement Learning with friend-or-foe bias (Ryu et al 2021).
16 engines = 16 agents, classified as:
  - FRIEND (native engines 01-04): real executors, cooperative bias
  - FOE (reference engines 05-16): simulations, competitive bias

Reward structure:
  - Team reward: coalition quality (shared among coalition members)
  - Individual reward: relative to tournament performance
  - Friend-or-foe bias: friends get bonus for helping foes improve

Credit assignment:
  - Counterfactual: what would team quality be without this agent?
  - Marginal contribution = team_quality - team_quality_without_agent

Constitution compliance:
  - MARL does NOT modify code — only updates biography priors
  - All engines remain in their roles (no auto-promotion)
  - Rewards are contextual priors, not truth claims
  - Friend-or-foe classification is static (constitution-defined engine types)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from .util import canonical_hash


MARL_VERSION = "METAENGINE-MARL-FRIEND-OR-FOE-1"


# ---------------------------------------------------------------------------
# Agent classification
# ---------------------------------------------------------------------------


# Native engines (01-04) are FRIENDS — real executors, cooperative
FRIEND_ENGINES = {"engine_01", "engine_02", "engine_03", "engine_04"}

# Reference engines (05-16) are FOES — simulations, competitive
FOE_ENGINES = {f"engine_{i:02d}" for i in range(5, 17)}


def classify_agent(engine_id: str) -> str:
    """Classify an engine as FRIEND or FOE."""
    if engine_id in FRIEND_ENGINES:
        return "FRIEND"
    elif engine_id in FOE_ENGINES:
        return "FOE"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------


@dataclass
class AgentState:
    """State of a single agent in the MARL setting."""
    engine_id: str
    agent_type: str  # FRIEND or FOE
    team_reward: float = 0.0  # shared coalition reward
    individual_reward: float = 0.0  # relative tournament reward
    marginal_contribution: float = 0.0  # counterfactual credit
    friend_bias: float = 0.0  # bonus for helping foes
    foe_bias: float = 0.0  # bonus for outperforming foes
    total_reward: float = 0.0  # weighted combination
    episodes: int = 0  # number of training episodes

    def payload(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "agent_type": self.agent_type,
            "team_reward": round(self.team_reward, 6),
            "individual_reward": round(self.individual_reward, 6),
            "marginal_contribution": round(self.marginal_contribution, 6),
            "friend_bias": round(self.friend_bias, 6),
            "foe_bias": round(self.foe_bias, 6),
            "total_reward": round(self.total_reward, 6),
            "episodes": self.episodes,
            "truth_effect": "NONE",
            "claim_ceiling": "MARL_REWARD_IS_PRIOR_NOT_TRUTH",
        }


# ---------------------------------------------------------------------------
# Episode result
# ---------------------------------------------------------------------------


@dataclass
class EpisodeResult:
    """Result of one MARL training episode."""
    episode_id: str
    coalition_members: tuple[str, ...]
    task_id: str
    team_quality: float
    individual_qualities: dict[str, float]  # engine_id → quality
    counterfactual_qualities: dict[str, float]  # engine_id → quality without that agent
    episode_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "coalition_members": list(self.coalition_members),
            "task_id": self.task_id,
            "team_quality": round(self.team_quality, 6),
            "individual_qualities": {k: round(v, 6) for k, v in self.individual_qualities.items()},
            "counterfactual_qualities": {k: round(v, 6) for k, v in self.counterfactual_qualities.items()},
            "truth_effect": "NONE",
        }


# ---------------------------------------------------------------------------
# MARL Trainer
# ---------------------------------------------------------------------------


class MARLTrainer:
    """Multi-Agent RL trainer with friend-or-foe bias.

    The trainer maintains agent states for all 16 engines and updates them
    based on episode results. Each episode:
      1. A coalition of engines works on a task
      2. Team quality is measured (shared reward)
      3. Individual qualities are measured (competitive reward)
      4. Counterfactual: what would team quality be without each agent?
      5. Marginal contribution = team_quality - counterfactual_quality
      6. Friend bias: friends get bonus if foes in coalition improved
      7. Foe bias: foes get bonus if they outperformed friends

    Usage:
        trainer = MARLTrainer()
        for episode in episodes:
            result = trainer.run_episode(coalition, task_id, quality_fn)
            trainer.update_agents(result)
    """

    def __init__(
        self,
        *,
        team_reward_weight: float = 0.4,
        individual_reward_weight: float = 0.3,
        marginal_contribution_weight: float = 0.2,
        friend_foe_bias_weight: float = 0.1,
        seed: int = 42,
    ):
        # Validate weights
        total = team_reward_weight + individual_reward_weight + marginal_contribution_weight + friend_foe_bias_weight
        if not 0.9 <= total <= 1.1:
            raise ValueError(f"REWARD_WEIGHTS_MUST_SUM_TO_1 (got {total})")

        self.weights = {
            "team": team_reward_weight,
            "individual": individual_reward_weight,
            "marginal": marginal_contribution_weight,
            "friend_foe": friend_foe_bias_weight,
        }
        self._rng = random.Random(seed)
        self.agents: dict[str, AgentState] = {}
        self.episodes: list[EpisodeResult] = []
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Initialize all 16 agents."""
        for engine_id in sorted(FRIEND_ENGINES | FOE_ENGINES):
            self.agents[engine_id] = AgentState(
                engine_id=engine_id,
                agent_type=classify_agent(engine_id),
            )

    # ------------------------------------------------------------------
    # Episode execution
    # ------------------------------------------------------------------

    def run_episode(
        self,
        *,
        coalition: list[str],
        task_id: str,
        quality_fn: Callable[[str, str], float],
        counterfactual_fn: Callable[[str, str], float] | None = None,
    ) -> EpisodeResult:
        """Run one MARL training episode.

        Args:
            coalition: list of engine_ids in the coalition.
            task_id: the task being worked on.
            quality_fn: fn(engine_id, task_id) → quality 0-1 for that engine.
            counterfactual_fn: fn(engine_id, task_id) → quality without that engine.
                              If None, uses 0.5 (neutral counterfactual).

        Returns:
            EpisodeResult with team/individual/counterfactual qualities.
        """
        # Validate coalition
        for eid in coalition:
            if eid not in self.agents:
                raise ValueError(f"UNKNOWN_ENGINE:{eid}")

        episode_id = f"ep.{task_id}.{canonical_hash({'coalition': sorted(coalition)})[:12]}"

        # Measure individual qualities
        individual_qualities = {eid: quality_fn(eid, task_id) for eid in coalition}

        # Team quality = mean of individual qualities (cooperative)
        team_quality = sum(individual_qualities.values()) / len(individual_qualities) if individual_qualities else 0.0

        # Counterfactual: quality without each agent
        counterfactual_qualities = {}
        for eid in coalition:
            if counterfactual_fn is not None:
                counterfactual_qualities[eid] = counterfactual_fn(eid, task_id)
            else:
                # Default: team quality without this agent = team_quality * 0.9 (slight degradation)
                counterfactual_qualities[eid] = team_quality * 0.9

        result = EpisodeResult(
            episode_id=episode_id,
            coalition_members=tuple(sorted(coalition)),
            task_id=task_id,
            team_quality=team_quality,
            individual_qualities=individual_qualities,
            counterfactual_qualities=counterfactual_qualities,
            episode_hash="",
        )
        h = canonical_hash(result.payload())
        result = EpisodeResult(**{**result.__dict__, "episode_hash": h})

        self.episodes.append(result)
        return result

    # ------------------------------------------------------------------
    # Agent update
    # ------------------------------------------------------------------

    def update_agents(self, episode: EpisodeResult) -> dict[str, AgentState]:
        """Update agent states based on episode result.

        For each agent in the coalition:
          - team_reward = episode.team_quality (shared)
          - individual_reward = agent's individual quality
          - marginal_contribution = team_quality - counterfactual_quality
          - friend_bias = bonus if foes in coalition improved
          - foe_bias = bonus if foe outperformed friends
          - total_reward = weighted combination

        Returns dict of updated agent states.
        """
        updated: dict[str, AgentState] = {}

        # Compute friend/foe statistics for the coalition
        friends_in_coalition = [eid for eid in episode.coalition_members if eid in FRIEND_ENGINES]
        foes_in_coalition = [eid for eid in episode.coalition_members if eid in FOE_ENGINES]

        friend_mean_quality = (
            sum(episode.individual_qualities[eid] for eid in friends_in_coalition) / len(friends_in_coalition)
            if friends_in_coalition else 0.0
        )
        foe_mean_quality = (
            sum(episode.individual_qualities[eid] for eid in foes_in_coalition) / len(foes_in_coalition)
            if foes_in_coalition else 0.0
        )

        for eid in episode.coalition_members:
            agent = self.agents[eid]
            agent_type = agent.agent_type

            # Team reward (shared)
            team_reward = episode.team_quality

            # Individual reward
            individual_reward = episode.individual_qualities.get(eid, 0.0)

            # Marginal contribution (counterfactual credit)
            cf_quality = episode.counterfactual_qualities.get(eid, episode.team_quality)
            marginal = episode.team_quality - cf_quality

            # Friend-or-foe bias
            friend_bias = 0.0
            foe_bias = 0.0
            if agent_type == "FRIEND" and foes_in_coalition:
                # Friend gets bonus if foes improved (cooperative)
                friend_bias = foe_mean_quality * 0.5
            elif agent_type == "FOE" and friends_in_coalition:
                # Foe gets bonus if it outperformed friends (competitive)
                if individual_reward > friend_mean_quality:
                    foe_bias = (individual_reward - friend_mean_quality) * 0.5

            # Total reward (weighted combination)
            total = (
                self.weights["team"] * team_reward
                + self.weights["individual"] * individual_reward
                + self.weights["marginal"] * marginal
                + self.weights["friend_foe"] * (friend_bias + foe_bias)
            )

            # Update agent (running average)
            n = agent.episodes
            agent.team_reward = round((agent.team_reward * n + team_reward) / (n + 1), 6)
            agent.individual_reward = round((agent.individual_reward * n + individual_reward) / (n + 1), 6)
            agent.marginal_contribution = round((agent.marginal_contribution * n + marginal) / (n + 1), 6)
            agent.friend_bias = round((agent.friend_bias * n + friend_bias) / (n + 1), 6)
            agent.foe_bias = round((agent.foe_bias * n + foe_bias) / (n + 1), 6)
            agent.total_reward = round((agent.total_reward * n + total) / (n + 1), 6)
            agent.episodes = n + 1

            updated[eid] = agent

        return updated

    # ------------------------------------------------------------------
    # Training loop
    # ------------------------------------------------------------------

    def train(
        self,
        *,
        episodes: list[tuple[list[str], str]],
        quality_fn: Callable[[str, str], float],
        counterfactual_fn: Callable[[str, str], float] | None = None,
    ) -> dict[str, Any]:
        """Run multiple training episodes.

        Args:
            episodes: list of (coalition, task_id) tuples.
            quality_fn: fn(engine_id, task_id) → quality.
            counterfactual_fn: fn(engine_id, task_id) → counterfactual quality.

        Returns:
            Training summary.
        """
        for coalition, task_id in episodes:
            result = self.run_episode(
                coalition=coalition,
                task_id=task_id,
                quality_fn=quality_fn,
                counterfactual_fn=counterfactual_fn,
            )
            self.update_agents(result)

        return self.summary()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return training summary."""
        if not self.episodes:
            return {
                "marl_version": MARL_VERSION,
                "episodes_run": 0,
                "truth_effect": "NONE",
            }

        # Aggregate agent stats
        friend_agents = [a for a in self.agents.values() if a.agent_type == "FRIEND"]
        foe_agents = [a for a in self.agents.values() if a.agent_type == "FOE"]

        friend_mean_reward = sum(a.total_reward for a in friend_agents) / len(friend_agents) if friend_agents else 0.0
        foe_mean_reward = sum(a.total_reward for a in foe_agents) / len(foe_agents) if foe_agents else 0.0

        active_agents = [a for a in self.agents.values() if a.episodes > 0]

        return {
            "marl_version": MARL_VERSION,
            "episodes_run": len(self.episodes),
            "reward_weights": self.weights,
            "total_agents": len(self.agents),
            "friend_agents": len(friend_agents),
            "foe_agents": len(foe_agents),
            "active_agents": len(active_agents),
            "friend_mean_reward": round(friend_mean_reward, 6),
            "foe_mean_reward": round(foe_mean_reward, 6),
            "agents": {eid: a.payload() for eid, a in sorted(self.agents.items()) if a.episodes > 0},
            "episode_summaries": [
                {
                    "episode_id": e.episode_id,
                    "task_id": e.task_id,
                    "team_quality": round(e.team_quality, 6),
                    "coalition_size": len(e.coalition_members),
                }
                for e in self.episodes
            ],
            "truth_effect": "NONE",
            "claim_ceiling": "MARL_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "no_code_modification": True,
                "friend_foe_classification_static": True,
                "no_auto_promotion": True,
                "rewards_are_priors": True,
            },
        }
