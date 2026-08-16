"""Tests for Phase 49 — Shared State Bus."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.state_bus import TrainingStateBus, BUS_VERSION


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_empty_bus(self):
        bus = TrainingStateBus()
        assert bus.rlaif_rewards == {}
        assert bus.pbt_champions == []
        assert bus.alphazero_mechanisms == []
        assert bus.redteam_vulnerabilities == []

    def test_bus_version(self):
        bus = TrainingStateBus()
        assert BUS_VERSION == "METAENGINE-TRAINING-STATE-BUS-2"


# ---------------------------------------------------------------------------
# Tests: Publish methods
# ---------------------------------------------------------------------------


class TestPublish:
    def test_publish_rlaif(self):
        bus = TrainingStateBus()
        bus.publish_rlaif("engine_16", 0.5, 0.9)
        assert bus.rlaif_rewards["engine_16"] == 0.5
        assert bus.rlaif_confidence["engine_16"] == 0.9
        assert bus.last_updated != ""

    def test_publish_pbt(self):
        bus = TrainingStateBus()
        bus.publish_pbt([{"policy": "A"}], 0.89, 3)
        assert len(bus.pbt_champions) == 1
        assert bus.pbt_best_fitness == 0.89
        assert bus.pbt_generation == 3

    def test_publish_alphazero(self):
        bus = TrainingStateBus()
        bus.publish_alphazero(["mech.1", "mech.2"], [{"id": "synth.1"}])
        assert bus.alphazero_mechanisms == ["mech.1", "mech.2"]
        assert len(bus.alphazero_architectures) == 1

    def test_publish_es(self):
        bus = TrainingStateBus()
        bus.publish_es(0.86, True, {"max_rounds": 4})
        assert bus.es_best_fitness == 0.86
        assert bus.es_converged is True
        assert bus.es_best_theta["max_rounds"] == 4

    def test_publish_marl(self):
        bus = TrainingStateBus()
        bus.publish_marl({"engine_16": 0.25}, 0.0, 0.02)
        assert bus.marl_agent_rewards["engine_16"] == 0.25
        assert bus.marl_friend_mean == 0.0
        assert bus.marl_foe_mean == 0.02

    def test_publish_redteam(self):
        bus = TrainingStateBus()
        bus.publish_redteam([{"vector": "TRUTH_PROMOTION"}], 0.0)
        assert len(bus.redteam_vulnerabilities) == 1
        assert bus.redteam_violation_rate == 0.0

    def test_publish_faithfulness(self):
        bus = TrainingStateBus()
        bus.publish_faithfulness({"engine_16": 0.61}, 0.61)
        assert bus.faithfulness_scores["engine_16"] == 0.61
        assert bus.faithfulness_mean == 0.61

    def test_publish_traces(self):
        bus = TrainingStateBus()
        bus.publish_traces(["trace.1", "trace.2", "trace.3"])
        assert len(bus.trace_mechanisms) == 3

    def test_publish_transfer(self):
        bus = TrainingStateBus()
        bus.publish_transfer(["mech.1", "mech.2"], 0.57)
        assert len(bus.transferable_mechanisms) == 2
        assert bus.transfer_rate == 0.57


# ---------------------------------------------------------------------------
# Tests: Subscribe methods
# ---------------------------------------------------------------------------


class TestSubscribe:
    def test_get_rlaif_reward(self):
        bus = TrainingStateBus()
        bus.publish_rlaif("engine_16", 0.5, 0.9)
        assert bus.get_rlaif_reward("engine_16") == 0.5
        assert bus.get_rlaif_reward("engine_99") is None

    def test_get_pbt_champions(self):
        bus = TrainingStateBus()
        bus.publish_pbt([{"policy": "A"}], 0.9, 1)
        champions = bus.get_pbt_champions()
        assert len(champions) == 1

    def test_get_alphazero_mechanisms(self):
        bus = TrainingStateBus()
        bus.publish_alphazero(["mech.1"], [])
        assert bus.get_alphazero_mechanisms() == ["mech.1"]

    def test_get_trace_mechanisms(self):
        bus = TrainingStateBus()
        bus.publish_traces(["trace.1"])
        assert bus.get_trace_mechanisms() == ["trace.1"]

    def test_get_redteam_vulnerabilities(self):
        bus = TrainingStateBus()
        bus.publish_redteam([{"v": 1}], 0.1)
        assert len(bus.get_redteam_vulnerabilities()) == 1

    def test_get_faithfulness_score(self):
        bus = TrainingStateBus()
        bus.publish_faithfulness({"engine_16": 0.61}, 0.61)
        assert bus.get_faithfulness_score("engine_16") == 0.61
        assert bus.get_faithfulness_score("engine_99") is None


# ---------------------------------------------------------------------------
# Tests: Hash and payload
# ---------------------------------------------------------------------------


class TestHashAndPayload:
    def test_compute_hash(self):
        bus = TrainingStateBus()
        bus.publish_rlaif("engine_16", 0.5, 0.9)
        h1 = bus.compute_hash()
        bus.publish_rlaif("engine_01", 0.3, 0.8)
        h2 = bus.compute_hash()
        assert h1 != h2  # different state → different hash

    def test_hash_deterministic(self):
        bus1 = TrainingStateBus()
        bus2 = TrainingStateBus()
        bus1.publish_rlaif("engine_16", 0.5, 0.9)
        bus2.publish_rlaif("engine_16", 0.5, 0.9)
        assert bus1.compute_hash() == bus2.compute_hash()

    def test_payload_has_required_fields(self):
        bus = TrainingStateBus()
        p = bus.payload()
        assert p["bus_version"] == BUS_VERSION
        assert "rlaif_rewards" in p
        assert "pbt_best_fitness" in p
        assert "es_best_fitness" in p
        assert "marl_agent_rewards" in p
        assert "redteam_vulnerabilities_count" in p
        assert "faithfulness_scores" in p
        assert "trace_mechanisms" in p
        assert "transferable_mechanisms" in p
        assert p["truth_effect"] == "NONE"
        assert p["constitution_compliance"]["no_auto_promotion"] is True


# ---------------------------------------------------------------------------
# Tests: Save and load
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_save_and_load(self, tmp_path):
        bus = TrainingStateBus()
        bus.publish_rlaif("engine_16", 0.5, 0.9)
        bus.publish_pbt([{"policy": "A"}], 0.89, 3)
        bus.publish_es(0.86, True, {"max_rounds": 4})

        path = tmp_path / "bus.json"
        bus.save(path)

        loaded = TrainingStateBus.load(path)
        assert loaded.rlaif_rewards["engine_16"] == 0.5
        assert loaded.pbt_best_fitness == 0.89
        assert loaded.es_best_fitness == 0.86
        assert loaded.es_converged is True
        assert loaded.es_best_theta["max_rounds"] == 4

    def test_load_nonexistent_returns_empty(self, tmp_path):
        bus = TrainingStateBus.load(tmp_path / "nonexistent.json")
        assert bus.rlaif_rewards == {}
        assert bus.pbt_champions == []


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_empty_summary(self):
        bus = TrainingStateBus()
        s = bus.summary()
        assert s["publishers"]["rlaif"] == 0
        assert s["key_metrics"]["rlaif_mean_reward"] == 0.0

    def test_summary_after_publishes(self):
        bus = TrainingStateBus()
        bus.publish_rlaif("engine_16", 0.5, 0.9)
        bus.publish_rlaif("engine_01", 0.3, 0.8)
        bus.publish_pbt([{"p": 1}], 0.89, 3)
        bus.publish_es(0.86, True, {})

        s = bus.summary()
        assert s["publishers"]["rlaif"] == 2
        assert s["publishers"]["pbt"] == 1
        assert s["publishers"]["es"] == 1
        assert s["key_metrics"]["rlaif_mean_reward"] == 0.4  # (0.5 + 0.3) / 2
        assert s["key_metrics"]["pbt_best_fitness"] == 0.89
        assert s["key_metrics"]["es_best_fitness"] == 0.86
        assert s["bus_hash"] != ""
        assert s["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_no_auto_promotion(self):
        """State bus has no methods to promote anything."""
        bus = TrainingStateBus()
        assert not hasattr(bus, "promote")
        assert not hasattr(bus, "auto_promote")

    def test_no_code_modification(self):
        """State bus has no methods to modify code."""
        bus = TrainingStateBus()
        assert not hasattr(bus, "modify_code")
        assert not hasattr(bus, "execute_code")

    def test_evaluative_not_truth(self):
        """Bus state is evaluative (truth_effect=NONE)."""
        bus = TrainingStateBus()
        assert bus.payload()["truth_effect"] == "NONE"
        assert "EVALUATIVE" in bus.payload()["claim_ceiling"]

    def test_idempotent_publish(self):
        """Publishing same data twice doesn't duplicate."""
        bus = TrainingStateBus()
        bus.publish_rlaif("engine_16", 0.5, 0.9)
        bus.publish_rlaif("engine_16", 0.5, 0.9)  # same data
        assert len(bus.rlaif_rewards) == 1  # not duplicated


# ---------------------------------------------------------------------------
# Step 2: Thread safety + lossy load fix tests
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """Step 2: Thread safety — all publish methods use RLock."""

    def test_bus_has_lock(self):
        """TrainingStateBus has _lock attribute."""
        bus = TrainingStateBus()
        assert hasattr(bus, "_lock")
        assert hasattr(bus._lock, "acquire")
        assert hasattr(bus._lock, "release")

    def test_concurrent_publish_rlaif(self):
        """Multiple threads publishing RLAIF rewards concurrently — no data loss."""
        import threading
        bus = TrainingStateBus()
        results = []

        def publish(engine_id):
            bus.publish_rlaif(f"engine_{engine_id:02d}", 0.5 * engine_id, 0.9)
            results.append(engine_id)

        threads = [threading.Thread(target=publish, args=(i,)) for i in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 16 engines should be in rlaif_rewards
        assert len(bus.rlaif_rewards) == 16
        assert len(results) == 16

    def test_concurrent_mixed_publish(self):
        """Multiple trainers publishing different data concurrently."""
        import threading
        bus = TrainingStateBus()

        def rlaif_worker():
            for i in range(10):
                bus.publish_rlaif(f"engine_{i:02d}", 0.5, 0.9)

        def pbt_worker():
            for i in range(10):
                bus.publish_pbt([{"eid": f"engine_{i:02d}"}], 0.8 + i * 0.01, i)

        def marl_worker():
            for i in range(10):
                bus.publish_marl({f"agent_{i}": 0.5}, 0.5, 0.3)

        def es_worker():
            for i in range(10):
                bus.publish_es(0.7 + i * 0.01, True, {"x": float(i)})

        threads = [
            threading.Thread(target=rlaif_worker),
            threading.Thread(target=pbt_worker),
            threading.Thread(target=marl_worker),
            threading.Thread(target=es_worker),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All data should be present (no races lost anything)
        assert len(bus.rlaif_rewards) == 10
        assert bus.pbt_generation == 9
        assert len(bus.marl_agent_rewards) == 1  # Overwritten each time, last one wins
        assert bus.es_best_fitness == 0.7 + 9 * 0.01

    def test_concurrent_read_write(self):
        """Concurrent reads while writes happen — readers don't crash."""
        import threading
        bus = TrainingStateBus()
        stop = threading.Event()

        def writer():
            for i in range(100):
                bus.publish_rlaif(f"engine_{i:02d}", 0.5, 0.9)
            stop.set()

        def reader():
            while not stop.is_set():
                bus.summary()
                bus.compute_hash()

        w = threading.Thread(target=writer)
        r = threading.Thread(target=reader)
        w.start()
        r.start()
        w.join(timeout=5)
        stop.set()
        r.join(timeout=5)
        # No exceptions = pass
        assert len(bus.rlaif_rewards) == 100


class TestLossyLoadFix:
    """Step 2: Fixed lossy load() — all fields now restored."""

    def test_save_load_preserves_pbt_champions(self, tmp_path):
        """pbt_champions is restored after save/load (was dropped before Step 2)."""
        bus = TrainingStateBus()
        bus.publish_pbt([{"engine_id": "engine_01", "reward": 0.9}], 0.9, 1)
        p = tmp_path / "bus.json"
        bus.save(p)
        restored = TrainingStateBus.load(p)
        assert len(restored.pbt_champions) == 1  # Was 0 before fix
        assert restored.pbt_champions[0]["engine_id"] == "engine_01"

    def test_save_load_preserves_alphazero_architectures(self, tmp_path):
        """alphazero_architectures is restored after save/load."""
        bus = TrainingStateBus()
        bus.publish_alphazero(["mech_1"], [{"arch": "test"}])
        p = tmp_path / "bus.json"
        bus.save(p)
        restored = TrainingStateBus.load(p)
        assert len(restored.alphazero_architectures) == 1  # Was 0 before fix

    def test_save_load_preserves_redteam_vulnerabilities(self, tmp_path):
        """redteam_vulnerabilities is restored after save/load."""
        bus = TrainingStateBus()
        bus.publish_redteam([{"vector": "test", "severity": "high"}], 0.5)
        p = tmp_path / "bus.json"
        bus.save(p)
        restored = TrainingStateBus.load(p)
        assert len(restored.redteam_vulnerabilities) == 1  # Was 0 before fix

    def test_save_load_preserves_tiered_fitness_all_fields(self, tmp_path):
        """All tiered_fitness fields are restored after save/load."""
        bus = TrainingStateBus()
        bus.publish_tiered_fitness(
            best_fitness=0.9, mean_fitness=0.7, generation=3, l2_calls=2,
            tier_distribution={"L0": 1, "L1": 2, "L2": 3},
            last_theta={"max_rounds": 4.0},
        )
        p = tmp_path / "bus.json"
        bus.save(p)
        restored = TrainingStateBus.load(p)
        # All these were dropped before Step 2
        assert restored.tiered_fitness_mean == 0.7  # Was 0 before fix
        assert restored.tiered_fitness_l2_calls == 2  # Was 0 before fix
        assert restored.tiered_fitness_tier_distribution == {"L0": 1, "L1": 2, "L2": 3}  # Was {} before fix
        assert restored.tiered_fitness_last_theta == {"max_rounds": 4.0}  # Was {} before fix

    def test_compute_hash_detects_field_changes(self):
        """Step 2: compute_hash now detects changes in previously-missing fields."""
        bus1 = TrainingStateBus()
        bus1.publish_marl({"agent_1": 0.5}, friend_mean=0.5, foe_mean=0.3)

        bus2 = TrainingStateBus()
        bus2.publish_marl({"agent_1": 0.5}, friend_mean=0.5, foe_mean=0.9)  # Different foe_mean

        # Before Step 2: marl_foe_mean was NOT in compute_hash → hashes would be equal
        # After Step 2: marl_foe_mean IS in compute_hash → hashes should differ
        assert bus1.compute_hash() != bus2.compute_hash()

    def test_compute_hash_detects_es_converged_change(self):
        """Step 2: compute_hash now detects es_converged change."""
        bus1 = TrainingStateBus()
        bus1.publish_es(0.8, converged=False, best_theta={})

        bus2 = TrainingStateBus()
        bus2.publish_es(0.8, converged=True, best_theta={})

        # Before Step 2: es_converged was NOT in compute_hash → hashes would be equal
        assert bus1.compute_hash() != bus2.compute_hash()

    def test_bus_version_bumped(self):
        """Step 2: Version is bumped to BUS-2."""
        assert BUS_VERSION == "METAENGINE-TRAINING-STATE-BUS-2"
