BEGIN;

CREATE SCHEMA IF NOT EXISTS destruktion_meta;

CREATE TABLE IF NOT EXISTS destruktion_meta.frontier_task_ledger (
    meta_run_id text PRIMARY KEY,
    task_ledger_hash text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    claim_ceiling text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.frontier_handoff_ledger (
    meta_run_id text NOT NULL,
    round_index integer NOT NULL,
    handoff_hash text NOT NULL,
    engine_id text NOT NULL,
    workstream_id text NOT NULL,
    objective text NOT NULL,
    budget_units double precision NOT NULL DEFAULT 0,
    guardrails text[] NOT NULL DEFAULT ARRAY[]::text[],
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_run_id, round_index, handoff_hash)
);

CREATE INDEX IF NOT EXISTS idx_dm_frontier_handoff_engine
    ON destruktion_meta.frontier_handoff_ledger (engine_id, round_index);

CREATE TABLE IF NOT EXISTS destruktion_meta.frontier_candidate_ledger (
    meta_run_id text NOT NULL,
    candidate_id text NOT NULL,
    round_index integer NOT NULL,
    engine_id text NOT NULL,
    receipt_hash text,
    ensemble_score double precision NOT NULL,
    pareto_member boolean NOT NULL DEFAULT false,
    evaluator_scores jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    truth_effect text NOT NULL DEFAULT 'NONE' CHECK (truth_effect = 'NONE'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_run_id, candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_dm_frontier_candidate_rank
    ON destruktion_meta.frontier_candidate_ledger (meta_run_id, ensemble_score DESC);

CREATE TABLE IF NOT EXISTS destruktion_meta.frontier_progress_ledger (
    meta_run_id text NOT NULL,
    round_index integer NOT NULL,
    progress_ledger_hash text NOT NULL,
    selected_topology_id text,
    replan_required boolean NOT NULL DEFAULT false,
    stop_recommended boolean NOT NULL DEFAULT false,
    reasons text[] NOT NULL DEFAULT ARRAY[]::text[],
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_run_id, round_index)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.frontier_policy_candidate_ledger (
    meta_run_id text NOT NULL,
    policy_candidate_id text NOT NULL,
    round_index integer NOT NULL,
    mutation text NOT NULL,
    deployment_status text NOT NULL CHECK (deployment_status = 'SHADOW_ONLY'),
    acceptance_gate text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_run_id, policy_candidate_id)
);

ALTER TABLE destruktion_meta.frontier_task_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_task_ledger FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_handoff_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_handoff_ledger FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_candidate_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_candidate_ledger FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_progress_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_progress_ledger FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_policy_candidate_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.frontier_policy_candidate_ledger FORCE ROW LEVEL SECURITY;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['frontier_task_ledger','frontier_handoff_ledger','frontier_candidate_ledger','frontier_progress_ledger','frontier_policy_candidate_ledger']
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'destruktion_meta'
               AND tablename = table_name
               AND policyname = 'metaengine_explicit_writer'
        ) THEN
            EXECUTE format(
                'CREATE POLICY metaengine_explicit_writer ON destruktion_meta.%I FOR ALL TO PUBLIC USING ((SELECT current_setting(''app.metaengine_writer'', true)) = ''on'') WITH CHECK ((SELECT current_setting(''app.metaengine_writer'', true)) = ''on'')',
                table_name
            );
        END IF;
    END LOOP;
END;
$$;

COMMIT;
