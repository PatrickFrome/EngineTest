"""METAENGINE Phase 42 — Parallel Training Campaign.

Unified harness that runs ALL 6 trainers in parallel:
  1. RLAIF (Phase 36) — constitutional reward signal
  2. PBT (Phase 37) — population evolution
  3. AlphaZero (Phase 38) — architecture synthesis via self-play
  4. ES (Phase 39) — hyperparameter fine-tuning
  5. MARL (Phase 40) — multi-agent credit assignment
  6. RedTeam (Phase 41) — adversarial vulnerability detection

The campaign runs trainers in parallel (ThreadPoolExecutor), collects results,
and produces a unified summary. Trainers share state:
  - EngineBiographies (updated by RLAIF, MARL)
  - MechanismLibrary (updated by AlphaZero)
  - PredictiveModel (updated by PBT, ES)
  - RedTeamResults (produced by RedTeam)

Constitution compliance:
  - All trainers remain SHADOW (no auto-promotion)
  - Shared state updates are idempotent (INSERT OR REPLACE)
  - truth_effect = NONE for all results
  - No trainer can modify code or constitution
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .util import canonical_hash


CAMPAIGN_VERSION = "METAENGINE-PARALLEL-TRAINING-CAMPAIGN-1"


# ---------------------------------------------------------------------------
# Trainer result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrainerResult:
    """Result of running one trainer in the campaign."""
    trainer_name: str
    started_at: float
    elapsed_seconds: float
    success: bool
    summary: dict[str, Any]
    error: str | None = None
    result_hash: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "trainer_name": self.trainer_name,
            "success": self.success,
            "summary": self.summary,
            "error": self.error,
            "truth_effect": "NONE",
            "claim_ceiling": "CAMPAIGN_TRAINER_RESULT_IS_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        # Full dict includes timing (for display), but hash uses payload (no timing)
        return {
            **self.payload(),
            "started_at": round(self.started_at, 6),
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "result_hash": self.result_hash,
        }


# ---------------------------------------------------------------------------
# Campaign result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CampaignResult:
    """Result of a full parallel training campaign."""
    campaign_id: str
    started_at: float
    elapsed_seconds: float
    trainer_results: tuple[TrainerResult, ...]
    shared_state_summary: dict[str, Any]
    campaign_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "campaign_version": CAMPAIGN_VERSION,
            "campaign_id": self.campaign_id,
            "started_at": round(self.started_at, 6),
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "trainer_count": len(self.trainer_results),
            "trainers_succeeded": sum(1 for t in self.trainer_results if t.success),
            "trainers_failed": sum(1 for t in self.trainer_results if not t.success),
            "trainer_results": [t.payload() for t in self.trainer_results],
            "shared_state_summary": self.shared_state_summary,
            "truth_effect": "NONE",
            "claim_ceiling": "CAMPAIGN_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "all_trainers_remain_shadow": True,
                "no_auto_promotion": True,
                "shared_state_idempotent": True,
                "no_code_modification": True,
            },
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "campaign_hash": self.campaign_hash}


# ---------------------------------------------------------------------------
# Parallel Training Campaign
# ---------------------------------------------------------------------------


class ParallelTrainingCampaign:
    """Unified harness for running all trainers in parallel.

    Each trainer is a callable that takes no args and returns a summary dict.
    The campaign runs them in parallel using ThreadPoolExecutor.

    Usage:
        campaign = ParallelTrainingCampaign(max_workers=4)
        campaign.register_trainer("RLAIF", rlaif_fn)
        campaign.register_trainer("PBT", pbt_fn)
        # ... register all 6 trainers
        result = campaign.run()
    """

    def __init__(
        self,
        *,
        max_workers: int = 4,
        campaign_id: str | None = None,
    ):
        if max_workers < 1:
            raise ValueError("MAX_WORKERS_MUST_BE_AT_LEAST_1")
        self.max_workers = max_workers
        self.campaign_id = campaign_id or f"campaign.{canonical_hash({'ts': time.time()})[:12]}"
        self.trainers: dict[str, Callable[[], dict[str, Any]]] = {}

    def register_trainer(
        self,
        name: str,
        trainer_fn: Callable[[], dict[str, Any]],
    ) -> None:
        """Register a trainer function.

        Args:
            name: trainer name (e.g., "RLAIF", "PBT").
            trainer_fn: callable that takes no args, returns summary dict.
        """
        if not name:
            raise ValueError("TRAINER_NAME_CANNOT_BE_EMPTY")
        self.trainers[name] = trainer_fn

    def unregister_trainer(self, name: str) -> None:
        """Remove a trainer."""
        self.trainers.pop(name, None)

    def _run_trainer(self, name: str, fn: Callable[[], dict[str, Any]]) -> TrainerResult:
        """Run a single trainer, capturing timing and errors."""
        started = time.perf_counter()
        started_at = time.time()
        try:
            summary = fn()
            elapsed = time.perf_counter() - started
            result = TrainerResult(
                trainer_name=name,
                started_at=started_at,
                elapsed_seconds=elapsed,
                success=True,
                summary=summary,
                error=None,
                result_hash="",
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            result = TrainerResult(
                trainer_name=name,
                started_at=started_at,
                elapsed_seconds=elapsed,
                success=False,
                summary={},
                error=str(exc)[:500],
                result_hash="",
            )
        h = canonical_hash(result.payload())
        return TrainerResult(**{**result.__dict__, "result_hash": h})

    def run(self) -> CampaignResult:
        """Run all registered trainers in parallel.

        Returns:
            CampaignResult with all trainer results.
        """
        if not self.trainers:
            raise ValueError("NO_TRAINERS_REGISTERED")

        started = time.perf_counter()
        started_at = time.time()

        results: list[TrainerResult] = []

        # Run trainers in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self._run_trainer, name, fn): name
                for name, fn in self.trainers.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    # Should not happen — _run_trainer catches exceptions
                    results.append(TrainerResult(
                        trainer_name=name,
                        started_at=started_at,
                        elapsed_seconds=0.0,
                        success=False,
                        summary={},
                        error=f"UNEXPECTED: {exc}",
                        result_hash="",
                    ))

        # Sort results by trainer name for deterministic output
        results.sort(key=lambda r: r.trainer_name)

        elapsed = time.perf_counter() - started

        # Build shared state summary
        shared_state = self._build_shared_state_summary(results)

        campaign = CampaignResult(
            campaign_id=self.campaign_id,
            started_at=started_at,
            elapsed_seconds=elapsed,
            trainer_results=tuple(results),
            shared_state_summary=shared_state,
            campaign_hash="",
        )
        h = canonical_hash(campaign.payload())
        return CampaignResult(**{**campaign.__dict__, "campaign_hash": h})

    def _build_shared_state_summary(self, results: list[TrainerResult]) -> dict[str, Any]:
        """Build a summary of shared state from trainer results."""
        summary: dict[str, Any] = {
            "trainers_run": len(results),
            "trainers_succeeded": sum(1 for r in results if r.success),
        }

        # Extract key metrics from each trainer's summary
        for r in results:
            if not r.success:
                continue
            trainer_summary = r.summary
            trainer_name = r.trainer_name

            if trainer_name == "RLAIF":
                summary["rlaif_reward"] = trainer_summary.get("best_fitness") or trainer_summary.get("reward", 0.0)
            elif trainer_name == "PBT":
                summary["pbt_best_fitness"] = trainer_summary.get("best_fitness") or trainer_summary.get("mean_fitness", 0.0)
            elif trainer_name == "AlphaZero":
                summary["alphazero_mechanisms_extracted"] = trainer_summary.get("total_mechanisms_extracted", 0)
                summary["alphazero_architectures_synthesized"] = trainer_summary.get("total_architectures_synthesized", 0)
            elif trainer_name == "ES":
                summary["es_best_fitness"] = trainer_summary.get("best_fitness", 0.0)
                summary["es_converged"] = trainer_summary.get("converged", False)
            elif trainer_name == "MARL":
                summary["marl_friend_mean_reward"] = trainer_summary.get("friend_mean_reward", 0.0)
                summary["marl_foe_mean_reward"] = trainer_summary.get("foe_mean_reward", 0.0)
            elif trainer_name == "RedTeam":
                summary["redteam_violation_rate"] = trainer_summary.get("overall_violation_rate", 0.0)
                summary["redteam_total_violations"] = trainer_summary.get("total_violations", 0)

        return summary

    def summary(self) -> dict[str, Any]:
        """Return campaign metadata (without running)."""
        return {
            "campaign_version": CAMPAIGN_VERSION,
            "campaign_id": self.campaign_id,
            "registered_trainers": list(self.trainers.keys()),
            "max_workers": self.max_workers,
            "truth_effect": "NONE",
        }
