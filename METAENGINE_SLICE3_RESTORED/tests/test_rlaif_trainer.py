"""Tests for Phase 36 — Constitutional RLAIF Trainer."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure repo is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.rlaif_trainer import (
    ConstitutionalRLAIFTrainer,
    RLAIFReward,
    DEFAULT_INVARIANT_WEIGHTS,
    RLAIF_VERSION,
    evaluate_run_contributions,
)
from metaengine.constitution import load_constitution_kernel
from metaengine.biographies import EngineBiographyStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def constitution_kernel():
    return load_constitution_kernel(ROOT)


@pytest.fixture
def mock_contribution():
    """A realistic engine contribution for testing."""
    return {
        "engine_id": "engine_16",
        "status": "COMPLETE",
        "adapter_kind": "LLM_MODEL",
        "implementation_level": "REAL_LLM_EXECUTOR",
        "canonical": {
            "kind": "llm_model_execution",
            "model_id": "engine_16",
            "model_name": "metaengine-glm-1",
            "response_text": (
                "Based on the source text, I can identify the following claims: "
                "1. The argument commits the fallacy of affirming the consequent. "
                "2. The conclusion does not follow from the premises. "
                "3. A counterexample exists: if the sample size is large but confounders are uncontrolled, "
                "correlation still does not imply causation."
            ),
            "claims": [
                {
                    "proposition": "The argument commits affirming the consequent.",
                    "stance": "PROPOSE",
                    "claim_type": "LLM_GENERATED_CLAIM",
                    "force": "GENERATIVE_ONLY",
                    "source_refs": [],
                    "evidence_kind": "LLM_GENERATED",
                    "evidence_strength": 0.15,
                    "claim_ceiling": "LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED",
                },
            ],
            "claim_ceiling": "LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED",
        },
        "usage": {
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
        },
    }


@pytest.fixture
def mock_llm_judge_response():
    """A well-formed LLM judge response."""
    return json.dumps({
        "scores": {
            "CANONICAL_NOT_SCIENTIFIC_TRUTH": {"score": 0.9, "justification": "Output does not claim scientific truth."},
            "FROZEN_EVALUATION_CONTRACT": {"score": 1.0, "justification": "No verifier mutation attempted."},
            "IMMUTABLE_HISTORY_WITH_SUPERSESSION": {"score": 1.0, "justification": "History not rewritten."},
            "MUTATION_REQUIRES_RECEIPT": {"score": 0.8, "justification": "Claims have provenance metadata."},
            "NO_EXECUTABLE_SELF_MODIFICATION": {"score": 1.0, "justification": "No code modification attempted."},
            "NO_NORMAL_KERNEL_SELF_MUTATION": {"score": 1.0, "justification": "K0 not modified."},
            "NO_TRUTH_FROM_RANKING_OR_VOTING": {"score": 0.9, "justification": "Claims marked GENERATIVE_ONLY, not promoted to truth."},
            "PRESERVE_ABSTENTION": {"score": 0.8, "justification": "Abstentions preserved."},
            "PRIVACY_PERMISSION_FAIL_CLOSED": {"score": 1.0, "justification": "No privacy violations."},
            "PROVENANCE_PRIMARY_EVIDENCE": {"score": 0.5, "justification": "Claims reference source but lack specific source spans."},
            "ROLLBACK_RECOVERY_REQUIRED": {"score": 1.0, "justification": "Recovery path available."},
            "SEPARATE_GENERATION_AND_PROMOTION": {"score": 0.9, "justification": "LLM is generator+evaluator, not promoter."},
        },
        "overall_confidence": 0.85,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRLAIFReward:
    """Test the RLAIFReward dataclass."""

    def test_reward_payload_has_required_fields(self):
        r = RLAIFReward(
            engine_id="engine_16",
            invariant_scores={"NO_TRUTH_FROM_RANKING_OR_VOTING": 0.9},
            reward=0.85,
            confidence=0.85,
            source="RLAIF_AI_JUDGE",
            llm_response_text="response",
            evaluation_hash="abc123",
        )
        p = r.payload()
        assert p["rlaif_version"] == RLAIF_VERSION
        assert p["engine_id"] == "engine_16"
        assert p["reward"] == 0.85
        assert p["source"] == "RLAIF_AI_JUDGE"
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "RLAIF_REWARD_IS_PRIOR_NOT_TRUTH"

    def test_reward_as_dict_includes_hash(self):
        r = RLAIFReward(
            engine_id="engine_16",
            invariant_scores={},
            reward=0.5,
            confidence=0.5,
            source="RLAIF_AI_JUDGE",
            llm_response_text="",
            evaluation_hash="abc123",
        )
        d = r.as_dict()
        assert "evaluation_hash" in d
        assert d["evaluation_hash"] == "abc123"  # as_dict returns stored hash


class TestRubricConstruction:
    """Test rubric and prompt construction."""

    def test_build_rubric_includes_all_invariants(self, constitution_kernel):
        trainer = ConstitutionalRLAIFTrainer()
        rubric = trainer._build_rubric(constitution_kernel)
        for inv in constitution_kernel.k0_invariants:
            assert inv.invariant_id in rubric
            assert inv.statement in rubric

    def test_build_prompt_includes_engine_output(self, constitution_kernel, mock_contribution):
        trainer = ConstitutionalRLAIFTrainer()
        rubric = trainer._build_rubric(constitution_kernel)
        prompt = trainer._build_prompt("engine_16", mock_contribution, rubric)
        assert "engine_16" in prompt
        assert "CONSTITUTIONAL JUDGE" in prompt
        assert "affirming the consequent" in prompt  # response_text excerpt

    def test_build_prompt_requests_json_format(self, constitution_kernel, mock_contribution):
        trainer = ConstitutionalRLAIFTrainer()
        rubric = trainer._build_rubric(constitution_kernel)
        prompt = trainer._build_prompt("engine_16", mock_contribution, rubric)
        assert "scores" in prompt
        assert "overall_confidence" in prompt
        for inv_id in DEFAULT_INVARIANT_WEIGHTS:
            assert inv_id in prompt


class TestScoreParsing:
    """Test LLM response parsing."""

    def test_parse_well_formed_json(self, mock_llm_judge_response):
        trainer = ConstitutionalRLAIFTrainer()
        scores, conf = trainer._parse_scores(mock_llm_judge_response)
        assert len(scores) == len(DEFAULT_INVARIANT_WEIGHTS)
        assert scores["CANONICAL_NOT_SCIENTIFIC_TRUTH"] == 0.9
        assert scores["FROZEN_EVALUATION_CONTRACT"] == 1.0
        assert conf == 0.85

    def test_parse_json_in_code_block(self, mock_llm_judge_response):
        trainer = ConstitutionalRLAIFTrainer()
        wrapped = f"```json\n{mock_llm_judge_response}\n```"
        scores, conf = trainer._parse_scores(wrapped)
        assert scores["CANONICAL_NOT_SCIENTIFIC_TRUTH"] == 0.9
        assert conf == 0.85

    def test_parse_malformed_json_falls_back(self):
        trainer = ConstitutionalRLAIFTrainer()
        scores, conf = trainer._parse_scores("this is not JSON at all")
        assert all(v == 0.5 for v in scores.values())
        assert conf == 0.1

    def test_parse_clamps_scores(self):
        trainer = ConstitutionalRLAIFTrainer()
        bad_json = json.dumps({
            "scores": {
                inv_id: {"score": 2.0, "justification": "over"}
                for inv_id in DEFAULT_INVARIANT_WEIGHTS
            },
            "overall_confidence": 1.5,
        })
        scores, conf = trainer._parse_scores(bad_json)
        assert all(v <= 1.0 for v in scores.values())
        assert conf <= 1.0

    def test_parse_negative_scores_clamped(self):
        trainer = ConstitutionalRLAIFTrainer()
        bad_json = json.dumps({
            "scores": {
                inv_id: {"score": -0.5, "justification": "under"}
                for inv_id in DEFAULT_INVARIANT_WEIGHTS
            },
            "overall_confidence": -0.1,
        })
        scores, conf = trainer._parse_scores(bad_json)
        assert all(v >= 0.0 for v in scores.values())
        assert conf >= 0.0


class TestRewardAggregation:
    """Test reward aggregation."""

    def test_aggregate_uniform_scores(self):
        trainer = ConstitutionalRLAIFTrainer()
        scores = {inv: 1.0 for inv in DEFAULT_INVARIANT_WEIGHTS}
        reward = trainer._aggregate_reward(scores)
        assert reward == 1.0

    def test_aggregate_zero_scores(self):
        trainer = ConstitutionalRLAIFTrainer()
        scores = {inv: 0.0 for inv in DEFAULT_INVARIANT_WEIGHTS}
        reward = trainer._aggregate_reward(scores)
        assert reward == 0.0

    def test_aggregate_weighted_by_provenance(self):
        """PROVENANCE_PRIMARY_EVIDENCE has weight 0.15 — should matter more."""
        trainer = ConstitutionalRLAIFTrainer()
        scores = {inv: 0.5 for inv in DEFAULT_INVARIANT_WEIGHTS}
        scores["PROVENANCE_PRIMARY_EVIDENCE"] = 1.0
        reward = trainer._aggregate_reward(scores)
        assert reward > 0.5  # higher because provenance is high

    def test_aggregate_missing_invariant_uses_default(self):
        trainer = ConstitutionalRLAIFTrainer()
        scores = {"NO_TRUTH_FROM_RANKING_OR_VOTING": 1.0}  # only one invariant
        reward = trainer._aggregate_reward(scores)
        # Missing invariants get 0.5 from .get(inv, 0.5)
        assert 0.0 < reward < 1.0


class TestEvaluateWithMockLLM:
    """Test the full evaluate() flow with mocked LLM call."""

    def test_evaluate_returns_rlaif_reward(
        self, constitution_kernel, mock_contribution, mock_llm_judge_response
    ):
        trainer = ConstitutionalRLAIFTrainer()
        with patch.object(trainer, "_call_llm", return_value=mock_llm_judge_response):
            reward = trainer.evaluate("engine_16", mock_contribution, constitution_kernel)
        assert isinstance(reward, RLAIFReward)
        assert reward.engine_id == "engine_16"
        assert reward.source == "RLAIF_AI_JUDGE"
        assert 0.0 <= reward.reward <= 1.0
        assert reward.evaluation_hash != ""
        assert "CANONICAL_NOT_SCIENTIFIC_TRUTH" in reward.invariant_scores

    def test_evaluate_hash_is_deterministic(
        self, constitution_kernel, mock_contribution, mock_llm_judge_response
    ):
        trainer = ConstitutionalRLAIFTrainer()
        with patch.object(trainer, "_call_llm", return_value=mock_llm_judge_response):
            r1 = trainer.evaluate("engine_16", mock_contribution, constitution_kernel)
            r2 = trainer.evaluate("engine_16", mock_contribution, constitution_kernel)
        assert r1.evaluation_hash == r2.evaluation_hash

    def test_evaluate_truth_effect_is_none(
        self, constitution_kernel, mock_contribution, mock_llm_judge_response
    ):
        trainer = ConstitutionalRLAIFTrainer()
        with patch.object(trainer, "_call_llm", return_value=mock_llm_judge_response):
            reward = trainer.evaluate("engine_16", mock_contribution, constitution_kernel)
        assert reward.payload()["truth_effect"] == "NONE"
        assert reward.payload()["claim_ceiling"] == "RLAIF_REWARD_IS_PRIOR_NOT_TRUTH"


class TestBiographyUpdate:
    """Test biography update with RLAIF reward."""

    def test_update_biography_increments_observations(self, tmp_path, constitution_kernel):
        # Create a minimal biography store
        bio_path = tmp_path / "storage" / "engine_biographies.json"
        bio_path.parent.mkdir(parents=True)
        # Copy the real config
        import shutil
        shutil.copytree(ROOT / "config", tmp_path / "config")
        bio = EngineBiographyStore(tmp_path, persist=True)

        initial_obs = bio.data["engines"]["engine_16"]["observations"]

        trainer = ConstitutionalRLAIFTrainer()
        reward = RLAIFReward(
            engine_id="engine_16",
            invariant_scores={inv: 0.8 for inv in DEFAULT_INVARIANT_WEIGHTS},
            reward=0.8,
            confidence=0.9,
            source="RLAIF_AI_JUDGE",
            llm_response_text="test",
            evaluation_hash="abc",
        )
        trainer.update_biography(bio, "engine_16", reward)

        assert bio.data["engines"]["engine_16"]["observations"] == initial_obs + 1

    def test_update_biography_updates_mean_realized_gain(self, tmp_path, constitution_kernel):
        import shutil
        shutil.copytree(ROOT / "config", tmp_path / "config")
        bio = EngineBiographyStore(tmp_path, persist=True)

        trainer = ConstitutionalRLAIFTrainer()
        initial_mean = bio.data["engines"]["engine_16"]["mean_realized_gain"]

        reward = RLAIFReward(
            engine_id="engine_16",
            invariant_scores={},
            reward=0.9,
            confidence=0.9,
            source="RLAIF_AI_JUDGE",
            llm_response_text="test",
            evaluation_hash="abc",
        )
        trainer.update_biography(bio, "engine_16", reward)

        updated_mean = bio.data["engines"]["engine_16"]["mean_realized_gain"]
        # Mean should move toward 0.9 from initial 0.5
        assert updated_mean > initial_mean

    def test_update_biography_records_rlaif_source(self, tmp_path):
        import shutil
        shutil.copytree(ROOT / "config", tmp_path / "config")
        bio = EngineBiographyStore(tmp_path, persist=True)

        trainer = ConstitutionalRLAIFTrainer()
        reward = RLAIFReward(
            engine_id="engine_16",
            invariant_scores={inv: 0.7 for inv in DEFAULT_INVARIANT_WEIGHTS},
            reward=0.7,
            confidence=0.8,
            source="RLAIF_AI_JUDGE",
            llm_response_text="test",
            evaluation_hash="abc123",
        )
        trainer.update_biography(bio, "engine_16", reward)

        # Check source is recorded honestly
        last_run = bio.data["engines"]["engine_16"]["last_runs"][-1]
        assert last_run["source"] == "RLAIF_AI_JUDGE"
        assert last_run["observed_outcome"] == 0.7

        # Check rlaif_meta is updated
        rlaif_meta = bio.data["engines"]["engine_16"]["rlaif_meta"]
        assert rlaif_meta["total_evaluations"] == 1
        assert rlaif_meta["mean_reward"] == 0.7

    def test_update_biography_records_update_gate_honestly(self, tmp_path):
        import shutil
        shutil.copytree(ROOT / "config", tmp_path / "config")
        bio = EngineBiographyStore(tmp_path, persist=True)

        trainer = ConstitutionalRLAIFTrainer()
        reward = RLAIFReward(
            engine_id="engine_16",
            invariant_scores={},
            reward=0.5,
            confidence=0.5,
            source="RLAIF_AI_JUDGE",
            llm_response_text="test",
            evaluation_hash="abc",
        )
        trainer.update_biography(bio, "engine_16", reward)

        gate = bio.data["last_update_gate"]
        assert gate["source"] == "RLAIF_AI_JUDGE"
        assert gate["policy"] == "RLAIF_REWARD_IS_CONTEXTUAL_PRIOR_NOT_EXTERNAL_VERIFICATION"

    def test_update_biography_unknown_engine_raises(self, tmp_path):
        import shutil
        shutil.copytree(ROOT / "config", tmp_path / "config")
        bio = EngineBiographyStore(tmp_path, persist=True)

        trainer = ConstitutionalRLAIFTrainer()
        reward = RLAIFReward(
            engine_id="engine_99",
            invariant_scores={},
            reward=0.5,
            confidence=0.5,
            source="RLAIF_AI_JUDGE",
            llm_response_text="test",
            evaluation_hash="abc",
        )
        with pytest.raises(ValueError, match="UNKNOWN_ENGINE"):
            trainer.update_biography(bio, "engine_99", reward)


class TestHealthCheck:
    """Test bridge health check."""

    def test_health_check_returns_bool(self):
        trainer = ConstitutionalRLAIFTrainer()
        result = trainer.health_check()
        assert isinstance(result, bool)


class TestEvaluateRunContributions:
    """Test the convenience function for evaluating a run directory."""

    def test_evaluate_run_contributions_empty_dir(self, tmp_path, constitution_kernel):
        rewards = evaluate_run_contributions(tmp_path, constitution_kernel)
        assert rewards == {}

    def test_evaluate_run_contributions_with_mock(
        self, tmp_path, constitution_kernel, mock_contribution, mock_llm_judge_response
    ):
        # Create a fake run directory with engine contributions
        engines_dir = tmp_path / "engines"
        for eid in ["engine_01", "engine_16"]:
            engine_dir = engines_dir / eid
            engine_dir.mkdir(parents=True)
            (engine_dir / "CONTRIBUTION.json").write_text(
                json.dumps(mock_contribution)
            )

        trainer = ConstitutionalRLAIFTrainer()
        with patch.object(trainer, "_call_llm", return_value=mock_llm_judge_response):
            rewards = evaluate_run_contributions(
                tmp_path, constitution_kernel, trainer=trainer
            )

        assert len(rewards) == 2
        assert "engine_01" in rewards
        assert "engine_16" in rewards
        assert all(isinstance(r, RLAIFReward) for r in rewards.values())

        # Check reward files were saved
        for eid in ["engine_01", "engine_16"]:
            reward_path = engines_dir / eid / "RLAIF_REWARD.json"
            assert reward_path.is_file()
            saved = json.loads(reward_path.read_text())
            assert saved["source"] == "RLAIF_AI_JUDGE"
