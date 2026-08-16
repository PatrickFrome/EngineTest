CREATE TABLE IF NOT EXISTS destruktion_meta.hybrid_mesh_ledger (
  meta_run_id text PRIMARY KEY,
  mesh_hash text NOT NULL,
  mesh_version text NOT NULL,
  engine_coverage integer NOT NULL,
  directed_pairwise_bridges integer NOT NULL,
  active_directed_pairwise_bridges integer NOT NULL,
  direct_typed_reuse_bridges integer NOT NULL,
  context_or_critique_bridges integer NOT NULL,
  signal_count integer NOT NULL,
  signal_type_count integer NOT NULL,
  metrics jsonb NOT NULL,
  claim_ceiling text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.hybrid_bridge_ledger (
  meta_run_id text NOT NULL,
  bridge_id text NOT NULL,
  from_engine text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  to_engine text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  mode text NOT NULL,
  direct_signal_types text[] NOT NULL DEFAULT ARRAY[]::text[],
  source_signal_count integer NOT NULL,
  target_consumes text[] NOT NULL DEFAULT ARRAY[]::text[],
  truth_promotion_allowed boolean NOT NULL DEFAULT false,
  PRIMARY KEY(meta_run_id, bridge_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.hybrid_agenda_ledger (
  meta_run_id text NOT NULL,
  agenda_id text NOT NULL,
  seed_kind text NOT NULL,
  seed_text text NOT NULL,
  source_engines text[] NOT NULL DEFAULT ARRAY[]::text[],
  truth_status text NOT NULL,
  payload jsonb NOT NULL,
  PRIMARY KEY(meta_run_id, agenda_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.hybrid_trace_ledger (
  meta_run_id text NOT NULL,
  trace_id text NOT NULL,
  agenda_id text NOT NULL,
  source_engines text[] NOT NULL DEFAULT ARRAY[]::text[],
  cross_family_depth integer NOT NULL,
  truth_status text NOT NULL,
  payload jsonb NOT NULL,
  PRIMARY KEY(meta_run_id, trace_id)
);

CREATE INDEX IF NOT EXISTS idx_dm_hybrid_bridge_run_pair ON destruktion_meta.hybrid_bridge_ledger(meta_run_id,from_engine,to_engine);
CREATE INDEX IF NOT EXISTS idx_dm_hybrid_agenda_run ON destruktion_meta.hybrid_agenda_ledger(meta_run_id);
CREATE INDEX IF NOT EXISTS idx_dm_hybrid_trace_run ON destruktion_meta.hybrid_trace_ledger(meta_run_id);
