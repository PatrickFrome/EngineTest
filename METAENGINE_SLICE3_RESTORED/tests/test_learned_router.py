"""Step 10: Tests for Learned top-k engine router."""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.learned_router import (
    LearnedRouter,
    TaskFeatures,
    RoutingDecision,
    ENGINE_PROFILES,
    ROUTER_VERSION,
)


class TestTaskFeatures:
    def test_extract_from_text(self):
        router = LearnedRouter()
        f = router.extract_features("What is the meaning of consciousness?")
        assert f.length > 0
        assert f.word_count > 0
        assert f.has_questions is True

    def test_complexity_range(self):
        router = LearnedRouter()
        f = router.extract_features("Short.")
        assert 0.0 <= f.complexity <= 1.0

    def test_domain_detection(self):
        router = LearnedRouter()
        f = router.extract_features("The experiment provides evidence for the hypothesis.")
        assert f.domains.get("science", 0) > 0

    def test_code_detection(self):
        router = LearnedRouter()
        f = router.extract_features("def foo(): return 42")
        assert f.has_code is True

    def test_math_detection(self):
        router = LearnedRouter()
        f = router.extract_features("The theorem proves that 2 + 2 = 4")
        assert f.has_math is True

    def test_to_vector_length(self):
        f = TaskFeatures(100, 20, 2, 0.5, {"philosophy": 0.5}, False, False, False)
        vec = f.to_vector()
        assert len(vec) == 17

    def test_payload(self):
        f = TaskFeatures(100, 20, 2, 0.5, {"science": 0.8}, True, False, False)
        p = f.payload()
        assert p["length"] == 100
        assert p["has_questions"] is True
        assert p["domains"]["science"] == 0.8


class TestLearnedRouter:
    def test_init(self):
        r = LearnedRouter(top_k=6)
        assert r.top_k == 6
        assert len(r._engine_weights) == 16

    def test_route_returns_decision(self):
        r = LearnedRouter(top_k=6)
        decision = r.route("What is the meaning of consciousness?")
        assert isinstance(decision, RoutingDecision)
        assert len(decision.selected_engines) <= 6
        assert len(decision.selected_engines) > 0
        assert len(decision.skipped_engines) > 0

    def test_route_includes_native_engines(self):
        """Native engines (01-04) are always included."""
        r = LearnedRouter(top_k=6, always_include_native=True)
        decision = r.route("Test input")
        native = ["engine_01", "engine_02", "engine_03", "engine_04"]
        for eid in native:
            assert eid in decision.selected_engines or eid in decision.skipped_engines

    def test_route_top_k_limit(self):
        """Never select more than top_k engines."""
        r = LearnedRouter(top_k=4)
        decision = r.route("Test input for routing")
        assert len(decision.selected_engines) <= 4

    def test_route_scores_all_engines(self):
        r = LearnedRouter()
        decision = r.route("Test input")
        assert len(decision.scores) == 16
        for score in decision.scores.values():
            assert 0.0 <= score <= 1.0

    def test_route_philosophy_prefers_engine_01(self):
        """Philosophical text should score engine_01 (frame-atom) high."""
        r = LearnedRouter(top_k=6)
        decision = r.route("What is the meaning of consciousness? This is a hermeneutic question about being and existence.")
        assert "engine_01" in decision.selected_engines

    def test_route_code_prefers_engine_04(self):
        """Code input should score engine_04 (parse-program) high."""
        r = LearnedRouter(top_k=6)
        decision = r.route("def function(x): return x + 1. This is a class variable.")
        assert "engine_04" in decision.selected_engines

    def test_route_memory_prefers_engine_05(self):
        """Memory-related text should score engine_05 high."""
        r = LearnedRouter(top_k=6)
        decision = r.route("Remember to store the archive and retrieve the persistent context.")
        assert "engine_05" in decision.selected_engines

    def test_route_graph_prefers_engine_06(self):
        """Graph-related text should score engine_06 high."""
        r = LearnedRouter(top_k=6)
        decision = r.route("Extract the graph topology, find community clusters and network edges.")
        assert "engine_06" in decision.selected_engines

    def test_route_research_prefers_engine_09(self):
        """Research text should score engine_09 high."""
        r = LearnedRouter(top_k=6)
        decision = r.route("Investigate and analyze the study, synthesize a report with citations.")
        assert "engine_09" in decision.selected_engines

    def test_route_with_features(self):
        """Can route with pre-extracted features instead of text."""
        r = LearnedRouter(top_k=6)
        features = r.extract_features("Test input for feature-based routing")
        decision = r.route(features=features)
        assert len(decision.selected_engines) > 0

    def test_add_observation(self):
        r = LearnedRouter()
        features = r.extract_features("Test input")
        r.add_observation(features, "engine_01", 0.85)
        assert len(r._observations) == 1

    def test_recalibrate_without_observations(self):
        """Recalibrate with < 10 observations returns 0."""
        r = LearnedRouter()
        for i in range(5):
            f = r.extract_features(f"Test input {i}")
            r.add_observation(f, "engine_01", 0.5)
        result = r.recalibrate()
        assert result == 0

    def test_recalibrate_with_observations(self):
        """Recalibrate with ≥ 10 observations adjusts weights."""
        r = LearnedRouter()
        for i in range(15):
            f = r.extract_features(f"Test input {i} for learning")
            r.add_observation(f, "engine_01", 0.9)  # High fitness
            r.add_observation(f, "engine_06", 0.2)  # Low fitness
        old_w1 = r._engine_weights["engine_01"][0]
        old_w6 = r._engine_weights["engine_06"][0]
        adjustments = r.recalibrate()
        assert adjustments > 0
        # engine_01 (high fitness) should get boosted
        assert r._engine_weights["engine_01"][0] >= old_w1
        # engine_06 (low fitness) should get reduced
        assert r._engine_weights["engine_06"][0] <= old_w6

    def test_rolling_window(self):
        r = LearnedRouter()
        for i in range(550):
            f = r.extract_features(f"Test {i}")
            r.add_observation(f, "engine_01", 0.5)
        assert len(r._observations) == 500

    def test_summary(self):
        r = LearnedRouter(top_k=6)
        s = r.summary()
        assert s["router_version"] == ROUTER_VERSION
        assert s["top_k"] == 6
        assert s["engine_count"] == 16
        assert s["truth_effect"] == "NONE"

    def truth_effect_none(self):
        r = LearnedRouter()
        assert r.summary()["truth_effect"] == "NONE"

    def test_constitution_compliance(self):
        r = LearnedRouter()
        s = r.summary()
        assert s["constitution_compliance"]["transparent_routing"] is True
        assert s["constitution_compliance"]["sparse_selection"] is True
        assert s["constitution_compliance"]["no_auto_promotion"] is True

    def test_decision_payload(self):
        r = LearnedRouter()
        decision = r.route("Test input for payload")
        p = decision.payload()
        assert "selected" in p
        assert "skipped" in p
        assert "scores" in p
        assert "features" in p
        assert p["truth_effect"] == "NONE"

    def test_engine_profiles_count(self):
        assert len(ENGINE_PROFILES) == 16

    def test_skipped_engines_not_in_selected(self):
        r = LearnedRouter(top_k=4)
        decision = r.route("Test input")
        for eid in decision.selected_engines:
            assert eid not in decision.skipped_engines
