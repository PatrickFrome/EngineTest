-- Destruktion 4.0 METAENGINE 16X 2.0
-- Self-reorganizing hermeneutic ecology persistence.
CREATE TABLE IF NOT EXISTS destruktion_meta.engine_biography_ledger (
  meta_run_id text NOT NULL,
  engine_id text NOT NULL,
  domain text NOT NULL DEFAULT 'GENERAL',
  task_fingerprint jsonb NOT NULL DEFAULT '{}'::jsonb,
  biography jsonb NOT NULL DEFAULT '{}'::jsonb,
  biography_hash text NOT NULL,
  claim_ceiling text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(meta_run_id, engine_id, domain)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.scheduler_round_ledger (
  meta_run_id text NOT NULL,
  round_index integer NOT NULL,
  plan_hash text NOT NULL,
  budget_units double precision NOT NULL,
  spent_units double precision NOT NULL,
  selected_engines text[] NOT NULL,
  scores jsonb NOT NULL DEFAULT '{}'::jsonb,
  selection jsonb NOT NULL DEFAULT '{}'::jsonb,
  policy jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, round_index)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.topology_ledger (
  meta_run_id text NOT NULL,
  round_index integer NOT NULL,
  architecture_hash text NOT NULL,
  selected_topology_id text NOT NULL,
  selected jsonb NOT NULL DEFAULT '{}'::jsonb,
  candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
  mutation jsonb NOT NULL DEFAULT '{}'::jsonb,
  disposition text,
  realized_gain double precision,
  claim_ceiling text NOT NULL,
  PRIMARY KEY(meta_run_id, round_index)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.architecture_candidate_ledger (
  meta_run_id text NOT NULL,
  round_index integer NOT NULL,
  candidate_id text NOT NULL,
  topology_id text,
  utility double precision,
  state text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, round_index, candidate_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.coalition_ledger (
  meta_run_id text NOT NULL,
  round_index integer NOT NULL,
  coalition_id text NOT NULL,
  coalition_type text NOT NULL,
  members text[] NOT NULL,
  trigger text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  truth_authority boolean NOT NULL DEFAULT false,
  PRIMARY KEY(meta_run_id, round_index, coalition_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.transformation_ledger (
  meta_run_id text NOT NULL,
  transformation_id text NOT NULL,
  engine_id text,
  transformation_type text NOT NULL,
  node_kind text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_regrounded boolean NOT NULL DEFAULT false,
  truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, transformation_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.transformation_edge_ledger (
  meta_run_id text NOT NULL,
  edge_id text NOT NULL,
  from_node text NOT NULL,
  to_node text NOT NULL,
  kind text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, edge_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.native_reentry_receipt_ledger (
  meta_run_id text NOT NULL,
  round_index integer NOT NULL,
  engine_id text NOT NULL,
  receipt_hash text NOT NULL,
  compiled_mode text NOT NULL,
  status text NOT NULL,
  specialized_native_executed boolean NOT NULL DEFAULT false,
  specialized_native_success boolean NOT NULL DEFAULT false,
  cache_reused boolean NOT NULL DEFAULT false,
  source_reground_required boolean NOT NULL DEFAULT true,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, round_index, engine_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.depth_budget_ledger (
  meta_run_id text NOT NULL,
  round_index integer NOT NULL,
  realized_marginal_gain double precision NOT NULL,
  stop_decision text NOT NULL,
  remaining_budget double precision NOT NULL,
  policy jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, round_index)
);

CREATE INDEX IF NOT EXISTS idx_dm_biography_engine_domain
  ON destruktion_meta.engine_biography_ledger(engine_id, domain);
CREATE INDEX IF NOT EXISTS idx_dm_scheduler_selected
  ON destruktion_meta.scheduler_round_ledger(meta_run_id, round_index);
CREATE INDEX IF NOT EXISTS idx_dm_topology_selected
  ON destruktion_meta.topology_ledger(selected_topology_id);
CREATE INDEX IF NOT EXISTS idx_dm_transform_type
  ON destruktion_meta.transformation_ledger(meta_run_id, transformation_type);
CREATE INDEX IF NOT EXISTS idx_dm_native_receipt_engine
  ON destruktion_meta.native_reentry_receipt_ledger(engine_id, status);
