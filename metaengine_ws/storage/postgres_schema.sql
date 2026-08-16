CREATE SCHEMA IF NOT EXISTS destruktion_meta;
CREATE TABLE IF NOT EXISTS destruktion_meta.engine_registry (
  engine_id text PRIMARY KEY, ordinal integer NOT NULL UNIQUE, name text NOT NULL, version text NOT NULL,
  lineage_policy text NOT NULL, status text NOT NULL, source_archive text NOT NULL, source_sha256 text NOT NULL,
  capabilities jsonb NOT NULL DEFAULT '[]'::jsonb, native_test jsonb NOT NULL DEFAULT '{}'::jsonb, metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  registered_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.run_ledger (
  meta_run_id text PRIMARY KEY, input_hash text NOT NULL, status text NOT NULL, barrier text NOT NULL,
  claim_ceiling text NOT NULL, input_envelope jsonb NOT NULL DEFAULT '{}'::jsonb, fusion jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS destruktion_meta.engine_run_ledger (
  meta_run_id text NOT NULL, engine_id text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id), wave integer NOT NULL,
  status text NOT NULL, input_hash text NOT NULL, output_hash text, native_output jsonb, canonical_output jsonb, error jsonb,
  started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
  PRIMARY KEY(meta_run_id, engine_id, wave)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.event_ledger (
  event_id text PRIMARY KEY, meta_run_id text NOT NULL, engine_id text, seq bigint NOT NULL,
  event_type text NOT NULL, payload jsonb NOT NULL DEFAULT '{}'::jsonb, payload_hash text NOT NULL,
  parent_event_ids text[] NOT NULL DEFAULT ARRAY[]::text[], created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(meta_run_id, seq)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.artifact_ledger (
  artifact_id text PRIMARY KEY, meta_run_id text NOT NULL, engine_id text, kind text NOT NULL, uri text NOT NULL,
  sha256 text NOT NULL, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.conflict_ledger (
  conflict_id text PRIMARY KEY, meta_run_id text NOT NULL, dimension text NOT NULL, engine_ids text[] NOT NULL,
  description jsonb NOT NULL, resolution_state text NOT NULL DEFAULT 'UNRESOLVED', resolution jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), resolved_at timestamptz
);
CREATE TABLE IF NOT EXISTS destruktion_meta.checkpoint_ledger (
  checkpoint_id text PRIMARY KEY, meta_run_id text NOT NULL, barrier text NOT NULL, state_hash text NOT NULL,
  state jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.memory_ledger (
  memory_id text PRIMARY KEY, subject_type text NOT NULL, subject_id text NOT NULL, version integer NOT NULL,
  content jsonb NOT NULL, content_hash text NOT NULL, parent_memory_id text, mutation_receipt jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(subject_type,subject_id,version)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.sync_receipt (
  receipt_id text PRIMARY KEY, event_id text NOT NULL, backend text NOT NULL, backend_ref text,
  status text NOT NULL, remote_hash text, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(event_id,backend)
);
CREATE INDEX IF NOT EXISTS idx_dm_event_run ON destruktion_meta.event_ledger(meta_run_id,seq);
CREATE INDEX IF NOT EXISTS idx_dm_engine_run ON destruktion_meta.engine_run_ledger(meta_run_id,status);
CREATE INDEX IF NOT EXISTS idx_dm_conflict_run ON destruktion_meta.conflict_ledger(meta_run_id,resolution_state);
CREATE TABLE IF NOT EXISTS destruktion_meta.core4_reentry_ledger (
  meta_run_id text PRIMARY KEY,
  reentry_hash text NOT NULL,
  recursive_rounds integer NOT NULL,
  total_generative_positions integer NOT NULL,
  mean_core4_divergence double precision NOT NULL,
  hermeneutic_cycle_count integer NOT NULL,
  hermeneutic_graph_hash text NOT NULL,
  metrics jsonb NOT NULL,
  claim_ceiling text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.core4_probe_ledger (
  meta_run_id text NOT NULL,
  probe_id text NOT NULL,
  engine_id text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  reentry_round integer NOT NULL,
  claim_type text NOT NULL,
  proposition text NOT NULL,
  payload jsonb NOT NULL,
  truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, probe_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.hermeneutic_edge_ledger (
  meta_run_id text NOT NULL,
  edge_id text NOT NULL,
  from_node text NOT NULL,
  to_node text NOT NULL,
  kind text NOT NULL,
  payload jsonb NOT NULL,
  truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, edge_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.nonlinearity_ledger (
  meta_run_id text PRIMARY KEY,
  evaluation_hash text NOT NULL,
  metric_version text NOT NULL,
  hermeneutic_nonlinearity double precision NOT NULL,
  epistemic_nonlinearity double precision NOT NULL,
  depth_proxy double precision NOT NULL,
  delta_vs_baseline jsonb NOT NULL DEFAULT '{}'::jsonb,
  epistemic_safety jsonb NOT NULL DEFAULT '{}'::jsonb,
  components jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  claim_ceiling text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dm_core4_probe_engine_round ON destruktion_meta.core4_probe_ledger(meta_run_id,engine_id,reentry_round);
CREATE INDEX IF NOT EXISTS idx_dm_herm_edge_kind ON destruktion_meta.hermeneutic_edge_ledger(meta_run_id,kind);

CREATE TABLE IF NOT EXISTS destruktion_meta.polycentric_reentry_ledger (
  meta_run_id text PRIMARY KEY,
  reentry_hash text NOT NULL,
  round_count integer NOT NULL,
  all16_rounds integer NOT NULL,
  total_generative_positions integer NOT NULL,
  unique_claim_types integer NOT NULL,
  peer_pair_coverage integer NOT NULL,
  mean_round_novelty double precision NOT NULL,
  last_round_novelty double precision NOT NULL,
  stop_reason text NOT NULL,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  claim_ceiling text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.polycentric_round_ledger (
  meta_run_id text NOT NULL,
  round_index integer NOT NULL,
  round_hash text NOT NULL,
  scheduled_engines text[] NOT NULL,
  global_novelty double precision NOT NULL,
  novelty jsonb NOT NULL DEFAULT '{}'::jsonb,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, round_index)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.useful_effect_ledger (
  meta_run_id text NOT NULL,
  effect_id text NOT NULL,
  state text NOT NULL,
  score double precision NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, effect_id)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.polycentric_edge_ledger (
  meta_run_id text NOT NULL,
  edge_id text NOT NULL,
  from_node text NOT NULL,
  to_node text NOT NULL,
  kind text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, edge_id)
);
CREATE INDEX IF NOT EXISTS idx_dm_poly_round_novelty ON destruktion_meta.polycentric_round_ledger(meta_run_id,global_novelty);
CREATE INDEX IF NOT EXISTS idx_dm_effect_state ON destruktion_meta.useful_effect_ledger(meta_run_id,state);
