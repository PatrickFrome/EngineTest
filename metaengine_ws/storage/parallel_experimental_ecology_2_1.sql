create schema if not exists destruktion_meta;
create table if not exists destruktion_meta.experiment_batch_ledger (
 batch_id text primary key, experiment_kind text not null, world_count integer not null,
 world_workers integer not null, inner_workers integer not null, freeze_hash text,
 status text not null, metrics jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
);
create table if not exists destruktion_meta.experiment_world_ledger (
 batch_id text not null, case_id text not null, kind text not null, status text not null,
 policy jsonb not null default '{}'::jsonb, metrics jsonb not null default '{}'::jsonb,
 run_hash text, primary key(batch_id,case_id)
);
create table if not exists destruktion_meta.cross_world_differential_ledger (
 batch_id text primary key, summary jsonb not null, comparison_hash text not null
);
create table if not exists destruktion_meta.stress_matrix_ledger (
 matrix_id text primary key, matrix_kind text not null, test_count integer not null,
 matrix_hash text not null, summary jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
);
