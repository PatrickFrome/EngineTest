"""METAENGINE Phase 7 — Predictive Organization Model.

Builds a world model of the design space: Task × Resources × Organization →
predicted Outcomes. Allows MetaEngine to predict outcomes BEFORE execution,
measure prediction accuracy, and reduce the number of brute-force experiments
needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .util import canonical_hash


PREDICTIVE_MODEL_VERSION = "METAENGINE-PREDICTIVE-ORGANIZATION-MODEL-1"


class PredictionStatus(str, Enum):
    CORRECT = "CORRECT"  # prediction matched actual (within tolerance)
    INCORRECT = "INCORRECT"  # prediction was wrong
    UNVERIFIED = "UNVERIFIED"  # no actual outcome to compare


@dataclass(frozen=True)
class OrganizationPrediction:
    """A prediction of outcomes for a task+organization combination."""
    task_id: str
    organization_policy_id: str
    predicted_quality: float
    predicted_cost: float
    predicted_latency: float
    confidence: float  # 0..1

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "organization_policy_id": self.organization_policy_id,
            "predicted_quality": round(self.predicted_quality, 6),
            "predicted_cost": round(self.predicted_cost, 6),
            "predicted_latency": round(self.predicted_latency, 6),
            "confidence": round(self.confidence, 6),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OrganizationPrediction":
        return cls(
            task_id=str(value["task_id"]),
            organization_policy_id=str(value["organization_policy_id"]),
            predicted_quality=float(value["predicted_quality"]),
            predicted_cost=float(value["predicted_cost"]),
            predicted_latency=float(value["predicted_latency"]),
            confidence=float(value["confidence"]),
        )


@dataclass(frozen=True)
class PredictionReceipt:
    """A prediction made BEFORE execution, compared with actual AFTER."""
    prediction: OrganizationPrediction
    actual_quality: float | None
    actual_cost: float | None
    actual_latency: float | None
    status: PredictionStatus
    quality_error: float
    cost_error: float
    latency_error: float

    def payload(self) -> dict[str, Any]:
        return {
            "prediction": self.prediction.payload(),
            "actual_quality": self.actual_quality,
            "actual_cost": self.actual_cost,
            "actual_latency": self.actual_latency,
            "status": self.status.value,
            "quality_error": round(self.quality_error, 6),
            "cost_error": round(self.cost_error, 6),
            "latency_error": round(self.latency_error, 6),
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.payload())


@dataclass(frozen=True)
class OrganizationModel:
    """A predictive model of the design space.

    Accumulates (task, organization) → outcome pairs and uses them to
    predict outcomes for new combinations. Currently uses simple mean-based
    prediction (baseline); can be replaced with learned models later.
    """
    model_version: str
    observations: tuple[dict[str, Any], ...]  # (task_id, policy_id, quality, cost, latency)

    @classmethod
    def create(cls, observations: Iterable[dict[str, Any]] = ()) -> "OrganizationModel":
        obs = tuple(sorted(observations, key=lambda o: (str(o.get("task_id", "")), str(o.get("policy_id", "")))))
        return cls(model_version=PREDICTIVE_MODEL_VERSION, observations=obs)

    def add_observation(self, task_id: str, policy_id: str, quality: float, cost: float, latency: float) -> "OrganizationModel":
        new_obs = self.observations + ({"task_id": task_id, "policy_id": policy_id, "quality": quality, "cost": cost, "latency": latency},)
        return OrganizationModel(model_version=self.model_version, observations=tuple(sorted(new_obs, key=lambda o: (o["task_id"], o["policy_id"]))))

    def predict(self, task_id: str, policy_id: str) -> OrganizationPrediction:
        """Predict outcomes for a task+organization combination.

        Uses mean of past observations for the same policy (or all if none).
        Confidence = fraction of observations for this policy.
        """
        policy_obs = [o for o in self.observations if o["policy_id"] == policy_id]
        if policy_obs:
            q = sum(o["quality"] for o in policy_obs) / len(policy_obs)
            c = sum(o["cost"] for o in policy_obs) / len(policy_obs)
            l = sum(o["latency"] for o in policy_obs) / len(policy_obs)
            conf = min(1.0, len(policy_obs) / 10.0)  # full confidence at 10+ observations
        elif self.observations:
            q = sum(o["quality"] for o in self.observations) / len(self.observations)
            c = sum(o["cost"] for o in self.observations) / len(self.observations)
            l = sum(o["latency"] for o in self.observations) / len(self.observations)
            conf = 0.1  # low confidence — no data for this policy
        else:
            q, c, l = 0.5, 1.0, 0.5  # default prior
            conf = 0.0  # no data at all
        return OrganizationPrediction(
            task_id=task_id, organization_policy_id=policy_id,
            predicted_quality=q, predicted_cost=c, predicted_latency=l, confidence=conf,
        )

    def verify_prediction(
        self,
        prediction: OrganizationPrediction,
        actual_quality: float,
        actual_cost: float,
        actual_latency: float,
        *,
        tolerance: float = 0.15,
    ) -> PredictionReceipt:
        """Compare a prediction with actual outcomes."""
        q_err = abs(prediction.predicted_quality - actual_quality)
        c_err = abs(prediction.predicted_cost - actual_cost)
        l_err = abs(prediction.predicted_latency - actual_latency)
        status = PredictionStatus.CORRECT if (q_err <= tolerance and c_err <= tolerance and l_err <= tolerance) else PredictionStatus.INCORRECT
        return PredictionReceipt(
            prediction=prediction,
            actual_quality=actual_quality,
            actual_cost=actual_cost,
            actual_latency=actual_latency,
            status=status,
            quality_error=q_err,
            cost_error=c_err,
            latency_error=l_err,
        )

    def prediction_accuracy(self, receipts: Iterable[PredictionReceipt]) -> float:
        """Fraction of CORRECT predictions."""
        receipt_list = list(receipts)
        if not receipt_list:
            return 0.0
        correct = sum(1 for r in receipt_list if r.status == PredictionStatus.CORRECT)
        return correct / len(receipt_list)

    def payload(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "observation_count": len(self.observations),
            "observations": [dict(o) for o in self.observations],
            "truth_effect": "NONE",
            "claim_ceiling": "PREDICTIVE_MODEL_IS_SEARCH_HEURISTIC_NOT_TRUTH",
        }

    @property
    def model_hash(self) -> str:
        return canonical_hash(self.payload())
