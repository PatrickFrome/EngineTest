"""METAENGINE Step C — Experiments ↔ Orchestrator wiring tests.

Tests that the experiment-validated capability routing is integrated into
the orchestrator's routing plan as an enrichment layer.
"""

from __future__ import annotations

import pytest

from metaengine.experiment_routing_bridge import (
    enrich_routing_with_experiment,
    build_specialists_from_engines,
    build_task_from_input,
    ExperimentRoutingEnrichment,
)


@pytest.fixture
def engine_configs():
    return [
        {"engine_id": "engine_01", "roles": ["frame_atom_externalization", "interrogative_induction"]},
        {"engine_id": "engine_02", "roles": ["open_set_operator_discovery", "operator_evolution"]},
        {"engine_id": "engine_03", "roles": ["shared_semantic_boundary", "cross_lineage_differential"]},
        {"engine_id": "engine_04", "roles": ["semantic_role", "discourse_uncertainty"]},
        {"engine_id": "engine_05", "roles": ["memory_management", "stateful_context"]},
        {"engine_id": "engine_06", "roles": ["graph_indexing", "entity_resolution"]},
    ]


@pytest.fixture
def routing_plan(engine_configs):
    """Simulate a routing plan from the legacy CapabilityRouter."""
    return {
        "routing_version": "16X-FRONTIER-EVIDENCE-CONTROL-2.2",
        "mode": "FULL_16_DIAGNOSTIC_SPARSE_DEEP_SELF_ORGANIZING",
        "all_16_scheduled": True,
        "task_fingerprint": {"tokens": ["test", "input", "analysis"]},
        "assignments": [
            {"engine_id": e["engine_id"], "scheduled": True, "role": "CORE", "relevance_score": 0.5}
            for e in engine_configs
        ],
        "role_counts": {"CORE": 6},
        "plan_hash": "0" * 64,
    }


# ---------------------------------------------------------------------------
# 1. build_specialists_from_engines
# ---------------------------------------------------------------------------


def test_build_specialists_from_engines(engine_configs):
    """Engine configs are converted to experiment Specialists."""
    specialists = build_specialists_from_engines(engine_configs)
    assert len(specialists) == len(engine_configs)
    assert all(s.resource_id.startswith("engine_") for s in specialists)
    assert all(len(s.capabilities) > 0 for s in specialists)


# ---------------------------------------------------------------------------
# 2. build_task_from_input
# ---------------------------------------------------------------------------


def test_build_task_from_input(tmp_path):
    """Input text is converted to a TaskRequirement with required capabilities."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("Test input for capability routing analysis. This text contains enough tokens for analysis.")
    task = build_task_from_input(input_file)
    assert task.task_id
    assert task.regime.value == "REGIME_A_SEPARABLE_SPECIALIST_TASKS"
    assert len(task.required_capabilities) > 0


# ---------------------------------------------------------------------------
# 3. enrich_routing_with_experiment
# ---------------------------------------------------------------------------


def test_enrich_routing_adds_experiment_fields(routing_plan, engine_configs, tmp_path):
    """The enrichment must add experiment routing fields to the routing plan."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("Test input for capability routing. Analysis of philosophical tensions.")
    enriched = enrich_routing_with_experiment(routing_plan, engine_configs, input_file, k=2)
    assert "experiment_routing" in enriched
    exp = enriched["experiment_routing"]
    assert "capability_routed_top_k" in exp
    assert "dense_all" in exp
    assert "random_top_k" in exp
    assert "experiment_version" in exp
    assert "mechanism_id" in exp
    assert exp["mechanism_id"] == "sparse-conditional-routing"
    assert len(exp["capability_routed_top_k"]) == 2
    assert len(exp["dense_all"]) == len(engine_configs)


def test_enrich_routing_preserves_original_fields(routing_plan, engine_configs, tmp_path):
    """The enrichment must NOT remove or alter any existing routing plan fields."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("Test input.")
    enriched = enrich_routing_with_experiment(routing_plan, engine_configs, input_file, k=2)
    for key in routing_plan:
        assert key in enriched, f"original key {key} was removed"
    assert enriched["routing_version"] == routing_plan["routing_version"]
    assert enriched["all_16_scheduled"] == routing_plan["all_16_scheduled"]
    assert enriched["assignments"] == routing_plan["assignments"]


def test_enrich_routing_capability_selection_is_deterministic(routing_plan, engine_configs, tmp_path):
    """Same input → same capability routing selection."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("Deterministic test input for capability routing selection.")
    e1 = enrich_routing_with_experiment(routing_plan, engine_configs, input_file, k=2)
    e2 = enrich_routing_with_experiment(routing_plan, engine_configs, input_file, k=2)
    assert e1["experiment_routing"]["capability_routed_top_k"] == e2["experiment_routing"]["capability_routed_top_k"]


def test_enrich_routing_random_uses_frozen_seed(routing_plan, engine_configs, tmp_path):
    """Random routing must use a frozen seed for reproducibility."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("Reproducibility test input.")
    e1 = enrich_routing_with_experiment(routing_plan, engine_configs, input_file, k=2, seed=42)
    e2 = enrich_routing_with_experiment(routing_plan, engine_configs, input_file, k=2, seed=42)
    assert e1["experiment_routing"]["random_top_k"] == e2["experiment_routing"]["random_top_k"]


# ---------------------------------------------------------------------------
# 4. ExperimentRoutingEnrichment dataclass
# ---------------------------------------------------------------------------


def test_enrichment_dataclass_fields():
    """ExperimentRoutingEnrichment must have all required fields."""
    e = ExperimentRoutingEnrichment(
        experiment_version="METAENGINE-EXPERIMENT-ROUTING-1",
        mechanism_id="sparse-conditional-routing",
        capability_routed_top_k=("engine_01", "engine_03"),
        dense_all=("engine_01", "engine_02", "engine_03", "engine_04"),
        random_top_k=("engine_02", "engine_05"),
        seed=42,
        k=2,
        local_decision="SUPPORTED_LOCAL",
        truth_effect="NONE",
        assimilation_effect="NONE",
    )
    assert e.capability_routed_top_k == ("engine_01", "engine_03")
    assert e.truth_effect == "NONE"
    assert e.assimilation_effect == "NONE"


def test_enrichment_to_dict():
    """ExperimentRoutingEnrichment must serialize to dict correctly."""
    e = ExperimentRoutingEnrichment(
        experiment_version="METAENGINE-EXPERIMENT-ROUTING-1",
        mechanism_id="sparse-conditional-routing",
        capability_routed_top_k=("engine_01",),
        dense_all=("engine_01", "engine_02"),
        random_top_k=("engine_02",),
        seed=42,
        k=2,
        local_decision="SUPPORTED_LOCAL",
        truth_effect="NONE",
        assimilation_effect="NONE",
    )
    d = e.to_dict()
    assert d["experiment_version"] == "METAENGINE-EXPERIMENT-ROUTING-1"
    assert d["capability_routed_top_k"] == ["engine_01"]
    assert d["truth_effect"] == "NONE"
