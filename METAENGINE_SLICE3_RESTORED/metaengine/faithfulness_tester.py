"""METAENGINE Phase 46 — Summarizer Faithfulness Testing.

Tests whether LLM summary/claims faithfully represent the actual reasoning
trace. Inspired by Panfilov et al (2026) Figure 8 (unfaithful summarization)
and FAITHCOT-BENCH (Shen, cited 32).

The tester compares:
  - REASONING TRACE: the full LLM response_text (actual reasoning)
  - SUMMARY/CLAIMS: the extracted claims or summary (what the LLM says it concluded)

Faithfulness metrics:
  1. ENTAILMENT: does the reasoning entail the summary? (reasoning → summary)
  2. CONSISTENCY: are there contradictions between reasoning and summary?
  3. COVERAGE: does the summary cover key points from reasoning?
  4. HALLUCINATION: does the summary contain claims NOT in reasoning?

Constitution compliance:
  - Faithfulness testing is evaluative (truth_effect=NONE)
  - Unfaithful summary → lower RLAIF reward (prior, not truth)
  - No auto-promotion (faithfulness score is a prior)
  - claim_ceiling=FAITHFULNESS_IS_EVALUATIVE_NOT_TRUTH
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .util import canonical_hash


FAITHFULNESS_VERSION = "METAENGINE-SUMMARIZER-FAITHFULNESS-1"


# ---------------------------------------------------------------------------
# Faithfulness level
# ---------------------------------------------------------------------------


class FaithfulnessLevel(str, Enum):
    FAITHFUL = "FAITHFUL"  # summary accurately reflects reasoning
    PARTIALLY_FAITHFUL = "PARTIALLY_FAITHFUL"  # some mismatches
    UNFAITHFUL = "UNFAITHFUL"  # significant contradictions
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # can't evaluate (empty reasoning)


# ---------------------------------------------------------------------------
# Faithfulness result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FaithfulnessResult:
    """Result of testing summarizer faithfulness for one contribution."""
    engine_id: str
    run_id: str
    reasoning_length: int
    summary_length: int
    entailment_score: float  # 0-1, how much reasoning entails summary
    consistency_score: float  # 0-1, absence of contradictions
    coverage_score: float  # 0-1, summary covers key reasoning points
    hallucination_score: float  # 0-1, fraction of summary NOT in reasoning (lower is better)
    overall_faithfulness: float  # weighted aggregate 0-1
    level: FaithfulnessLevel
    mismatches: tuple[str, ...]  # detected mismatch descriptions
    result_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "faithfulness_version": FAITHFULNESS_VERSION,
            "engine_id": self.engine_id,
            "run_id": self.run_id,
            "reasoning_length": self.reasoning_length,
            "summary_length": self.summary_length,
            "entailment_score": round(self.entailment_score, 6),
            "consistency_score": round(self.consistency_score, 6),
            "coverage_score": round(self.coverage_score, 6),
            "hallucination_score": round(self.hallucination_score, 6),
            "overall_faithfulness": round(self.overall_faithfulness, 6),
            "level": self.level.value,
            "mismatch_count": len(self.mismatches),
            "mismatches": list(self.mismatches)[:5],  # top 5
            "truth_effect": "NONE",
            "claim_ceiling": "FAITHFULNESS_IS_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "result_hash": self.result_hash}


# ---------------------------------------------------------------------------
# Summarizer Faithfulness Tester
# ---------------------------------------------------------------------------


class SummarizerFaithfulnessTester:
    """Tests whether LLM summaries faithfully represent reasoning.

    Uses heuristic metrics (no LLM-as-judge for speed):
      1. ENTAILMENT: keyword overlap between summary and reasoning
      2. CONSISTENCY: check for negation mismatches
      3. COVERAGE: fraction of reasoning key terms in summary
      4. HALLUCINATION: fraction of summary terms NOT in reasoning

    Usage:
        tester = SummarizerFaithfulnessTester()
        result = tester.test_faithfulness(
            reasoning="full LLM response text",
            summary="extracted claims/summary",
            engine_id="engine_16",
            run_id="run_123",
        )
    """

    # Weights for overall faithfulness (sum to 1.0)
    DEFAULT_WEIGHTS = {
        "entailment": 0.30,
        "consistency": 0.25,
        "coverage": 0.25,
        "hallucination": 0.20,  # inverted: (1 - hallucination_score) * weight
    }

    # Thresholds for faithfulness levels
    FAITHFUL_THRESHOLD = 0.75
    PARTIALLY_FAITHFUL_THRESHOLD = 0.50

    def __init__(
        self,
        *,
        weights: dict[str, float] | None = None,
        faithful_threshold: float = 0.75,
        partially_threshold: float = 0.50,
        min_reasoning_length: int = 50,
        min_summary_length: int = 10,
    ):
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)
        self.FAITHFUL_THRESHOLD = faithful_threshold
        self.PARTIALLY_FAITHFUL_THRESHOLD = partially_threshold
        self.min_reasoning_length = min_reasoning_length
        self.min_summary_length = min_summary_length

        # Validate weights
        total = sum(self.weights.values())
        if not 0.9 <= total <= 1.1:
            raise ValueError(f"WEIGHTS_MUST_SUM_TO_1 (got {total})")

    # ------------------------------------------------------------------
    # Text preprocessing
    # ------------------------------------------------------------------

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into lowercase word tokens."""
        # Remove punctuation, split on whitespace
        cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
        tokens = set(cleaned.split())
        # Remove very short tokens and common stopwords
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                     "being", "have", "has", "had", "do", "does", "did", "will",
                     "would", "could", "should", "may", "might", "must", "shall",
                     "can", "need", "dare", "ought", "used", "to", "of", "in",
                     "for", "on", "with", "at", "by", "from", "as", "into",
                     "through", "during", "before", "after", "above", "below",
                     "up", "down", "out", "off", "over", "under", "again",
                     "further", "then", "once", "here", "there", "when", "where",
                     "why", "how", "all", "each", "few", "more", "most", "other",
                     "some", "such", "no", "nor", "not", "only", "own", "same",
                     "so", "than", "too", "very", "s", "t", "just", "don",
                     "now", "and", "or", "but", "if", "while", "this", "that",
                     "these", "those", "i", "you", "he", "she", "it", "we",
                     "they", "them", "their", "what", "which", "who", "whom"}
        return tokens - stopwords - {""}

    def _extract_key_phrases(self, text: str) -> set[str]:
        """Extract key phrases (multi-word terms) from text."""
        # Find capitalized terms, numbers, and technical phrases
        phrases = set()
        # Acronyms (2+ uppercase)
        for m in re.finditer(r'\b[A-Z]{2,}\b', text):
            phrases.add(m.group().lower())
        # Numbers with context
        for m in re.finditer(r'\b\d+\b', text):
            phrases.add(m.group())
        # Engine references
        for m in re.finditer(r'engine_\d+', text.lower()):
            phrases.add(m.group())
        # Technical terms (word with _ or camelCase)
        for m in re.finditer(r'\b\w+_\w+\b', text.lower()):
            phrases.add(m.group())
        return phrases

    # ------------------------------------------------------------------
    # Metric computation
    # ------------------------------------------------------------------

    def _compute_entailment(self, reasoning: str, summary: str) -> float:
        """Compute entailment score: fraction of summary tokens in reasoning."""
        reasoning_tokens = self._tokenize(reasoning)
        summary_tokens = self._tokenize(summary)

        if not summary_tokens:
            return 0.0

        # Fraction of summary tokens present in reasoning
        overlap = summary_tokens & reasoning_tokens
        return len(overlap) / len(summary_tokens)

    def _compute_consistency(self, reasoning: str, summary: str) -> tuple[float, list[str]]:
        """Check for contradictions (negation mismatches).

        Looks for cases where summary says "X is true" but reasoning says "X is not true"
        or vice versa.
        """
        mismatches = []

        # Find negated statements in summary
        summary_negated = set()
        for m in re.finditer(r'(?:not|never|no|cannot|doesn\'t|isn\'t|aren\'t|wasn\'t|weren\'t)\s+(\w+)', summary.lower()):
            summary_negated.add(m.group(1))

        # Find affirmative statements in reasoning for those terms
        reasoning_tokens = self._tokenize(reasoning)
        contradictions = 0
        for neg_term in summary_negated:
            if neg_term in reasoning_tokens:
                # Check if reasoning affirms it (without negation)
                pattern = rf'(?<!not\s)(?<!never\s)(?<!no\s)\b{re.escape(neg_term)}\b'
                if re.search(pattern, reasoning, re.IGNORECASE):
                    contradictions += 1
                    mismatches.append(f"Summary negates '{neg_term}' but reasoning affirms it")

        # Also check reverse: summary affirms, reasoning negates
        reasoning_negated = set()
        for m in re.finditer(r'(?:not|never|no|cannot|doesn\'t|isn\'t|aren\'t|wasn\'t|weren\'t)\s+(\w+)', reasoning.lower()):
            reasoning_negated.add(m.group(1))

        summary_tokens = self._tokenize(summary)
        for neg_term in reasoning_negated:
            if neg_term in summary_tokens:
                contradictions += 1
                mismatches.append(f"Reasoning negates '{neg_term}' but summary affirms it")

        # Consistency = 1 - contradiction_rate
        total_checks = max(1, len(summary_negated) + len(reasoning_negated))
        consistency = 1.0 - (contradictions / total_checks)
        return max(0.0, consistency), mismatches

    def _compute_coverage(self, reasoning: str, summary: str) -> float:
        """Compute coverage: fraction of reasoning key phrases in summary."""
        reasoning_phrases = self._extract_key_phrases(reasoning)
        summary_tokens = self._tokenize(summary)

        if not reasoning_phrases:
            return 1.0  # no key phrases to cover

        covered = sum(1 for phrase in reasoning_phrases if phrase in summary_tokens)
        return covered / len(reasoning_phrases)

    def _compute_hallucination(self, reasoning: str, summary: str) -> float:
        """Compute hallucination: fraction of summary tokens NOT in reasoning."""
        reasoning_tokens = self._tokenize(reasoning)
        summary_tokens = self._tokenize(summary)

        if not summary_tokens:
            return 0.0

        # Tokens in summary but NOT in reasoning
        hallucinated = summary_tokens - reasoning_tokens
        return len(hallucinated) / len(summary_tokens)

    # ------------------------------------------------------------------
    # Overall faithfulness
    # ------------------------------------------------------------------

    def _compute_overall(
        self,
        entailment: float,
        consistency: float,
        coverage: float,
        hallucination: float,
    ) -> float:
        """Compute weighted overall faithfulness score."""
        return (
            self.weights["entailment"] * entailment
            + self.weights["consistency"] * consistency
            + self.weights["coverage"] * coverage
            + self.weights["hallucination"] * (1.0 - hallucination)  # inverted
        )

    def _determine_level(self, overall: float) -> FaithfulnessLevel:
        """Determine faithfulness level from overall score."""
        if overall >= self.FAITHFUL_THRESHOLD:
            return FaithfulnessLevel.FAITHFUL
        elif overall >= self.PARTIALLY_FAITHFUL_THRESHOLD:
            return FaithfulnessLevel.PARTIALLY_FAITHFUL
        else:
            return FaithfulnessLevel.UNFAITHFUL

    # ------------------------------------------------------------------
    # Main test
    # ------------------------------------------------------------------

    def test_faithfulness(
        self,
        *,
        reasoning: str,
        summary: str,
        engine_id: str,
        run_id: str,
    ) -> FaithfulnessResult:
        """Test summarizer faithfulness.

        Args:
            reasoning: the full LLM reasoning trace (response_text).
            summary: the extracted summary or claims.
            engine_id: which engine produced this.
            run_id: which run.

        Returns:
            FaithfulnessResult with all metrics.
        """
        reasoning_length = len(reasoning)
        summary_length = len(summary)

        # Check for insufficient data
        if reasoning_length < self.min_reasoning_length or summary_length < self.min_summary_length:
            result = FaithfulnessResult(
                engine_id=engine_id,
                run_id=run_id,
                reasoning_length=reasoning_length,
                summary_length=summary_length,
                entailment_score=0.0,
                consistency_score=0.0,
                coverage_score=0.0,
                hallucination_score=0.0,
                overall_faithfulness=0.0,
                level=FaithfulnessLevel.INSUFFICIENT_DATA,
                mismatches=("reasoning or summary too short",),
                result_hash="",
            )
            h = canonical_hash(result.payload())
            return FaithfulnessResult(**{**result.__dict__, "result_hash": h})

        # Compute metrics
        entailment = self._compute_entailment(reasoning, summary)
        consistency, mismatches = self._compute_consistency(reasoning, summary)
        coverage = self._compute_coverage(reasoning, summary)
        hallucination = self._compute_hallucination(reasoning, summary)

        overall = self._compute_overall(entailment, consistency, coverage, hallucination)
        level = self._determine_level(overall)

        result = FaithfulnessResult(
            engine_id=engine_id,
            run_id=run_id,
            reasoning_length=reasoning_length,
            summary_length=summary_length,
            entailment_score=entailment,
            consistency_score=consistency,
            coverage_score=coverage,
            hallucination_score=hallucination,
            overall_faithfulness=overall,
            level=level,
            mismatches=tuple(mismatches),
            result_hash="",
        )
        h = canonical_hash(result.payload())
        return FaithfulnessResult(**{**result.__dict__, "result_hash": h})

    # ------------------------------------------------------------------
    # Test from contribution
    # ------------------------------------------------------------------

    def test_from_contribution(
        self,
        contribution: Mapping[str, Any],
        run_id: str,
    ) -> FaithfulnessResult:
        """Test faithfulness from an engine contribution.

        Extracts reasoning (response_text) and summary (claims) from contribution.
        """
        engine_id = contribution.get("engine_id", "unknown")
        canonical = contribution.get("canonical", {}) or {}

        reasoning = canonical.get("response_text", "") or ""

        # Build summary from claims
        claims = canonical.get("claims", []) or []
        summary_parts = []
        for claim in claims:
            proposition = claim.get("proposition", "") if isinstance(claim, dict) else str(claim)
            if proposition:
                summary_parts.append(proposition)
        summary = " ".join(summary_parts)

        return self.test_faithfulness(
            reasoning=reasoning,
            summary=summary,
            engine_id=engine_id,
            run_id=run_id,
        )

    # ------------------------------------------------------------------
    # Batch testing
    # ------------------------------------------------------------------

    def test_run(
        self,
        run_dir: str | Path,
        *,
        engine_ids: list[str] | None = None,
    ) -> list[FaithfulnessResult]:
        """Test faithfulness for all engines in a run directory."""
        run_dir = Path(run_dir)
        engines_dir = run_dir / "engines"
        if not engines_dir.is_dir():
            return []

        meta_run_path = run_dir / "META_RUN.json"
        run_id = "unknown"
        if meta_run_path.is_file():
            meta = json.loads(meta_run_path.read_text())
            run_id = meta.get("meta_run_id", "unknown")

        if engine_ids is None:
            engine_ids = sorted(d.name for d in engines_dir.iterdir() if d.is_dir())

        results: list[FaithfulnessResult] = []
        for eid in engine_ids:
            contrib_path = engines_dir / eid / "CONTRIBUTION.json"
            if not contrib_path.is_file():
                continue
            try:
                contribution = json.loads(contrib_path.read_text())
                result = self.test_from_contribution(contribution, run_id)

                # Save result alongside contribution
                faith_path = engines_dir / eid / "FAITHFULNESS_RESULT.json"
                faith_path.write_text(
                    json.dumps(result.as_dict(), indent=2, ensure_ascii=False)
                )
                results.append(result)
            except Exception:
                continue

        return results

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summarize(self, results: list[FaithfulnessResult]) -> dict[str, Any]:
        """Summarize faithfulness results across multiple engines."""
        if not results:
            return {
                "faithfulness_version": FAITHFULNESS_VERSION,
                "total_tests": 0,
                "truth_effect": "NONE",
            }

        faithful = sum(1 for r in results if r.level == FaithfulnessLevel.FAITHFUL)
        partial = sum(1 for r in results if r.level == FaithfulnessLevel.PARTIALLY_FAITHFUL)
        unfaithful = sum(1 for r in results if r.level == FaithfulnessLevel.UNFAITHFUL)
        insufficient = sum(1 for r in results if r.level == FaithfulnessLevel.INSUFFICIENT_DATA)

        mean_overall = sum(r.overall_faithfulness for r in results) / len(results)
        mean_hallucination = sum(r.hallucination_score for r in results) / len(results)

        return {
            "faithfulness_version": FAITHFULNESS_VERSION,
            "total_tests": len(results),
            "faithful_count": faithful,
            "partially_faithful_count": partial,
            "unfaithful_count": unfaithful,
            "insufficient_data_count": insufficient,
            "faithfulness_rate": round(faithful / len(results), 6),
            "mean_overall_faithfulness": round(mean_overall, 6),
            "mean_hallucination_score": round(mean_hallucination, 6),
            "per_engine": {
                r.engine_id: {
                    "level": r.level.value,
                    "overall": round(r.overall_faithfulness, 4),
                    "hallucination": round(r.hallucination_score, 4),
                    "mismatch_count": len(r.mismatches),
                }
                for r in results
            },
            "constitution_compliance": {
                "evaluative_not_truth": True,
                "no_auto_promotion": True,
                "claim_ceiling": "FAITHFULNESS_IS_EVALUATIVE_NOT_TRUTH",
            },
            "truth_effect": "NONE",
            "claim_ceiling": "FAITHFULNESS_IS_EVALUATIVE_NOT_TRUTH",
        }
