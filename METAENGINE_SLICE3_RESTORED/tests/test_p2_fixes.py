"""Tests for P2 Nice-to-Have Fixes (N1, N2, N3, N4, N5).

P0 (C1-C5) wired the modules together. P1 (I1-I6) closed the quality gaps.
P2 closes the "nice-to-have" gaps identified in CRITICAL_ANALYSIS_64_69.md:

  N1 — WebSocket real-time event push (event_publisher + ws-events service)
  N2 — Background health recovery in MultiModelRouter (timer-based reaper)
  N3 — Cost-aware routing (prefer cheaper models for simple tasks)
  N4 — Distillation persistence (save insights across runs)
  N5 — ML-based amplification (learn which amplify rules work)

Constitution compliance:
  - All fixes preserve truth_effect=NONE
  - No auto-promotion, no code modification
  - Background reaper is observable + bounded
  - Cost-aware routing is transparent (doesn't change outputs)
  - Distillation history is observational (doesn't promote insights to truth)
  - Rule weights are bounded [0.1, 3.0] and observable
  - Events are append-only + observational
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.multi_model_router import (
    MultiModelRouter,
    ModelBackend,
    BackendHealth,
    create_default_router,
)
from metaengine.amplify_distill import (
    AmplifyDistillCycle,
    IDA_VERSION,
)
from metaengine.event_publisher import (
    publish_event,
    read_events_since,
    get_event_count,
    reset_event_log,
    publisher_state,
    EVENT_PUBLISHER_VERSION,
)


# ---------------------------------------------------------------------------
# N1: Event Publisher
# ---------------------------------------------------------------------------


class TestN1EventPublisher:
    """N1: Event publisher writes events to a shared JSONL log."""

    def setup_method(self):
        reset_event_log()

    def teardown_method(self):
        reset_event_log()

    def test_publish_event_returns_hash(self):
        h = publish_event("test.event", {"key": "value"})
        assert h is not None
        assert len(h) == 64  # SHA-256 hex

    def test_published_event_carries_truth_effect_none(self):
        publish_event("test.event", {"x": 1})
        events, _ = read_events_since(0)
        assert len(events) == 1
        assert events[0]["truth_effect"] == "NONE"
        assert events[0]["claim_ceiling"] == "EVENT_IS_OBSERVATIONAL_NOT_TRUTH"

    def test_published_event_has_type_and_timestamp(self):
        publish_event("fitness.evaluated", {"fitness": 0.85})
        events, _ = read_events_since(0)
        assert events[0]["type"] == "fitness.evaluated"
        assert "timestamp" in events[0]
        assert "T" in events[0]["timestamp"]  # ISO format

    def test_read_events_since_offset(self):
        for i in range(5):
            publish_event("test.event", {"index": i})
        events_all, offset = read_events_since(0)
        assert len(events_all) == 5
        # Read from the middle
        events_partial, _ = read_events_since(offset // 2)
        assert len(events_partial) < 5  # fewer events from middle

    def test_get_event_count(self):
        assert get_event_count() == 0
        publish_event("a", {})
        publish_event("b", {})
        assert get_event_count() == 2

    def test_reset_event_log(self):
        publish_event("test", {})
        assert get_event_count() == 1
        reset_event_log()
        assert get_event_count() == 0

    def test_publisher_state(self):
        publish_event("test", {"x": 1})
        state = publisher_state()
        assert state["event_publisher_version"] == EVENT_PUBLISHER_VERSION
        assert state["event_count"] == 1
        assert state["log_size_bytes"] > 0
        assert state["truth_effect"] == "NONE"

    def test_publish_failure_is_non_fatal(self):
        """Publishing should never raise — failures are swallowed."""
        # Pass an unserializable object (shouldn't crash, just returns None)
        h = publish_event("test.event", {"unserializable": object()})
        # object() isn't JSON-serializable → publish fails silently → returns None
        # OR it succeeds via default=str. Either way, no exception.
        assert h is None or isinstance(h, str)

    def test_multiple_event_types(self):
        publish_event("fitness.evaluated", {"tier": "L2", "fitness": 0.9})
        publish_event("recursive.generation", {"gen": 0, "mean": 0.85})
        publish_event("router.failover", {"from": "glm-1", "to": "glm-thinking"})
        publish_event("api.rate_limited", {"endpoint": "/api/benchmark/run"})
        events, _ = read_events_since(0)
        assert len(events) == 4
        assert events[0]["type"] == "fitness.evaluated"
        assert events[1]["type"] == "recursive.generation"
        assert events[2]["type"] == "router.failover"
        assert events[3]["type"] == "api.rate_limited"


# ---------------------------------------------------------------------------
# N2: Background Health Recovery
# ---------------------------------------------------------------------------


class TestN2BackgroundReaper:
    """N2: MultiModelRouter has a background reaper that recovers unhealthy backends."""

    def test_router_has_reaper_state(self):
        r = MultiModelRouter()
        s = r.summary()
        assert "background_recovery" in s
        assert s["background_recovery"]["enabled"] is False
        assert s["background_recovery"]["total_probes"] == 0
        assert s["background_recovery"]["total_recovered"] == 0

    def test_reap_now_probes_unhealthy_backends(self):
        r = MultiModelRouter()
        r.add_backend("b1", "m1", "http://localhost:3031/v1/chat/completions")
        b1 = r.backends[0]
        b1.health = BackendHealth.UNHEALTHY
        b1.failure_count = 3
        b1.last_failure_time = 0  # cooldown expired (far in past)

        # Inject a probe that returns True (backend is healthy now)
        r._probe_fn = lambda backend: True
        result = r.reap_now()

        assert result["probed"] == 1
        assert result["recovered"] == 1
        assert b1.health == BackendHealth.HEALTHY
        assert b1.failure_count == 0

    def test_reap_skips_backends_in_cooldown(self):
        r = MultiModelRouter()
        r.add_backend("b1", "m1")
        b1 = r.backends[0]
        b1.health = BackendHealth.UNHEALTHY
        b1.failure_count = 3
        b1.last_failure_time = time.time()  # just failed → cooldown NOT expired

        r._probe_fn = lambda backend: True
        result = r.reap_now()

        assert result["probed"] == 1
        assert result["recovered"] == 0
        assert result["skipped_cooldown"] == 1
        assert b1.health == BackendHealth.UNHEALTHY  # still unhealthy

    def test_reap_marks_still_unhealthy_when_probe_fails(self):
        r = MultiModelRouter()
        r.add_backend("b1", "m1")
        b1 = r.backends[0]
        b1.health = BackendHealth.UNHEALTHY
        b1.failure_count = 3
        b1.last_failure_time = 0  # cooldown expired

        r._probe_fn = lambda backend: False  # probe fails
        result = r.reap_now()

        assert result["probed"] == 1
        assert result["still_unhealthy"] == 1
        assert b1.health == BackendHealth.UNHEALTHY

    def test_reaper_can_be_started_and_stopped(self):
        r = MultiModelRouter(background_health_recovery=True, health_recovery_interval=0.1)
        assert r._reaper_thread is not None
        assert r._reaper_thread.is_alive()
        r.stop_reaper()
        assert r._reaper_thread is None or not r._reaper_thread.is_alive()

    def test_reaper_doesnt_crash_on_probe_exception(self):
        r = MultiModelRouter()
        r.add_backend("b1", "m1")
        b1 = r.backends[0]
        b1.health = BackendHealth.UNHEALTHY
        b1.failure_count = 3
        b1.last_failure_time = 0

        # Probe that raises an exception
        def bad_probe(backend):
            raise RuntimeError("probe failed")

        r._probe_fn = bad_probe
        result = r.reap_now()
        # Should not crash; backend stays unhealthy
        assert result["still_unhealthy"] == 1
        assert b1.health == BackendHealth.UNHEALTHY

    def test_summary_includes_reaper_stats(self):
        r = MultiModelRouter()
        r.add_backend("b1", "m1")
        b1 = r.backends[0]
        b1.health = BackendHealth.UNHEALTHY
        b1.failure_count = 3
        b1.last_failure_time = 0
        r._probe_fn = lambda backend: True
        r.reap_now()
        s = r.summary()
        assert s["background_recovery"]["total_probes"] == 1
        assert s["background_recovery"]["total_recovered"] == 1
        assert s["background_recovery"]["recovery_rate"] == 1.0

    def test_constitution_compliance(self):
        r = MultiModelRouter()
        s = r.summary()
        assert s["truth_effect"] == "NONE"
        assert s["constitution_compliance"]["reaper_bounded"] is True
        assert s["constitution_compliance"]["reaper_observational"] is True


# ---------------------------------------------------------------------------
# N3: Cost-Aware Routing
# ---------------------------------------------------------------------------


class TestN3CostAwareRouting:
    """N3: Router prefers cheaper backends for simple tasks."""

    def test_router_has_cost_aware_state(self):
        r = MultiModelRouter()
        s = r.summary()
        assert "cost_aware" in s
        assert s["cost_aware"]["enabled"] is True
        assert s["cost_aware"]["simple_prompt_max_chars"] > 0
        assert s["cost_aware"]["simple_max_tokens"] > 0

    def test_backend_has_cost_score_and_capability_tier(self):
        b = ModelBackend(model_id="test", model_name="m", endpoint="http://x", cost_score=0.5, capability_tier="simple")
        p = b.payload()
        assert p["cost_score"] == 0.5
        assert p["capability_tier"] == "simple"

    def test_simple_task_routes_to_cheap_backend(self):
        r = MultiModelRouter(cost_aware=True)
        r.add_backend("cheap", "cheap-model", "http://x", cost_score=0.5, capability_tier="simple")
        r.add_backend("expensive", "expensive-model", "http://x", cost_score=2.0, capability_tier="complex")

        # Simple task: short prompt + low max_tokens
        backend = r._next_backend(prompt="What is 2+2?", max_tokens=64)
        assert backend.model_id == "cheap"

    def test_complex_task_routes_to_expensive_backend(self):
        r = MultiModelRouter(cost_aware=True)
        r.add_backend("cheap", "cheap-model", "http://x", cost_score=0.5, capability_tier="simple")
        r.add_backend("expensive", "expensive-model", "http://x", cost_score=2.0, capability_tier="complex")

        # Complex task: long prompt + high max_tokens
        long_prompt = "Analyze: " + "x" * 300
        backend = r._next_backend(prompt=long_prompt, max_tokens=512)
        assert backend.model_id == "expensive"

    def test_cost_aware_can_be_disabled(self):
        r = MultiModelRouter(cost_aware=False)
        r.add_backend("b1", "m1", "http://x", cost_score=0.5, capability_tier="simple")
        r.add_backend("b2", "m2", "http://x", cost_score=2.0, capability_tier="complex")
        # With cost_aware=False, should use round-robin (not cost-based selection)
        # We can't assert which backend is selected (round-robin), but we can verify
        # cost_aware is disabled in the summary
        s = r.summary()
        assert s["cost_aware"]["enabled"] is False

    def test_no_simple_tier_falls_back_to_cheapest(self):
        r = MultiModelRouter(cost_aware=True)
        r.add_backend("std1", "m1", "http://x", cost_score=1.0, capability_tier="standard")
        r.add_backend("std2", "m2", "http://x", cost_score=1.5, capability_tier="standard")
        # Simple task but no "simple" tier backends → should pick cheapest standard
        backend = r._next_backend(prompt="Hi", max_tokens=32)
        assert backend.model_id == "std1"  # lower cost_score

    def test_create_default_router_has_cost_metadata(self):
        r = create_default_router()
        backends = r.backends
        assert len(backends) == 2
        # glm-1 is standard cost
        glm1 = next(b for b in backends if b.model_id == "glm-1")
        assert glm1.cost_score == 1.0
        assert glm1.capability_tier == "standard"
        # glm-thinking is expensive + complex
        glm_thinking = next(b for b in backends if b.model_id == "glm-thinking")
        assert glm_thinking.cost_score == 1.5
        assert glm_thinking.capability_tier == "complex"

    def test_is_simple_task_classification(self):
        r = MultiModelRouter(cost_aware=True)
        assert r._is_simple_task("short", 64) is True
        assert r._is_simple_task("long" * 100, 64) is False  # long prompt
        assert r._is_simple_task("short", 512) is False  # high max_tokens

    def test_constitution_compliance(self):
        r = MultiModelRouter(cost_aware=True)
        s = r.summary()
        assert s["constitution_compliance"]["cost_aware_transparent"] is True
        assert s["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# N4: Distillation Persistence
# ---------------------------------------------------------------------------


class TestN4DistillationPersistence:
    """N4: AmplifyDistillCycle persists distillations to a JSON file across runs."""

    def test_cycle_without_persistence_works(self):
        cycle = AmplifyDistillCycle()
        assert cycle.persistence_path is None
        assert cycle.get_persisted_history() == []

    def test_distill_persists_to_file(self, tmp_path):
        hist_path = tmp_path / "history.json"
        cycle = AmplifyDistillCycle(persistence_path=hist_path)
        metrics = {
            "rlaif_reward": 0.5, "pbt_best_fitness": 0.6, "es_best_fitness": 0.6,
            "es_converged": False, "marl_foe_mean": 0.02, "faithfulness_mean": 0.61,
            "redteam_violation_rate": 0.0, "transfer_rate": 0.57,
        }
        cycle.distill(campaign_result={"metrics": metrics}, gen_metrics=metrics, previous_metrics=None, generation=0)
        assert hist_path.is_file()
        data = json.loads(hist_path.read_text())
        assert data["total_distillations"] == 1
        assert data["truth_effect"] == "NONE"

    def test_persistence_accumulates_across_runs(self, tmp_path):
        hist_path = tmp_path / "history.json"
        # Run 1
        cycle1 = AmplifyDistillCycle(persistence_path=hist_path)
        metrics1 = {"rlaif_reward": 0.5, "pbt_best_fitness": 0.6, "es_best_fitness": 0.6, "es_converged": False, "marl_foe_mean": 0.02, "faithfulness_mean": 0.61, "redteam_violation_rate": 0.0, "transfer_rate": 0.57}
        cycle1.distill(campaign_result={"metrics": metrics1}, gen_metrics=metrics1, previous_metrics=None, generation=0)
        # Run 2 — new cycle, should load existing history
        cycle2 = AmplifyDistillCycle(persistence_path=hist_path)
        assert len(cycle2.get_persisted_history()) == 1
        # Add another
        metrics2 = dict(metrics1)
        metrics2["rlaif_reward"] = 0.6
        cycle2.distill(campaign_result={"metrics": metrics2}, gen_metrics=metrics2, previous_metrics=metrics1, generation=1)
        # File should now have 2 entries
        data = json.loads(hist_path.read_text())
        assert data["total_distillations"] == 2

    def test_persistence_is_idempotent(self, tmp_path):
        hist_path = tmp_path / "history.json"
        cycle = AmplifyDistillCycle(persistence_path=hist_path)
        metrics = {"rlaif_reward": 0.5}
        r1 = cycle.distill(campaign_result={"metrics": metrics}, gen_metrics=metrics, previous_metrics=None, generation=0)
        # Persist the same distillation again
        cycle._persist_distillation(r1, metrics, None)
        data = json.loads(hist_path.read_text())
        assert data["total_distillations"] == 1  # not 2

    def test_persisted_history_has_insights(self, tmp_path):
        hist_path = tmp_path / "history.json"
        cycle = AmplifyDistillCycle(persistence_path=hist_path)
        m1 = {"rlaif_reward": 0.5, "pbt_best_fitness": 0.6, "es_best_fitness": 0.6, "es_converged": False, "marl_foe_mean": 0.02, "faithfulness_mean": 0.61, "redteam_violation_rate": 0.0, "transfer_rate": 0.57}
        m2 = {"rlaif_reward": 0.6, "pbt_best_fitness": 0.7, "es_best_fitness": 0.7, "es_converged": False, "marl_foe_mean": 0.02, "faithfulness_mean": 0.65, "redteam_violation_rate": 0.0, "transfer_rate": 0.57}
        cycle.distill(campaign_result={"metrics": m1}, gen_metrics=m1, previous_metrics=None, generation=0)
        cycle.distill(campaign_result={"metrics": m2}, gen_metrics=m2, previous_metrics=m1, generation=1)
        insights = cycle.get_persisted_insights()
        assert len(insights) > 0
        # Should contain improvement notes
        assert any("improved" in s for s in insights)

    def test_summary_includes_persistence_state(self, tmp_path):
        hist_path = tmp_path / "history.json"
        cycle = AmplifyDistillCycle(persistence_path=hist_path)
        s = cycle.summary()
        assert "persistence" in s
        assert s["persistence"]["enabled"] is True
        assert s["persistence"]["persisted_count"] == 0

    def test_persistence_is_observational_not_truth(self, tmp_path):
        hist_path = tmp_path / "history.json"
        cycle = AmplifyDistillCycle(persistence_path=hist_path)
        s = cycle.summary()
        assert s["truth_effect"] == "NONE"
        assert s["constitution_compliance"]["persistence_observational"] is True

    def test_persistence_records_improvement_delta(self, tmp_path):
        hist_path = tmp_path / "history.json"
        cycle = AmplifyDistillCycle(persistence_path=hist_path)
        m1 = {"rlaif_reward": 0.5}
        m2 = {"rlaif_reward": 0.6}
        cycle.distill(campaign_result={"metrics": m1}, gen_metrics=m1, previous_metrics=None, generation=0)
        cycle.distill(campaign_result={"metrics": m2}, gen_metrics=m2, previous_metrics=m1, generation=1)
        history = cycle.get_persisted_history()
        # Second entry should have improvement_delta
        assert history[1]["improvement_delta"] == 0.1


# ---------------------------------------------------------------------------
# N5: ML-Based Amplification
# ---------------------------------------------------------------------------


class TestN5MLAmplification:
    """N5: AmplifyDistillCycle learns rule weights from improvement signals."""

    BAD_METRICS = {
        "rlaif_reward": 0.2, "pbt_best_fitness": 0.3, "es_best_fitness": 0.3,
        "es_converged": False, "marl_foe_mean": 0.01, "faithfulness_mean": 0.3,
        "redteam_violation_rate": 0.1, "transfer_rate": 0.1,
    }

    def test_cycle_has_ml_amplification_state(self):
        cycle = AmplifyDistillCycle(ml_amplification=True)
        s = cycle.summary()
        assert "ml_amplification" in s
        assert s["ml_amplification"]["enabled"] is True
        assert len(s["ml_amplification"]["rule_weights"]) == 7

    def test_rule_weights_start_at_1(self):
        cycle = AmplifyDistillCycle(ml_amplification=True)
        weights = cycle.get_rule_weights()
        assert all(w == 1.0 for w in weights.values())
        assert len(weights) == 7  # 7 amplify rules

    def test_ml_disabled_returns_neutral_weight(self):
        cycle = AmplifyDistillCycle(ml_amplification=False)
        weights = cycle.get_rule_weights()
        # Weights are tracked but not applied (amplify uses 1.0 when ml_amplification=False)
        assert all(w == 1.0 for w in weights.values())

    def test_amplify_tracks_fired_rules(self):
        cycle = AmplifyDistillCycle(ml_amplification=True)
        cycle.amplify(self.BAD_METRICS, generation=0)
        # All 7 rules should fire for bad metrics
        assert len(cycle._last_fired_rules) == 7

    def test_distill_updates_weights_on_improvement(self):
        cycle = AmplifyDistillCycle(ml_amplification=True, rule_learning_rate=0.5)
        # Gen 0: amplify + distill (no baseline)
        cycle.amplify(self.BAD_METRICS, generation=0)
        cycle.distill(campaign_result={"metrics": self.BAD_METRICS}, gen_metrics=self.BAD_METRICS, previous_metrics=None, generation=0)
        weights_before = cycle.get_rule_weights()
        assert all(w == 1.0 for w in weights_before.values())  # no update without baseline

        # Gen 1: amplify + distill with IMPROVEMENT
        good = dict(self.BAD_METRICS)
        good["rlaif_reward"] = 0.5  # +0.3 improvement
        cycle.amplify(good, previous_config=cycle.amplifications[-1].amplified_config, generation=1)
        fired_gen1 = list(cycle._last_fired_rules)
        cycle.distill(campaign_result={"metrics": good}, gen_metrics=good, previous_metrics=self.BAD_METRICS, generation=1)
        weights_after = cycle.get_rule_weights()
        # Fired rules should have INCREASED weight
        for rule in fired_gen1:
            assert weights_after[rule] > 1.0, f"{rule} should have increased, got {weights_after[rule]}"

    def test_distill_updates_weights_on_regression(self):
        cycle = AmplifyDistillCycle(ml_amplification=True, rule_learning_rate=0.5)
        # Gen 0: amplify with bad metrics + distill
        cycle.amplify(self.BAD_METRICS, generation=0)
        m_good = dict(self.BAD_METRICS)
        m_good["rlaif_reward"] = 0.5
        cycle.distill(campaign_result={"metrics": m_good}, gen_metrics=m_good, previous_metrics=self.BAD_METRICS, generation=0)
        weights_after_improvement = cycle.get_rule_weights()

        # Gen 1: amplify + distill with REGRESSION
        m_worse = dict(m_good)
        m_worse["rlaif_reward"] = 0.2  # -0.3 regression
        cycle.amplify(m_worse, previous_config=cycle.amplifications[-1].amplified_config, generation=1)
        fired_gen1 = list(cycle._last_fired_rules)
        cycle.distill(campaign_result={"metrics": m_worse}, gen_metrics=m_worse, previous_metrics=m_good, generation=1)
        weights_after_regression = cycle.get_rule_weights()
        # Fired rules should have DECREASED weight
        for rule in fired_gen1:
            assert weights_after_regression[rule] < weights_after_improvement[rule], f"{rule} should have decreased"

    def test_rule_weights_are_bounded(self):
        cycle = AmplifyDistillCycle(ml_amplification=True, rule_learning_rate=1.0)
        # Hammer with extreme positive improvements
        prev = dict(self.BAD_METRICS)
        for i in range(20):
            curr = dict(prev)
            curr["rlaif_reward"] = prev["rlaif_reward"] + 0.5  # huge improvement
            cycle.amplify(curr, previous_config=(cycle.amplifications[-1].amplified_config if cycle.amplifications else None), generation=i)
            cycle.distill(campaign_result={"metrics": curr}, gen_metrics=curr, previous_metrics=prev, generation=i)
            prev = curr
        weights = cycle.get_rule_weights()
        for w in weights.values():
            assert w <= 3.0, f"weight {w} exceeds upper bound 3.0"
            assert w >= 0.1, f"weight {w} below lower bound 0.1"

    def test_rule_weight_history_is_recorded(self):
        cycle = AmplifyDistillCycle(ml_amplification=True)
        cycle.amplify(self.BAD_METRICS, generation=0)
        good = dict(self.BAD_METRICS)
        good["rlaif_reward"] = 0.5
        cycle.distill(campaign_result={"metrics": good}, gen_metrics=good, previous_metrics=self.BAD_METRICS, generation=0)
        history = cycle.get_rule_weight_history()
        assert len(history) == 1
        assert "improvement" in history[0]
        assert "fired_rules" in history[0]
        assert "updates" in history[0]

    def test_amplify_with_high_weight_scales_change_more(self):
        cycle = AmplifyDistillCycle(ml_amplification=True, rule_learning_rate=1.0)
        # Manually boost the temperature rule's weight to 3.0
        cycle._rule_weights["rlaif_low_increase_temperature"] = 3.0
        # Amplify with bad rlaif_reward → rule fires
        amp = cycle.amplify(self.BAD_METRICS, generation=0)
        # The temperature change should be larger than the default (weight=1.0)
        # Default change: 0.4 * 1.2 - 0.4 = 0.08
        # With weight 3.0: 0.4 + (0.08 * 3.0) = 0.64
        new_temp = amp.amplified_config.get("llm_temperature", 0.4)
        # Should be higher than the default (0.48)
        assert new_temp > 0.48, f"expected boosted temperature > 0.48, got {new_temp}"

    def test_constitution_compliance(self):
        cycle = AmplifyDistillCycle(ml_amplification=True)
        s = cycle.summary()
        assert s["truth_effect"] == "NONE"
        assert s["constitution_compliance"]["rule_weights_bounded"] is True
        assert s["constitution_compliance"]["rule_weights_observational"] is True


# ---------------------------------------------------------------------------
# Cross-cutting: P2 doesn't break constitution compliance
# ---------------------------------------------------------------------------


class TestP2ConstitutionCompliance:
    """All P2 fixes preserve truth_effect=NONE and K0 invariants."""

    def test_event_publisher_truth_effect_none(self):
        reset_event_log()
        publish_event("test", {"x": 1})
        events, _ = read_events_since(0)
        assert events[0]["truth_effect"] == "NONE"
        reset_event_log()

    def test_router_truth_effect_none(self):
        r = MultiModelRouter()
        s = r.summary()
        assert s["truth_effect"] == "NONE"

    def test_cycle_truth_effect_none(self):
        cycle = AmplifyDistillCycle()
        s = cycle.summary()
        assert s["truth_effect"] == "NONE"

    def test_no_code_modification_attrs(self):
        r = MultiModelRouter()
        assert not hasattr(r, "modify_code")
        cycle = AmplifyDistillCycle()
        assert not hasattr(cycle, "modify_code")

    def test_no_auto_promotion_attrs(self):
        r = MultiModelRouter()
        assert not hasattr(r, "promote")
        assert not hasattr(r, "auto_promote")
        cycle = AmplifyDistillCycle()
        assert not hasattr(cycle, "promote")
        assert not hasattr(cycle, "auto_promote")


# ---------------------------------------------------------------------------
# L2 Fallback Fix (found during massive test series)
# ---------------------------------------------------------------------------


class TestL2FallbackFix:
    """L2 fallback tracking: when L2 fails, tier stays L1, budget not consumed."""

    def test_evaluate_l2_returns_tuple(self):
        """_evaluate_l2 now returns (score, fell_back, metadata) tuple."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        from unittest.mock import patch
        import json as _json
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=2, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        # Mock urlopen to raise (simulates bridge down)
        with patch("urllib.request.urlopen", side_effect=Exception("bridge down")):
            result = adapter._evaluate_l2(theta)
        assert isinstance(result, tuple)
        assert len(result) == 3
        score, fell_back, metadata = result
        assert isinstance(score, float)
        assert isinstance(fell_back, bool)
        assert isinstance(metadata, dict)
        assert fell_back is True  # bridge down → fallback

    def test_evaluate_l2_success_returns_fell_back_false(self):
        """When L2 succeeds, fell_back is False."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        from unittest.mock import patch
        import json as _json
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=2, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        mock_response = {
            "choices": [{"message": {"content": "391. This is generative-only."}}]
        }
        # R2.4: Force the math task (17*23=391) so the test is deterministic
        with patch("metaengine.tiered_fitness.random.choice", return_value=adapter.L2_TASKS[0]), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = _json.dumps(mock_response).encode()
            score, fell_back, metadata = adapter._evaluate_l2(theta)
        assert fell_back is False  # real L2 success
        assert score >= 0.7  # R2.1: correct + disclaimer (0.1 + 0.6 + 0.2 = 0.9, or 0.7 if not verified)
        assert metadata["correct"] is True

    def test_l2_fallback_does_not_consume_budget(self):
        """When L2 falls back, L2 budget is NOT consumed."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter, FitnessTier
        from unittest.mock import patch
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=2, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        adapter.start_generation()
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        # Mock urlopen to raise (bridge down → L2 falls back)
        with patch("urllib.request.urlopen", side_effect=Exception("bridge down")):
            result = adapter.evaluate(theta)
        # Budget should NOT be consumed (L2 fell back)
        assert adapter._l2_calls_this_gen == 0, f"budget should be 0, got {adapter._l2_calls_this_gen}"
        # Tier should be L1 (not L2_REAL_LLM)
        assert result.tier == FitnessTier.L1_CONSTITUTION, f"tier should be L1, got {result.tier.value}"

    def test_l2_fallback_tracks_count(self):
        """L2 fallback count is tracked in summary."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        from unittest.mock import patch
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=2, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        adapter.start_generation()
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        with patch("urllib.request.urlopen", side_effect=Exception("bridge down")):
            adapter.evaluate(theta)
        s = adapter.summary()
        assert s["l2_fallback_count"] >= 1, f"fallback count should be >=1, got {s.get('l2_fallback_count', 0)}"

    def test_l2_fallback_does_not_update_surrogate(self):
        """When L2 falls back, surrogate is NOT updated (no false learning)."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        from unittest.mock import patch
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=2, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
            surrogate_learning_rate=0.5,
        )
        adapter.start_generation()
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        with patch("urllib.request.urlopen", side_effect=Exception("bridge down")):
            adapter.evaluate(theta)
        # Surrogate should have 0 observations (no update on fallback)
        s = adapter.summary()
        assert s["surrogate"]["observation_count"] == 0, f"surrogate should have 0 obs, got {s['surrogate']['observation_count']}"

    def test_l2_fallback_publishes_event(self):
        """L2 fallback publishes fitness.l2_fallback event."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        from metaengine.event_publisher import reset_event_log, read_events_since
        from unittest.mock import patch
        reset_event_log()
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=2, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        adapter.start_generation()
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        with patch("urllib.request.urlopen", side_effect=Exception("bridge down")):
            adapter.evaluate(theta)
        events, _ = read_events_since(0)
        fallback_events = [e for e in events if e["type"] == "fitness.l2_fallback"]
        assert len(fallback_events) >= 1, f"should have l2_fallback event, got {len(fallback_events)}"
        assert fallback_events[0]["payload"]["tier"] == "L2_FALLBACK_TO_L1"


# ---------------------------------------------------------------------------
# P0-Enhanced Self-Improvement Fixes (R2.1, R3.3, R2.4, R1.1, R1.2, R6.2, R5.2)
# ---------------------------------------------------------------------------


class TestP0EnhancedFixes:
    """Tests for the P0-enhanced self-improvement fixes."""

    def test_r21_l2_scoring_correctness_dominant(self):
        """R2.1: Correct answer scores much higher than wrong+disclaimer."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        from unittest.mock import patch
        import json as _json
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=2, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        
        # Correct + disclaimer → should be >= 0.7
        mock_correct = {"choices": [{"message": {"content": "391. This is generative-only."}}]}
        with patch("metaengine.tiered_fitness.random.choice", return_value=adapter.L2_TASKS[0]), \
             patch("urllib.request.urlopen") as mock:
            mock.return_value.__enter__.return_value.read.return_value = _json.dumps(mock_correct).encode()
            score_correct, _, meta = adapter._evaluate_l2(theta)
        
        # Wrong + disclaimer → should be <= 0.3
        mock_wrong = {"choices": [{"message": {"content": "400. This is generative-only."}}]}
        with patch("metaengine.tiered_fitness.random.choice", return_value=adapter.L2_TASKS[0]), \
             patch("urllib.request.urlopen") as mock:
            mock.return_value.__enter__.return_value.read.return_value = _json.dumps(mock_wrong).encode()
            score_wrong, _, meta_w = adapter._evaluate_l2(theta)
        
        assert score_correct > score_wrong + 0.3, f"correct ({score_correct}) should be >> wrong ({score_wrong})"
        assert score_wrong <= 0.3, f"wrong answer should be <= 0.3, got {score_wrong}"

    def test_r33_execution_verification_math(self):
        """R3.3: Math tasks are verified by execution (ground truth)."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        from unittest.mock import patch
        import json as _json
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=2, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        
        # 17*23=391 — correct answer
        mock_response = {"choices": [{"message": {"content": "391"}}]}
        with patch("metaengine.tiered_fitness.random.choice", return_value=adapter.L2_TASKS[0]), \
             patch("urllib.request.urlopen") as mock:
            mock.return_value.__enter__.return_value.read.return_value = _json.dumps(mock_response).encode()
            score, _, meta = adapter._evaluate_l2(theta)
        
        assert meta["verified"] is True, f"math should be verified, got {meta.get('verified')}"
        assert meta["correct"] is True
        assert meta["task_type"] == "math"

    def test_r24_expanded_task_bank(self):
        """R2.4: Task bank has 12+ tasks with metadata."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=2)
        assert len(adapter.L2_TASKS) >= 12, f"expected 12+ tasks, got {len(adapter.L2_TASKS)}"
        # Each task should have metadata
        for task in adapter.L2_TASKS:
            assert "prompt" in task
            assert "check" in task
            assert "task_type" in task
            assert "difficulty" in task

    def test_r12_convergence_criterion(self):
        """R1.2: run() accepts convergence_threshold + convergence_patience params."""
        from metaengine.real_recursive import RealRecursiveRunner
        runner = RealRecursiveRunner(root=ROOT, l2_budget=0, num_pbt_generations=1, pbt_population_size=2)
        # Just verify the params are accepted (don't need to run)
        import inspect
        sig = inspect.signature(runner.run)
        assert "convergence_threshold" in sig.parameters
        assert "convergence_patience" in sig.parameters

    def test_r52_ucb_state_in_summary(self):
        """R5.2: Summary includes UCB acquisition state."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=2)
        s = adapter.summary()
        assert "ucb" in s
        assert "exploration_constant" in s["ucb"]
        assert "total_l2_evals" in s["ucb"]
        assert "unique_thetas_evaluated" in s["ucb"]
        assert s["ucb"]["total_l2_evals"] == 0  # no L2 evals yet

    def test_r52_ucb_gives_exploration_bonus(self):
        """R5.2: UCB gives higher score to under-evaluated thetas."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=2, ucb_exploration=0.5)
        
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        
        # Before any L2 evals: UCB score should include exploration bonus
        ucb_before = adapter._ucb_score(theta, l0_score=0.8)
        
        # Simulate one L2 eval of this theta
        adapter._record_l2_eval(theta)
        adapter._total_l2_evals = 1
        
        # After 1 eval: UCB score should be lower (less exploration needed)
        ucb_after = adapter._ucb_score(theta, l0_score=0.8)
        
        assert ucb_before > ucb_after, f"UCB should decrease after eval ({ucb_before} → {ucb_after})"

    def test_constitution_compliance_preserved(self):
        """All P0-enhanced fixes preserve truth_effect=NONE."""
        from metaengine.tiered_fitness import ThreeTierFitnessAdapter
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=2)
        s = adapter.summary()
        assert s["truth_effect"] == "NONE"
        assert s["constitution_compliance"]["no_truth_promotion"] is True
        assert s["constitution_compliance"]["no_code_modification"] is True
