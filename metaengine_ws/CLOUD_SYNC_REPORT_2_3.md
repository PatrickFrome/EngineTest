# MetaEngine 16X 2.3 — cloud synchronization report

Date: 2026-08-12

## Result

Supabase project `gzrbxoiuenkksualgpvp` is the sole canonical cloud database for MetaEngine. Runtime replication now accepts only `supabase`; any attempt to use Neon fails closed with `BACKEND_RETIRED_NO_READS_NO_WRITES`.

Neon project `falling-hat-08217783` was not modified by the 2.3 migration and was not physically deleted. It is recorded as retired, with no reads or writes, so reactivation remains an explicit administrative decision.

## Applied Supabase migrations

- `metaengine_outcome_gated_self_learning_2_3`
- `metaengine_frontier_evidence_control_2_2`
- `metaengine_optimize_2_3_writer_policies`
- `metaengine_harden_2_3_promotion_function_and_foreign_keys`

## Read-back verification

| Check | Result |
|---|---:|
| Architecture policies | 75 |
| Active policies | 1 |
| Active policy hash | `1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48` |
| Evolution generations | 3 |
| Promotion receipts | 2 |
| External outcomes | 7,200 |
| Outcomes per generation | 2,400 / 2,400 / 2,400 |
| Suites / seeds | 6 / 2 |
| Null outcomes / hard failures | 0 / 0 |
| New tables with forced RLS | 14 / 14 |
| Explicit writer policies | 14 / 14 |
| New-object security warnings | 0 |
| New-object performance warnings, excluding fresh unused-index INFO | 0 |

The champion smoke run is persisted with 27 claims, 43 claim positions, 27 arbitrations, 8 typed handoffs, 8 native receipts, 174 transformations, 182 transformation edges, 4 telemetry events, one verifier report, one dialectical graph, and 8 frontier candidates.

## GitHub state

The connected GitHub profile is `PatrickFrome`, but it exposes no accessible repository and the workspace is not a Git checkout. Publication is therefore blocked without a repository target; no remote repository was created or mutated.
