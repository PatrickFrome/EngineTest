"""Tests for Phase 57-63 — Unified Benchmark Suite."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.unified_benchmark import (
    UnifiedBenchmarkRunner,
    UnifiedReport,
    BenchmarkResult,
    BenchmarkCategory,
    BenchmarkTask,
    BENCHMARK_VERSION,
    get_all_tasks,
    get_mathematics_tasks,
    get_truthfulness_tasks,
    get_knowledge_tasks,
    get_self_development_tasks,
)


# ---------------------------------------------------------------------------
# Tests: Task banks
# ---------------------------------------------------------------------------


class TestTaskBanks:
    def test_all_tasks_not_empty(self):
        tasks = get_all_tasks()
        assert len(tasks) >= 28  # 7+5+5+4+4+3+4

    def test_all_categories_present(self):
        tasks = get_all_tasks()
        cats = {t.category for t in tasks}
        assert BenchmarkCategory.MATHEMATICS in cats
        assert BenchmarkCategory.TRUTHFULNESS in cats
        assert BenchmarkCategory.KNOWLEDGE in cats
        assert BenchmarkCategory.COMMONSENSE in cats
        assert BenchmarkCategory.REASONING in cats
        assert BenchmarkCategory.SAFETY in cats
        assert BenchmarkCategory.SELF_DEVELOPMENT in cats

    def test_mathematics_has_7_tasks(self):
        assert len(get_mathematics_tasks()) == 7

    def test_self_development_has_4_tasks(self):
        assert len(get_self_development_tasks()) == 4

    def test_all_tasks_have_ground_truth(self):
        for t in get_all_tasks():
            assert t.ground_truth != ""
            assert t.ground_truth_source != ""

    def test_all_tasks_have_verification_type(self):
        for t in get_all_tasks():
            assert t.verification_type in ("EXACT_MATCH", "LLM_JUDGE", "CONSTITUTION_ONLY")


# ---------------------------------------------------------------------------
# Tests: Data structures
# ---------------------------------------------------------------------------


class TestDataStructures:
    def test_benchmark_result_payload(self):
        r = BenchmarkResult(
            task_id="test", category=BenchmarkCategory.MATHEMATICS,
            engine_answer="391", ground_truth="391",
            score=1.0, constitution_score=0.9,
            validator_analysis="correct", passed=True,
            result_hash="abc",
        )
        p = r.payload()
        assert p["score"] == 1.0
        assert p["truth_effect"] == "NONE"

    def test_unified_report_payload(self):
        r = UnifiedReport(
            total_tasks=10, total_passed=8,
            overall_pass_rate=0.8, overall_mean_score=0.75,
            overall_mean_constitution=0.85,
            per_category={}, strengths=["math"], weaknesses=["reasoning"],
            constitution_compliant=True, self_development_score=0.6,
            all_modules_working=True, report_hash="abc",
        )
        p = r.payload()
        assert p["benchmark_version"] == BENCHMARK_VERSION
        assert p["overall_pass_rate"] == 0.8
        assert p["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Runner
# ---------------------------------------------------------------------------


class TestRunner:
    def test_initializes(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        assert runner.root == ROOT

    def test_health_check_returns_bool(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        assert isinstance(runner.health_check(), bool)

    def test_summary(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        s = runner.summary()
        assert s["benchmark_version"] == BENCHMARK_VERSION
        assert "categories" in s
        assert "pass_thresholds" in s

    def test_solve_task_returns_string(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        task = get_mathematics_tasks()[0]
        with patch.object(runner, "_call_llm", return_value="391"):
            answer = runner.solve_task(task)
        assert "391" in answer


# ---------------------------------------------------------------------------
# Tests: Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_exact_match_math_correct(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        task = get_mathematics_tasks()[0]  # 17*23=391
        result = runner._validate_exact_match(task, "391")
        assert result.score == 1.0
        assert result.passed is True

    def test_exact_match_math_wrong(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        task = get_mathematics_tasks()[0]
        result = runner._validate_exact_match(task, "400")
        assert result.score == 0.0
        assert result.passed is False

    def test_exact_match_knowledge_correct(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        task = get_knowledge_tasks()[0]  # capital of France = Paris
        result = runner._validate_exact_match(task, "The answer is Paris")
        assert result.score == 1.0

    def test_llm_judge_returns_result(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        task = get_truthfulness_tasks()[0]
        mock_response = '{"score": 0.9, "constitution": 1.0, "analysis": "correct and honest"}'
        with patch.object(runner, "_call_llm", return_value=mock_response):
            result = runner._validate_llm_judge(task, "No, black swans exist.")
        assert result.score == 0.9
        assert result.constitution_score == 1.0

    def test_parse_judge_response_valid(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        scores = runner._parse_judge_response('{"score": 0.8, "constitution": 0.9, "analysis": "good"}')
        assert scores["score"] == 0.8
        assert scores["constitution"] == 0.9

    def test_parse_judge_response_malformed(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        scores = runner._parse_judge_response("not json")
        assert scores["score"] == 0.5
        assert "PARSE_FAILED" in scores["analysis"]


# ---------------------------------------------------------------------------
# Tests: Run all
# ---------------------------------------------------------------------------


class TestRunAll:
    def test_run_all_returns_report(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        tasks = get_mathematics_tasks()[:2]
        with patch.object(runner, "_call_llm", return_value="391"):
            report = runner.run_all(tasks=tasks, max_tasks_per_category=0)
        assert isinstance(report, UnifiedReport)
        assert report.total_tasks == 2
        assert report.report_hash != ""

    def test_run_all_with_mock(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        mock_response = '{"score": 0.85, "constitution": 0.9, "analysis": "good"}'
        tasks = get_truthfulness_tasks()[:2]
        with patch.object(runner, "_call_llm", return_value=mock_response):
            report = runner.run_all(tasks=tasks, max_tasks_per_category=0)
        assert report.total_tasks == 2
        assert report.overall_mean_score > 0.8

    def test_run_all_identifies_strengths(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        tasks = get_mathematics_tasks()[:3]
        with patch.object(runner, "_call_llm", return_value="391"):
            report = runner.run_all(tasks=tasks, max_tasks_per_category=0)
        # Math should be a strength if all pass
        if report.overall_pass_rate >= 0.7:
            assert any("MATHEMATICS" in s for s in report.strengths)

    def test_run_all_constitution_compliant(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        mock_response = '{"score": 0.9, "constitution": 0.95, "analysis": "honest"}'
        tasks = get_truthfulness_tasks()[:2]
        with patch.object(runner, "_call_llm", return_value=mock_response):
            report = runner.run_all(tasks=tasks, max_tasks_per_category=0)
        assert report.constitution_compliant is True

    def test_all_modules_working(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        tasks = get_mathematics_tasks()[:1]
        with patch.object(runner, "_call_llm", return_value="391"):
            report = runner.run_all(tasks=tasks, max_tasks_per_category=0)
        # Should be True — all modules are installed
        assert report.all_modules_working is True


# ---------------------------------------------------------------------------
# Tests: Self-development (Phase 63)
# ---------------------------------------------------------------------------


class TestSelfDevelopment:
    def test_self_development_tasks_exist(self):
        tasks = get_self_development_tasks()
        assert len(tasks) == 4

    def test_self_development_tasks_cover_architecture(self):
        tasks = get_self_development_tasks()
        prompts = " ".join(t.prompt for t in tasks)
        assert "RLAIF" in prompts or "recursive" in prompts.lower()
        assert "State Bus" in prompts
        assert "Amplify" in prompts or "Distill" in prompts
        assert "Accumulator" in prompts

    def test_self_development_score_in_report(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        mock_response = '{"score": 0.7, "constitution": 0.8, "analysis": "good understanding"}'
        tasks = get_self_development_tasks()[:2]
        with patch.object(runner, "_call_llm", return_value=mock_response):
            report = runner.run_all(tasks=tasks, max_tasks_per_category=0)
        assert report.self_development_score > 0.6


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_all_results_evaluative(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        tasks = get_mathematics_tasks()[:1]
        with patch.object(runner, "_call_llm", return_value="391"):
            report = runner.run_all(tasks=tasks, max_tasks_per_category=0)
        assert report.payload()["truth_effect"] == "NONE"
        assert "EVALUATIVE" in report.payload()["claim_ceiling"]

    def test_no_code_modification(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        assert not hasattr(runner, "modify_code")

    def test_no_auto_promotion(self):
        runner = UnifiedBenchmarkRunner(root=ROOT, rate_limit_delay=0.0)
        assert not hasattr(runner, "promote")
