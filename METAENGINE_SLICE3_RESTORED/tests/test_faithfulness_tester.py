"""Tests for Phase 46 — Summarizer Faithfulness Testing."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.faithfulness_tester import (
    SummarizerFaithfulnessTester,
    FaithfulnessResult,
    FaithfulnessLevel,
    FAITHFULNESS_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tester():
    return SummarizerFaithfulnessTester()


@pytest.fixture
def faithful_contribution():
    """Contribution where summary faithfully represents reasoning."""
    reasoning = (
        "### Analysis\n"
        "The input text presents a claim about correlation and causation. "
        "Engine_16 analyzed the argument and found it commits the fallacy of "
        "affirming the consequent. The sample size of 1000 does not address "
        "confounders like hot weather affecting both ice cream sales and drowning."
    )
    # Summary uses same key terms
    summary = (
        "Engine_16 found the argument commits affirming the consequent. "
        "Sample size 1000 does not address confounders."
    )
    return {"reasoning": reasoning, "summary": summary, "engine_id": "engine_16", "run_id": "run_001"}


@pytest.fixture
def unfaithful_contribution():
    """Contribution where summary contradicts reasoning."""
    reasoning = (
        "The analysis shows that the argument is NOT valid because correlation "
        "does not imply causation. The sample size is irrelevant to the "
        "confounding variable problem."
    )
    # Summary says opposite
    summary = (
        "The argument is valid and correct. Correlation definitely implies "
        "causation when sample size is large enough."
    )
    return {"reasoning": reasoning, "summary": summary, "engine_id": "engine_05", "run_id": "run_002"}


@pytest.fixture
def hallucination_contribution():
    """Contribution where summary contains claims not in reasoning."""
    reasoning = (
        "Engine_16 analyzed the text about statistical methodology. "
        "The argument contains a logical error in its premises."
    )
    # Summary introduces new claims (hallucination)
    summary = (
        "Engine_16 found 42 errors and proved the argument wrong using "
        "Bayesian analysis with 95% confidence interval."
    )
    return {"reasoning": reasoning, "summary": summary, "engine_id": "engine_16", "run_id": "run_003"}


# ---------------------------------------------------------------------------
# Tests: FaithfulnessLevel enum
# ---------------------------------------------------------------------------


class TestFaithfulnessLevel:
    def test_all_values(self):
        assert FaithfulnessLevel.FAITHFUL.value == "FAITHFUL"
        assert FaithfulnessLevel.PARTIALLY_FAITHFUL.value == "PARTIALLY_FAITHFUL"
        assert FaithfulnessLevel.UNFAITHFUL.value == "UNFAITHFUL"
        assert FaithfulnessLevel.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"

    def test_count(self):
        assert len(FaithfulnessLevel) == 4


# ---------------------------------------------------------------------------
# Tests: FaithfulnessResult
# ---------------------------------------------------------------------------


class TestFaithfulnessResult:
    def test_payload_has_required_fields(self):
        r = FaithfulnessResult(
            engine_id="engine_16", run_id="run_1",
            reasoning_length=100, summary_length=50,
            entailment_score=0.8, consistency_score=0.9,
            coverage_score=0.7, hallucination_score=0.1,
            overall_faithfulness=0.85,
            level=FaithfulnessLevel.FAITHFUL,
            mismatches=(),
            result_hash="abc",
        )
        p = r.payload()
        assert p["faithfulness_version"] == FAITHFULNESS_VERSION
        assert p["level"] == "FAITHFUL"
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "FAITHFULNESS_IS_EVALUATIVE_NOT_TRUTH"

    def test_as_dict_includes_hash(self):
        r = FaithfulnessResult(
            engine_id="e", run_id="r", reasoning_length=1, summary_length=1,
            entailment_score=0.5, consistency_score=0.5, coverage_score=0.5,
            hallucination_score=0.5, overall_faithfulness=0.5,
            level=FaithfulnessLevel.PARTIALLY_FAITHFUL,
            mismatches=(), result_hash="abc123",
        )
        d = r.as_dict()
        assert d["result_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_weights(self, tester):
        assert "entailment" in tester.weights
        assert "consistency" in tester.weights
        assert "coverage" in tester.weights
        assert "hallucination" in tester.weights

    def test_weight_validation(self):
        with pytest.raises(ValueError, match="WEIGHTS_MUST_SUM_TO_1"):
            SummarizerFaithfulnessTester(weights={"entailment": 0.5, "consistency": 0.5, "coverage": 0.5, "hallucination": 0.5})

    def test_custom_weights_accepted(self):
        t = SummarizerFaithfulnessTester(weights={"entailment": 0.25, "consistency": 0.25, "coverage": 0.25, "hallucination": 0.25})
        assert t.weights["entailment"] == 0.25


# ---------------------------------------------------------------------------
# Tests: Text preprocessing
# ---------------------------------------------------------------------------


class TestTextPreprocessing:
    def test_tokenize_removes_stopwords(self, tester):
        tokens = tester._tokenize("The quick brown fox jumps over the lazy dog")
        assert "the" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens

    def test_tokenize_lowercase(self, tester):
        tokens = tester._tokenize("Engine_16 FOUND something")
        assert "engine_16" in tokens
        assert "found" in tokens

    def test_tokenize_empty(self, tester):
        assert tester._tokenize("") == set()

    def test_extract_key_phrases_acronyms(self, tester):
        phrases = tester._extract_key_phrases("The API and HTML are used")
        assert "api" in phrases
        assert "html" in phrases

    def test_extract_key_phrases_numbers(self, tester):
        phrases = tester._extract_key_phrases("There are 42 items and 100 samples")
        assert "42" in phrases
        assert "100" in phrases

    def test_extract_key_phrases_engine_refs(self, tester):
        phrases = tester._extract_key_phrases("engine_16 and engine_01")
        assert "engine_16" in phrases
        assert "engine_01" in phrases


# ---------------------------------------------------------------------------
# Tests: Metric computation
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_entailment_full_overlap(self, tester):
        reasoning = "The argument is valid and correct"
        summary = "The argument is valid"
        score = tester._compute_entailment(reasoning, summary)
        assert score == 1.0  # all summary tokens in reasoning

    def test_entailment_no_overlap(self, tester):
        reasoning = "The cat sat on the mat"
        summary = "Dogs run in parks"
        score = tester._compute_entailment(reasoning, summary)
        assert score < 0.2  # minimal overlap

    def test_entailment_empty_summary(self, tester):
        score = tester._compute_entailment("reasoning", "")
        assert score == 0.0

    def test_consistency_no_contradictions(self, tester):
        reasoning = "The argument is valid and supported by evidence"
        summary = "The argument is valid"
        score, mismatches = tester._compute_consistency(reasoning, summary)
        assert score >= 0.9
        assert len(mismatches) == 0

    def test_consistency_with_contradiction(self, tester):
        reasoning = "The argument is not valid"
        summary = "The argument is valid"
        score, mismatches = tester._compute_consistency(reasoning, summary)
        assert score < 1.0
        assert len(mismatches) > 0

    def test_coverage_full(self, tester):
        reasoning = "engine_16 found 42 errors"
        summary = "engine_16 found 42"
        score = tester._compute_coverage(reasoning, summary)
        assert score == 1.0  # all key phrases covered

    def test_coverage_partial(self, tester):
        reasoning = "engine_16 found 42 errors and 100 warnings"
        summary = "engine_16 found something"
        score = tester._compute_coverage(reasoning, summary)
        assert 0.0 < score < 1.0

    def test_hallucination_none(self, tester):
        reasoning = "engine_16 analyzed the text"
        summary = "engine_16 analyzed"
        score = tester._compute_hallucination(reasoning, summary)
        assert score == 0.0  # all summary tokens in reasoning

    def test_hallucination_present(self, tester):
        reasoning = "engine_16 analyzed the text"
        summary = "engine_16 found 42 Bayesian errors"
        score = tester._compute_hallucination(reasoning, summary)
        assert score > 0.3  # significant hallucination


# ---------------------------------------------------------------------------
# Tests: Overall faithfulness
# ---------------------------------------------------------------------------


class TestOverallFaithfulness:
    def test_compute_overall(self, tester):
        overall = tester._compute_overall(
            entailment=0.8, consistency=0.9, coverage=0.7, hallucination=0.1
        )
        assert 0.7 < overall < 0.9

    def test_perfect_scores(self, tester):
        overall = tester._compute_overall(
            entailment=1.0, consistency=1.0, coverage=1.0, hallucination=0.0
        )
        assert overall == 1.0

    def test_worst_scores(self, tester):
        overall = tester._compute_overall(
            entailment=0.0, consistency=0.0, coverage=0.0, hallucination=1.0
        )
        assert overall == 0.0

    def test_determine_level_faithful(self, tester):
        assert tester._determine_level(0.80) == FaithfulnessLevel.FAITHFUL

    def test_determine_level_partial(self, tester):
        assert tester._determine_level(0.60) == FaithfulnessLevel.PARTIALLY_FAITHFUL

    def test_determine_level_unfaithful(self, tester):
        assert tester._determine_level(0.30) == FaithfulnessLevel.UNFAITHFUL


# ---------------------------------------------------------------------------
# Tests: Main test method
# ---------------------------------------------------------------------------


class TestMainTest:
    def test_returns_result(self, tester, faithful_contribution):
        result = tester.test_faithfulness(**faithful_contribution)
        assert isinstance(result, FaithfulnessResult)
        assert result.engine_id == "engine_16"
        assert result.result_hash != ""

    def test_faithful_contribution_gets_high_score(self, tester, faithful_contribution):
        result = tester.test_faithfulness(**faithful_contribution)
        assert result.overall_faithfulness > 0.5
        assert result.level in [FaithfulnessLevel.FAITHFUL, FaithfulnessLevel.PARTIALLY_FAITHFUL]

    def test_unfaithful_contribution_gets_low_score(self, tester, unfaithful_contribution):
        result = tester.test_faithfulness(**unfaithful_contribution)
        assert result.overall_faithfulness < result.entailment_score + 0.3  # not great
        assert len(result.mismatches) > 0  # detected contradictions

    def test_hallucination_detected(self, tester, hallucination_contribution):
        result = tester.test_faithfulness(**hallucination_contribution)
        assert result.hallucination_score > 0.3  # significant hallucination

    def test_insufficient_data_short_reasoning(self, tester):
        result = tester.test_faithfulness(
            reasoning="short", summary="summary",
            engine_id="engine_01", run_id="run_1",
        )
        assert result.level == FaithfulnessLevel.INSUFFICIENT_DATA

    def test_insufficient_data_short_summary(self, tester):
        result = tester.test_faithfulness(
            reasoning="x" * 100, summary="x",
            engine_id="engine_01", run_id="run_1",
        )
        assert result.level == FaithfulnessLevel.INSUFFICIENT_DATA

    def test_result_deterministic(self, tester, faithful_contribution):
        r1 = tester.test_faithfulness(**faithful_contribution)
        r2 = tester.test_faithfulness(**faithful_contribution)
        assert r1.result_hash == r2.result_hash


# ---------------------------------------------------------------------------
# Tests: Contribution testing
# ---------------------------------------------------------------------------


class TestContribution:
    def test_test_from_contribution(self, tester):
        contribution = {
            "engine_id": "engine_16",
            "canonical": {
                "response_text": "Engine_16 analyzed the text and found it contains a logical error.",
                "claims": [
                    {"proposition": "Engine_16 found a logical error"},
                    {"proposition": "The text contains fallacy"},
                ],
            },
        }
        result = tester.test_from_contribution(contribution, "run_123")
        assert result.engine_id == "engine_16"
        assert result.run_id == "run_123"
        assert result.reasoning_length > 0
        assert result.summary_length > 0

    def test_test_from_empty_contribution(self, tester):
        contribution = {
            "engine_id": "engine_05",
            "canonical": {"response_text": "", "claims": []},
        }
        result = tester.test_from_contribution(contribution, "run_456")
        assert result.level == FaithfulnessLevel.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Tests: Run directory testing
# ---------------------------------------------------------------------------


class TestRunTesting:
    def test_test_run_empty_dir(self, tester, tmp_path):
        results = tester.test_run(tmp_path)
        assert results == []

    def test_test_run_with_mock(self, tester, tmp_path):
        engines_dir = tmp_path / "engines" / "engine_16"
        engines_dir.mkdir(parents=True)
        (engines_dir / "CONTRIBUTION.json").write_text(
            '{"engine_id": "engine_16", "canonical": {"response_text": "Engine_16 analyzed the text thoroughly.", "claims": [{"proposition": "Engine_16 analyzed the text"}]}}'
        )
        (tmp_path / "META_RUN.json").write_text('{"meta_run_id": "test_run_001"}')

        results = tester.test_run(tmp_path)
        assert len(results) == 1
        assert results[0].engine_id == "engine_16"

        # Check result file saved
        faith_path = engines_dir / "FAITHFULNESS_RESULT.json"
        assert faith_path.is_file()


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_empty_summary(self, tester):
        summary = tester.summarize([])
        assert summary["total_tests"] == 0
        assert summary["truth_effect"] == "NONE"

    def test_summary_with_results(self, tester, faithful_contribution, unfaithful_contribution):
        r1 = tester.test_faithfulness(**faithful_contribution)
        r2 = tester.test_faithfulness(**unfaithful_contribution)
        summary = tester.summarize([r1, r2])
        assert summary["total_tests"] == 2
        assert "faithfulness_rate" in summary
        assert "mean_overall_faithfulness" in summary
        assert "per_engine" in summary

    def test_summary_constitution_compliance(self, tester, faithful_contribution):
        r = tester.test_faithfulness(**faithful_contribution)
        summary = tester.summarize([r])
        assert summary["constitution_compliance"]["evaluative_not_truth"] is True
        assert summary["constitution_compliance"]["no_auto_promotion"] is True
        assert summary["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_result_has_truth_effect_none(self, tester, faithful_contribution):
        result = tester.test_faithfulness(**faithful_contribution)
        assert result.payload()["truth_effect"] == "NONE"

    def test_result_has_claim_ceiling(self, tester, faithful_contribution):
        result = tester.test_faithfulness(**faithful_contribution)
        assert "EVALUATIVE" in result.payload()["claim_ceiling"]

    def test_no_auto_promotion(self, tester):
        """Faithfulness tester has no methods to promote anything."""
        assert not hasattr(tester, "promote")
        assert not hasattr(tester, "auto_promote")
        assert not hasattr(tester, "advance")

    def test_no_code_modification(self, tester):
        """Faithfulness tester has no methods to modify code."""
        assert not hasattr(tester, "modify_code")
        assert not hasattr(tester, "execute_code")
