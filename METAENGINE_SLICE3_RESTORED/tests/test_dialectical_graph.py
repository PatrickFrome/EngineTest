"""Fix 2: Tests for dialectical_graph.py — previously had NO tests."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.dialectical_graph import DialecticalGraphBuilder
from metaengine.architecture_policy import initial_policy


class TestDialecticalGraph:
    def test_build_returns_dict(self):
        builder = DialecticalGraphBuilder()
        graph = builder.build("test text", "source_1", initial_policy())
        assert isinstance(graph, dict)

    def test_build_has_nodes(self):
        builder = DialecticalGraphBuilder()
        graph = builder.build("test text", "source_1", initial_policy())
        assert "nodes" in graph
        assert len(graph["nodes"]) > 0

    def test_build_has_edges(self):
        builder = DialecticalGraphBuilder()
        graph = builder.build("test text", "source_1", initial_policy())
        assert "edges" in graph

    def test_build_has_graph_hash(self):
        builder = DialecticalGraphBuilder()
        graph = builder.build("test text", "source_1", initial_policy())
        assert "graph_hash" in graph

    def test_build_with_engine_contributions(self):
        """R5: engine_contributions create engine discourse nodes."""
        builder = DialecticalGraphBuilder()
        contribs = [
            {"engine_id": "engine_01", "canonical": {"kind": "test"}, "status": "COMPLETE"},
            {"engine_id": "engine_02", "canonical": {"kind": "different"}, "status": "COMPLETE"},
        ]
        graph = builder.build("test text", "source_1", initial_policy(), engine_contributions=contribs)
        engine_nodes = [n for n in graph["nodes"] if n.get("engine_id")]
        assert len(engine_nodes) >= 2

    def test_build_truth_effect_none(self):
        builder = DialecticalGraphBuilder()
        graph = builder.build("test text", "source_1", initial_policy())
        assert graph.get("claim_ceiling") is not None

    def test_build_metrics(self):
        builder = DialecticalGraphBuilder()
        graph = builder.build("test text", "source_1", initial_policy())
        assert "metrics" in graph
        assert "node_count" in graph["metrics"]
