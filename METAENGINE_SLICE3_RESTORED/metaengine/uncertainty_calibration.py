"""METAENGINE Phase 22a — Uncertainty Calibration.

Measures how well the engine's prediction confidence matches actual correctness.
A well-calibrated system: when it says "90% confident", it's correct ~90% of the time.
"""

from __future__ import annotations

from typing import Any

from .util import canonical_hash


CALIBRATION_VERSION = "METAENGINE-UNCERTAINTY-CALIBRATION-1"


class UncertaintyCalibrator:
    """Tracks prediction confidence vs actual correctness."""

    def __init__(self):
        self._observations: list[tuple[float, bool]] = []  # (predicted_confidence, actual_correct)

    def add_observation(self, *, predicted_confidence: float, actual_correct: bool) -> None:
        self._observations.append((float(predicted_confidence), bool(actual_correct)))

    def calibration_error(self) -> float:
        """Mean absolute calibration error.

        For each confidence bucket, compares predicted confidence with actual
        fraction correct. Returns mean absolute difference.
        """
        if not self._observations:
            return 0.0

        # Bucket by confidence (0.1 intervals)
        buckets: dict[float, list[bool]] = {}
        for conf, correct in self._observations:
            bucket = round(conf * 10) / 10  # round to 0.1
            buckets.setdefault(bucket, []).append(correct)

        errors = []
        for bucket, results in buckets.items():
            actual_rate = sum(1 for r in results if r) / len(results)
            errors.append(abs(bucket - actual_rate))

        return sum(errors) / len(errors) if errors else 0.0

    def calibrator_hash(self) -> str:
        return canonical_hash({
            "calibration_version": CALIBRATION_VERSION,
            "observation_count": len(self._observations),
            "calibration_error": self.calibration_error(),
        })

    def payload(self) -> dict[str, Any]:
        return {
            "calibration_version": CALIBRATION_VERSION,
            "observation_count": len(self._observations),
            "calibration_error": round(self.calibration_error(), 6),
            "truth_effect": "NONE",
        }
