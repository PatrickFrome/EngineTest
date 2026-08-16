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
