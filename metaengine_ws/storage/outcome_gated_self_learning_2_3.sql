BEGIN;

CREATE SCHEMA IF NOT EXISTS destruktion_meta;

CREATE TABLE IF NOT EXISTS destruktion_meta.architecture_policy (
    policy_hash text PRIMARY KEY,
    parent_policy_hash text REFERENCES destruktion_meta.architecture_policy(policy_hash),
    generation integer NOT NULL CHECK (generation >= 0),
    topology_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('DRAFT','SHADOW','ELIGIBLE','CANARY','ACTIVE','QUARANTINED','ROLLED_BACK','RETIRED')),
    guardrail_hash text NOT NULL,
    verifier_hash text NOT NULL,
    benchmark_hash text NOT NULL,
    mutation_receipt jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload jsonb NOT NULL,
    self_modifying_code_allowed boolean NOT NULL DEFAULT false CHECK (self_modifying_code_allowed = false),
    truth_effect text NOT NULL DEFAULT 'NONE' CHECK (truth_effect = 'NONE'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.evolution_generation (
    campaign_hash text NOT NULL,
    generation integer NOT NULL,
    champion_before text NOT NULL REFERENCES destruktion_meta.architecture_policy(policy_hash),
    champion_after text REFERENCES destruktion_meta.architecture_policy(policy_hash),
    freeze_hash text NOT NULL,
    decision_hash text NOT NULL,
    world_count integer NOT NULL CHECK (world_count > 0),
    candidate_count integer NOT NULL CHECK (candidate_count > 0),
    disposition text NOT NULL CHECK (disposition IN ('PROMOTED','RETAINED','QUARANTINED','ROLLED_BACK')),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_hash, generation)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.external_outcome (
    world_id text PRIMARY KEY,
    campaign_hash text NOT NULL,
    generation integer NOT NULL,
    policy_hash text NOT NULL REFERENCES destruktion_meta.architecture_policy(policy_hash),
    case_id text NOT NULL,
    suite text NOT NULL,
    seed bigint NOT NULL,
    candidate_hash text NOT NULL,
    oracle_commitment text NOT NULL,
    verifier_hash text NOT NULL,
    observed_outcome double precision CHECK (observed_outcome BETWEEN 0 AND 1),
    promotion_eligible boolean NOT NULL DEFAULT false,
    hard_failures text[] NOT NULL DEFAULT ARRAY[]::text[],
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    actual_cost jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_hash, generation, policy_hash, case_id, seed)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.promotion_receipt (
    promotion_receipt_hash text PRIMARY KEY,
    campaign_hash text NOT NULL,
    generation integer NOT NULL,
    expected_champion_hash text NOT NULL REFERENCES destruktion_meta.architecture_policy(policy_hash),
    candidate_policy_hash text NOT NULL REFERENCES destruktion_meta.architecture_policy(policy_hash),
    freeze_hash text NOT NULL,
    decision_hash text NOT NULL,
    paired_n integer NOT NULL CHECK (paired_n > 0),
    mean_quality_delta double precision NOT NULL,
    lower_confidence_bound double precision NOT NULL,
    cost_ratio double precision NOT NULL CHECK (cost_ratio > 0),
    suite_noninferiority boolean NOT NULL,
    hard_failure_count integer NOT NULL CHECK (hard_failure_count >= 0),
    promotion_eligible boolean NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_hash, generation)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.champion_pointer (
    pointer_id smallint PRIMARY KEY DEFAULT 1 CHECK (pointer_id = 1),
    policy_hash text NOT NULL REFERENCES destruktion_meta.architecture_policy(policy_hash),
    generation integer NOT NULL CHECK (generation >= 0),
    promotion_receipt_hash text REFERENCES destruktion_meta.promotion_receipt(promotion_receipt_hash),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.rollback_event (
    rollback_hash text PRIMARY KEY,
    from_policy_hash text NOT NULL REFERENCES destruktion_meta.architecture_policy(policy_hash),
    to_policy_hash text NOT NULL REFERENCES destruktion_meta.architecture_policy(policy_hash),
    reason text NOT NULL,
    canary_or_safety_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.verifier_outcome_telemetry (
    event_hash text PRIMARY KEY,
    meta_run_id text,
    world_id text,
    parent_event_hash text,
    event_kind text NOT NULL,
    monotonic_seconds double precision NOT NULL CHECK (monotonic_seconds >= 0),
    usage jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.dialectical_graph_ledger (
    meta_run_id text PRIMARY KEY,
    graph_hash text NOT NULL,
    policy_hash text NOT NULL REFERENCES destruktion_meta.architecture_policy(policy_hash),
    source_id text NOT NULL,
    operators_realized text[] NOT NULL DEFAULT ARRAY[]::text[],
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload jsonb NOT NULL,
    truth_effect text NOT NULL DEFAULT 'NONE' CHECK (truth_effect = 'NONE'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.verifier_report_ledger (
    meta_run_id text NOT NULL,
    verifier_hash text NOT NULL,
    candidate_hash text NOT NULL,
    verification_status text NOT NULL,
    observed_outcome double precision CHECK (observed_outcome BETWEEN 0 AND 1),
    promotion_eligible boolean NOT NULL DEFAULT false,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    hard_failures text[] NOT NULL DEFAULT ARRAY[]::text[],
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_run_id, verifier_hash)
);

CREATE INDEX IF NOT EXISTS idx_dm_outcome_policy_suite ON destruktion_meta.external_outcome(policy_hash, suite);
CREATE INDEX IF NOT EXISTS idx_dm_generation_champion ON destruktion_meta.evolution_generation(champion_after, generation DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dm_one_active_policy ON destruktion_meta.architecture_policy((status)) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_dm_policy_parent ON destruktion_meta.architecture_policy(parent_policy_hash);
CREATE INDEX IF NOT EXISTS idx_dm_champion_policy ON destruktion_meta.champion_pointer(policy_hash);
CREATE INDEX IF NOT EXISTS idx_dm_champion_receipt ON destruktion_meta.champion_pointer(promotion_receipt_hash);
CREATE INDEX IF NOT EXISTS idx_dm_dialectical_policy ON destruktion_meta.dialectical_graph_ledger(policy_hash);
CREATE INDEX IF NOT EXISTS idx_dm_generation_before ON destruktion_meta.evolution_generation(champion_before);
CREATE INDEX IF NOT EXISTS idx_dm_promotion_candidate ON destruktion_meta.promotion_receipt(candidate_policy_hash);
CREATE INDEX IF NOT EXISTS idx_dm_promotion_expected ON destruktion_meta.promotion_receipt(expected_champion_hash);
CREATE INDEX IF NOT EXISTS idx_dm_rollback_from ON destruktion_meta.rollback_event(from_policy_hash);
CREATE INDEX IF NOT EXISTS idx_dm_rollback_to ON destruktion_meta.rollback_event(to_policy_hash);

CREATE OR REPLACE FUNCTION destruktion_meta.promote_architecture_policy(
    expected_champion text,
    candidate text,
    receipt text
) RETURNS boolean
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
DECLARE
    changed integer;
    candidate_generation integer;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM destruktion_meta.promotion_receipt pr
        WHERE pr.promotion_receipt_hash = receipt
          AND pr.expected_champion_hash = expected_champion
          AND pr.candidate_policy_hash = candidate
          AND pr.promotion_eligible
          AND pr.suite_noninferiority
          AND pr.hard_failure_count = 0
          AND pr.lower_confidence_bound > 0
    ) THEN
        RAISE EXCEPTION 'PROMOTION_GATE_REJECTED';
    END IF;
    SELECT generation INTO candidate_generation
      FROM destruktion_meta.architecture_policy
     WHERE policy_hash = candidate AND status IN ('SHADOW','ELIGIBLE','CANARY');
    IF candidate_generation IS NULL THEN
        RAISE EXCEPTION 'CANDIDATE_POLICY_NOT_ELIGIBLE';
    END IF;
    UPDATE destruktion_meta.champion_pointer
       SET policy_hash = candidate, generation = candidate_generation,
           promotion_receipt_hash = receipt, updated_at = now()
     WHERE pointer_id = 1 AND policy_hash = expected_champion;
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 1 THEN
        RAISE EXCEPTION 'CHAMPION_COMPARE_AND_SWAP_FAILED';
    END IF;
    UPDATE destruktion_meta.architecture_policy SET status = 'ROLLED_BACK'
     WHERE policy_hash = expected_champion AND status = 'ACTIVE';
    UPDATE destruktion_meta.architecture_policy SET status = 'ACTIVE'
     WHERE policy_hash = candidate;
    RETURN true;
END;
$$;

-- Fail closed. A service transaction must explicitly SET LOCAL app.metaengine_writer = 'on'.
ALTER TABLE destruktion_meta.architecture_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.architecture_policy FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.evolution_generation ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.evolution_generation FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.external_outcome ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.external_outcome FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.promotion_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.promotion_receipt FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.champion_pointer ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.champion_pointer FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.rollback_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.rollback_event FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.verifier_outcome_telemetry ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.verifier_outcome_telemetry FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.dialectical_graph_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.dialectical_graph_ledger FORCE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.verifier_report_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE destruktion_meta.verifier_report_ledger FORCE ROW LEVEL SECURITY;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['architecture_policy','evolution_generation','external_outcome','promotion_receipt','champion_pointer','rollback_event','verifier_outcome_telemetry','dialectical_graph_ledger','verifier_report_ledger']
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
