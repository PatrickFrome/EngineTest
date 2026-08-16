# MetaEngine 16X 2.2 — release validation

## Result

The frontier evidence-control architecture is integrated into the executable MetaEngine path and passed local regression plus a full 16-lineage integration smoke.

| Gate | Result |
|---|---:|
| Python regression | 48/48 passed |
| Full primary engine states | 16/16 |
| Deep rounds | 2 |
| Sparse deep executions | 7 |
| Frontier candidates | 7 |
| Pareto members across rounds | 3 |
| Derived truth-promotion violations | 0 |
| Native lineage fixity vs 2.1 | 9 839/9 839 byte-identical |
| Frontier Postgres tables | 5, migration prepared but not applied |

The smoke moved from `DYNAMIC_GAIN_TOPOLOGY` in round 1 to `ADVERSARIAL_FORK` in round 2. Both Progress Ledgers reported continued gain; therefore no shadow policy mutation was created in this successful run. The dedicated stall regression verifies that echo/marginal traces do create a `SHADOW_ONLY` policy candidate and cannot self-deploy it.

## Artifacts

- `release-evidence/2.2/smoke/FRONTIER_CONTROL_PLANE.json`
- `release-evidence/2.2/smoke/frontier_control_plane/TASK_LEDGER.json`
- `release-evidence/2.2/smoke/frontier_control_plane/ROUND_1_PLAN.json`
- `release-evidence/2.2/smoke/frontier_control_plane/ROUND_1_EVALUATION.json`
- `release-evidence/2.2/smoke/frontier_control_plane/ROUND_2_PLAN.json`
- `release-evidence/2.2/smoke/frontier_control_plane/ROUND_2_EVALUATION.json`
- `RELEASE_MANIFEST_2_2.json`

## Limits

This validates software integration, schema safety and control-plane invariants. It does not prove higher external reasoning quality. The next release gate is a preregistered blind A/B against the best single engine and MetaEngine 2.1.
