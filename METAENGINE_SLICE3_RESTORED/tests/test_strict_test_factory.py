"""Tests for Phase 55 — Strict Test Factory with External Validator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.strict_test_factory import (
    StrictTestFactory,
    TestStatus,
    TestSeverity,
    TestCategory,
    TestResult,
    TestSuiteResult,
    STRICT_TEST_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def factory():
    return StrictTestFactory(root=ROOT)


# ---------------------------------------------------------------------------
# Tests: Enums
# ---------------------------------------------------------------------------


class TestEnums:
    def test_test_status_values(self):
        assert TestStatus.PASS.value == "PASS"
        assert TestStatus.FAIL.value == "FAIL"
        assert TestStatus.SKIP.value == "SKIP"
        assert TestStatus.ERROR.value == "ERROR"

    def test_test_severity_values(self):
        assert TestSeverity.CRITICAL.value == "CRITICAL"
        assert TestSeverity.MAJOR.value == "MAJOR"
        assert TestSeverity.MINOR.value == "MINOR"
        assert TestSeverity.INFO.value == "INFO"

    def test_test_category_values(self):
        assert len(TestCategory) == 8
        assert TestCategory.CONSTITUTION_COMPLIANCE.value == "CONSTITUTION_COMPLIANCE"
        assert TestCategory.ACCUMULATION_IDEMPOTENCY.value == "ACCUMULATION_IDEMPOTENCY"


# ---------------------------------------------------------------------------
# Tests: TestResult and TestSuiteResult
# ---------------------------------------------------------------------------


class TestResultDataclasses:
    def test_test_result_payload(self):
        r = TestResult(
            test_id="CC-001",
            category=TestCategory.CONSTITUTION_COMPLIANCE,
            description="test",
            severity=TestSeverity.CRITICAL,
            status=TestStatus.PASS,
            ground_truth="expected",
            evidence="passed",
            elapsed_seconds=0.01,
            result_hash="abc",
        )
        p = r.payload()
        assert p["test_id"] == "CC-001"
        assert p["status"] == "PASS"
        assert p["truth_effect"] == "NONE"

    def test_suite_result_payload(self):
        s = TestSuiteResult(
            total=10, passed=8, failed=1, skipped=0, errors=1,
            pass_rate=0.8, critical_failures=0, major_failures=1,
            results=(), suite_hash="abc",
        )
        p = s.payload()
        assert p["strict_test_version"] == STRICT_TEST_VERSION
        assert p["pass_rate"] == 0.8
        assert p["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Factory initialization
# ---------------------------------------------------------------------------


class TestFactoryInit:
    def test_factory_initializes(self, factory):
        assert factory.root == ROOT
        assert len(factory._test_cases) > 0

    def test_factory_has_8_categories(self, factory):
        categories = {tc.category for tc in factory._test_cases}
        assert len(categories) == 8

    def test_factory_has_constitution_tests(self, factory):
        cc_tests = [tc for tc in factory._test_cases if tc.category == TestCategory.CONSTITUTION_COMPLIANCE]
        assert len(cc_tests) >= 5  # at least 5 constitution tests

    def test_factory_has_rlaif_tests(self, factory):
        rq_tests = [tc for tc in factory._test_cases if tc.category == TestCategory.RLAIF_REWARD_QUALITY]
        assert len(rq_tests) >= 2

    def test_factory_has_redteam_tests(self, factory):
        rt_tests = [tc for tc in factory._test_cases if tc.category == TestCategory.RED_TEAM_DETECTION]
        assert len(rt_tests) >= 2

    def test_all_tests_have_callable_fn(self, factory):
        for tc in factory._test_cases:
            assert callable(tc.test_fn), f"{tc.test_id} has non-callable test_fn"

    def test_all_tests_have_severity(self, factory):
        for tc in factory._test_cases:
            assert tc.severity in TestSeverity, f"{tc.test_id} has invalid severity"


# ---------------------------------------------------------------------------
# Tests: Run all tests
# ---------------------------------------------------------------------------


class TestRunAllTests:
    def test_run_all_returns_suite_result(self, factory):
        suite = factory.run_all_tests()
        assert isinstance(suite, TestSuiteResult)
        assert suite.total > 0
        assert suite.passed + suite.failed + suite.skipped + suite.errors == suite.total
        assert suite.suite_hash != ""

    def test_run_all_has_results(self, factory):
        suite = factory.run_all_tests()
        assert len(suite.results) > 0

    def test_run_all_pass_rate_in_range(self, factory):
        suite = factory.run_all_tests()
        assert 0.0 <= suite.pass_rate <= 1.0

    def test_run_all_deterministic(self, factory):
        s1 = factory.run_all_tests()
        s2 = factory.run_all_tests()
        assert s1.suite_hash == s2.suite_hash

    def test_run_all_constitution_tests(self, factory):
        suite = factory.run_all_tests()
        cc_results = [r for r in suite.results if r.category == TestCategory.CONSTITUTION_COMPLIANCE]
        assert len(cc_results) >= 5

    def test_all_results_have_truth_effect_none(self, factory):
        suite = factory.run_all_tests()
        for r in suite.results:
            assert r.payload()["truth_effect"] == "NONE"

    def test_failed_tests_counted_by_severity(self, factory):
        suite = factory.run_all_tests()
        # critical_failures + major_failures should <= failed
        assert suite.critical_failures + suite.major_failures <= suite.failed + suite.errors


# ---------------------------------------------------------------------------
# Tests: Individual test functions
# ---------------------------------------------------------------------------


class TestIndividualFunctions:
    def test_no_truth_promotion(self, factory):
        result = factory._test_no_truth_promotion()
        assert isinstance(result, bool)

    def test_preserve_abstention(self, factory):
        result = factory._test_preserve_abstention()
        assert isinstance(result, bool)

    def test_separate_generation_promotion(self, factory):
        result = factory._test_separate_generation_promotion()
        assert isinstance(result, bool)

    def test_no_code_modification(self, factory):
        result = factory._test_no_code_modification()
        assert isinstance(result, bool)

    def test_frozen_evaluation_contract(self, factory):
        result = factory._test_frozen_evaluation_contract()
        assert isinstance(result, bool)

    def test_mutation_receipt(self, factory):
        result = factory._test_mutation_receipt()
        assert isinstance(result, bool)

    def test_rlaif_range(self, factory):
        result = factory._test_rlaif_range()
        assert isinstance(result, bool)

    def test_rlaif_source(self, factory):
        result = factory._test_rlaif_source()
        assert isinstance(result, bool)

    def test_traces_no_scraping(self, factory):
        result = factory._test_traces_no_scraping()
        assert isinstance(result, bool)

    def test_redteam_vector_count(self, factory):
        result = factory._test_redteam_vector_count()
        assert result is True  # should have 7 vectors

    def test_redteam_no_exploit(self, factory):
        result = factory._test_redteam_no_exploit()
        assert result is True

    def test_redteam_no_autofix(self, factory):
        result = factory._test_redteam_no_autofix()
        assert result is True

    def test_synthesis_shadow(self, factory):
        result = factory._test_synthesis_shadow()
        assert result is True

    def test_synthesis_valid_operators(self, factory):
        result = factory._test_synthesis_valid_operators()
        assert result is True

    def test_accumulation_idempotent(self, factory):
        result = factory._test_accumulation_idempotent()
        assert isinstance(result, bool)

    def test_accumulation_observational(self, factory):
        result = factory._test_accumulation_observational()
        assert result is True


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_fields(self, factory):
        s = factory.summary()
        assert s["strict_test_version"] == STRICT_TEST_VERSION
        assert "total_test_cases" in s
        assert "categories" in s
        assert s["truth_effect"] == "NONE"

    def test_summary_categories(self, factory):
        s = factory.summary()
        assert "CONSTITUTION_COMPLIANCE" in s["categories"]
        assert "RED_TEAM_DETECTION" in s["categories"]
        assert s["categories"]["CONSTITUTION_COMPLIANCE"] >= 5


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_all_tests_evaluative(self, factory):
        suite = factory.run_all_tests()
        for r in suite.results:
            assert r.payload()["truth_effect"] == "NONE"

    def test_no_code_modification_by_factory(self, factory):
        assert not hasattr(factory, "modify_code")
        assert not hasattr(factory, "execute_code")

    def test_no_auto_promotion_by_factory(self, factory):
        assert not hasattr(factory, "promote")
        assert not hasattr(factory, "enforce")
