"""METAENGINE Phase 20 — Architecture Synthesis G+2.

Synthesizes new architecture candidates by combining winning mechanisms
from different tournament worlds. Does NOT assume that the sum of positive
components gives a positive result — each synthesis must be tested.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from typing import Any, Iterable

from .util import canonical_hash


SYNTHESIS_VERSION = "METAENGINE-ARCHITECTURE-SYNTHESIS-1"


@dataclass(frozen=True)
class SynthesizedArchitecture:
    """A candidate synthesized from multiple winning mechanisms."""
    synthesis_id: str
    combined_mechanisms: tuple[str, ...]
    rationale: str
    novelty_score: float
    synthesis_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            "combined_mechanisms": list(self.combined_mechanisms),
            "rationale": self.rationale,
            "novelty_score": round(self.novelty_score, 6),
            "truth_effect": "NONE",
            "claim_ceiling": "SYNTHESIS_IS_HYPOTHESIS_NOT_FACT",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "synthesis_hash": self.synthesis_hash}


@dataclass(frozen=True)
class SynthesisResult:
    """Result of architecture synthesis."""
    syntheses: tuple[SynthesizedArchitecture, ...]
    source_mechanisms: tuple[str, ...]
    result_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "synthesis_version": SYNTHESIS_VERSION,
            "syntheses": [s.payload() for s in self.syntheses],
            "source_mechanisms": list(self.source_mechanisms),
            "truth_effect": "NONE",
            "claim_ceiling": "SYNTHESIS_RESULT_DOES_NOT_ASSUME_POSITIVE_SUM",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "result_hash": self.result_hash}


class ArchitectureSynthesizer:
    """Synthesizes new architectures by combining winning mechanisms."""

    def __init__(self, *, seed: int = 42):
        self._rng = random.Random(seed)

    def synthesize(
        self,
        *,
        winning_mechanisms: list[str],
        max_combinations: int = 5,
    ) -> SynthesisResult:
        """Generate synthesized architectures from winning mechanisms.

        Creates combinations of 2-3 mechanisms. Does NOT assume the sum is
        positive — each synthesis is a hypothesis that must be tested.
        """
        syntheses: list[SynthesizedArchitecture] = []

        if len(winning_mechanisms) < 2:
            # Can't synthesize from fewer than 2 mechanisms
            result = SynthesisResult(
                syntheses=(), source_mechanisms=tuple(winning_mechanisms), result_hash="",
            )
            h = canonical_hash(result.payload())
            return SynthesisResult(**{**result.__dict__, "result_hash": h})

        # Generate all pairs and triples
        pairs = list(itertools.combinations(winning_mechanisms, 2))
        triples = list(itertools.combinations(winning_mechanisms, 3)) if len(winning_mechanisms) >= 3 else []

        all_combos = pairs + triples
        self._rng.shuffle(all_combos)

        for combo in all_combos[:max_combinations]:
            combo_sorted = tuple(sorted(combo))
            # Novelty: higher for larger combinations (more unexplored)
            novelty = len(combo_sorted) / max(2, len(winning_mechanisms))
            # Check if this combination has been tested before (in experience)
            # For now, all syntheses are novel
            synthesis = SynthesizedArchitecture(
                synthesis_id=f"synth.{canonical_hash({'combo': combo_sorted})[:12]}",
                combined_mechanisms=combo_sorted,
                rationale=f"Combines {len(combo_sorted)} winning mechanisms; does not assume positive sum",
                novelty_score=round(novelty, 6),
                synthesis_hash="",
            )
            h = canonical_hash(synthesis.payload())
            synthesis = SynthesizedArchitecture(**{**synthesis.__dict__, "synthesis_hash": h})
            syntheses.append(synthesis)

        result = SynthesisResult(
            syntheses=tuple(syntheses),
            source_mechanisms=tuple(sorted(winning_mechanisms)),
            result_hash="",
        )
        h = canonical_hash(result.payload())
        return SynthesisResult(**{**result.__dict__, "result_hash": h})
