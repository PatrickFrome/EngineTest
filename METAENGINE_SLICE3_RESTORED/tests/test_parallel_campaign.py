"""Tests for Phase 42 — Parallel Training Campaign."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.parallel_campaign import (
    ParallelTrainingCampaign,
    TrainerResult,
    CampaignResult,
    CAMPAIGN_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def campaign():
    return ParallelTrainingCampaign(max_workers=4, campaign_id="test-campaign")


def make_mock_trainer(name: str, delay: float = 0.01, summary: dict | None = None):
    """Create a mock trainer function."""
    def trainer_fn():
        time.sleep(delay)
        return summary or {"trainer": name, "best_fitness": 0.5}
    return trainer_fn


def make_failing_trainer(name: str, error: str = "INTENTIONAL_FAILURE"):
    """Create a trainer that raises an exception."""
    def trainer_fn():
        raise RuntimeError(error)
    return trainer_fn


# ---------------------------------------------------------------------------
# Tests: TrainerResult
# ---------------------------------------------------------------------------


class TestTrainerResult:
    """Test the TrainerResult dataclass."""

    def test_payload_has_required_fields(self):
        r = TrainerResult(
            trainer_name="RLAIF",
            started_at=1000.0,
            elapsed_seconds=1.5,
            success=True,
            summary={"reward": 0.5},
            error=None,
            result_hash="abc",
        )
        p = r.payload()
        assert p["trainer_name"] == "RLAIF"
        assert p["success"] is True
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "CAMPAIGN_TRAINER_RESULT_IS_EVALUATIVE_NOT_TRUTH"

    def test_as_dict_includes_hash(self):
        r = TrainerResult(
            trainer_name="test",
            started_at=0.0,
            elapsed_seconds=0.0,
            success=True,
            summary={},
            error=None,
            result_hash="abc123",
        )
        d = r.as_dict()
        assert d["result_hash"] == "abc123"

    def test_failed_trainer_has_error(self):
        r = TrainerResult(
            trainer_name="failing",
            started_at=0.0,
            elapsed_seconds=0.0,
            success=False,
            summary={},
            error="SOMETHING_WENT_WRONG",
            result_hash="",
        )
        assert r.payload()["error"] == "SOMETHING_WENT_WRONG"


# ---------------------------------------------------------------------------
# Tests: CampaignResult
# ---------------------------------------------------------------------------


class TestCampaignResult:
    """Test the CampaignResult dataclass."""

    def test_payload_has_required_fields(self):
        r = CampaignResult(
            campaign_id="test",
            started_at=0.0,
            elapsed_seconds=1.0,
            trainer_results=(),
            shared_state_summary={"trainers_run": 0},
            campaign_hash="abc",
        )
        p = r.payload()
        assert p["campaign_version"] == CAMPAIGN_VERSION
        assert p["campaign_id"] == "test"
        assert p["truth_effect"] == "NONE"
        assert p["constitution_compliance"]["all_trainers_remain_shadow"] is True

    def test_as_dict_includes_hash(self):
        r = CampaignResult(
            campaign_id="test",
            started_at=0.0,
            elapsed_seconds=0.0,
            trainer_results=(),
            shared_state_summary={},
            campaign_hash="abc123",
        )
        d = r.as_dict()
        assert d["campaign_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: ParallelTrainingCampaign initialization
# ---------------------------------------------------------------------------


class TestCampaignInit:
    """Test campaign initialization."""

    def test_initializes_empty(self, campaign):
        assert campaign.trainers == {}
        assert campaign.max_workers == 4

    def test_max_workers_validation(self):
        with pytest.raises(ValueError, match="MAX_WORKERS_MUST_BE_AT_LEAST_1"):
            ParallelTrainingCampaign(max_workers=0)

    def test_campaign_id_generated(self):
        c = ParallelTrainingCampaign()
        assert c.campaign_id.startswith("campaign.")

    def test_campaign_id_custom(self):
        c = ParallelTrainingCampaign(campaign_id="my-campaign")
        assert c.campaign_id == "my-campaign"


# ---------------------------------------------------------------------------
# Tests: Trainer registration
# ---------------------------------------------------------------------------


class TestTrainerRegistration:
    """Test trainer registration."""

    def test_register_trainer(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF"))
        assert "RLAIF" in campaign.trainers

    def test_register_multiple_trainers(self, campaign):
        for name in ["RLAIF", "PBT", "AlphaZero", "ES", "MARL", "RedTeam"]:
            campaign.register_trainer(name, make_mock_trainer(name))
        assert len(campaign.trainers) == 6

    def test_register_empty_name_raises(self, campaign):
        with pytest.raises(ValueError, match="TRAINER_NAME_CANNOT_BE_EMPTY"):
            campaign.register_trainer("", make_mock_trainer("test"))

    def test_unregister_trainer(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF"))
        campaign.unregister_trainer("RLAIF")
        assert "RLAIF" not in campaign.trainers

    def test_unregister_nonexistent_trainer(self, campaign):
        # Should not raise
        campaign.unregister_trainer("nonexistent")


# ---------------------------------------------------------------------------
# Tests: Running trainers
# ---------------------------------------------------------------------------


class TestRunTrainers:
    """Test running trainers in parallel."""

    def test_run_single_trainer(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF", summary={"reward": 0.7}))
        result = campaign.run()
        assert result.campaign_id == "test-campaign"
        assert len(result.trainer_results) == 1
        assert result.trainer_results[0].trainer_name == "RLAIF"
        assert result.trainer_results[0].success is True
        assert result.trainer_results[0].summary["reward"] == 0.7

    def test_run_multiple_trainers_parallel(self, campaign):
        for name in ["RLAIF", "PBT", "AlphaZero"]:
            campaign.register_trainer(name, make_mock_trainer(name, delay=0.05))
        result = campaign.run()
        assert len(result.trainer_results) == 3
        # All should succeed
        for r in result.trainer_results:
            assert r.success is True
        # Should be sorted by name
        names = [r.trainer_name for r in result.trainer_results]
        assert names == ["AlphaZero", "PBT", "RLAIF"]

    def test_run_all_6_trainers(self, campaign):
        trainer_names = ["AlphaZero", "ES", "MARL", "PBT", "RedTeam", "RLAIF"]
        for name in trainer_names:
            campaign.register_trainer(name, make_mock_trainer(name))
        result = campaign.run()
        assert len(result.trainer_results) == 6
        # All should succeed
        succeeded = sum(1 for r in result.trainer_results if r.success)
        assert succeeded == 6

    def test_run_handles_failing_trainer(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF"))
        campaign.register_trainer("FAILING", make_failing_trainer("FAILING"))
        result = campaign.run()
        assert len(result.trainer_results) == 2
        # One should fail
        failing = [r for r in result.trainer_results if not r.success]
        assert len(failing) == 1
        assert failing[0].trainer_name == "FAILING"
        assert "INTENTIONAL_FAILURE" in failing[0].error

    def test_run_no_trainers_raises(self, campaign):
        with pytest.raises(ValueError, match="NO_TRAINERS_REGISTERED"):
            campaign.run()

    def test_elapsed_seconds_positive(self, campaign):
        campaign.register_trainer("slow", make_mock_trainer("slow", delay=0.1))
        result = campaign.run()
        assert result.elapsed_seconds > 0.05  # at least 50ms

    def test_parallel_faster_than_sequential(self):
        """Running 4 trainers with 0.1s delay each should be ~0.1s, not 0.4s."""
        campaign = ParallelTrainingCampaign(max_workers=4)
        for i in range(4):
            campaign.register_trainer(f"trainer_{i}", make_mock_trainer(f"t{i}", delay=0.1))
        result = campaign.run()
        # Parallel should be much faster than sequential (0.4s)
        assert result.elapsed_seconds < 0.3  # parallel < 0.3s vs sequential 0.4s

    def test_campaign_hash_deterministic(self):
        """Same trainers + same results → same trainer result hashes (excluding timestamps)."""
        c1 = ParallelTrainingCampaign(campaign_id="test", max_workers=2)
        c2 = ParallelTrainingCampaign(campaign_id="test", max_workers=2)
        c1.register_trainer("A", make_mock_trainer("A", summary={"x": 1}))
        c2.register_trainer("A", make_mock_trainer("A", summary={"x": 1}))
        r1 = c1.run()
        r2 = c2.run()
        # Trainer result hashes should be the same (summary is deterministic)
        # Note: campaign_hash includes started_at timestamp, so we check trainer hashes
        assert r1.trainer_results[0].result_hash == r2.trainer_results[0].result_hash


# ---------------------------------------------------------------------------
# Tests: Shared state summary
# ---------------------------------------------------------------------------


class TestSharedStateSummary:
    """Test shared state summary extraction."""

    def test_rlaif_reward_extracted(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF", summary={"best_fitness": 0.65}))
        result = campaign.run()
        assert result.shared_state_summary.get("rlaif_reward") == 0.65

    def test_pbt_best_fitness_extracted(self, campaign):
        campaign.register_trainer("PBT", make_mock_trainer("PBT", summary={"best_fitness": 0.89}))
        result = campaign.run()
        assert result.shared_state_summary.get("pbt_best_fitness") == 0.89

    def test_alphazero_metrics_extracted(self, campaign):
        campaign.register_trainer("AlphaZero", make_mock_trainer("AlphaZero", summary={
            "total_mechanisms_extracted": 6,
            "total_architectures_synthesized": 3,
        }))
        result = campaign.run()
        assert result.shared_state_summary.get("alphazero_mechanisms_extracted") == 6
        assert result.shared_state_summary.get("alphazero_architectures_synthesized") == 3

    def test_es_metrics_extracted(self, campaign):
        campaign.register_trainer("ES", make_mock_trainer("ES", summary={
            "best_fitness": 0.86,
            "converged": True,
        }))
        result = campaign.run()
        assert result.shared_state_summary.get("es_best_fitness") == 0.86
        assert result.shared_state_summary.get("es_converged") is True

    def test_marl_metrics_extracted(self, campaign):
        campaign.register_trainer("MARL", make_mock_trainer("MARL", summary={
            "friend_mean_reward": 0.3,
            "foe_mean_reward": 0.25,
        }))
        result = campaign.run()
        assert result.shared_state_summary.get("marl_friend_mean_reward") == 0.3
        assert result.shared_state_summary.get("marl_foe_mean_reward") == 0.25

    def test_redteam_metrics_extracted(self, campaign):
        campaign.register_trainer("RedTeam", make_mock_trainer("RedTeam", summary={
            "overall_violation_rate": 0.15,
            "total_violations": 3,
        }))
        result = campaign.run()
        assert result.shared_state_summary.get("redteam_violation_rate") == 0.15
        assert result.shared_state_summary.get("redteam_total_violations") == 3

    def test_failed_trainer_not_extracted(self, campaign):
        campaign.register_trainer("RLAIF", make_failing_trainer("RLAIF"))
        result = campaign.run()
        # Failed trainer's summary is empty → key not in shared_state
        assert "rlaif_reward" not in result.shared_state_summary


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    """Test that campaign preserves constitution."""

    def test_all_results_have_truth_effect_none(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF"))
        result = campaign.run()
        for tr in result.trainer_results:
            assert tr.payload()["truth_effect"] == "NONE"

    def test_campaign_payload_has_constitution_compliance(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF"))
        result = campaign.run()
        p = result.payload()
        assert p["constitution_compliance"]["all_trainers_remain_shadow"] is True
        assert p["constitution_compliance"]["no_auto_promotion"] is True
        assert p["constitution_compliance"]["shared_state_idempotent"] is True
        assert p["constitution_compliance"]["no_code_modification"] is True

    def test_campaign_claim_ceiling(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF"))
        result = campaign.run()
        assert result.payload()["claim_ceiling"] == "CAMPAIGN_RESULTS_ARE_EVALUATIVE_NOT_TRUTH"
        assert result.payload()["truth_effect"] == "NONE"

    def test_summary_without_running(self, campaign):
        campaign.register_trainer("RLAIF", make_mock_trainer("RLAIF"))
        s = campaign.summary()
        assert s["campaign_version"] == CAMPAIGN_VERSION
        assert s["registered_trainers"] == ["RLAIF"]
        assert s["truth_effect"] == "NONE"
