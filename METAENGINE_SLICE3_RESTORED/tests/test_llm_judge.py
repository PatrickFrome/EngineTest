"""Tests for Phase 51 — LLM-as-Judge Integration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.llm_judge import (
    LLMJudgeAdapter,
    JudgeResult,
    JUDGE_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter():
    return LLMJudgeAdapter(temperature=0.2)


@pytest.fixture
def mock_llm_response():
    """A well-formed LLM judge response."""
    return '{"score": 0.8, "confidence": 0.9}'


# ---------------------------------------------------------------------------
# Tests: JudgeResult
# ---------------------------------------------------------------------------


class TestJudgeResult:
    def test_payload_has_required_fields(self):
        r = JudgeResult(
            judge_type="RED_TEAM",
            target="NO_TRUTH_FROM_RANKING_OR_VOTING",
            score=0.8,
            violated=True,
            faithful=False,
            llm_response="test",
            confidence=0.9,
            result_hash="abc",
        )
        p = r.payload()
        assert p["judge_version"] == JUDGE_VERSION
        assert p["judge_type"] == "RED_TEAM"
        assert p["score"] == 0.8
        assert p["violated"] is True
        assert p["truth_effect"] == "NONE"

    def test_as_dict_includes_hash(self):
        r = JudgeResult(
            judge_type="FAITHFULNESS", target="engine_16",
            score=0.7, violated=False, faithful=True,
            llm_response="test", confidence=0.8,
            result_hash="abc123",
        )
        d = r.as_dict()
        assert d["result_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_thresholds(self, adapter):
        assert adapter.violation_threshold == 0.5
        assert adapter.faithfulness_threshold == 0.6

    def test_custom_thresholds(self):
        a = LLMJudgeAdapter(violation_threshold=0.7, faithfulness_threshold=0.8)
        assert a.violation_threshold == 0.7
        assert a.faithfulness_threshold == 0.8

    def test_low_temperature(self, adapter):
        assert adapter.temperature == 0.2  # low for consistent judging


# ---------------------------------------------------------------------------
# Tests: Score parsing
# ---------------------------------------------------------------------------


class TestScoreParsing:
    def test_parse_json_score(self, adapter, mock_llm_response):
        score, conf = adapter._parse_score(mock_llm_response)
        assert score == 0.8
        assert conf == 0.9

    def test_parse_score_with_text(self, adapter):
        response = 'The violation is severe. {"score": 0.9, "confidence": 0.8} Done.'
        score, conf = adapter._parse_score(response)
        assert score == 0.9
        assert conf == 0.8

    def test_parse_score_pattern(self, adapter):
        response = "Score: 0.65"
        score, conf = adapter._parse_score(response)
        assert score == 0.65
        assert conf == 0.5

    def test_parse_score_clamped(self, adapter):
        response = '{"score": 1.5, "confidence": 2.0}'
        score, conf = adapter._parse_score(response)
        assert score == 1.0  # clamped
        assert conf == 1.0  # clamped

    def test_parse_malformed_fallback(self, adapter):
        score, conf = adapter._parse_score("this is not JSON at all")
        assert score == 0.5  # fallback
        assert conf == 0.1   # low confidence


# ---------------------------------------------------------------------------
# Tests: Red team judge
# ---------------------------------------------------------------------------


class TestRedTeamJudge:
    def test_make_red_team_judge_returns_callable(self, adapter):
        judge = adapter.make_red_team_judge_fn()
        assert callable(judge)

    def test_red_team_judge_with_mock_llm(self, adapter, mock_llm_response):
        with patch.object(adapter, "_call_llm", return_value=mock_llm_response):
            judge = adapter.make_red_team_judge_fn()
            violated, severity = judge("adversarial", "defender output", "NO_TRUTH_FROM_RANKING_OR_VOTING")
        assert violated is True  # score=0.8 > threshold=0.5
        assert severity == 0.8

    def test_red_team_judge_safe_output(self, adapter):
        """Safe defender output → low score → not violated."""
        with patch.object(adapter, "_call_llm", return_value='{"score": 0.1, "confidence": 0.9}'):
            judge = adapter.make_red_team_judge_fn()
            violated, severity = judge("attack", "safe output", "PRESERVE_ABSTENTION")
        assert violated is False  # 0.1 < 0.5
        assert severity == 0.1

    def test_red_team_judge_error_fallback(self, adapter):
        """On error, should return safe default (no violation)."""
        with patch.object(adapter, "_call_llm", side_effect=Exception("bridge down")):
            judge = adapter.make_red_team_judge_fn()
            violated, severity = judge("attack", "output", "invariant")
        assert violated is False  # safe fallback
        assert severity == 0.0

    def test_red_team_prompt_contains_invariant(self, adapter):
        prompt = adapter._build_red_team_prompt("input", "output", "NO_TRUTH_FROM_RANKING_OR_VOTING")
        assert "NO_TRUTH_FROM_RANKING_OR_VOTING" in prompt
        assert "input" in prompt
        assert "output" in prompt


# ---------------------------------------------------------------------------
# Tests: Faithfulness judge
# ---------------------------------------------------------------------------


class TestFaithfulnessJudge:
    def test_make_faithfulness_judge_returns_callable(self, adapter):
        judge = adapter.make_faithfulness_judge_fn()
        assert callable(judge)

    def test_faithfulness_judge_with_mock_llm(self, adapter):
        with patch.object(adapter, "_call_llm", return_value='{"score": 0.8, "confidence": 0.9}'):
            judge = adapter.make_faithfulness_judge_fn()
            faithful, score = judge("reasoning text", "summary text", "engine_16")
        assert faithful is True  # 0.8 > threshold=0.6
        assert score == 0.8

    def test_faithfulness_judge_unfaithful(self, adapter):
        with patch.object(adapter, "_call_llm", return_value='{"score": 0.3, "confidence": 0.8}'):
            judge = adapter.make_faithfulness_judge_fn()
            faithful, score = judge("reasoning", "contradictory summary", "engine_16")
        assert faithful is False  # 0.3 < 0.6
        assert score == 0.3

    def test_faithfulness_judge_error_fallback(self, adapter):
        """On error, should return safe default (assume faithful)."""
        with patch.object(adapter, "_call_llm", side_effect=Exception("timeout")):
            judge = adapter.make_faithfulness_judge_fn()
            faithful, score = judge("reasoning", "summary", "engine_16")
        assert faithful is True  # safe fallback
        assert score == 0.5

    def test_faithfulness_prompt_contains_engine(self, adapter):
        prompt = adapter._build_faithfulness_prompt("reasoning", "summary", "engine_16")
        assert "engine_16" in prompt
        assert "reasoning" in prompt
        assert "summary" in prompt


# ---------------------------------------------------------------------------
# Tests: Full evaluation
# ---------------------------------------------------------------------------


class TestFullEvaluation:
    def test_evaluate_red_team_returns_judge_result(self, adapter, mock_llm_response):
        with patch.object(adapter, "_call_llm", return_value=mock_llm_response):
            result = adapter.evaluate_red_team("attack", "output", "NO_TRUTH_FROM_RANKING_OR_VOTING")
        assert isinstance(result, JudgeResult)
        assert result.judge_type == "RED_TEAM"
        assert result.violated is True
        assert result.result_hash != ""

    def test_evaluate_faithfulness_returns_judge_result(self, adapter):
        with patch.object(adapter, "_call_llm", return_value='{"score": 0.7, "confidence": 0.8}'):
            result = adapter.evaluate_faithfulness("reasoning", "summary", "engine_16")
        assert isinstance(result, JudgeResult)
        assert result.judge_type == "FAITHFULNESS"
        assert result.faithful is True
        assert result.result_hash != ""

    def test_evaluate_red_team_deterministic(self, adapter, mock_llm_response):
        with patch.object(adapter, "_call_llm", return_value=mock_llm_response):
            r1 = adapter.evaluate_red_team("attack", "output", "invariant")
            r2 = adapter.evaluate_red_team("attack", "output", "invariant")
        assert r1.result_hash == r2.result_hash


# ---------------------------------------------------------------------------
# Tests: Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_check_returns_bool(self, adapter):
        result = adapter.health_check()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_fields(self, adapter):
        s = adapter.summary()
        assert s["judge_version"] == JUDGE_VERSION
        assert "violation_threshold" in s
        assert "faithfulness_threshold" in s
        assert "bridge_healthy" in s
        assert s["truth_effect"] == "NONE"

    def test_summary_constitution_compliance(self, adapter):
        s = adapter.summary()
        assert s["constitution_compliance"]["evaluative_not_truth"] is True
        assert s["constitution_compliance"]["no_auto_promotion"] is True
        assert s["constitution_compliance"]["safe_fallback"] is True


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_safe_fallback_on_red_team_error(self, adapter):
        """Red team judge returns False (no violation) on error — safe fallback."""
        with patch.object(adapter, "_call_llm", side_effect=Exception("error")):
            judge = adapter.make_red_team_judge_fn()
            violated, _ = judge("attack", "output", "invariant")
        assert violated is False  # safe: don't report false violations

    def test_safe_fallback_on_faithfulness_error(self, adapter):
        """Faithfulness judge returns True (faithful) on error — safe fallback."""
        with patch.object(adapter, "_call_llm", side_effect=Exception("error")):
            judge = adapter.make_faithfulness_judge_fn()
            faithful, _ = judge("reasoning", "summary", "engine_16")
        assert faithful is True  # safe: don't report false unfaithfulness

    def test_no_code_modification(self, adapter):
        assert not hasattr(adapter, "modify_code")
        assert not hasattr(adapter, "execute_code")

    def test_all_results_evaluative(self, adapter, mock_llm_response):
        with patch.object(adapter, "_call_llm", return_value=mock_llm_response):
            result = adapter.evaluate_red_team("attack", "output", "invariant")
        assert result.payload()["truth_effect"] == "NONE"
        assert "EVALUATIVE" in result.payload()["claim_ceiling"]
