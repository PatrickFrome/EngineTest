"""Step 7: Tests for LangGraph orchestrator."""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.langgraph_orchestrator import LangGraphOrchestrator, OrchestratorState, ORCHESTRATOR_VERSION


class TestLangGraphOrchestrator:
    """Test the LangGraph-based orchestrator."""

    def test_import(self):
        """LangGraphOrchestrator can be imported."""
        assert LangGraphOrchestrator is not None

    def test_version(self):
        assert ORCHESTRATOR_VERSION == "METAENGINE-LANGGRAPH-ORCHESTRATOR-1"

    def test_init_without_checkpoint(self):
        """Can initialize without checkpoint path."""
        orch = LangGraphOrchestrator(root=ROOT)
        assert orch._graph is not None
        assert orch._checkpointer is None

    def test_init_with_checkpoint(self, tmp_path):
        """Can initialize with checkpoint path for crash recovery."""
        cp = tmp_path / "checkpoints.db"
        orch = LangGraphOrchestrator(root=ROOT, checkpoint_path=cp)
        assert orch._graph is not None
        assert orch._checkpointer is not None
        assert cp.exists()

    def test_summary(self):
        """Summary returns graph info."""
        orch = LangGraphOrchestrator(root=ROOT)
        s = orch.summary()
        assert s["orchestrator_version"] == ORCHESTRATOR_VERSION
        assert "routing" in s["graph_nodes"]
        assert "primary" in s["graph_nodes"]
        assert "diagnostics" in s["graph_nodes"]
        assert s["checkpointing_enabled"] is False
        assert s["truth_effect"] == "NONE"

    def test_summary_with_checkpoint(self, tmp_path):
        """Summary shows checkpointing enabled."""
        cp = tmp_path / "cp.db"
        orch = LangGraphOrchestrator(root=ROOT, checkpoint_path=cp)
        s = orch.summary()
        assert s["checkpointing_enabled"] is True

    def test_run_basic(self, tmp_path):
        """Basic run produces output files."""
        input_file = tmp_path / "input.txt"
        input_file.write_text("Test input for LangGraph orchestrator. " * 5)
        out_dir = tmp_path / "output"

        orch = LangGraphOrchestrator(root=ROOT)
        result = orch.run(input_file, out_dir, max_workers=2)

        assert result["status"] in ["COMPLETED", "DEGRADED", "FAILED"]
        assert (out_dir / "META_RUN.json").is_file()

    def test_run_produces_dialectical_graph(self, tmp_path):
        """Run produces DIALECTICAL_GRAPH.json."""
        input_file = tmp_path / "input.txt"
        input_file.write_text("Test input for dialectical analysis. " * 3)
        out_dir = tmp_path / "output"

        orch = LangGraphOrchestrator(root=ROOT)
        orch.run(input_file, out_dir, max_workers=2)

        assert (out_dir / "DIALECTICAL_GRAPH.json").is_file()

    def test_run_produces_tiered_fitness(self, tmp_path):
        """Run produces TIERED_FITNESS.json."""
        input_file = tmp_path / "input.txt"
        input_file.write_text("Test input for fitness evaluation. " * 3)
        out_dir = tmp_path / "output"

        orch = LangGraphOrchestrator(root=ROOT)
        orch.run(input_file, out_dir, max_workers=2)

        assert (out_dir / "TIERED_FITNESS.json").is_file()

    def test_run_produces_state_bus(self, tmp_path):
        """Run produces STATE_BUS.json."""
        input_file = tmp_path / "input.txt"
        input_file.write_text("Test input for state bus. " * 3)
        out_dir = tmp_path / "output"

        orch = LangGraphOrchestrator(root=ROOT)
        orch.run(input_file, out_dir, max_workers=2)

        assert (out_dir / "STATE_BUS.json").is_file()

    def test_run_with_checkpoint(self, tmp_path):
        """Run with checkpointing creates checkpoint database."""
        input_file = tmp_path / "input.txt"
        input_file.write_text("Test input with checkpointing. " * 3)
        out_dir = tmp_path / "output"
        cp = tmp_path / "checkpoints.db"

        orch = LangGraphOrchestrator(root=ROOT, checkpoint_path=cp)
        result = orch.run(input_file, out_dir, max_workers=2, thread_id="test-run-001")

        assert result["status"] in ["COMPLETED", "DEGRADED"]
        assert cp.exists()

    def test_graph_has_7_nodes(self):
        """Graph has exactly 7 phase nodes."""
        orch = LangGraphOrchestrator(root=ROOT)
        s = orch.summary()
        assert len(s["graph_nodes"]) == 7

    def test_truth_effect_none(self):
        """All outputs carry truth_effect=NONE."""
        orch = LangGraphOrchestrator(root=ROOT)
        s = orch.summary()
        assert s["truth_effect"] == "NONE"

    def test_constitution_compliance(self):
        """Constitution compliance flags present."""
        orch = LangGraphOrchestrator(root=ROOT)
        s = orch.summary()
        assert "claim_ceiling" in s
        assert "ORCHESTRATOR" in s["claim_ceiling"]
