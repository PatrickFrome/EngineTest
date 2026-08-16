"""Tests for Phase 40 — MARL Friend-or-Foe Trainer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.marl_trainer import (
    MARLTrainer,
    AgentState,
    EpisodeResult,
    MARL_VERSION,
    FRIEND_ENGINES,
    FOE_ENGINES,
    classify_agent,
)


# ---------------------------------------------------------------------------
# Tests: Agent classification
# ---------------------------------------------------------------------------


class TestAgentClassification:
    """Test friend-or-foe classification."""

    def test_native_engines_are_friends(self):
        for eid in ["engine_01", "engine_02", "engine_03", "engine_04"]:
            assert classify_agent(eid) == "FRIEND"

    def test_reference_engines_are_foes(self):
        for i in range(5, 17):
            eid = f"engine_{i:02d}"
            assert classify_agent(eid) == "FOE"

    def test_unknown_engine(self):
        assert classify_agent("engine_99") == "UNKNOWN"

    def test_friend_set_size(self):
        assert len(FRIEND_ENGINES) == 4

    def test_foe_set_size(self):
        assert len(FOE_ENGINES) == 12

    def test_friend_foe_disjoint(self):
        assert FRIEND_ENGINES & FOE_ENGINES == set()


# ---------------------------------------------------------------------------
# Tests: AgentState
# ---------------------------------------------------------------------------


class TestAgentState:
    """Test the AgentState dataclass."""

    def test_initial_state(self):
        a = AgentState(engine_id="engine_01", agent_type="FRIEND")
        assert a.team_reward == 0.0
        assert a.individual_reward == 0.0
        assert a.marginal_contribution == 0.0
        assert a.episodes == 0

    def test_payload_has_truth_effect_none(self):
        a = AgentState(engine_id="engine_01", agent_type="FRIEND")
        p = a.payload()
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "MARL_REWARD_IS_PRIOR_NOT_TRUTH"

    def test_payload_has_agent_type(self):
        a = AgentState(engine_id="engine_01", agent_type="FRIEND")
        assert a.payload()["agent_type"] == "FRIEND"


# ---------------------------------------------------------------------------
# Tests: MARLTrainer initialization
# ---------------------------------------------------------------------------


class TestMARLTrainerInit:
    """Test trainer initialization."""

    def test_initializes_all_16_agents(self):
        trainer = MARLTrainer()
        assert len(trainer.agents) == 16

    def test_friend_agents_classified(self):
        trainer = MARLTrainer()
        for eid in FRIEND_ENGINES:
            assert trainer.agents[eid].agent_type == "FRIEND"

    def test_foe_agents_classified(self):
        trainer = MARLTrainer()
        for eid in FOE_ENGINES:
            assert trainer.agents[eid].agent_type == "FOE"

    def test_reward_weight_validation(self):
        with pytest.raises(ValueError, match="REWARD_WEIGHTS_MUST_SUM_TO_1"):
            MARLTrainer(
                team_reward_weight=0.5,
                individual_reward_weight=0.5,
                marginal_contribution_weight=0.5,
                friend_foe_bias_weight=0.5,
            )

    def test_valid_weights_accepted(self):
        trainer = MARLTrainer(
            team_reward_weight=0.25,
            individual_reward_weight=0.25,
            marginal_contribution_weight=0.25,
            friend_foe_bias_weight=0.25,
        )
        assert trainer.weights["team"] == 0.25


# ---------------------------------------------------------------------------
# Tests: Episode execution
# ---------------------------------------------------------------------------


class TestEpisodeExecution:
    """Test episode running."""

    def test_run_episode_returns_result(self):
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01", "engine_05"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.7,
        )
        assert isinstance(result, EpisodeResult)
        assert result.episode_id.startswith("ep.task_1.")
        assert result.episode_hash != ""

    def test_run_episode_team_quality_is_mean(self):
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01", "engine_02"],
            task_id="task_1",
            quality_fn=lambda eid, tid: {"engine_01": 0.6, "engine_02": 0.8}[eid],
        )
        assert result.team_quality == 0.7  # mean of 0.6 and 0.8

    def test_run_episode_individual_qualities(self):
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01", "engine_05"],
            task_id="task_1",
            quality_fn=lambda eid, tid: {"engine_01": 0.9, "engine_05": 0.3}[eid],
        )
        assert result.individual_qualities["engine_01"] == 0.9
        assert result.individual_qualities["engine_05"] == 0.3

    def test_run_episode_counterfactual_default(self):
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.8,
        )
        # Default counterfactual = team_quality * 0.9
        assert abs(result.counterfactual_qualities["engine_01"] - 0.72) < 0.001  # 0.8 * 0.9

    def test_run_episode_counterfactual_custom(self):
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.8,
            counterfactual_fn=lambda eid, tid: 0.5,
        )
        assert result.counterfactual_qualities["engine_01"] == 0.5

    def test_run_episode_unknown_engine_raises(self):
        trainer = MARLTrainer()
        with pytest.raises(ValueError, match="UNKNOWN_ENGINE"):
            trainer.run_episode(
                coalition=["engine_99"],
                task_id="task_1",
                quality_fn=lambda eid, tid: 0.5,
            )

    def test_episode_added_to_history(self):
        trainer = MARLTrainer()
        trainer.run_episode(
            coalition=["engine_01"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.5,
        )
        assert len(trainer.episodes) == 1


# ---------------------------------------------------------------------------
# Tests: Agent update
# ---------------------------------------------------------------------------


class TestAgentUpdate:
    """Test agent state updates after episodes."""

    def test_update_increments_episodes(self):
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.7,
        )
        trainer.update_agents(result)
        assert trainer.agents["engine_01"].episodes == 1

    def test_update_sets_team_reward(self):
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01", "engine_02"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.8,
        )
        trainer.update_agents(result)
        assert trainer.agents["engine_01"].team_reward == 0.8

    def test_update_sets_individual_reward(self):
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.9,
        )
        trainer.update_agents(result)
        assert trainer.agents["engine_01"].individual_reward == 0.9

    def test_marginal_contribution_positive(self):
        """If counterfactual < team_quality, marginal is positive."""
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.8,
            counterfactual_fn=lambda eid, tid: 0.5,  # lower than 0.8
        )
        trainer.update_agents(result)
        # marginal = 0.8 - 0.5 = 0.3 (positive contribution)
        assert trainer.agents["engine_01"].marginal_contribution > 0

    def test_marginal_contribution_negative(self):
        """If counterfactual > team_quality, marginal is negative."""
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.5,
            counterfactual_fn=lambda eid, tid: 0.8,  # higher than 0.5
        )
        trainer.update_agents(result)
        assert trainer.agents["engine_01"].marginal_contribution < 0

    def test_friend_bias_when_foe_in_coalition(self):
        """Friend gets friend_bias when foes are in coalition."""
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01", "engine_05"],  # friend + foe
            task_id="task_1",
            quality_fn=lambda eid, tid: {"engine_01": 0.6, "engine_05": 0.4}[eid],
        )
        trainer.update_agents(result)
        # engine_01 is FRIEND, foe_mean_quality=0.4, friend_bias=0.4*0.5=0.2
        assert trainer.agents["engine_01"].friend_bias > 0

    def test_foe_bias_when_outperforming_friend(self):
        """Foe gets foe_bias if it outperforms friends."""
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01", "engine_05"],
            task_id="task_1",
            quality_fn=lambda eid, tid: {"engine_01": 0.3, "engine_05": 0.9}[eid],  # foe > friend
        )
        trainer.update_agents(result)
        # engine_05 is FOE, outperformed friend (0.9 > 0.3)
        assert trainer.agents["engine_05"].foe_bias > 0

    def test_no_foe_bias_when_not_outperforming(self):
        """Foe gets no foe_bias if it doesn't outperform friends."""
        trainer = MARLTrainer()
        result = trainer.run_episode(
            coalition=["engine_01", "engine_05"],
            task_id="task_1",
            quality_fn=lambda eid, tid: {"engine_01": 0.9, "engine_05": 0.3}[eid],  # friend > foe
        )
        trainer.update_agents(result)
        assert trainer.agents["engine_05"].foe_bias == 0.0

    def test_total_reward_is_weighted_combination(self):
        trainer = MARLTrainer(
            team_reward_weight=0.5,
            individual_reward_weight=0.5,
            marginal_contribution_weight=0.0,
            friend_foe_bias_weight=0.0,
        )
        result = trainer.run_episode(
            coalition=["engine_01"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.8,
            counterfactual_fn=lambda eid, tid: 0.8,  # zero marginal
        )
        trainer.update_agents(result)
        # total = 0.5*0.8 + 0.5*0.8 + 0 + 0 = 0.8
        assert abs(trainer.agents["engine_01"].total_reward - 0.8) < 0.001

    def test_running_average_updates(self):
        """Multiple episodes should compute running average."""
        trainer = MARLTrainer()
        qualities = [0.6, 0.8, 0.4]
        for i, q in enumerate(qualities):
            result = trainer.run_episode(
                coalition=["engine_01"],
                task_id=f"task_{i}",
                quality_fn=lambda eid, tid: q,
            )
            trainer.update_agents(result)
        # Running average of [0.6, 0.8, 0.4] = 0.6
        assert abs(trainer.agents["engine_01"].individual_reward - 0.6) < 0.01


# ---------------------------------------------------------------------------
# Tests: Training loop
# ---------------------------------------------------------------------------


class TestTrainingLoop:
    """Test the full training loop."""

    def test_train_multiple_episodes(self):
        trainer = MARLTrainer()
        episodes = [
            (["engine_01", "engine_05"], "task_1"),
            (["engine_02", "engine_06"], "task_2"),
            (["engine_01", "engine_02", "engine_05"], "task_3"),
        ]
        summary = trainer.train(
            episodes=episodes,
            quality_fn=lambda eid, tid: 0.7,
        )
        assert summary["episodes_run"] == 3
        assert summary["active_agents"] > 0

    def test_train_updates_all_coalition_members(self):
        trainer = MARLTrainer()
        trainer.train(
            episodes=[(["engine_01", "engine_05", "engine_06"], "task_1")],
            quality_fn=lambda eid, tid: 0.5,
        )
        assert trainer.agents["engine_01"].episodes == 1
        assert trainer.agents["engine_05"].episodes == 1
        assert trainer.agents["engine_06"].episodes == 1
        # engine_02 not in coalition
        assert trainer.agents["engine_02"].episodes == 0

    def test_summary_returns_evaluative_not_truth(self):
        trainer = MARLTrainer()
        trainer.train(
            episodes=[(["engine_01"], "task_1")],
            quality_fn=lambda eid, tid: 0.5,
        )
        summary = trainer.summary()
        assert summary["truth_effect"] == "NONE"
        assert summary["claim_ceiling"] == "MARL_RESULTS_ARE_EVALUATIVE_NOT_TRUTH"


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    """Test that MARL preserves constitution."""

    def test_constitution_compliance_fields(self):
        trainer = MARLTrainer()
        trainer.train(
            episodes=[(["engine_01"], "task_1")],
            quality_fn=lambda eid, tid: 0.5,
        )
        summary = trainer.summary()
        assert summary["constitution_compliance"]["no_code_modification"] is True
        assert summary["constitution_compliance"]["friend_foe_classification_static"] is True
        assert summary["constitution_compliance"]["no_auto_promotion"] is True
        assert summary["constitution_compliance"]["rewards_are_priors"] is True

    def test_agent_types_never_change(self):
        """Friend/foe classification is static (constitution-defined)."""
        trainer = MARLTrainer()
        initial_types = {eid: a.agent_type for eid, a in trainer.agents.items()}
        trainer.train(
            episodes=[(["engine_01", "engine_05"], "task_1")],
            quality_fn=lambda eid, tid: 0.9,
        )
        for eid, initial_type in initial_types.items():
            assert trainer.agents[eid].agent_type == initial_type

    def test_all_episode_results_have_truth_effect_none(self):
        trainer = MARLTrainer()
        trainer.train(
            episodes=[(["engine_01"], "task_1")],
            quality_fn=lambda eid, tid: 0.5,
        )
        for ep in trainer.episodes:
            assert ep.payload()["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_seed_same_episode_hash(self):
        t1 = MARLTrainer(seed=42)
        t2 = MARLTrainer(seed=42)
        r1 = t1.run_episode(
            coalition=["engine_01", "engine_05"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.7,
        )
        r2 = t2.run_episode(
            coalition=["engine_01", "engine_05"],
            task_id="task_1",
            quality_fn=lambda eid, tid: 0.7,
        )
        assert r1.episode_hash == r2.episode_hash
