# Single canonical Postgres persistence

Local JSON/JSONL remains the always-on portable record. Supabase is the sole canonical cloud ledger and promotion authority. The former Neon backend is retired from reads and writes and is not a replication target.

## Base schema
`postgres_schema.sql` contains engine/run/event/artifact/conflict/checkpoint/memory/sync ledgers.

## 1.1 coordination schema
`epistemic_coordination_1_1.sql` adds routing, claim, claim-position, claim-edge, disagreement, review and arbitration ledgers.

## Portable replication
No credentials are stored in the archive. Set `SUPABASE_DATABASE_URL`, install `psql`, then run:

```bash
PYTHONPATH=. python -m metaengine.cli replicate ./runs/example --backend supabase
```

Missing credentials return `UNAVAILABLE_NO_CREDENTIAL`; local provenance is kept for later retry.

## 1.2 interwoven architecture schema
`interwoven_architecture_1_2.sql` adds hybrid mesh, directed bridge, research-agenda and cross-architecture trace ledgers. The replication adapter persists `HYBRID_MESH.json` separately from native engine outputs so architectural mixing remains auditable.

## 1.3 Core-4 recursive schema
`recursive_core4_nonlinearity_1_3.sql` persists Core-4 re-entry, probe, hermeneutic-edge and nonlinearity evidence.

## 1.4 polycentric recursive schema
`polycentric_reentry_1_4.sql` adds polycentric re-entry summaries, per-round novelty, useful-effect observations and typed polycentric graph edges. `CLOUD_SCHEMA_STATUS_1.4.json` records that the four tables were verified present in both Neon and Supabase. These records are coordination/provenance state only and have no truth-promoting authority.


## 2.0 self-organizing ecology schema
`self_reorganizing_ecology_2_0.sql` adds scheduler-round, architecture-candidate, topology, coalition, depth-budget, transformation-node/edge, native-reentry-receipt and engine-biography ledgers. These tables record computational reorganization and provenance; they do not grant epistemic authority.

Exact local replication is available through `python -m metaengine.cli replicate RUN_DIR --backend supabase` when `SUPABASE_DATABASE_URL` and `psql` are available. Missing credentials are reported as `UNAVAILABLE_NO_CREDENTIAL`; local evidence remains intact.

## 2.3 outcome-gated evolution schema

`outcome_gated_self_learning_2_3.sql` adds architecture policies, frozen generations, external outcomes, promotion receipts, a champion pointer, rollback events, verifier reports, dialectical graphs and telemetry. Promotion uses compare-and-swap semantics and tables are fail-closed behind an explicit writer session flag.

Cloud writes use environment-only credentials and a content-addressed local outbox. Failed or unavailable replication remains retryable without changing epistemic state.

`CLOUD_SCHEMA_STATUS_2.3.json` records the applied Supabase migration and the single-writer decision. Supabase is the only writable champion-pointer authority. Neon is not queried or synchronized after retirement, preventing split-brain promotion state.
