"""Fix 2: Tests for fusion.py — previously had NO tests."""
from __future__ import annotations
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.fusion import fuse


@dataclass
class MockContribution:
    engine_id: str
    status: str
    canonical: dict[str, Any] = None
    adapter_kind: str = "NATIVE_LOCAL"
    implementation_level: str = "REAL_EXECUTOR"
    error: str | None = None


class TestFusion:
    def test_fuse_returns_dict(self):
        contribs = [MockContribution("engine_01", "COMPLETE")]
        result = fuse(contribs)
        assert isinstance(result, dict)

    def test_fuse_has_fusion_metrics(self):
        """Fix 10: fusion now includes real metrics."""
        contribs = [MockContribution("engine_01", "COMPLETE")]
        result = fuse(contribs)
        assert "fusion_metrics" in result
        assert "total_claims" in result["fusion_metrics"]
        assert "consensus_ratio" in result["fusion_metrics"]

    def test_fuse_extracts_claims(self):
        """Fix 10: fusion extracts claims from canonical output."""
        contribs = [
            MockContribution("engine_01", "COMPLETE", canonical={"claims": [{"proposition": "test", "stance": "PROPOSE"}]}),
            MockContribution("engine_02", "COMPLETE", canonical={"claims": [{"proposition": "test", "stance": "PROPOSE"}]}),
        ]
        result = fuse(contribs)
        assert result["fusion_metrics"]["total_claims"] == 2
        assert len(result["consensus_claims"]) > 0

    def test_fuse_identifies_disagreements(self):
        """Fix 10: fusion identifies stance disagreements."""
        contribs = [
            MockContribution("engine_01", "COMPLETE", canonical={"claims": [{"proposition": "same text", "stance": "PROPOSE"}]}),
            MockContribution("engine_02", "COMPLETE", canonical={"claims": [{"proposition": "same text", "stance": "ASSERT"}]}),
        ]
        result = fuse(contribs)
        assert len(result["disagreements"]) > 0

    def test_fuse_truth_effect_none(self):
        contribs = [MockContribution("engine_01", "COMPLETE")]
        result = fuse(contribs)
        assert "DOES_NOT CREATE TRUTH BY VOTE" in result.get("claim_ceiling", "")

    def test_fuse_status_counts(self):
        contribs = [
            MockContribution("engine_01", "COMPLETE"),
            MockContribution("engine_02", "FAILED"),
        ]
        result = fuse(contribs)
        assert "COMPLETE" in result["status_counts"]
        assert "FAILED" in result["status_counts"]
