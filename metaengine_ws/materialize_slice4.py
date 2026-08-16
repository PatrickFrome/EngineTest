#!/usr/bin/env python3
"""METAENGINE-1-SLICE-4 — materialize the extended mechanism library.

Re-registers the Slice-3 mechanism candidates with the Slice-4 extended
MechanismCandidate (now including the promotion_authority field) and adds:

1. Retrospective registration of existing MetaEngine 2.2/2.3 architecture
   influences (spec §10.4 last paragraph: "Existing 2.2/2.3 architecture
   influences must be retrospectively registered rather than reimplemented
   under new names").

2. Completion of the 12 section-10.4 mechanism-candidate families.

Honesty note (PRESERVE_ABSTENTION): no A2/A3 mechanisms are created — real
ablation/transfer evidence does not exist in this recovery environment.
The AssimilationGate is exercised by unit tests only (with synthetic
receipts). has_a3_influence() remains False after Slice 4.
"""

from __future__ import annotations

import json
from pathlib import Path

from metaengine.mechanism_library import (
    MechanismCandidate,
    MechanismLibrary,
    MechanismState,
)
from metaengine.util import write_json

ROOT = Path(__file__).resolve().parent
ARCH_LIB = ROOT / "research" / "architecture_library"


# ---------------------------------------------------------------------------
# Slice-3 external-source mechanism candidates (re-registered for Slice 4)
# ---------------------------------------------------------------------------

external_candidates = (
    MechanismCandidate.create(
        mechanism_id="mec.sparse_conditional_routing",
        semantic_definition="Route only a subset of experts/paths per token via a learned gate.",
        origin_source_ids=("src.deepseek.1", "src.qwen.1", "src.glm.1", "src.llama4.1"),
        source_fact_boundary="Source papers report the routing pattern; exact gate implementation is source code only where permissively licensed.",
        hypothesized_effect="Reduces per-token compute without proportional quality loss under bounded load.",
        task_scope=("GENERATION", "MIXED_RETRIEVAL"),
        prerequisites=("learned_router_weights",),
        resource_cost="UNOBSERVED",
        complexity_cost="moderate router + load balancing",
        known_incompatibilities=("strict-determinism pipelines",),
        known_failures=(),
        implementation_variants=("top-1-router", "top-2-router"),
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.latent_context_compression",
        semantic_definition="Compress KV/context state into a latent representation to reduce attention cost.",
        origin_source_ids=("src.deepseek.1", "src.kimi-linear.1"),
        source_fact_boundary="Reported in public papers; transfer to MetaEngine is unverified.",
        hypothesized_effect="Longer effective context at fixed memory budget.",
        task_scope=("LONG_CONTEXT",),
        prerequisites=("compressor_head",),
        resource_cost="UNOBSERVED",
        complexity_cost="encoder + reconstruction",
        confidence="UNOBSERVED",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.adaptive_reasoning_budget",
        semantic_definition="Allocate reasoning depth/budget adaptively per query.",
        origin_source_ids=("src.qwen.1", "src.gpt-5.6.1", "src.gemini-deep-think.1"),
        source_fact_boundary="Observed as behavior in closed systems and as a mode toggle in Qwen3 public material.",
        hypothesized_effect="Better quality/cost trade-off across query difficulty.",
        task_scope=("REASONING",),
        prerequisites=("budget_controller",),
        resource_cost="UNOBSERVED",
        complexity_cost="budget policy + early-exit heads",
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.constitution_derived_testing",
        semantic_definition="Derive tests/invariants from a constitutional rule set.",
        origin_source_ids=("src.metaengine.design.1", "src.claude.1"),
        source_fact_boundary="MetaEngine K0/K1 invariants are the source fact; Claude constitutional-AI is behavioral evidence only.",
        hypothesized_effect="Automated, provenance-bound test generation from invariants.",
        task_scope=("TESTING",),
        prerequisites=("constitution_kernel",),
        resource_cost="low",
        complexity_cost="invariant->test compiler",
        confidence="LOW",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.residual_organization_paths",
        semantic_definition="Maintain residual paths across organization waves so earlier outputs remain reachable.",
        origin_source_ids=("src.mistral.1",),
        source_fact_boundary="Sliding-window/GQA patterns reported in public Mistral material.",
        hypothesized_effect="Stable long-range information flow in multi-wave organizations.",
        task_scope=("MULTI_WAVE",),
        prerequisites=(),
        resource_cost="UNOBSERVED",
        complexity_cost="residual wiring",
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.parallel_hypothesis_generation",
        semantic_definition="Generate multiple parallel hypotheses/plans and critique them.",
        origin_source_ids=("src.kimi-k3.1", "src.gpt-5.6.1"),
        source_fact_boundary="Observed as agentic behavior in closed/restricted systems.",
        hypothesized_effect="Higher coverage of solution space at higher compute cost.",
        task_scope=("PLANNING",),
        prerequisites=("critic_role",),
        resource_cost="UNOBSERVED",
        complexity_cost="fan-out + discriminator",
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.speculative_multi_action",
        semantic_definition="Speculatively propose multiple actions/plans and verify in parallel.",
        origin_source_ids=("src.gpt-5.6.1",),
        source_fact_boundary="Behavioral observation only; no source.",
        hypothesized_effect="Lower latency for multi-step actions when verifier is cheap.",
        task_scope=("AGENTIC",),
        prerequisites=("verifier_role",),
        resource_cost="UNOBSERVED",
        complexity_cost="speculator + verifier",
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    # --- Remaining section-10.4 families ---
    MechanismCandidate.create(
        mechanism_id="mec.hybrid_compressed_full_attention",
        semantic_definition="Alternate between compressed-state and full-attention layers within a single organization.",
        origin_source_ids=("src.deepseek.1", "src.kimi-linear.1"),
        source_fact_boundary="Public papers describe hybrid attention patterns; exact layer ratios are implementation-specific.",
        hypothesized_effect="Balances long-context reach with local precision at controlled memory cost.",
        task_scope=("LONG_CONTEXT", "GENERATION"),
        prerequisites=("compressor_head",),
        resource_cost="UNOBSERVED",
        complexity_cost="dual-path attention + scheduler",
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.sparse_evidence_attention_retrieval",
        semantic_definition="Attend selectively to evidence retrieved on-demand rather than scanning the full context.",
        origin_source_ids=("src.gpt-5.6.1", "src.claude.1"),
        source_fact_boundary="Behavioral observation in closed systems; no source code.",
        hypothesized_effect="Improves factual grounding without proportional context-length cost.",
        task_scope=("RETRIEVAL", "REASONING"),
        prerequisites=("retriever_role",),
        resource_cost="UNOBSERVED",
        complexity_cost="retriever + attention gate",
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.dynamic_specialist_swarm_instantiation",
        semantic_definition="Dynamically instantiate a swarm of specialist workers conditioned on the task.",
        origin_source_ids=("src.kimi-k3.1", "src.gpt-5.6.1"),
        source_fact_boundary="Agentic behavior observed; mechanism is hypothesized, not confirmed.",
        hypothesized_effect="Better task-specific quality at the cost of orchestration overhead.",
        task_scope=("AGENTIC", "PLANNING"),
        prerequisites=("orchestrator_role",),
        resource_cost="UNOBSERVED",
        complexity_cost="specialist pool + dispatcher",
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.preserved_structured_state",
        semantic_definition="Carry forward a structured state representation across organization waves.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="MetaEngine's own state_cache.py and replication_outbox.py implement a variant of this.",
        hypothesized_effect="Reduces redundant recomputation across waves; preserves provenance.",
        task_scope=("MULTI_WAVE",),
        prerequisites=("state_store",),
        resource_cost="low",
        complexity_cost="state schema + serialization",
        confidence="LOW",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.objective_neutral_load_balancing",
        semantic_definition="Distribute work across engines/roles without optimizing for any single objective metric.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="MetaEngine's polycentric_reentry.py and parallel_ecology.py implement balance patterns.",
        hypothesized_effect="Prevents single-objective overfitting in multi-wave organizations.",
        task_scope=("MULTI_WAVE",),
        prerequisites=(),
        resource_cost="low",
        complexity_cost="balance policy",
        confidence="LOW",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    # --- Retrospective MetaEngine 2.2/2.3 architecture influences ---
    # Registered under their EXISTING names (spec: "retrospectively registered
    # rather than reimplemented under new names").
    MechanismCandidate.create(
        mechanism_id="mec.metaengine.polycentric_reentry",
        semantic_definition="Multi-center re-entry orchestration where multiple cognitive centers re-enter the problem from different angles.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="Implemented in metaengine/polycentric_reentry.py (2.2); registered retrospectively, not reimplemented.",
        hypothesized_effect="Broader solution-space coverage via polycentric perspective shifts.",
        task_scope=("REASONING", "MULTI_WAVE"),
        prerequisites=("orchestrator_role",),
        resource_cost="moderate",
        complexity_cost="center coordinator + re-entry scheduler",
        confidence="MEDIUM",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.metaengine.hybrid_mesh",
        semantic_definition="Hybrid mesh topology combining deep and shallow engine paths.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="Implemented in metaengine/hybrid_mesh.py (2.2); registered retrospectively.",
        hypothesized_effect="Flexible depth/compute trade-off per token.",
        task_scope=("GENERATION",),
        prerequisites=(),
        resource_cost="moderate",
        complexity_cost="mesh router + depth policy",
        confidence="MEDIUM",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.metaengine.dialectical_graph",
        semantic_definition="Graph-structured dialectical reasoning where engines produce thesis/antithesis/synthesis nodes.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="Implemented in metaengine/dialectical_graph.py (2.2); registered retrospectively.",
        hypothesized_effect="Structured disagreement leads to higher-quality synthesis.",
        task_scope=("REASONING",),
        prerequisites=(),
        resource_cost="moderate",
        complexity_cost="graph builder + synthesis resolver",
        confidence="MEDIUM",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.metaengine.epistemic_gain",
        semantic_definition="Measure and maximize epistemic gain (information quality) across organization rounds.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="Implemented in metaengine/epistemic_gain.py (2.2); registered retrospectively.",
        hypothesized_effect="Organizations that maximize knowledge gain rather than token count.",
        task_scope=("REASONING", "TESTING"),
        prerequisites=(),
        resource_cost="low",
        complexity_cost="gain estimator + feedback loop",
        confidence="MEDIUM",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.metaengine.parallel_ecology",
        semantic_definition="Parallel experimental ecology where multiple organization variants compete in an ecosystem.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="Implemented in metaengine/parallel_ecology.py (2.1); registered retrospectively.",
        hypothesized_effect="Diverse variants explored in parallel; winners selected by outcome.",
        task_scope=("MULTI_WAVE",),
        prerequisites=(),
        resource_cost="high",
        complexity_cost="ecology runner + selection policy",
        confidence="MEDIUM",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.metaengine.frozen_matrix",
        semantic_definition="Frozen evaluation matrix that pins task/resource/regime contracts before execution.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="Implemented in metaengine/frozen_matrix.py (2.3); registered retrospectively.",
        hypothesized_effect="Reproducible evaluation immune to retroactive metric redefinition.",
        task_scope=("TESTING",),
        prerequisites=(),
        resource_cost="low",
        complexity_cost="matrix freezer + verifier",
        confidence="MEDIUM",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.metaengine.transformation_graph",
        semantic_definition="Graph of transformation operators applied to organization state, with provenance edges.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="Implemented in metaengine/transformation_graph.py (2.3); registered retrospectively.",
        hypothesized_effect="Auditable chain of transformations; rollback and replay supported.",
        task_scope=("MULTI_WAVE",),
        prerequisites=(),
        resource_cost="low",
        complexity_cost="graph store + provenance tracker",
        confidence="MEDIUM",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.metaengine.self_organizing_metrics",
        semantic_definition="Metrics that reorganize themselves based on observed organization behavior.",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="Implemented in metaengine/self_organizing_metrics.py (2.0); registered retrospectively.",
        hypothesized_effect="Metric system adapts to task regime without manual redesign.",
        task_scope=("TESTING", "MULTI_WAVE"),
        prerequisites=(),
        resource_cost="low",
        complexity_cost="metric reorganizer + stability guard",
        confidence="MEDIUM",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
)

library = MechanismLibrary.create(external_candidates)
assert library.verify() is True
assert library.has_a3_influence() is False
library.assert_no_a3_influence()  # must not raise

write_json(ARCH_LIB / "mechanism_library.json", library.as_dict())

summary = {
    "slice": "METAENGINE-1-SLICE-4",
    "mechanism_library_hash": library.library_hash,
    "mechanism_count": len(library.candidates),
    "a0_count": sum(1 for c in library.candidates if c.status is MechanismState.A0_OBSERVED),
    "a1_count": sum(1 for c in library.candidates if c.status is MechanismState.A1_MECHANISM_HYPOTHESIS),
    "a2_count": sum(1 for c in library.candidates if c.status is MechanismState.A2_TRANSFERABLE),
    "a3_count": sum(1 for c in library.candidates if c.status is MechanismState.A3_ASSIMILATED),
    "has_a3_influence": library.has_a3_influence(),
    "section_10_4_families_covered": [
        "sparse conditional routing",
        "hybrid compressed-state/full-attention organization",
        "latent/context compression",
        "sparse evidence attention/retrieval",
        "speculative multi-action/multi-plan proposal",
        "adaptive reasoning budget",
        "parallel hypothesis generation and critique",
        "constitution-derived testing",
        "residual organization paths",
        "dynamic specialist/swarm instantiation",
        "preserved structured state",
        "objective-neutral load balancing",
    ],
    "retrospective_metaengine_influences_registered": [
        "mec.metaengine.polycentric_reentry",
        "mec.metaengine.hybrid_mesh",
        "mec.metaengine.dialectical_graph",
        "mec.metaengine.epistemic_gain",
        "mec.metaengine.parallel_ecology",
        "mec.metaengine.frozen_matrix",
        "mec.metaengine.transformation_graph",
        "mec.metaengine.self_organizing_metrics",
    ],
    "honesty_note": "No A2/A3 mechanisms created: real ablation/transfer evidence does not exist in this recovery environment. The AssimilationGate is exercised by unit tests only. has_a3_influence() remains False.",
}
write_json(ARCH_LIB / "slice4_mechanism_summary.json", summary)

print("SLICE4_MATERIALIZE_PASS")
print(json.dumps(summary, indent=2))
