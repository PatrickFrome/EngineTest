# METAENGINE 16X 2.1 — Parallel Experimental Ecology Report

## Scope

2.1 adds an outer parallel experimental ecology above the 2.0 self-reorganizing metaengine. Heavy native worlds execute in bounded batches with frozen biography priors, isolated cold caches and an explicit cross-world freeze barrier. A fresh outer thread-pool is created every four heavy worlds to prevent long-lived worker degradation after repeated nested Node/native subprocess launches.

## Completed parallel test volume

**64,320 completed test executions/checks** are represented in the final 2.1 release evidence:

- **93** full native end-to-end world executions;
- **17** frozen-primary single ablations;
- **120/120** frozen-primary pairwise ablations;
- **560/560** frozen-primary triple ablations;
- **16,384** router perturbation tests;
- **32,768** exact cache-key stress checks;
- **8,192** structural topology screenings;
- **6,144** randomized frozen-subset coordination tests;
- **42/42** regression tests.

Four additional native pair-removal worlds reached primary completion but their batch exceeded the external controller ceiling before freeze-barrier completion. They are recorded as **infrastructure-aborted partial worlds** and are excluded from quality/success counts.

## Parallelism and recycling

- 4-world native smoke: about **3.50×** effective parallel speedup.
- 4-world perturbation tail: about **3.93×**.
- 5-world task benchmark: about **3.03×**.
- final 8-world recycled-pool smoke: **8/8 COMPLETE**, **3.905×** effective speedup, max causal depth **8**, truth-promotion violations **0**.

The aggressive heavy-world sweep demonstrated that nested concurrency cannot be increased without bound on the 5-CPU / ~6 GB execution environment. The final fabric therefore uses **bounded heavy-world batches of four with worker recycling**, while combinatorial coverage is moved to frozen-state matrices that can safely use much higher parallel fan-out.

## Full native benchmark

Five task classes completed 5/5. Mean deep executions: **12.6**. Mean causal depth: **9.4**; maximum: **12**. Mean hermeneutic nonlinearity proxy: **0.905**. Mean epistemic nonlinearity proxy: **0.6969**. Truth-promotion violations: **0**.

## Native all-16 leave-one-out

A complete shallow native leave-one-out campaign ran the full baseline plus removal of each Engine 1–16: **17/17 worlds COMPLETE**. Batch speedup ranged approximately **3.67–3.84×**.

The result is intentionally non-monotonic: under this shallow profile, removing some engines left H unchanged, while removing Engines 5–7 increased H proxy and causal depth. This does **not** mean those engines are harmful; it demonstrates redundancy/suppression and proves that “more engines automatically means more nonlinearity” is false. Native contribution must be evaluated by task, depth, topology and interaction, not by presence alone.

## Native pairwise spot-check and full pairwise coverage

A heavy native pair-removal sweep completed **24 pair worlds** with no engine failures before the next four worlds encountered the external infrastructure ceiling after primary completion. The completed batches showed effective speedups about **3.30–3.83×**.

All **120/120 pair combinations** are nevertheless covered at the frozen-primary coordination layer, where the purpose is exhaustive interaction mapping without native re-execution. The release therefore keeps native and frozen evidence separate instead of pretending they measure the same thing.

## Triple ablation landscape

All **560** three-engine removals were evaluated at the frozen-primary layer. Baseline: 25 claim nodes / 35 positions / 71 edges. Across triple removals, claim nodes ranged **6–25**, positions **10–35**, edges **0–71**.

The strongest primary-claim collapse was removal of **Engines 9 + 13 + 14**, leaving 6 nodes / 16 positions / 1 edge; 9 + 13 + 15 left 8 / 18 / 0. This identifies a strong primary research-claim emission cluster. Qualification: Core-4 often contributes most strongly during recursive/native re-entry, so primary-claim ablation is not a global importance ranking.

## Perturbation swarm

24/24 native perturbation worlds completed. Mean deep executions: 9; causal depth 5–6; mean H proxy 0.7593; mean E proxy 0.595. Native claim-node and native-position deltas remained **0 / 0**. Derived truth-promotion violations: **0**.

## Router stress — useful negative finding

**16,384 routing perturbations** covered all 9 routing domains but collapsed to only **45 coarse task fingerprints**. This is now recorded as `ROUTER_RESOLUTION_SATURATION`: the current task fingerprint is useful for coarse routing but too low-resolution to serve as a sufficient empirical task identity for future specialization learning.

## Topology stress — useful negative finding

Across **8,192** structural topology screens:

- `DYNAMIC_GAIN_TOPOLOGY`: **7,485** selections;
- `DISAGREEMENT_RESOLUTION_TOPOLOGY`: **707** selections.

All six fixed topology families remain executable in native forced-world tests, but the structural selector strongly concentrates on two generated families. This is retained both as evidence for generated-topology usefulness and as a possible `TOPOLOGY_SELECTOR_CONCENTRATION` failure mode to test in 2.2.

## Cache integrity

**32,768/32,768** generated cache keys were unique with **0 collisions**; identical input tuples reproduce the identical key. This validates exact hash-bound reuse only, not semantic-equivalence caching.

## Randomized subset stress

**6,144** randomized frozen engine-subset tests completed in independent seed ranges. Remaining engines ranged from 10 to 15; observed claim nodes ranged 1–25; `truth_vote_used_count = 0` across the full matrix.

## Useful effects fixed by 2.1

1. Parallel wall-clock gain without cross-world biography contamination.
2. Independent hermeneutic trajectories before comparison.
3. Complete pairwise and triple combinatorial ablation coverage at the coordination layer.
4. Complete native single-engine leave-one-out evidence.
5. Native pairwise spot-check evidence separated from frozen-primary exhaustive evidence.
6. Non-monotonic contribution is observable instead of being hidden by ensemble size.
7. Generated-topology dominance can be measured rather than assumed.
8. Router-resolution saturation is now empirically visible.
9. Cache exactness survives tens of thousands of parallel key tests.
10. Oversubscription and long-lived worker degradation are treated as infrastructure failure modes and mitigated by batch recycling.
11. Truth-bearing node/position counts stay invariant under perturbation worlds.
12. Freeze barrier prevents benchmark worlds from training one another.

## Claim ceiling

`CONTROLLED_PARALLEL_ARCHITECTURAL_ROBUSTNESS_ABLATION_TOPOLOGY_PERFORMANCE_AND_INTERACTION_EVIDENCE; FROZEN_PRIMARY MATRICES DO NOT REEXECUTE NATIVE ENGINES; NOT EXTERNAL PHILOSOPHICAL SEMANTIC SCIENTIFIC OR GENERAL-REASONING SUPERIORITY VALIDATION`
