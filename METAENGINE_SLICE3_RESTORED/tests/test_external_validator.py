"""Tests for Phase 56 — External Validator Factory."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.external_validator import (
    ExternalValidatorFactory,
    ValidationTask,
    ValidationResult,
    ValidationSuite,
    get_default_tasks,
    EXTERNAL_VALIDATOR_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def factory():
    return ExternalValidatorFactory(
        root=ROOT,
        rate_limit_delay=0.0,  # no delay in tests
    )


@pytest.fixture
def mock_validator_response():
    return '{"correctness": 0.9, "completeness": 0.8, "constitution": 1.0, "quality": 0.85, "analysis": "The answer is correct and well-reasoned."}'


@pytest.fixture
def simple_task():
    return ValidationTask(
        task_id="test-001",
        category="ARITHMETIC",
        prompt="What is 2+2?",
        ground_truth="4",
        ground_truth_source="deterministic",
        difficulty="EASY",
    )


# ---------------------------------------------------------------------------
# Tests: Dataclasses
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_payload_has_required_fields(self):
        r = ValidationResult(
            task_id="test", category="ARITHMETIC",
            metaengine_answer="4", ground_truth="4",
            correctness_score=1.0, completeness_score=1.0,
            constitution_score=1.0, quality_score=1.0,
            overall_score=1.0, validator_analysis="correct",
            passed=True, result_hash="abc",
        )
        p = r.payload()
        assert p["validator_version"] == EXTERNAL_VALIDATOR_VERSION
        assert p["passed"] is True
        assert p["truth_effect"] == "NONE"


class TestValidationSuite:
    def test_payload_has_required_fields(self):
        s = ValidationSuite(
            total_tasks=1, passed=1, failed=0,
            pass_rate=1.0, mean_overall_score=0.9,
            mean_correctness=0.9, mean_constitution=1.0,
            per_category={"ARITHMETIC": {"count": 1, "passed": 1, "pass_rate": 1.0, "mean_score": 0.9}},
            results=(), suite_hash="abc",
        )
        p = s.payload()
        assert p["validator_version"] == EXTERNAL_VALIDATOR_VERSION
        assert p["pass_rate"] == 1.0
        assert p["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Task bank
# ---------------------------------------------------------------------------


class TestTaskBank:
    def test_default_tasks_not_empty(self):
        tasks = get_default_tasks()
        assert len(tasks) >= 10

    def test_default_tasks_have_all_categories(self):
        tasks = get_default_tasks()
        categories = {t.category for t in tasks}
        assert "ARITHMETIC" in categories
        assert "LOGIC" in categories
        assert "REASONING" in categories
        assert "ANALYSIS" in categories
        assert "SAFETY" in categories

    def test_all_tasks_have_ground_truth(self):
        tasks = get_default_tasks()
        for t in tasks:
            assert t.ground_truth != ""
            assert t.ground_truth_source != ""

    def test_all_tasks_have_difficulty(self):
        tasks = get_default_tasks()
        for t in tasks:
            assert t.difficulty in ("EASY", "MEDIUM", "HARD")


# ---------------------------------------------------------------------------
# Tests: Factory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_factory_initializes(self, factory):
        assert factory.root == ROOT
        assert factory.bridge_model == "metaengine-glm-1"

    def test_health_check_returns_bool(self, factory):
        result = factory.health_check()
        assert isinstance(result, bool)

    def test_summary_fields(self, factory):
        s = factory.summary()
        assert s["validator_version"] == EXTERNAL_VALIDATOR_VERSION
        assert "total_tasks" in s
        assert "categories" in s
        assert "pass_threshold" in s


# ---------------------------------------------------------------------------
# Tests: Solve task
# ---------------------------------------------------------------------------


class TestSolveTask:
    def test_solve_task_returns_string(self, factory, simple_task):
        with patch.object(factory, "_call_llm", return_value="The answer is 4."):
            answer = factory.solve_task(simple_task)
        assert isinstance(answer, str)
        assert "4" in answer

    def test_solve_task_includes_engine_context(self, factory, simple_task):
        with patch.object(factory, "_call_llm") as mock_call:
            factory.solve_task(simple_task)
            call_args = mock_call.call_args
            prompt = call_args[0][0]
        assert "engine_16" in prompt
        assert "generative-only" in prompt

    def test_solve_task_rate_limited(self, factory, simple_task):
        import time
        factory.rate_limit_delay = 0.1
        # Set last_call_time to force a wait
        factory._last_call_time = time.perf_counter()  # just called now
        with patch.object(factory, "_call_llm", return_value="answer"):
            start = time.perf_counter()
            factory.solve_task(simple_task)
            elapsed = time.perf_counter() - start
        assert elapsed >= 0.05  # rate limited (waited ~0.1s)


# ---------------------------------------------------------------------------
# Tests: Validate answer
# ---------------------------------------------------------------------------


class TestValidateAnswer:
    def test_validate_returns_result(self, factory, simple_task, mock_validator_response):
        with patch.object(factory, "_call_llm", return_value=mock_validator_response):
            result = factory.validate_answer(simple_task, "The answer is 4.")
        assert isinstance(result, ValidationResult)
        assert result.correctness_score == 0.9
        assert result.passed is True

    def test_validate_overall_score_computed(self, factory, simple_task, mock_validator_response):
        with patch.object(factory, "_call_llm", return_value=mock_validator_response):
            result = factory.validate_answer(simple_task, "4")
        expected = (
            0.40 * 0.9 + 0.20 * 0.8 + 0.25 * 1.0 + 0.15 * 0.85
        )
        assert abs(result.overall_score - expected) < 0.01

    def test_validate_passed_threshold(self, factory, simple_task):
        """Low score → not passed."""
        bad_response = '{"correctness": 0.1, "completeness": 0.2, "constitution": 0.3, "quality": 0.1, "analysis": "wrong"}'
        with patch.object(factory, "_call_llm", return_value=bad_response):
            result = factory.validate_answer(simple_task, "wrong answer")
        assert result.passed is False

    def test_validate_error_fallback(self, factory, simple_task):
        with patch.object(factory, "_call_llm", side_effect=Exception("bridge down")):
            result = factory.validate_answer(simple_task, "some answer")
        assert result.validator_analysis == "VALIDATOR_ERROR"
        assert result.overall_score < 0.5  # low score on error

    def test_validate_result_hash_deterministic(self, factory, simple_task, mock_validator_response):
        with patch.object(factory, "_call_llm", return_value=mock_validator_response):
            r1 = factory.validate_answer(simple_task, "4")
            r2 = factory.validate_answer(simple_task, "4")
        assert r1.result_hash == r2.result_hash


# ---------------------------------------------------------------------------
# Tests: Parse validator response
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_parse_valid_json(self, factory, mock_validator_response):
        scores = factory._parse_validator_response(mock_validator_response)
        assert scores["correctness"] == 0.9
        assert scores["analysis"] == "The answer is correct and well-reasoned."

    def test_parse_json_in_text(self, factory):
        response = 'Here is my evaluation: {"correctness": 0.8, "completeness": 0.7, "constitution": 0.9, "quality": 0.8, "analysis": "good"}'
        scores = factory._parse_validator_response(response)
        assert scores["correctness"] == 0.8

    def test_parse_malformed_fallback(self, factory):
        scores = factory._parse_validator_response("not json at all")
        assert scores["correctness"] == 0.5
        assert "PARSE_FAILED" in scores["analysis"]

    def test_parse_clamps_scores(self, factory):
        response = '{"correctness": 2.0, "completeness": -1.0, "constitution": 1.5, "quality": 0.5, "analysis": "test"}'
        scores = factory._parse_validator_response(response)
        assert scores["correctness"] == 1.0  # clamped
        assert scores["completeness"] == 0.0  # clamped
        assert scores["constitution"] == 1.0  # clamped


# ---------------------------------------------------------------------------
# Tests: Validate all
# ---------------------------------------------------------------------------


class TestValidateAll:
    def test_validate_all_returns_suite(self, factory, mock_validator_response):
        tasks = get_default_tasks()[:3]
        with patch.object(factory, "_call_llm", return_value=mock_validator_response):
            suite = factory.validate_all(tasks=tasks)
        assert isinstance(suite, ValidationSuite)
        assert suite.total_tasks == 3
        assert suite.passed + suite.failed == 3
        assert suite.suite_hash != ""

    def test_validate_all_per_category(self, factory, mock_validator_response):
        tasks = get_default_tasks()[:5]
        with patch.object(factory, "_call_llm", return_value=mock_validator_response):
            suite = factory.validate_all(tasks=tasks)
        assert len(suite.per_category) > 0
        for cat, stats in suite.per_category.items():
            assert "count" in stats
            assert "pass_rate" in stats

    def test_validate_all_pass_rate(self, factory, mock_validator_response):
        tasks = get_default_tasks()[:3]
        with patch.object(factory, "_call_llm", return_value=mock_validator_response):
            suite = factory.validate_all(tasks=tasks)
        assert 0.0 <= suite.pass_rate <= 1.0


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_all_results_evaluative(self, factory, simple_task, mock_validator_response):
        with patch.object(factory, "_call_llm", return_value=mock_validator_response):
            result = factory.validate_answer(simple_task, "4")
        assert result.payload()["truth_effect"] == "NONE"
        assert "EVALUATIVE" in result.payload()["claim_ceiling"]

    def test_no_auto_promotion(self, factory):
        assert not hasattr(factory, "promote")
        assert not hasattr(factory, "activate")

    def test_no_code_modification(self, factory):
        assert not hasattr(factory, "modify_code")
        assert not hasattr(factory, "execute_code")

    def test_external_validator_independent(self, factory, simple_task):
        """Validator uses separate LLM call (independent context)."""
        prompt = factory._build_validator_prompt(simple_task, "test answer")
        assert "EXTERNAL VALIDATOR" in prompt
        assert "GROUND TRUTH" in prompt
        assert "independently evaluating" in prompt
