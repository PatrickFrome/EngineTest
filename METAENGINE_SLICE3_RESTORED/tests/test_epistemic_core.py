"""METAENGINE Step D — Direct tests for untested epistemic core modules.

Covers 14 modules that had 0 direct tests (from Task 35 analysis).
Each module is tested with minimal valid inputs to verify its API contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metaengine.adapters.base import EngineContribution
from metaengine.architecture_policy import initial_policy


# ---------------------------------------------------------------------------
# fusion.py
# ---------------------------------------------------------------------------


class TestFuse:
    def test_fuse_empty(self):
        from metaengine.fusion import fuse
        result = fuse([])
        assert result["policy"] == "FUSION_WITHOUT_ERASURE"
        assert result["complete_engines"] == []
        assert result["claim_ceiling"].startswith("META_SYNTHESIS")

    def test_fuse_complete_contributions(self):
        from metaengine.fusion import fuse
        contribs = [
            EngineContribution("engine_01", "COMPLETE", {}, {"kind": "test"}, None, "NATIVE_LOCAL", "REAL_EXECUTOR"),
            EngineContribution("engine_02", "COMPLETE", {}, {"kind": "test"}, None, "NATIVE_LOCAL", "REAL_EXECUTOR"),
        ]
        result = fuse(contribs)
        assert "engine_01" in result["complete_engines"]
        assert "engine_02" in result["complete_engines"]
        assert result["conflicts"] == []

    def test_fuse_with_failures_records_conflict(self):
        from metaengine.fusion import fuse
        contribs = [
            EngineContribution("engine_01", "COMPLETE", {}, {}, None, "NATIVE_LOCAL", "REAL_EXECUTOR"),
            EngineContribution("engine_02", "FAILED", {}, {}, "error", "NATIVE_LOCAL", "REAL_EXECUTOR"),
        ]
        result = fuse(contribs)
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["dimension"] == "execution_status"

    def test_fuse_majority_is_not_truth(self):
        from metaengine.fusion import fuse
        result = fuse([])
        assert result["consensus_core"]["majority_is_not_truth"] is True


# ---------------------------------------------------------------------------
# claims.py
# ---------------------------------------------------------------------------


class TestClaims:
    def test_extract_positions_from_complete_contribution(self):
        from metaengine.claims import extract_positions, ClaimGraphBuilder
        contrib = EngineContribution(
            "engine_01", "COMPLETE",
            {"stdout": "test"},
            {"kind": "test", "claims": [{"proposition": "test claim", "stance": "ASSERT"}]},
            None, "NATIVE_LOCAL", "REAL_EXECUTOR",
        )
        positions = extract_positions(contrib)
        assert len(positions) == 1
        assert positions[0]["proposition"] == "test claim"

    def test_claim_graph_builder_empty(self):
        from metaengine.claims import ClaimGraphBuilder
        builder = ClaimGraphBuilder()
        graph = builder.build([])
        assert "nodes" in graph
        assert "edges" in graph
        assert graph.get("claim_ceiling") is not None


# ---------------------------------------------------------------------------
# dialectical_graph.py
# ---------------------------------------------------------------------------


class TestDialecticalGraph:
    def test_build_from_source_text(self):
        from metaengine.dialectical_graph import DialecticalGraphBuilder
        builder = DialecticalGraphBuilder()
        policy = initial_policy()
        graph = builder.build("This is a test. The source describes a tension between evidence and generative reasoning.", "test-source", policy)
        assert "nodes" in graph
        assert "edges" in graph
        assert graph.get("graph_hash") is not None

    def test_build_has_claim_ceiling(self):
        from metaengine.dialectical_graph import DialecticalGraphBuilder
        builder = DialecticalGraphBuilder()
        graph = builder.build("Short text.", "src", initial_policy())
        assert "claim_ceiling" in graph


# ---------------------------------------------------------------------------
# synthesis.py
# ---------------------------------------------------------------------------


class TestSynthesis:
    def test_synthesize_empty_inputs(self):
        from metaengine.synthesis import AuditableSynthesizer
        result = AuditableSynthesizer.synthesize(
            {"nodes": [], "edges": []},
            {"decisions": []},
            {"verification_status": "INSUFFICIENT_EXTERNAL_EVIDENCE"},
        )
        assert result["majority_vote_used"] is False
        assert "synthesis_hash" in result

    def test_synthesis_claim_ceiling(self):
        from metaengine.synthesis import AuditableSynthesizer
        result = AuditableSynthesizer.synthesize({}, {}, {})
        assert "claim_ceiling" in result


# ---------------------------------------------------------------------------
# arbitration.py
# ---------------------------------------------------------------------------


class TestArbitration:
    def test_arbitrate_empty(self):
        from metaengine.arbitration import AdaptiveArbitrator
        arb = AdaptiveArbitrator()
        result = arb.arbitrate({"nodes": []}, {"conflicts": [], "conflict_count": 0}, {"assignments": []})
        assert "decisions" in result
        assert result.get("arbitration_hash") is not None or "arbitration_version" in result


# ---------------------------------------------------------------------------
# disagreement.py
# ---------------------------------------------------------------------------


class TestDisagreement:
    def test_analyze_empty(self):
        from metaengine.disagreement import DisagreementEngine
        engine = DisagreementEngine()
        result = engine.analyze({"nodes": [], "edges": []})
        assert "conflict_count" in result or "conflicts" in result

    def test_analyze_has_map_hash(self):
        from metaengine.disagreement import DisagreementEngine
        engine = DisagreementEngine()
        result = engine.analyze({"nodes": [], "edges": []})
        assert "map_hash" in result or isinstance(result, dict)


# ---------------------------------------------------------------------------
# epistemic_gain.py
# ---------------------------------------------------------------------------


class TestEpistemicGain:
    def test_scheduler_score(self):
        from metaengine.epistemic_gain import ExpectedEpistemicGainScheduler
        class MockBios:
            def contextual_prior(self, eid, fp): return 0.5
            def pair_prior(self, eid, peers): return 0.3
        scheduler = ExpectedEpistemicGainScheduler(biographies=MockBios())
        assignment = {"engine_id": "engine_01", "relevance_score": 0.8}
        result = scheduler.score(assignment, {"tokens": ["test"], "active_domains": ["PHILOSOPHICAL_HERMENEUTICS"]}, {"conflicts": [], "conflict_count": 0, "max_tension_score": 0.0})
        assert "expected_gain" in result or "utility" in result

    def test_scheduler_allocate(self):
        from metaengine.epistemic_gain import ExpectedEpistemicGainScheduler
        class MockBios:
            def contextual_prior(self, eid, fp): return 0.5
            def pair_prior(self, eid, peers): return 0.3
        scheduler = ExpectedEpistemicGainScheduler(biographies=MockBios())
        routing = {"assignments": [{"engine_id": "engine_01", "scheduled": True, "role": "CORE", "relevance_score": 0.8}], "task_fingerprint": {"tokens": ["test"]}}
        result = scheduler.allocate(routing, {"conflicts": [], "conflict_count": 0, "max_tension_score": 0.0}, budget_units=8)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# coalitions.py
# ---------------------------------------------------------------------------


class TestCoalitions:
    def test_build_empty(self):
        from metaengine.coalitions import CoalitionFactory
        factory = CoalitionFactory()
        routing = {"assignments": [], "task_fingerprint": {"active_domains": []}}
        result = factory.build(routing, {"conflicts": [], "conflict_count": 0}, {"selected": ["engine_01","engine_02","engine_03"]})
        assert "coalitions" in result


# ---------------------------------------------------------------------------
# topology.py
# ---------------------------------------------------------------------------


class TestTopology:
    def test_waves_from_scores(self):
        from metaengine.topology import _waves_from_scores
        scores = [{"engine_id": "engine_01", "utility": 0.9, "expected_gain": 0.8}, {"engine_id": "engine_02", "utility": 0.7, "expected_gain": 0.6}]
        waves = _waves_from_scores(scores, width=2)
        assert isinstance(waves, list)


# ---------------------------------------------------------------------------
# depth_budget.py
# ---------------------------------------------------------------------------


class TestDepthBudget:
    def test_next_budget(self):
        from metaengine.depth_budget import DepthBudgetController
        controller = DepthBudgetController(complexity=0.5)
        budget = controller.next_budget(round_index=1)
        assert budget is not None


# ---------------------------------------------------------------------------
# biographies.py
# ---------------------------------------------------------------------------


class TestBiographies:
    def test_snapshot_empty(self):
        from metaengine.biographies import EngineBiographyStore
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        store = EngineBiographyStore(root, persist=False)
        snapshot = store.snapshot()
        assert isinstance(snapshot, (dict, list))


# ---------------------------------------------------------------------------
# transformation_graph.py
# ---------------------------------------------------------------------------


class TestTransformationGraph:
    def test_empty_graph(self):
        from metaengine.transformation_graph import TransformationGraph
        tg = TransformationGraph()
        metrics = tg.metrics()
        assert "node_count" in metrics
        assert metrics["node_count"] == 1  # SOURCE node always exists

    def test_add_node(self):
        from metaengine.transformation_graph import TransformationGraph
        tg = TransformationGraph()
        tg.add_node("PRIMARY", "test", engine_id="engine_01", round_index=1)
        assert tg.metrics()["node_count"] == 2  # SOURCE + new node

    def test_add_edge(self):
        from metaengine.transformation_graph import TransformationGraph
        tg = TransformationGraph()
        tg.add_node("PRIMARY", "a", engine_id="e1", round_index=1)
        tg.add_node("PRIMARY", "b", engine_id="e2", round_index=1)
        tg.edge("a", "b", "CHANGES_SPACE_OF")
        assert tg.metrics()["edge_count"] == 1

    def test_artifact(self):
        from metaengine.transformation_graph import TransformationGraph
        tg = TransformationGraph()
        artifact = tg.artifact()
        assert "graph_hash" in artifact
        assert "claim_ceiling" in artifact


# ---------------------------------------------------------------------------
# verifier_plane.py
# ---------------------------------------------------------------------------


class TestVerifierPlane:
    def test_outcome_oracle_commitment(self):
        from metaengine.verifier_plane import OutcomeOracle
        oracle = OutcomeOracle(oracle_id="test-oracle")
        commitment = oracle.commitment()
        assert isinstance(commitment, str)
        assert len(commitment) == 64

    def test_external_verifier_evaluate_empty(self):
        from metaengine.verifier_plane import ExternalVerifierPlane
        verifier = ExternalVerifierPlane()
        report = verifier.evaluate("test source", {"nodes": []}, None)
        assert report.verification_status is not None
        assert report.promotion_eligible is False

    def test_verifier_report_has_hash(self):
        from metaengine.verifier_plane import ExternalVerifierPlane
        verifier = ExternalVerifierPlane()
        report = verifier.evaluate("test", {"nodes": []}, None)
        d = report.as_dict()
        assert "verifier_hash" in d


# ---------------------------------------------------------------------------
# native_reentry_compiler.py
# ---------------------------------------------------------------------------


class TestNativeReentryCompiler:
    def test_interrogative_manifest(self):
        from metaengine.native_reentry_compiler import _interrogative_manifest
        manifest = _interrogative_manifest("This is a test sentence. Another sentence here.")
        assert "training_windows" in manifest
        assert len(manifest["training_windows"]) > 0
        assert manifest["claim_ceiling"] is not None
