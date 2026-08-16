"""METAENGINE Phase 44 — Reasoning Trace Extraction Module.

Extracts reasoning traces from MetaEngine's OWN LLM runs (via the bridge) and
adds them to the MechanismLibrary as A0_OBSERVED candidates.

This is a SELF-DISTILLATION approach (Apr 2026, "Embarrassingly Simple Self-
Distillation") — using the model's own outputs as training data. NO scraping,
NO proprietary model distillation, NO ToS violation. Only own API calls.

Architecture:
  1. Load engine contribution (from orchestrator run)
  2. Extract response_text (the LLM's reasoning trace)
  3. Parse into structured reasoning steps (sentences/paragraphs)
  4. For each step, create a ReasoningTrace:
     - trace_text: the reasoning text
     - source_engine: which engine produced it
     - source_run_id: which run
     - claim_ceiling: LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED
  5. Score each trace (heuristic: length, structure, specificity)
  6. Add high-scoring traces to MechanismLibrary as A0_OBSERVED

Constitution compliance:
  - Extracted traces = generative (claim_ceiling)
  - No truth promotion (A0 only, not A3)
  - No code modification
  - Source recorded honestly (OWN_LLM_RUN, not EXTERNAL)
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .util import canonical_hash


TRACE_EXTRACTION_VERSION = "METAENGINE-REASONING-TRACE-EXTRACTION-1"


# ---------------------------------------------------------------------------
# Reasoning trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReasoningTrace:
    """A single extracted reasoning trace from an LLM run."""
    trace_id: str
    trace_text: str
    source_engine: str
    source_run_id: str
    source_contribution_hash: str
    step_index: int  # position in the original response
    score: float  # heuristic quality score 0-1
    length_chars: int
    has_structure: bool  # has markdown/numbering
    has_specificity: bool  # contains specific terms/numbers
    trace_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "trace_text": self.trace_text[:1000],  # truncated for storage
            "source_engine": self.source_engine,
            "source_run_id": self.source_run_id,
            "source_contribution_hash": self.source_contribution_hash[:16],
            "step_index": self.step_index,
            "score": round(self.score, 6),
            "length_chars": self.length_chars,
            "has_structure": self.has_structure,
            "has_specificity": self.has_specificity,
            "claim_ceiling": "LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED",
            "source": "OWN_LLM_RUN",
            "truth_effect": "NONE",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "trace_hash": self.trace_hash}


# ---------------------------------------------------------------------------
# Extraction result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractionResult:
    """Result of extracting traces from a run."""
    run_id: str
    engine_id: str
    total_traces: int
    high_score_traces: int  # traces with score > threshold
    mean_score: float
    traces: tuple[ReasoningTrace, ...]
    extraction_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "extraction_version": TRACE_EXTRACTION_VERSION,
            "run_id": self.run_id,
            "engine_id": self.engine_id,
            "total_traces": self.total_traces,
            "high_score_traces": self.high_score_traces,
            "mean_score": round(self.mean_score, 6),
            "trace_count": len(self.traces),
            "truth_effect": "NONE",
            "claim_ceiling": "EXTRACTED_TRACES_ARE_GENERATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "extraction_hash": self.extraction_hash}


# ---------------------------------------------------------------------------
# Reasoning Trace Extractor
# ---------------------------------------------------------------------------


class ReasoningTraceExtractor:
    """Extracts reasoning traces from MetaEngine's own LLM runs.

    Usage:
        extractor = ReasoningTraceExtractor()
        result = extractor.extract_from_contribution(contribution, run_id)
        extractor.add_to_mechanism_library(result, library)
    """

    def __init__(
        self,
        *,
        min_length: int = 50,  # min chars for a trace
        max_length: int = 500,  # max chars per trace
        score_threshold: float = 0.4,  # min score to add to library
        max_traces_per_run: int = 10,
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.score_threshold = score_threshold
        self.max_traces_per_run = max_traces_per_run

    # ------------------------------------------------------------------
    # Text parsing
    # ------------------------------------------------------------------

    def _split_into_steps(self, text: str) -> list[str]:
        """Split response text into reasoning steps.

        Splits on:
          - Markdown headers (###, ##, #)
          - Numbered lists (1., 2., 3.)
          - Bullet points (-, *)
          - Sentence boundaries (.!? followed by whitespace)
        """
        if not text or not text.strip():
            return []

        # First, try markdown headers (also match at start of text)
        # Use findall to locate all headers, then extract text between them
        header_pattern = r'(?:^|\n)(#{1,4}\s+[^\n]+)'
        header_matches = list(re.finditer(header_pattern, text))
        if len(header_matches) >= 2:
            steps = []
            for i, match in enumerate(header_matches):
                start = match.start()
                # Strip leading \n
                if text[start] == '\n':
                    start += 1
                end = header_matches[i + 1].start() if i + 1 < len(header_matches) else len(text)
                section = text[start:end].strip()
                if section:
                    full = section[:self.max_length]
                    if len(full) >= self.min_length:
                        steps.append(full)
            if steps:
                return steps

        # Fallback: split on numbered list items (also match at start)
        numbered = re.split(r'(?:^|\n)(?=\d+\.\s)', text)
        if len(numbered) > 1:
            result = [s.strip()[:self.max_length] for s in numbered if s.strip() and len(s.strip()) >= self.min_length]
            if result:
                return result

        # Fallback: split on bullet points (also match at start)
        bullets = re.split(r'(?:^|\n)(?=[-•*]\s)', text)
        if len(bullets) > 1:
            result = [s.strip()[:self.max_length] for s in bullets if s.strip() and len(s.strip()) >= self.min_length]
            if result:
                return result

        # Final fallback: split on sentence boundaries and merge
        sentences = re.split(r'(?<=[.!?])\s+', text)
        merged = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) < self.max_length:
                current = (current + " " + sent).strip()
            else:
                if len(current) >= self.min_length:
                    merged.append(current[:self.max_length])
                current = sent[:self.max_length]
        if current and len(current) >= self.min_length:
            merged.append(current[:self.max_length])
        return merged[:self.max_traces_per_run]

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_trace(self, text: str) -> tuple[float, bool, bool]:
        """Score a reasoning trace heuristically.

        Returns (score, has_structure, has_specificity).
        """
        length = len(text)

        # Length score (longer = better, up to max_length)
        length_score = min(1.0, length / self.max_length)

        # Structure: has markdown/numbering/bullets
        has_structure = bool(
            re.search(r'#{1,4}\s', text)
            or re.search(r'\d+\.\s', text)
            or re.search(r'[-•*]\s', text)
            or re.search(r'\*\*.*\*\*', text)  # bold
        )
        structure_score = 0.3 if has_structure else 0.0

        # Specificity: contains numbers, technical terms, or specific references
        has_specificity = bool(
            re.search(r'\d+', text)  # numbers
            or re.search(r'\b[A-Z]{2,}\b', text)  # acronyms
            or re.search(r'engine_\d+', text)  # engine references
            or re.search(r'claim|evidence|source|proof', text, re.IGNORECASE)
        )
        specificity_score = 0.3 if has_specificity else 0.0

        # Coherence: not just random words
        word_count = len(text.split())
        coherence_score = min(0.2, word_count / 50.0) if word_count > 5 else 0.0

        score = min(1.0, length_score * 0.3 + structure_score + specificity_score + coherence_score)
        return round(score, 4), has_structure, has_specificity

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract_from_contribution(
        self,
        contribution: Mapping[str, Any],
        run_id: str,
    ) -> ExtractionResult:
        """Extract reasoning traces from an engine contribution.

        Args:
            contribution: the EngineContribution dict (has 'canonical', 'usage', etc.)
            run_id: the orchestrator run ID.

        Returns:
            ExtractionResult with all extracted traces.
        """
        engine_id = contribution.get("engine_id", "unknown")
        canonical = contribution.get("canonical", {}) or {}
        response_text = canonical.get("response_text", "") or ""

        if not response_text:
            return ExtractionResult(
                run_id=run_id,
                engine_id=engine_id,
                total_traces=0,
                high_score_traces=0,
                mean_score=0.0,
                traces=(),
                extraction_hash="",
            )

        # Compute contribution hash for provenance
        contrib_hash = canonical_hash({
            "engine_id": engine_id,
            "run_id": run_id,
            "response_text": response_text[:500],
        })

        # Split into steps
        steps = self._split_into_steps(response_text)

        # Score each step
        traces: list[ReasoningTrace] = []
        for i, step_text in enumerate(steps[:self.max_traces_per_run]):
            score, has_structure, has_specificity = self._score_trace(step_text)
            trace_id = f"trace.{engine_id}.{run_id[:12]}.{i:02d}"

            trace = ReasoningTrace(
                trace_id=trace_id,
                trace_text=step_text,
                source_engine=engine_id,
                source_run_id=run_id,
                source_contribution_hash=contrib_hash,
                step_index=i,
                score=score,
                length_chars=len(step_text),
                has_structure=has_structure,
                has_specificity=has_specificity,
                trace_hash="",
            )
            h = canonical_hash(trace.payload())
            trace = ReasoningTrace(**{**trace.__dict__, "trace_hash": h})
            traces.append(trace)

        high_score = [t for t in traces if t.score >= self.score_threshold]
        mean_score = sum(t.score for t in traces) / len(traces) if traces else 0.0

        result = ExtractionResult(
            run_id=run_id,
            engine_id=engine_id,
            total_traces=len(traces),
            high_score_traces=len(high_score),
            mean_score=mean_score,
            traces=tuple(traces),
            extraction_hash="",
        )
        h = canonical_hash(result.payload())
        return ExtractionResult(**{**result.__dict__, "extraction_hash": h})

    # ------------------------------------------------------------------
    # Add to mechanism library
    # ------------------------------------------------------------------

    def add_to_mechanism_library(
        self,
        result: ExtractionResult,
        library,
    ) -> list:
        """Add high-scoring traces to the MechanismLibrary as A0_OBSERVED.

        Args:
            result: the ExtractionResult from extract_from_contribution.
            library: the MechanismLibrary to add to.

        Returns:
            List of added MechanismCandidate objects.
        """
        from .mechanism_library import MechanismCandidate, MechanismState

        added = []
        for trace in result.traces:
            if trace.score < self.score_threshold:
                continue

            mechanism_id = f"trace_mech.{trace.source_engine}.{trace.trace_id[-12:]}"

            candidate = MechanismCandidate.create(
                mechanism_id=mechanism_id,
                semantic_definition=f"Reasoning trace from {trace.source_engine}: {trace.trace_text[:200]}",
                origin_source_ids=[trace.source_engine],
                source_fact_boundary="OWN_LLM_RUN",
                hypothesized_effect=f"Produces reasoning with score {trace.score:.2f}",
                resource_cost=f"length={trace.length_chars}",
                complexity_cost=f"step={trace.step_index}",
                confidence="LOW",
                status=MechanismState.A0_OBSERVED,
                promotion_authority=None,
            )
            library = library.add_candidate(candidate)
            added.append(candidate)

        return library, added

    # ------------------------------------------------------------------
    # Extract from run directory
    # ------------------------------------------------------------------

    def extract_from_run(
        self,
        run_dir: str | Path,
        *,
        engine_ids: list[str] | None = None,
    ) -> list[ExtractionResult]:
        """Extract traces from all engine contributions in a run directory.

        Args:
            run_dir: path to the orchestrator output directory.
            engine_ids: list of engine IDs to extract from (default: all).

        Returns:
            List of ExtractionResult, one per engine.
        """
        run_dir = Path(run_dir)
        engines_dir = run_dir / "engines"
        if not engines_dir.is_dir():
            return []

        # Get run_id from META_RUN.json
        meta_run_path = run_dir / "META_RUN.json"
        run_id = "unknown"
        if meta_run_path.is_file():
            meta = json.loads(meta_run_path.read_text())
            run_id = meta.get("meta_run_id", "unknown")

        if engine_ids is None:
            engine_ids = sorted(
                d.name for d in engines_dir.iterdir() if d.is_dir()
            )

        results: list[ExtractionResult] = []
        for eid in engine_ids:
            contrib_path = engines_dir / eid / "CONTRIBUTION.json"
            if not contrib_path.is_file():
                continue
            try:
                contribution = json.loads(contrib_path.read_text())
                result = self.extract_from_contribution(contribution, run_id)

                # Save traces alongside contribution
                traces_path = engines_dir / eid / "REASONING_TRACES.json"
                traces_path.write_text(
                    json.dumps(result.as_dict(), indent=2, ensure_ascii=False)
                )
                results.append(result)
            except Exception:
                continue

        return results

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summarize_results(self, results: list[ExtractionResult]) -> dict[str, Any]:
        """Summarize extraction results across multiple runs/engines."""
        if not results:
            return {
                "extraction_version": TRACE_EXTRACTION_VERSION,
                "total_runs": 0,
                "truth_effect": "NONE",
            }

        total_traces = sum(r.total_traces for r in results)
        total_high = sum(r.high_score_traces for r in results)
        all_scores = [t.score for r in results for t in r.traces]
        mean_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

        return {
            "extraction_version": TRACE_EXTRACTION_VERSION,
            "total_runs": len(results),
            "total_traces_extracted": total_traces,
            "total_high_score_traces": total_high,
            "mean_trace_score": round(mean_score, 6),
            "score_threshold": self.score_threshold,
            "per_engine": {
                r.engine_id: {
                    "total": r.total_traces,
                    "high_score": r.high_score_traces,
                    "mean_score": round(r.mean_score, 4),
                }
                for r in results
            },
            "constitution_compliance": {
                "source": "OWN_LLM_RUN",
                "no_scraping": True,
                "no_proprietary_distillation": True,
                "claim_ceiling": "LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED",
                "no_auto_promotion": True,
                "a0_only": True,
            },
            "truth_effect": "NONE",
            "claim_ceiling": "EXTRACTED_TRACES_ARE_GENERATIVE_NOT_TRUTH",
        }
