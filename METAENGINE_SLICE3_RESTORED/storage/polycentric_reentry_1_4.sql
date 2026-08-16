-- Destruktion 4.0 METAENGINE 16X 1.4
-- Polycentric recursive re-entry / useful-effect persistence.
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

CREATE INDEX IF NOT EXISTS idx_dm_poly_round_novelty
  ON destruktion_meta.polycentric_round_ledger(meta_run_id, global_novelty);
CREATE INDEX IF NOT EXISTS idx_dm_effect_state
  ON destruktion_meta.useful_effect_ledger(meta_run_id, state);
