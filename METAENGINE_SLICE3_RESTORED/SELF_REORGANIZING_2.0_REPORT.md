# METAENGINE 16X 2.0 — Controlled A/B: 1.4 vs 2.0

## Aggregate result

- median runtime: **3.25 s → 2.53 s** (~**1.2846×** median speedup)
- deep engine executions: **200 → 62** (**69.0% reduction**)
- mean 2.0 causal transformation depth: **8**
- 2.0 architecture mutations across five cases: **5**
- native claim-node delta: **0**
- native position delta: **0**
- derived truth-promotion violations: **0**

## Per-case

| Case | Runtime 1.4 | Runtime 2.0 | Deep 1.4 | Deep 2.0 | 2.0 causal depth | 2.0 stop | 2.0 topology |
|---|---:|---:|---:|---:|---:|---|---|
| 01_hermeneutic | 3.19s | 3.32s | 40 | 9 | 6 | STOP_MARGINAL_GAIN | EVIDENCE_FIRST |
| 02_evidence | 3.19s | 2.23s | 40 | 14 | 8 | STOP_BUDGET_EXHAUSTED | ADVERSARIAL_FORK |
| 03_memory_history | 3.25s | 2.53s | 40 | 12 | 10 | STOP_BUDGET_EXHAUSTED | GRAPH_FIRST |
| 04_graph_workflow | 3.49s | 2.29s | 40 | 17 | 9 | STOP_BUDGET_EXHAUSTED | WORKFLOW_SWARM |
| 05_mixed_research | 3.25s | 3.14s | 40 | 10 | 7 | STOP_MAX_DEPTH_SAFETY | ADVERSARIAL_FORK |

## Warm exact-hash reuse

Exact repeat of the hermeneutic case: **3.32s → 1.14s** (~**2.9123×**), with **9/9** deep states reused. Cache identity is hash-bound; no semantic-equivalence guessing is permitted.

## Interpretation

The main performance gain is not shallower thinking but **sparse deep execution**. All 16 engines still participate in the diagnostic wave; only the deep native passes are budgeted. The Transformation Graph records typed causal changes and source-regrounding, while the Claim Graph remains unchanged by derived re-entry.

The 1.4 `round_count` and 2.0 `causal_depth` are not identical metrics, so they are not subtracted as if on one scale. The reproducible common evidence is: fewer deep executions, lower median local runtime, longer typed causal chains in 2.0, and unchanged native truth-bearing state.

## Claim ceiling

CONTROLLED_LOCAL_ARCHITECTURAL_PERFORMANCE_AND_CAUSAL_DEPTH_EVIDENCE_NOT_EXTERNAL_PHILOSOPHICAL_SUPERIORITY
