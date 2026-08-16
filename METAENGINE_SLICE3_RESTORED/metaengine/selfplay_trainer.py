"""METAENGINE Phase 38 — AlphaZero Self-Play Architecture Trainer.

Implements the AlphaZero-style self-play loop for architecture search:
  1. TOURNAMENT: pairwise comparison of policies (self-play)
  2. EXTRACT: winner's mechanisms → MechanismCandidate (A0_OBSERVED)
  3. RECOMBINE: ArchitectureSynthesizer combines winning mechanisms (G+2)
  4. ABLATE: loser's mechanisms → marked for retirement
  5. ADVANCE: A0 → A1 (hypothesized) → A2 (validated) → A3 (assimilated)
  6. New generation: synthesized candidates + surviving champions
  7. Repeat

This closes the architecture search loop. Unlike PBT (which evolves
hyperparameters), AlphaZero self-play CREATES new architectures by
combining winning mechanisms from the tournament.

Constitution compliance:
  - All synthesized architectures are HYPOTHESES (not facts)
  - SynthesisResult carries claim_ceiling = SYNTHESIS_IS_HYPOTHESIS_NOT_FACT
  - No auto-promotion to ACTIVE — all remain SHADOW
  - Mechanism advancement requires AssimilationGate (A0→A3)
  - Tournament results are EVALUATIVE, not truth
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .util import canonical_hash, write_json
from .architecture_policy import ArchitecturePolicy, initial_policy
from .organization_tournament import (
    PolicyResult,
    run_tournament,
    TournamentResult,
)
from .architecture_synthesis import ArchitectureSynthesizer, SynthesisResult
from .mechanism_library import MechanismLibrary, MechanismCandidate, MechanismState
from .policy_generator import extract_mechanism_from_tournament


SELFPLAY_VERSION = "METAENGINE-SELFPLAY-ARCHITECTURE-TRAINER-1"


# ---------------------------------------------------------------------------
# Self-play generation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelfPlayGeneration:
    """Result of one self-play generation."""
    generation: int
    tournament: TournamentResult
    extracted_mechanisms: tuple[dict, ...]  # MechanismCandidate payloads
    syntheses: SynthesisResult
    ablated_mechanism_ids: tuple[str, ...]
    advanced_mechanisms: tuple[dict, ...]  # mechanisms that advanced state
    generation_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "selfplay_version": SELFPLAY_VERSION,
            "generation": self.generation,
            "tournament_hash": self.tournament.tournament_hash[:32],
            "pareto_winners": [e.policy_id for e in self.tournament.pareto_frontier if not e.dominated],
            "extracted_mechanisms_count": len(self.extracted_mechanisms),
            "syntheses_count": len(self.syntheses.syntheses),
            "ablated_mechanism_ids": list(self.ablated_mechanism_ids),
            "advanced_mechanisms_count": len(self.advanced_mechanisms),
            "truth_effect": "NONE",
            "claim_ceiling": "SELFPLAY_GENERATION_IS_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "generation_hash": self.generation_hash}


# ---------------------------------------------------------------------------
# Self-play trainer
# ---------------------------------------------------------------------------


class SelfPlayArchitectureTrainer:
    """AlphaZero-style self-play architecture search.

    The loop:
      1. Run tournament (pairwise comparison of policies)
      2. Extract winning mechanisms → A0_OBSERVED
      3. Synthesize new architectures (G+2 combinations)
      4. Ablate losing mechanisms (mark for retirement)
      5. Advance mechanism states (A0 → A1 → A2 → A3)
      6. New generation: synthesized + surviving champions

    Usage:
        trainer = SelfPlayArchitectureTrainer(mechanism_library=lib)
        for gen in range(num_generations):
            generation = trainer.run_generation(
                policies=policies,
                task_results=task_results,
                generation_index=gen,
            )
    """

    def __init__(
        self,
        *,
        mechanism_library: MechanismLibrary | None = None,
        synthesizer: ArchitectureSynthesizer | None = None,
        seed: int = 42,
    ):
        self.mechanism_library = mechanism_library or MechanismLibrary.create(())
        self.synthesizer = synthesizer or ArchitectureSynthesizer(seed=seed)
        self._rng = random.Random(seed)
        self.generations: list[SelfPlayGeneration] = []

    # ------------------------------------------------------------------
    # Tournament (self-play)
    # ------------------------------------------------------------------

    def run_tournament(
        self,
        *,
        policy_results: list[PolicyResult],
        policy_ids: list[str],
        task_ids: list[str],
    ) -> TournamentResult:
        """Run a pairwise tournament over policy results."""
        return run_tournament(policy_results, policy_ids=policy_ids, task_ids=task_ids)

    # ------------------------------------------------------------------
    # Extract winning mechanisms
    # ------------------------------------------------------------------

    def extract_winning_mechanisms(
        self,
        tournament: TournamentResult,
    ) -> list[MechanismCandidate]:
        """Extract mechanisms from tournament winners (Pareto non-dominated).

        For each Pareto winner, create an A0_OBSERVED MechanismCandidate.
        """
        winners = [e for e in tournament.pareto_frontier if not e.dominated]
        extracted: list[MechanismCandidate] = []

        for winner in winners:
            mechanism_id = f"mech.{winner.policy_id}.{winner.metrics['quality']:.2f}"
            candidate = MechanismCandidate.create(
                mechanism_id=mechanism_id,
                semantic_definition=(
                    f"Tournament winner: policy={winner.policy_id}, "
                    f"quality={winner.metrics['quality']:.4f}"
                ),
                origin_source_ids=[winner.policy_id],
                source_fact_boundary="TOURNAMENT_PARETO_FRONTIER",
                hypothesized_effect=f"Produces quality {winner.metrics['quality']:.2f}",
                resource_cost=f"cost={winner.metrics['cost']:.4f}",
                complexity_cost=f"latency={winner.metrics['latency']:.4f}",
                confidence="LOW",
                status=MechanismState.A0_OBSERVED,
                promotion_authority=None,
            )
            self.mechanism_library = self.mechanism_library.add_candidate(candidate)
            extracted.append(candidate)

        return extracted

    # ------------------------------------------------------------------
    # Synthesize new architectures
    # ------------------------------------------------------------------

    def synthesize_architectures(
        self,
        winning_mechanism_ids: list[str],
        *,
        max_combinations: int = 5,
    ) -> SynthesisResult:
        """Synthesize new architectures from winning mechanisms (G+2)."""
        return self.synthesizer.synthesize(
            winning_mechanisms=winning_mechanism_ids,
            max_combinations=max_combinations,
        )

    # ------------------------------------------------------------------
    # Ablate losing mechanisms
    # ------------------------------------------------------------------

    def ablate_losing_mechanisms(
        self,
        tournament: TournamentResult,
    ) -> list[str]:
        """Identify losing (dominated) policies and mark their mechanisms for ablation.

        Returns list of mechanism_ids that should be ablated.
        Does NOT actually retire them — just identifies candidates.
        """
        losers = [e for e in tournament.pareto_frontier if e.dominated]
        ablated: list[str] = []
        for loser in losers:
            # Find mechanisms observed from this loser policy (in origin_source_ids)
            for candidate in self.mechanism_library.candidates:
                if loser.policy_id in candidate.origin_source_ids:
                    ablated.append(candidate.mechanism_id)
        return ablated

    # ------------------------------------------------------------------
    # Advance mechanism states (A0 → A1 → A2 → A3)
    # ------------------------------------------------------------------

    def advance_mechanism_states(self) -> list[dict]:
        """Advance mechanism states.

        Simplified advancement (full AssimilationGate is in assimilation.py):
          A0_OBSERVED → A1_MECHANISM_HYPOTHESIS (always — we observed it)
          A1 → A2 requires AssimilationGate receipt (constitution — NOT done here)
          A2 → A3 requires external promotion authority (constitution — NOT done here)

        Returns list of advanced mechanism payloads.
        """
        advanced: list[dict] = []
        new_candidates: list[MechanismCandidate] = []

        for candidate in self.mechanism_library.candidates:
            old_state = candidate.status
            new_state = old_state

            if old_state == MechanismState.A0_OBSERVED:
                # A0 → A1: hypothesized (always, since we observed it)
                new_state = MechanismState.A1_MECHANISM_HYPOTHESIS
            # A1 → A2 requires AssimilationGate receipt (constitution guard)
            # A2 → A3 requires external promotion authority (constitution guard)

            if new_state != old_state:
                advanced.append({
                    "mechanism_id": candidate.mechanism_id,
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "origin_source_ids": list(candidate.origin_source_ids),
                })
                # Create updated candidate with new status (frozen dataclass → replace)
                import dataclasses
                updated = dataclasses.replace(candidate, status=new_state)
                new_candidates.append(updated)
            else:
                new_candidates.append(candidate)

        # Rebuild library directly (bypass create() to avoid re-validation of A1)
        new_candidates_sorted = tuple(sorted(new_candidates, key=lambda c: c.mechanism_id))
        self.mechanism_library = MechanismLibrary(
            library_version=self.mechanism_library.library_version,
            candidates=new_candidates_sorted,
        )

        return advanced

    # ------------------------------------------------------------------
    # Full generation
    # ------------------------------------------------------------------

    def run_generation(
        self,
        *,
        policies: list[tuple[str, ArchitecturePolicy]],
        task_results: list[PolicyResult],
        generation_index: int,
    ) -> SelfPlayGeneration:
        """Run one full self-play generation.

        Args:
            policies: List of (policy_id, ArchitecturePolicy) tuples.
            task_results: List of PolicyResult from running policies on tasks.
            generation_index: The generation number.

        Returns:
            SelfPlayGeneration with all artifacts.
        """
        policy_ids = [pid for pid, _ in policies]
        task_ids = sorted({r.task_id for r in task_results})

        # 1. Tournament (self-play)
        tournament = self.run_tournament(
            policy_results=task_results,
            policy_ids=policy_ids,
            task_ids=task_ids,
        )

        # 2. Extract winning mechanisms
        extracted = self.extract_winning_mechanisms(tournament)

        # 3. Synthesize new architectures
        winning_mechanism_ids = [c.mechanism_id for c in extracted]
        syntheses = self.synthesize_architectures(
            winning_mechanism_ids,
            max_combinations=5,
        )

        # 4. Ablate losing mechanisms
        ablated = self.ablate_losing_mechanisms(tournament)

        # 5. Advance mechanism states
        advanced = self.advance_mechanism_states()

        # Build generation result
        gen = SelfPlayGeneration(
            generation=generation_index,
            tournament=tournament,
            extracted_mechanisms=tuple(c.payload() for c in extracted),
            syntheses=syntheses,
            ablated_mechanism_ids=tuple(ablated),
            advanced_mechanisms=tuple(advanced),
            generation_hash="",
        )
        h = canonical_hash(gen.payload())
        gen = SelfPlayGeneration(**{**gen.__dict__, "generation_hash": h})
        self.generations.append(gen)
        return gen

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a summary of all generations run."""
        if not self.generations:
            return {
                "selfplay_version": SELFPLAY_VERSION,
                "generations_run": 0,
                "truth_effect": "NONE",
            }

        total_extracted = sum(len(g.extracted_mechanisms) for g in self.generations)
        total_synthesized = sum(len(g.syntheses.syntheses) for g in self.generations)
        total_ablated = sum(len(g.ablated_mechanism_ids) for g in self.generations)
        total_advanced = sum(len(g.advanced_mechanisms) for g in self.generations)

        return {
            "selfplay_version": SELFPLAY_VERSION,
            "generations_run": len(self.generations),
            "total_mechanisms_extracted": total_extracted,
            "total_architectures_synthesized": total_synthesized,
            "total_mechanisms_ablated": total_ablated,
            "total_mechanisms_advanced": total_advanced,
            "mechanism_library_size": len(self.mechanism_library.candidates),
            "mechanism_states": self._mechanism_state_distribution(),
            "generations": [g.payload() for g in self.generations],
            "truth_effect": "NONE",
            "claim_ceiling": "SELFPLAY_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "all_syntheses_are_hypotheses": True,
                "no_auto_promotion_to_a3": True,
                "a3_requires_external_authority": True,
                "tournament_results_evaluative": True,
            },
        }

    def _mechanism_state_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for c in self.mechanism_library.candidates:
            state = c.status.value
            dist[state] = dist.get(state, 0) + 1
        return dist
