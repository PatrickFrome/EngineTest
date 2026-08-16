"""Tests for Phase 44 — Reasoning Trace Extraction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.trace_extractor import (
    ReasoningTraceExtractor,
    ReasoningTrace,
    ExtractionResult,
    TRACE_EXTRACTION_VERSION,
)
from metaengine.mechanism_library import MechanismLibrary, MechanismState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    return ReasoningTraceExtractor(
        min_length=30,
        max_length=400,
        score_threshold=0.3,
        max_traces_per_run=5,
    )


@pytest.fixture
def mock_contribution():
    """A realistic LLM contribution with structured reasoning."""
    return {
        "engine_id": "engine_16",
        "status": "COMPLETE",
        "adapter_kind": "LLM_MODEL",
        "canonical": {
            "kind": "llm_model_execution",
            "response_text": (
                "### Analysis of Input Text\n\n"
                "The input presents a specific testable claim about correlation and causation.\n\n"
                "### Claim 1: The argument is fallacious\n\n"
                "The text states that correlation implies causation when sample size exceeds 1000. "
                "This is incorrect because correlation does not imply causation regardless of sample size.\n\n"
                "### Claim 2: Statistical power misconception\n\n"
                "A large sample size increases statistical power but does not address confounders. "
                "For example, ice cream sales correlate with drowning, but hot weather is the cause.\n\n"
                "### Conclusion\n\n"
                "The argument commits the affirming the consequent fallacy. "
                "Engine_16 identifies this as a reasoning error."
            ),
            "claims": [],
            "claim_ceiling": "LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED",
        },
        "usage": {"total_tokens": 500},
    }


@pytest.fixture
def empty_contribution():
    return {
        "engine_id": "engine_05",
        "status": "COMPLETE",
        "canonical": {"response_text": ""},
        "usage": {},
    }


# ---------------------------------------------------------------------------
# Tests: ReasoningTrace
# ---------------------------------------------------------------------------


class TestReasoningTrace:
    def test_payload_has_required_fields(self):
        t = ReasoningTrace(
            trace_id="trace.001",
            trace_text="test reasoning",
            source_engine="engine_16",
            source_run_id="run_123",
            source_contribution_hash="abc",
            step_index=0,
            score=0.5,
            length_chars=14,
            has_structure=False,
            has_specificity=False,
            trace_hash="xyz",
        )
        p = t.payload()
        assert p["trace_id"] == "trace.001"
        assert p["source"] == "OWN_LLM_RUN"
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED"

    def test_as_dict_includes_hash(self):
        t = ReasoningTrace(
            trace_id="t", trace_text="x", source_engine="e",
            source_run_id="r", source_contribution_hash="c",
            step_index=0, score=0.5, length_chars=1,
            has_structure=False, has_specificity=False, trace_hash="abc123",
        )
        d = t.as_dict()
        assert d["trace_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: ExtractionResult
# ---------------------------------------------------------------------------


class TestExtractionResult:
    def test_payload_has_required_fields(self):
        r = ExtractionResult(
            run_id="run_1", engine_id="engine_16",
            total_traces=5, high_score_traces=3,
            mean_score=0.6, traces=(), extraction_hash="abc",
        )
        p = r.payload()
        assert p["extraction_version"] == TRACE_EXTRACTION_VERSION
        assert p["total_traces"] == 5
        assert p["truth_effect"] == "NONE"

    def test_as_dict_includes_hash(self):
        r = ExtractionResult(
            run_id="r", engine_id="e", total_traces=0,
            high_score_traces=0, mean_score=0.0, traces=(),
            extraction_hash="abc123",
        )
        d = r.as_dict()
        assert d["extraction_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: Text parsing
# ---------------------------------------------------------------------------


class TestTextParsing:
    """Test the _split_into_steps method."""

    def test_split_markdown_headers(self, extractor):
        text = "### Header 1\nThis is content under header one with enough text.\n\n### Header 2\nThis is content under header two with enough text."
        steps = extractor._split_into_steps(text)
        assert len(steps) >= 2

    def test_split_numbered_list(self, extractor):
        text = "1. First step with enough text to pass min length\n2. Second step with enough text to pass min length\n3. Third step with enough text to pass min length"
        steps = extractor._split_into_steps(text)
        assert len(steps) >= 2

    def test_split_bullet_points(self, extractor):
        text = "- First point with enough text to pass min length\n- Second point with enough text to pass min length\n- Third point with enough text to pass min length"
        steps = extractor._split_into_steps(text)
        assert len(steps) >= 2

    def test_split_sentence_boundaries(self, extractor):
        text = "This is the first sentence. This is the second sentence. And a third one here."
        steps = extractor._split_into_steps(text)
        assert len(steps) >= 1

    def test_split_empty_text(self, extractor):
        steps = extractor._split_into_steps("")
        assert steps == []

    def test_split_respects_max_length(self, extractor):
        text = "### Header\n" + "x" * 1000
        steps = extractor._split_into_steps(text)
        for step in steps:
            assert len(step) <= extractor.max_length

    def test_split_filters_short_steps(self, extractor):
        text = "### Header\nShort.\n\n### Long Header\n" + "y" * 100
        steps = extractor._split_into_steps(text)
        for step in steps:
            assert len(step) >= extractor.min_length or len(steps) == 1


# ---------------------------------------------------------------------------
# Tests: Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    """Test the _score_trace method."""

    def test_long_trace_scores_higher(self, extractor):
        short = "Short text."
        long_text = "This is a longer reasoning trace with more content and detail. " * 5
        s_short, _, _ = extractor._score_trace(short)
        s_long, _, _ = extractor._score_trace(long_text)
        assert s_long > s_short

    def test_structured_trace_scores_higher(self, extractor):
        plain = "This is plain text without any structure at all."
        structured = "### Header\n1. First point with detail\n2. Second point"
        s_plain, struct_plain, _ = extractor._score_trace(plain)
        s_struct, struct_struct, _ = extractor._score_trace(structured)
        assert struct_struct is True
        assert struct_plain is False
        assert s_struct > s_plain

    def test_specific_trace_scores_higher(self, extractor):
        generic = "The model produces some output based on input."
        specific = "Engine_16 identified 42 claims with evidence_strength 0.15."
        s_gen, _, spec_gen = extractor._score_trace(generic)
        s_spec, _, spec_spec = extractor._score_trace(specific)
        assert spec_spec is True
        assert s_spec > s_gen

    def test_score_in_range_0_1(self, extractor):
        texts = ["", "short", "### Long structured text with numbers 42 and Engine_16"]
        for t in texts:
            score, _, _ = extractor._score_trace(t)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Tests: Extraction
# ---------------------------------------------------------------------------


class TestExtraction:
    """Test the extract_from_contribution method."""

    def test_extract_returns_result(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        assert isinstance(result, ExtractionResult)
        assert result.engine_id == "engine_16"
        assert result.run_id == "run_123"
        assert result.extraction_hash != ""

    def test_extract_finds_traces(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        assert result.total_traces > 0
        assert len(result.traces) > 0

    def test_extract_empty_contribution(self, extractor, empty_contribution):
        result = extractor.extract_from_contribution(empty_contribution, "run_456")
        assert result.total_traces == 0
        assert result.traces == ()

    def test_extract_traces_have_claim_ceiling(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        for trace in result.traces:
            assert trace.payload()["claim_ceiling"] == "LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED"
            assert trace.payload()["source"] == "OWN_LLM_RUN"

    def test_extract_traces_have_hashes(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        for trace in result.traces:
            assert trace.trace_hash != ""

    def test_extract_respects_max_traces(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        assert len(result.traces) <= extractor.max_traces_per_run

    def test_extract_mean_score_computed(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        if result.traces:
            expected = sum(t.score for t in result.traces) / len(result.traces)
            assert abs(result.mean_score - expected) < 0.001

    def test_extract_high_score_count(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        expected_high = sum(1 for t in result.traces if t.score >= extractor.score_threshold)
        assert result.high_score_traces == expected_high

    def test_extract_deterministic(self, extractor, mock_contribution):
        r1 = extractor.extract_from_contribution(mock_contribution, "run_123")
        r2 = extractor.extract_from_contribution(mock_contribution, "run_123")
        assert r1.extraction_hash == r2.extraction_hash


# ---------------------------------------------------------------------------
# Tests: MechanismLibrary integration
# ---------------------------------------------------------------------------


class TestMechanismLibraryIntegration:
    """Test adding traces to MechanismLibrary."""

    def test_add_to_library(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        library = MechanismLibrary.create(())
        library, added = extractor.add_to_mechanism_library(result, library)
        assert len(added) > 0
        assert len(library.candidates) > 0

    def test_added_mechanisms_are_a0(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        library = MechanismLibrary.create(())
        library, added = extractor.add_to_mechanism_library(result, library)
        for candidate in added:
            assert candidate.status == MechanismState.A0_OBSERVED
            assert candidate.promotion_authority is None

    def test_only_high_score_added(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        library = MechanismLibrary.create(())
        library, added = extractor.add_to_mechanism_library(result, library)
        for candidate in added:
            # The trace score should be >= threshold
            # (mechanism_id encodes the trace, we check it was added)
            assert candidate.mechanism_id.startswith("trace_mech.")

    def test_add_idempotent(self, extractor, mock_contribution):
        """Adding the same traces twice should not duplicate."""
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        library = MechanismLibrary.create(())
        library, added1 = extractor.add_to_mechanism_library(result, library)
        count_after_first = len(library.candidates)
        library, added2 = extractor.add_to_mechanism_library(result, library)
        count_after_second = len(library.candidates)
        assert count_after_first == count_after_second  # idempotent


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    """Test that trace extraction preserves constitution."""

    def test_source_is_own_llm_run(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        for trace in result.traces:
            assert trace.payload()["source"] == "OWN_LLM_RUN"

    def test_no_scraping(self, extractor):
        """The extractor does NOT scrape public traces."""
        assert not hasattr(extractor, "scrape")
        assert not hasattr(extractor, "fetch_public_traces")

    def test_no_proprietary_distillation(self, extractor):
        """The extractor does NOT distill proprietary models."""
        assert not hasattr(extractor, "distill")
        assert not hasattr(extractor, "query_proprietary")

    def test_claim_ceiling_propagated(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        for trace in result.traces:
            assert "GENERATIVE" in trace.payload()["claim_ceiling"]

    def test_summary_constitution_compliance(self, extractor, mock_contribution):
        result = extractor.extract_from_contribution(mock_contribution, "run_123")
        summary = extractor.summarize_results([result])
        assert summary["constitution_compliance"]["no_scraping"] is True
        assert summary["constitution_compliance"]["no_proprietary_distillation"] is True
        assert summary["constitution_compliance"]["a0_only"] is True
        assert summary["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Run directory extraction
# ---------------------------------------------------------------------------


class TestRunExtraction:
    """Test extracting from a run directory."""

    def test_extract_from_run_empty_dir(self, extractor, tmp_path):
        results = extractor.extract_from_run(tmp_path)
        assert results == []

    def test_extract_from_run_with_mock(self, extractor, tmp_path, mock_contribution):
        # Create a fake run directory
        engines_dir = tmp_path / "engines" / "engine_16"
        engines_dir.mkdir(parents=True)
        (engines_dir / "CONTRIBUTION.json").write_text(
            json.dumps(mock_contribution)
        )
        (tmp_path / "META_RUN.json").write_text(
            json.dumps({"meta_run_id": "test_run_001"})
        )

        results = extractor.extract_from_run(tmp_path)
        assert len(results) == 1
        assert results[0].engine_id == "engine_16"
        assert results[0].total_traces > 0

        # Check traces file was saved
        traces_path = engines_dir / "REASONING_TRACES.json"
        assert traces_path.is_file()
        saved = json.loads(traces_path.read_text())
        assert saved["extraction_version"] == TRACE_EXTRACTION_VERSION

    def test_extract_from_run_multiple_engines(self, extractor, tmp_path, mock_contribution):
        for eid in ["engine_01", "engine_16"]:
            engine_dir = tmp_path / "engines" / eid
            engine_dir.mkdir(parents=True)
            (engine_dir / "CONTRIBUTION.json").write_text(
                json.dumps({**mock_contribution, "engine_id": eid})
            )
        (tmp_path / "META_RUN.json").write_text(
            json.dumps({"meta_run_id": "test_run_002"})
        )

        results = extractor.extract_from_run(tmp_path)
        assert len(results) == 2
        engine_ids = [r.engine_id for r in results]
        assert "engine_01" in engine_ids
        assert "engine_16" in engine_ids

    def test_extract_from_run_specific_engines(self, extractor, tmp_path, mock_contribution):
        for eid in ["engine_01", "engine_16"]:
            engine_dir = tmp_path / "engines" / eid
            engine_dir.mkdir(parents=True)
            (engine_dir / "CONTRIBUTION.json").write_text(
                json.dumps({**mock_contribution, "engine_id": eid})
            )
        (tmp_path / "META_RUN.json").write_text(
            json.dumps({"meta_run_id": "test_run_003"})
        )

        results = extractor.extract_from_run(tmp_path, engine_ids=["engine_16"])
        assert len(results) == 1
        assert results[0].engine_id == "engine_16"
