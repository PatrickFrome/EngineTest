"""METAENGINE Phase 13 — Architecture Search Space Generator.

Automatically generates novel architecture candidates from the mechanism
library, biographies, and tournament results. This closes the gap between
"manual architecture specification" and "automated architecture discovery."

The generator produces candidates by:
1. Combining mechanisms from the library (recombination)
2. Using biography priors to predict which combinations are promising
3. Using tournament results to avoid dominated configurations
4. Adding novelty pressure (candidates that explore unexplored space)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .util import canonical_hash


SEARCH_GENERATOR_VERSION = "METAENGINE-ARCHITECTURE-SEARCH-1"


class CandidateOrigin(str, Enum):
    RECOMBINATION = "RECOMBINATION"  # combined from mechanism library
    BIOGRAPHY_GUIDED = "BIOGRAPHY_GUIDED"  # guided by biography priors
    TOURNAMENT_INFORMED = "TOURNAMENT_INFORMED"  # avoids dominated configs
    NOVELTY = "NOVELTY"  # explores unexplored space
    ADVERSARIAL = "ADVERSARIAL"  # designed to break current champion


@dataclass(frozen=True)
class ArchitectureCandidate:
    """A generated architecture candidate for tournament evaluation."""
    candidate_id: str
    origin: CandidateOrigin
    mechanism_ids: tuple[str, ...]
    organization_type: str
    predicted_quality: float
    predicted_cost: float
    novelty_score: float
    rationale: str
    candidate_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "origin": self.origin.value,
            "mechanism_ids": list(self.mechanism_ids),
            "organization_type": self.organization_type,
            "predicted_quality": round(self.predicted_quality, 6),
            "predicted_cost": round(self.predicted_cost, 6),
            "novelty_score": round(self.novelty_score, 6),
            "rationale": self.rationale,
            "truth_effect": "NONE",
            "claim_ceiling": "CANDIDATE_IS_HYPOTHESIS_NOT_FACT",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "candidate_hash": self.candidate_hash}


class ArchitectureSearchGenerator:
    """Generates novel architecture candidates from accumulated knowledge."""

    def __init__(self, *, seed: int = 42):
        self._rng = random.Random(seed)

    def generate(
        self,
        *,
        mechanism_ids: Iterable[str] = (),
        biography_priors: Mapping[str, float] | None = None,
        dominated_configs: Iterable[tuple[str, ...]] = (),
        champion_mechanisms: Iterable[str] = (),
        max_candidates: int = 10,
    ) -> tuple[ArchitectureCandidate, ...]:
        """Generate architecture candidates.

        Args:
            mechanism_ids: Available mechanisms from the library.
            biography_priors: engine_id → mean_realized_gain (from biographies).
            dominated_configs: Configurations known to be dominated (from tournament).
            champion_mechanisms: Mechanisms used by the current champion.
            max_candidates: Maximum number of candidates to generate.

        Returns:
            Tuple of generated candidates, sorted by novelty_score descending.
        """
        mechs = list(mechanism_ids) or ["mec.default"]
        priors = dict(biography_priors or {})
        dominated = set(tuple(sorted(c)) for c in dominated_configs)
        champion = set(champion_mechanisms)

        candidates: list[ArchitectureCandidate] = []

        # Strategy 1: Recombination — combine 2-3 mechanisms
        for _ in range(max_candidates // 3):
            k = min(self._rng.randint(2, 3), len(mechs))
            combo = tuple(sorted(self._rng.sample(mechs, k)))
            if combo in dominated:
                continue
            novelty = 1.0 - (len(set(combo) & champion) / max(1, len(combo)))
            candidates.append(ArchitectureCandidate(
                candidate_id=f"cand.recomb.{canonical_hash({'combo': combo})[:12]}",
                origin=CandidateOrigin.RECOMBINATION,
                mechanism_ids=combo,
                organization_type="SPECIALIST_ROUTING",
                predicted_quality=sum(priors.get(m, 0.5) for m in combo) / len(combo),
                predicted_cost=1.0 + 0.1 * len(combo),
                novelty_score=round(novelty, 6),
                rationale=f"Recombination of {len(combo)} mechanisms; novelty={novelty:.2f}",
                candidate_hash="",
            ))

        # Strategy 2: Biography-guided — use highest-prior mechanisms
        if priors:
            top_mechs = sorted(mechs, key=lambda m: priors.get(m, 0.5), reverse=True)[:3]
            combo = tuple(sorted(top_mechs))
            if combo not in dominated:
                candidates.append(ArchitectureCandidate(
                    candidate_id=f"cand.bio.{canonical_hash({'combo': combo})[:12]}",
                    origin=CandidateOrigin.BIOGRAPHY_GUIDED,
                    mechanism_ids=combo,
                    organization_type="RESOURCE_PLUS_VERIFIER",
                    predicted_quality=sum(priors.get(m, 0.5) for m in combo) / len(combo),
                    predicted_cost=1.2,
                    novelty_score=0.3,
                    rationale=f"Top-3 mechanisms by biography prior; avg prior={sum(priors.get(m, 0.5) for m in combo)/len(combo):.2f}",
                    candidate_hash="",
                ))

        # Strategy 3: Novelty — explore unexplored space
        for _ in range(max_candidates // 3):
            k = min(self._rng.randint(1, 2), len(mechs))
            combo = tuple(sorted(self._rng.sample(mechs, k)))
            overlap = len(set(combo) & champion)
            novelty = 1.0 - overlap / max(1, len(combo))
            if novelty < 0.5:
                continue  # not novel enough
            candidates.append(ArchitectureCandidate(
                candidate_id=f"cand.novel.{canonical_hash({'combo': combo, 'i': len(candidates)})[:12]}",
                origin=CandidateOrigin.NOVELTY,
                mechanism_ids=combo,
                organization_type="ONE_RESOURCE",
                predicted_quality=0.5,  # no prediction — exploration
                predicted_cost=0.8,
                novelty_score=round(novelty, 6),
                rationale=f"Novelty-driven exploration; overlap with champion={overlap}",
                candidate_hash="",
            ))

        # Strategy 4: Adversarial — designed to break champion
        non_champion = [m for m in mechs if m not in champion]
        if non_champion:
            combo = tuple(sorted(non_champion[:2]))
            candidates.append(ArchitectureCandidate(
                candidate_id=f"cand.advers.{canonical_hash({'combo': combo})[:12]}",
                origin=CandidateOrigin.ADVERSARIAL,
                mechanism_ids=combo,
                organization_type="PARALLEL_ENSEMBLE",
                predicted_quality=0.4,  # expected to lose, but tests boundaries
                predicted_cost=1.5,
                novelty_score=1.0,
                rationale=f"Adversarial candidate using non-champion mechanisms only",
                candidate_hash="",
            ))

        # Deduplicate and compute hashes
        seen: set[tuple[str, ...]] = set()
        unique: list[ArchitectureCandidate] = []
        for c in candidates:
            if c.mechanism_ids in seen:
                continue
            seen.add(c.mechanism_ids)
            h = canonical_hash(c.payload())
            unique.append(ArchitectureCandidate(**{**c.__dict__, "candidate_hash": h}))

        # Sort by novelty descending
        unique.sort(key=lambda c: -c.novelty_score)
        return tuple(unique[:max_candidates])
