# RELEASE VALIDATION — METAENGINE 16X 2.1.0-alpha.1

## Result

**PASS** — Parallel Experimental Ecology is executable, bounded, worker-recycled, freeze-barrier isolated and compatible with the immutable 16-lineage base.

## Regression

- pytest: **42/42 passed**
- completed release-stage tests/executions: **281,204**
- full native world executions: **117**

## Heavy-world parallel execution

- final 8-world worker-recycling smoke: **8/8 COMPLETE**
- effective parallel speedup: **3.905×**
- max causal depth: **8**
- truth-promotion violations: **0**
- resource policy: `FRESH_THREAD_POOL_PER_BATCH`, default batch size **4**

Earlier aggressive sweeps exposed nested oversubscription and long-lived worker degradation. Partial worlds that failed to reach the freeze barrier are labelled **infrastructure-aborted**, never engine failures, and excluded from quality counts.

## High-volume matrices

- frozen-primary single ablations: **17**
- frozen-primary pairwise ablations: **120/120**
- frozen-primary triple ablations: **560/560**
- router perturbations: **16,384**
- cache-key stress: **32,768 unique / 32,768; collisions 0**
- topology structural screens: **8,192**
- randomized frozen-subset coordination tests: **6,144**

## Native ablation

- all-16 leave-one-out: **17/17 complete** (baseline + 16 removals)
- native pairwise spot-check: **24 complete**, **0 engine failures**
- four further pair worlds reached primary completion but were infrastructure-aborted before the batch freeze barrier.

## Epistemic safety

- completed native perturbation truth-promotion violations: **0**
- final recycled smoke truth-promotion violations: **0**
- randomized subset majority-truth usage: **0**
- frozen-world comparison occurs only after freeze barrier.

## Lineage fixity

Caches excluded from the fixity domain:

- baseline lineage files: **9839**
- current lineage files: **9839**
- byte-identical: **9839**
- missing / added / changed: **0 / 0 / 0**

## Cloud

Supabase and Neon both verify all four 2.1 experimental-ledger tables: `experiment_batch_ledger`, `experiment_world_ledger`, `cross_world_differential_ledger`, `stress_matrix_ledger`. Databases remain provenance stores, not epistemic authorities.

## Important empirical limitations discovered

- 16,384 router perturbations produce only 45 coarse task fingerprints: **router-resolution saturation**.
- 8,192 structural topology screens concentrate on two generated topology families: possible **selector concentration**.
- full native pairwise execution is bounded by infrastructure; exhaustive 120-pair coverage is therefore frozen-primary, not native.

## Extended parallel campaign

After the original release-stage campaign, 2.1 was stress-expanded without changing any lineage bytes:

- cache-key stress: **131,072 / 131,072 unique, 0 collisions**;
- router perturbations: **65,536**, still only **45 coarse fingerprints**;
- topology structural screens: **16,384** (`DYNAMIC_GAIN_TOPOLOGY` 14,523; `DISAGREEMENT_RESOLUTION_TOPOLOGY` 1,861);
- frozen order-4 ablations: **1,820 / 1,820**;
- additional randomized frozen subsets: **2,048**, majority-truth usage **0**;
- full-native topology × task worlds: **24 / 24 COMPLETE**, 6 topology families × 4 task classes, causal depth max **8**, truth-promotion violations **0**, native-position delta **0**.

Total completed release-stage checks/executions are now **281,204**, including **117 full-native worlds**. The larger matrices confirm two useful negative findings rather than erasing them: router-resolution saturation and topology-selector concentration.

## Claim ceiling

Internal tests establish controlled architecture, concurrency, robustness, isolation, ablation, topology and performance properties. They do **not** establish external philosophical, semantic, scientific or general-reasoning superiority.
