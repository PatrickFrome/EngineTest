CREATE TABLE IF NOT EXISTS destruktion_meta.routing_ledger (
  meta_run_id text PRIMARY KEY,
  plan_hash text NOT NULL,
  mode text NOT NULL,
  task_fingerprint jsonb NOT NULL,
  assignments jsonb NOT NULL,
  role_counts jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.claim_ledger (
  meta_run_id text NOT NULL,
  claim_id text NOT NULL,
  proposition_key text NOT NULL,
  representative text NOT NULL,
  engine_ids text[] NOT NULL DEFAULT ARRAY[]::text[],
  source_refs text[] NOT NULL DEFAULT ARRAY[]::text[],
  stances text[] NOT NULL DEFAULT ARRAY[]::text[],
  max_evidence_strength double precision NOT NULL DEFAULT 0,
  positions jsonb NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY(meta_run_id, claim_id)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.claim_position_ledger (
  position_id text PRIMARY KEY,
  meta_run_id text NOT NULL,
  claim_id text NOT NULL,
  engine_id text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  stance text NOT NULL,
  claim_type text NOT NULL,
  force text NOT NULL,
  proposition text NOT NULL,
  source_refs text[] NOT NULL DEFAULT ARRAY[]::text[],
  evidence_kind text NOT NULL,
  evidence_strength double precision NOT NULL,
  claim_ceiling text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS destruktion_meta.claim_edge_ledger (
  meta_run_id text NOT NULL,
  edge_id text NOT NULL,
  from_claim_id text NOT NULL,
  to_claim_id text NOT NULL,
  kind text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, edge_id)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.disagreement_ledger (
  disagreement_id text PRIMARY KEY,
  meta_run_id text NOT NULL,
  claim_id text NOT NULL,
  kind text NOT NULL,
  engine_ids text[] NOT NULL,
  tension_score double precision NOT NULL,
  research_priority text NOT NULL,
  resolution_state text NOT NULL,
  positions jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.review_ledger (
  meta_run_id text NOT NULL,
  engine_id text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  review_state text NOT NULL,
  routing_role text,
  selected_disagreements text[] NOT NULL DEFAULT ARRAY[]::text[],
  payload jsonb NOT NULL,
  PRIMARY KEY(meta_run_id, engine_id)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.arbitration_ledger (
  meta_run_id text NOT NULL,
  claim_id text NOT NULL,
  state text NOT NULL,
  reason text NOT NULL,
  disagreement_id text,
  majority_vote_used boolean NOT NULL DEFAULT false,
  decision jsonb NOT NULL,
  PRIMARY KEY(meta_run_id, claim_id)
);
CREATE INDEX IF NOT EXISTS idx_dm_claim_run ON destruktion_meta.claim_ledger(meta_run_id);
CREATE INDEX IF NOT EXISTS idx_dm_claim_position_run_engine ON destruktion_meta.claim_position_ledger(meta_run_id,engine_id);
CREATE INDEX IF NOT EXISTS idx_dm_disagreement_run_priority ON destruktion_meta.disagreement_ledger(meta_run_id,research_priority,resolution_state);
CREATE INDEX IF NOT EXISTS idx_dm_arbitration_run_state ON destruktion_meta.arbitration_ledger(meta_run_id,state);
