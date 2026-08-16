-- Metaengine Stage D6-D Federated Chat Fabric ledger.
-- Canonical checkpoint authority remains destruktion_meta.chat_capsule_checkpoint.
-- Federation objects are private and callable only through fixed service-role RPCs.

create schema if not exists destruktion_meta;
revoke usage on schema destruktion_meta from anon, authenticated;
grant usage on schema destruktion_meta to service_role;

create table if not exists destruktion_meta.federated_epoch (
  epoch_id text primary key,
  base_checkpoint_id text not null references destruktion_meta.chat_capsule_checkpoint(checkpoint_id),
  base_payload_root text not null check (base_payload_root ~ '^[0-9a-f]{64}$'),
  federation_policy_hash text not null check (federation_policy_hash ~ '^[0-9a-f]{64}$'),
  role_catalog_hash text not null check (role_catalog_hash ~ '^[0-9a-f]{64}$'),
  producer_concurrency integer not null check (producer_concurrency between 2 and 6),
  state text not null check (state in ('OPEN','INTEGRATING','CLOSED','ABORTED')),
  created_at timestamptz not null default now(),
  closed_at timestamptz
);

create table if not exists destruktion_meta.federated_slot (
  slot_id text primary key check (slot_id in ('C0','C1','C2','C3','C4','C5','C6','C7')),
  role_name text not null,
  state text not null check (state in ('ACTIVE','IDLE','REVIEW_ONLY','SUSPENDED','RECLAIMABLE')),
  lease_generation bigint not null default 0 check (lease_generation >= 0)
);

insert into destruktion_meta.federated_slot(slot_id, role_name, state)
values
  ('C0','SYNCHRONIZER_INTEGRATOR','IDLE'),
  ('C1','ARCHITECTURE','IDLE'),
  ('C2','CORE_ENGINE','IDLE'),
  ('C3','AI_SWARM','IDLE'),
  ('C4','EDGE_MCP','IDLE'),
  ('C5','DATA_SERVICES','IDLE'),
  ('C6','VERIFICATION_SECURITY','REVIEW_ONLY'),
  ('C7','RESEARCH_BENCHMARK','IDLE')
on conflict (slot_id) do update set role_name = excluded.role_name;

create table if not exists destruktion_meta.federated_role_genome (
  role_profile_hash text primary key check (role_profile_hash ~ '^[0-9a-f]{64}$'),
  slot_id text not null references destruktion_meta.federated_slot(slot_id),
  genome_version text not null,
  parent_profile_hash text references destruktion_meta.federated_role_genome(role_profile_hash),
  hard_genome jsonb not null,
  soft_genome jsonb not null,
  created_at timestamptz not null default now(),
  unique (slot_id, genome_version)
);

create table if not exists destruktion_meta.federated_session (
  session_id text primary key,
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  slot_id text not null references destruktion_meta.federated_slot(slot_id),
  lease_generation bigint not null,
  capsule_sha256 text not null check (capsule_sha256 ~ '^[0-9a-f]{64}$'),
  protocol_version text not null,
  role_profile_hash text not null references destruktion_meta.federated_role_genome(role_profile_hash),
  revoked boolean not null default false,
  released_at timestamptz,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create unique index if not exists federated_session_one_active_slot
  on destruktion_meta.federated_session(epoch_id, slot_id)
  where revoked = false and released_at is null;

create table if not exists destruktion_meta.federated_task (
  task_hash text primary key check (task_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  task_version integer not null check (task_version > 0),
  owner_slot text not null references destruktion_meta.federated_slot(slot_id),
  role_profile_hash text not null references destruktion_meta.federated_role_genome(role_profile_hash),
  base_checkpoint_id text not null references destruktion_meta.chat_capsule_checkpoint(checkpoint_id),
  envelope jsonb not null,
  state text not null check (state in ('OPEN','CLAIMED','TERMINAL','CANCELLED')),
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_assignment (
  assignment_id text primary key,
  task_hash text not null references destruktion_meta.federated_task(task_hash),
  session_id text not null references destruktion_meta.federated_session(session_id),
  lease_generation bigint not null,
  assignment_state text not null check (assignment_state in ('CLAIMED','RELEASED','COMPLETED','STALE_FENCED')),
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_candidate_receipt (
  candidate_hash text primary key check (candidate_hash ~ '^[0-9a-f]{64}$'),
  task_hash text not null references destruktion_meta.federated_task(task_hash),
  session_id text not null references destruktion_meta.federated_session(session_id),
  lease_generation bigint not null,
  receipt jsonb not null,
  eligibility text not null check (eligibility in ('ELIGIBLE','STALE_FENCED','STALE_TASK_VERSION','MISSING_REVIEW','REJECTED')),
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_review_receipt (
  review_hash text primary key check (review_hash ~ '^[0-9a-f]{64}$'),
  candidate_hash text not null references destruktion_meta.federated_candidate_receipt(candidate_hash),
  session_id text not null references destruktion_meta.federated_session(session_id),
  lease_generation bigint not null,
  verdict text not null check (verdict in ('PASS','FAIL','INCONCLUSIVE','INCONCLUSIVE_SECURITY_FEED')),
  receipt jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_conflict_event (
  conflict_hash text primary key check (conflict_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  conflict_class text not null,
  left_candidate_hash text references destruktion_meta.federated_candidate_receipt(candidate_hash),
  right_candidate_hash text references destruktion_meta.federated_candidate_receipt(candidate_hash),
  resolution_receipt_hash text,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_integration_decision (
  decision_hash text primary key check (decision_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  candidate_hash text references destruktion_meta.federated_candidate_receipt(candidate_hash),
  decision text not null check (decision in ('INCLUDE','EXCLUDE','CONFLICT_TASK','STALE')),
  reason text not null,
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_sync_snapshot (
  snapshot_hash text primary key check (snapshot_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  snapshot jsonb not null,
  checkpoint_proposal_hash text,
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_role_outcome (
  outcome_hash text primary key check (outcome_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  slot_id text not null references destruktion_meta.federated_slot(slot_id),
  role_profile_hash text not null references destruktion_meta.federated_role_genome(role_profile_hash),
  metrics jsonb not null,
  created_at timestamptz not null default now()
);

-- RLS and table privileges are defense in depth. service_role is the only runtime DML role.
alter table destruktion_meta.federated_epoch enable row level security;
alter table destruktion_meta.federated_epoch force row level security;
revoke all on table destruktion_meta.federated_epoch from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_epoch to service_role;

alter table destruktion_meta.federated_slot enable row level security;
alter table destruktion_meta.federated_slot force row level security;
revoke all on table destruktion_meta.federated_slot from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_slot to service_role;

alter table destruktion_meta.federated_role_genome enable row level security;
alter table destruktion_meta.federated_role_genome force row level security;
revoke all on table destruktion_meta.federated_role_genome from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_role_genome to service_role;

alter table destruktion_meta.federated_session enable row level security;
alter table destruktion_meta.federated_session force row level security;
revoke all on table destruktion_meta.federated_session from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_session to service_role;

alter table destruktion_meta.federated_task enable row level security;
alter table destruktion_meta.federated_task force row level security;
revoke all on table destruktion_meta.federated_task from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_task to service_role;

alter table destruktion_meta.federated_assignment enable row level security;
alter table destruktion_meta.federated_assignment force row level security;
revoke all on table destruktion_meta.federated_assignment from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_assignment to service_role;

alter table destruktion_meta.federated_candidate_receipt enable row level security;
alter table destruktion_meta.federated_candidate_receipt force row level security;
revoke all on table destruktion_meta.federated_candidate_receipt from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_candidate_receipt to service_role;

alter table destruktion_meta.federated_review_receipt enable row level security;
alter table destruktion_meta.federated_review_receipt force row level security;
revoke all on table destruktion_meta.federated_review_receipt from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_review_receipt to service_role;

alter table destruktion_meta.federated_conflict_event enable row level security;
alter table destruktion_meta.federated_conflict_event force row level security;
revoke all on table destruktion_meta.federated_conflict_event from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_conflict_event to service_role;

alter table destruktion_meta.federated_integration_decision enable row level security;
alter table destruktion_meta.federated_integration_decision force row level security;
revoke all on table destruktion_meta.federated_integration_decision from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_integration_decision to service_role;

alter table destruktion_meta.federated_sync_snapshot enable row level security;
alter table destruktion_meta.federated_sync_snapshot force row level security;
revoke all on table destruktion_meta.federated_sync_snapshot from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_sync_snapshot to service_role;

alter table destruktion_meta.federated_role_outcome enable row level security;
alter table destruktion_meta.federated_role_outcome force row level security;
revoke all on table destruktion_meta.federated_role_outcome from anon, authenticated;
grant select, insert, update, delete on table destruktion_meta.federated_role_outcome to service_role;


-- Federation FK/query-path indexes for bounded multi-chat concurrency.
create index if not exists idx_fed_epoch_base_checkpoint on destruktion_meta.federated_epoch(base_checkpoint_id);
create index if not exists idx_fed_role_parent on destruktion_meta.federated_role_genome(parent_profile_hash);
create index if not exists idx_fed_session_slot on destruktion_meta.federated_session(slot_id);
create index if not exists idx_fed_session_role on destruktion_meta.federated_session(role_profile_hash);
create index if not exists idx_fed_task_epoch on destruktion_meta.federated_task(epoch_id);
create index if not exists idx_fed_task_owner on destruktion_meta.federated_task(owner_slot);
create index if not exists idx_fed_task_role on destruktion_meta.federated_task(role_profile_hash);
create index if not exists idx_fed_task_checkpoint on destruktion_meta.federated_task(base_checkpoint_id);
create index if not exists idx_fed_assignment_task on destruktion_meta.federated_assignment(task_hash);
create index if not exists idx_fed_assignment_session on destruktion_meta.federated_assignment(session_id);
create index if not exists idx_fed_candidate_task on destruktion_meta.federated_candidate_receipt(task_hash);
create index if not exists idx_fed_candidate_session on destruktion_meta.federated_candidate_receipt(session_id);
create index if not exists idx_fed_review_candidate on destruktion_meta.federated_review_receipt(candidate_hash);
create index if not exists idx_fed_review_session on destruktion_meta.federated_review_receipt(session_id);
create index if not exists idx_fed_conflict_epoch on destruktion_meta.federated_conflict_event(epoch_id);
create index if not exists idx_fed_conflict_left on destruktion_meta.federated_conflict_event(left_candidate_hash);
create index if not exists idx_fed_conflict_right on destruktion_meta.federated_conflict_event(right_candidate_hash);
create index if not exists idx_fed_decision_epoch on destruktion_meta.federated_integration_decision(epoch_id);
create index if not exists idx_fed_decision_candidate on destruktion_meta.federated_integration_decision(candidate_hash);
create index if not exists idx_fed_snapshot_epoch on destruktion_meta.federated_sync_snapshot(epoch_id);
create index if not exists idx_fed_outcome_epoch on destruktion_meta.federated_role_outcome(epoch_id);
create index if not exists idx_fed_outcome_slot on destruktion_meta.federated_role_outcome(slot_id);
create index if not exists idx_fed_outcome_role on destruktion_meta.federated_role_outcome(role_profile_hash);

-- Read-only RPCs. All return JSON so the caller sees a stable, narrow surface.
create or replace function public.metaengine_federation_status_v1(p_epoch_id text)
returns jsonb
language sql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
  select jsonb_build_object(
    'epoch', to_jsonb(e),
    'active_sessions', (select count(*) from destruktion_meta.federated_session s where s.epoch_id = e.epoch_id and s.revoked = false and s.released_at is null),
    'open_tasks', (select count(*) from destruktion_meta.federated_task t where t.epoch_id = e.epoch_id and t.state in ('OPEN','CLAIMED')),
    'candidates', (select count(*) from destruktion_meta.federated_candidate_receipt c join destruktion_meta.federated_task t on t.task_hash = c.task_hash where t.epoch_id = e.epoch_id),
    'conflicts', (select count(*) from destruktion_meta.federated_conflict_event c where c.epoch_id = e.epoch_id)
  )
  from destruktion_meta.federated_epoch e
  where e.epoch_id = p_epoch_id;
$$;

create or replace function public.metaengine_federation_slot_catalog_v1()
returns jsonb
language sql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
  select coalesce(jsonb_agg(to_jsonb(s) order by s.slot_id), '[]'::jsonb)
  from destruktion_meta.federated_slot s;
$$;

create or replace function public.metaengine_federation_session_status_v1(p_session_id text)
returns jsonb
language sql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
  select to_jsonb(s)
  from destruktion_meta.federated_session s
  where s.session_id = p_session_id;
$$;

create or replace function public.metaengine_federation_epoch_status_v1(p_epoch_id text)
returns jsonb
language sql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
  select to_jsonb(e)
  from destruktion_meta.federated_epoch e
  where e.epoch_id = p_epoch_id;
$$;

create or replace function public.metaengine_federation_task_get_v1(p_session_id text, p_task_hash text)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
declare
  v_epoch_id text;
  v_task jsonb;
begin
  select s.epoch_id into v_epoch_id
  from destruktion_meta.federated_session s
  where s.session_id = p_session_id and s.revoked = false and s.released_at is null;
  if v_epoch_id is null then
    raise exception 'FEDERATION_SESSION_INACTIVE';
  end if;
  select to_jsonb(t) into v_task
  from destruktion_meta.federated_task t
  where t.task_hash = p_task_hash and t.epoch_id = v_epoch_id;
  return v_task;
end;
$$;

create or replace function public.metaengine_federation_task_dependencies_v1(p_session_id text, p_task_hash text)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
declare
  v_task jsonb;
begin
  v_task := public.metaengine_federation_task_get_v1(p_session_id, p_task_hash);
  if v_task is null then
    return null;
  end if;
  return coalesce(v_task -> 'envelope' -> 'dependencies', '[]'::jsonb);
end;
$$;

create or replace function public.metaengine_federation_candidate_status_v1(p_session_id text, p_candidate_hash text)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
declare
  v_epoch_id text;
  v_candidate jsonb;
begin
  select s.epoch_id into v_epoch_id
  from destruktion_meta.federated_session s
  where s.session_id = p_session_id and s.revoked = false and s.released_at is null;
  if v_epoch_id is null then
    raise exception 'FEDERATION_SESSION_INACTIVE';
  end if;
  select to_jsonb(c) into v_candidate
  from destruktion_meta.federated_candidate_receipt c
  join destruktion_meta.federated_task t on t.task_hash = c.task_hash
  where c.candidate_hash = p_candidate_hash and t.epoch_id = v_epoch_id;
  return v_candidate;
end;
$$;

create or replace function public.metaengine_federation_conflict_status_v1(p_session_id text, p_epoch_id text)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
declare
  v_session_epoch text;
  v_result jsonb;
begin
  select s.epoch_id into v_session_epoch
  from destruktion_meta.federated_session s
  where s.session_id = p_session_id and s.revoked = false and s.released_at is null;
  if v_session_epoch is distinct from p_epoch_id then
    raise exception 'FEDERATION_EPOCH_MISMATCH';
  end if;
  select coalesce(jsonb_agg(to_jsonb(c) order by c.created_at, c.conflict_hash), '[]'::jsonb)
  into v_result
  from destruktion_meta.federated_conflict_event c
  where c.epoch_id = p_epoch_id;
  return v_result;
end;
$$;

create or replace function public.metaengine_federation_sync_snapshot_get_v1(p_session_id text, p_epoch_id text)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
declare
  v_session_epoch text;
  v_snapshot jsonb;
begin
  select s.epoch_id into v_session_epoch
  from destruktion_meta.federated_session s
  where s.session_id = p_session_id and s.revoked = false and s.released_at is null;
  if v_session_epoch is distinct from p_epoch_id then
    raise exception 'FEDERATION_EPOCH_MISMATCH';
  end if;
  select to_jsonb(x) into v_snapshot
  from destruktion_meta.federated_sync_snapshot x
  where x.epoch_id = p_epoch_id
  order by x.created_at desc, x.snapshot_hash desc
  limit 1;
  return v_snapshot;
end;
$$;

-- Guarded write RPCs.
create or replace function public.metaengine_federation_register_v1(
  p_epoch_id text,
  p_requested_slot text,
  p_session_id text,
  p_capsule_sha256 text,
  p_protocol_version text,
  p_role_profile_hash text
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_slot_id text;
  v_generation bigint;
  v_role_slot text;
  v_epoch_state text;
begin
  if p_capsule_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'FEDERATION_CAPSULE_HASH_INVALID';
  end if;
  if nullif(p_session_id, '') is null or nullif(p_protocol_version, '') is null then
    raise exception 'FEDERATION_SESSION_INPUT_INVALID';
  end if;
  select e.state into v_epoch_state from destruktion_meta.federated_epoch e where e.epoch_id = p_epoch_id;
  if v_epoch_state is distinct from 'OPEN' then
    raise exception 'FEDERATION_EPOCH_NOT_OPEN';
  end if;
  select g.slot_id into v_role_slot from destruktion_meta.federated_role_genome g where g.role_profile_hash = p_role_profile_hash;
  if v_role_slot is null then
    raise exception 'FEDERATION_ROLE_PROFILE_UNKNOWN';
  end if;
  if p_requested_slot = 'AUTO' then
    v_slot_id := v_role_slot;
  else
    v_slot_id := p_requested_slot;
  end if;
  if v_slot_id not in ('C0','C1','C2','C3','C4','C5','C6','C7') or v_slot_id is distinct from v_role_slot then
    raise exception 'FEDERATION_ROLE_SLOT_MISMATCH';
  end if;
  if exists (
    select 1 from destruktion_meta.federated_session s
    where s.epoch_id = p_epoch_id and s.slot_id = v_slot_id and s.revoked = false and s.released_at is null
  ) then
    raise exception 'FEDERATION_SLOT_ALREADY_ACTIVE';
  end if;
  select s.lease_generation into v_generation
  from destruktion_meta.federated_slot s
  where s.slot_id = v_slot_id
  for update;
  v_generation := v_generation + 1;
  update destruktion_meta.federated_slot
  set lease_generation = v_generation,
      state = case when v_slot_id = 'C6' then 'REVIEW_ONLY' else 'ACTIVE' end
  where slot_id = v_slot_id;
  insert into destruktion_meta.federated_session(
    session_id, epoch_id, slot_id, lease_generation, capsule_sha256, protocol_version, role_profile_hash
  ) values (
    p_session_id, p_epoch_id, v_slot_id, v_generation, p_capsule_sha256, p_protocol_version, p_role_profile_hash
  );
  return jsonb_build_object('session_id', p_session_id, 'epoch_id', p_epoch_id, 'slot_id', v_slot_id, 'lease_generation', v_generation, 'role_profile_hash', p_role_profile_hash);
end;
$$;

create or replace function public.metaengine_federation_release_v1(p_session_id text, p_expected_generation bigint)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_slot_id text;
  v_generation bigint;
begin
  select s.slot_id, s.lease_generation into v_slot_id, v_generation
  from destruktion_meta.federated_session s
  where s.session_id = p_session_id and s.revoked = false and s.released_at is null
  for update;
  if v_slot_id is null then raise exception 'FEDERATION_SESSION_INACTIVE'; end if;
  if v_generation is distinct from p_expected_generation then raise exception 'FEDERATION_FENCE_MISMATCH'; end if;
  update destruktion_meta.federated_session set revoked = true, released_at = now(), last_seen_at = now() where session_id = p_session_id;
  update destruktion_meta.federated_assignment set assignment_state = 'RELEASED' where session_id = p_session_id and assignment_state = 'CLAIMED';
  if not exists (select 1 from destruktion_meta.federated_session s where s.slot_id = v_slot_id and s.revoked = false and s.released_at is null) then
    update destruktion_meta.federated_slot set state = case when v_slot_id = 'C6' then 'REVIEW_ONLY' else 'IDLE' end where slot_id = v_slot_id;
  end if;
  return jsonb_build_object('session_id', p_session_id, 'released', true, 'lease_generation', v_generation);
end;
$$;

create or replace function public.metaengine_federation_claim_task_v1(p_session_id text, p_task_hash text, p_expected_generation bigint)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_session destruktion_meta.federated_session%rowtype;
  v_task destruktion_meta.federated_task%rowtype;
  v_assignment_id text;
begin
  select * into v_session from destruktion_meta.federated_session s where s.session_id = p_session_id for update;
  if v_session.session_id is null or v_session.revoked or v_session.released_at is not null then raise exception 'FEDERATION_SESSION_INACTIVE'; end if;
  if v_session.lease_generation is distinct from p_expected_generation then raise exception 'FEDERATION_FENCE_MISMATCH'; end if;
  if (select lease_generation from destruktion_meta.federated_slot where slot_id = v_session.slot_id) is distinct from p_expected_generation then raise exception 'FEDERATION_FENCE_STALE'; end if;
  select * into v_task from destruktion_meta.federated_task t where t.task_hash = p_task_hash for update;
  if v_task.task_hash is null then raise exception 'FEDERATION_TASK_UNKNOWN'; end if;
  if v_task.epoch_id is distinct from v_session.epoch_id or v_task.owner_slot is distinct from v_session.slot_id then raise exception 'FEDERATION_TASK_NOT_OWNED'; end if;
  if v_task.state not in ('OPEN','CLAIMED') then raise exception 'FEDERATION_TASK_NOT_CLAIMABLE'; end if;
  v_assignment_id := p_task_hash || ':' || p_session_id || ':' || p_expected_generation::text;
  insert into destruktion_meta.federated_assignment(assignment_id, task_hash, session_id, lease_generation, assignment_state)
  values (v_assignment_id, p_task_hash, p_session_id, p_expected_generation, 'CLAIMED')
  on conflict (assignment_id) do update set assignment_state = 'CLAIMED';
  update destruktion_meta.federated_task set state = 'CLAIMED' where task_hash = p_task_hash;
  update destruktion_meta.federated_session set last_seen_at = now() where session_id = p_session_id;
  return jsonb_build_object('assignment_id', v_assignment_id, 'task_hash', p_task_hash, 'lease_generation', p_expected_generation);
end;
$$;

create or replace function public.metaengine_federation_progress_v1(p_session_id text, p_task_hash text, p_expected_generation bigint, p_progress jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_valid boolean;
begin
  select true into v_valid
  from destruktion_meta.federated_session s
  join destruktion_meta.federated_task t on t.epoch_id = s.epoch_id and t.owner_slot = s.slot_id
  where s.session_id = p_session_id and s.revoked = false and s.released_at is null
    and s.lease_generation = p_expected_generation
    and t.task_hash = p_task_hash
    and exists (select 1 from destruktion_meta.federated_slot sl where sl.slot_id = s.slot_id and sl.lease_generation = p_expected_generation);
  if coalesce(v_valid, false) = false then raise exception 'FEDERATION_PROGRESS_FENCED'; end if;
  if jsonb_typeof(p_progress) is distinct from 'object' then raise exception 'FEDERATION_PROGRESS_INVALID'; end if;
  update destruktion_meta.federated_session set last_seen_at = now() where session_id = p_session_id;
  return jsonb_build_object('accepted', true, 'task_hash', p_task_hash, 'lease_generation', p_expected_generation);
end;
$$;

create or replace function public.metaengine_federation_submit_candidate_v1(
  p_session_id text,
  p_expected_generation bigint,
  p_candidate_hash text,
  p_task_hash text,
  p_receipt jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_session destruktion_meta.federated_session%rowtype;
  v_task destruktion_meta.federated_task%rowtype;
  v_slot_generation bigint;
  v_eligibility text;
  v_risk text;
begin
  if p_candidate_hash !~ '^[0-9a-f]{64}$' then raise exception 'FEDERATION_CANDIDATE_HASH_INVALID'; end if;
  select * into v_session from destruktion_meta.federated_session s where s.session_id = p_session_id;
  select * into v_task from destruktion_meta.federated_task t where t.task_hash = p_task_hash;
  if v_session.session_id is null or v_task.task_hash is null or v_session.epoch_id is distinct from v_task.epoch_id or v_session.slot_id is distinct from v_task.owner_slot then
    raise exception 'FEDERATION_CANDIDATE_CONTEXT_INVALID';
  end if;
  select sl.lease_generation into v_slot_generation from destruktion_meta.federated_slot sl where sl.slot_id = v_session.slot_id;
  if v_session.revoked or v_session.released_at is not null or v_session.lease_generation is distinct from p_expected_generation or v_slot_generation is distinct from p_expected_generation then
    v_eligibility := 'STALE_FENCED';
  elsif v_task.state in ('CANCELLED','TERMINAL') then
    v_eligibility := 'REJECTED';
  else
    v_risk := coalesce(v_task.envelope -> 'base_task' ->> 'risk_class', v_task.envelope ->> 'risk_class', 'NORMAL');
    if v_risk in ('HIGH','RELEASE') then v_eligibility := 'MISSING_REVIEW'; else v_eligibility := 'ELIGIBLE'; end if;
  end if;
  insert into destruktion_meta.federated_candidate_receipt(candidate_hash, task_hash, session_id, lease_generation, receipt, eligibility)
  values (p_candidate_hash, p_task_hash, p_session_id, p_expected_generation, p_receipt, v_eligibility)
  on conflict (candidate_hash) do nothing;
  if v_eligibility <> 'STALE_FENCED' then
    update destruktion_meta.federated_assignment set assignment_state = 'COMPLETED' where task_hash = p_task_hash and session_id = p_session_id and lease_generation = p_expected_generation;
  end if;
  update destruktion_meta.federated_session set last_seen_at = now() where session_id = p_session_id;
  return jsonb_build_object('candidate_hash', p_candidate_hash, 'eligibility', v_eligibility);
end;
$$;

create or replace function public.metaengine_federation_submit_review_v1(
  p_session_id text,
  p_expected_generation bigint,
  p_review_hash text,
  p_candidate_hash text,
  p_receipt jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_session destruktion_meta.federated_session%rowtype;
  v_candidate destruktion_meta.federated_candidate_receipt%rowtype;
  v_task_epoch text;
  v_slot_generation bigint;
  v_verdict text;
begin
  if p_review_hash !~ '^[0-9a-f]{64}$' then raise exception 'FEDERATION_REVIEW_HASH_INVALID'; end if;
  select * into v_session from destruktion_meta.federated_session s where s.session_id = p_session_id;
  if v_session.session_id is null or v_session.slot_id <> 'C6' or v_session.revoked or v_session.released_at is not null then raise exception 'FEDERATION_REVIEWER_INVALID'; end if;
  select sl.lease_generation into v_slot_generation from destruktion_meta.federated_slot sl where sl.slot_id = 'C6';
  if v_session.lease_generation is distinct from p_expected_generation or v_slot_generation is distinct from p_expected_generation then raise exception 'FEDERATION_REVIEW_FENCED'; end if;
  select * into v_candidate from destruktion_meta.federated_candidate_receipt c where c.candidate_hash = p_candidate_hash;
  if v_candidate.candidate_hash is null or v_candidate.session_id = p_session_id then raise exception 'FEDERATION_REVIEW_TARGET_INVALID'; end if;
  select t.epoch_id into v_task_epoch from destruktion_meta.federated_task t where t.task_hash = v_candidate.task_hash;
  if v_task_epoch is distinct from v_session.epoch_id then raise exception 'FEDERATION_REVIEW_EPOCH_MISMATCH'; end if;
  v_verdict := p_receipt ->> 'verdict';
  if v_verdict not in ('PASS','FAIL','INCONCLUSIVE','INCONCLUSIVE_SECURITY_FEED') then raise exception 'FEDERATION_REVIEW_VERDICT_INVALID'; end if;
  insert into destruktion_meta.federated_review_receipt(review_hash, candidate_hash, session_id, lease_generation, verdict, receipt)
  values (p_review_hash, p_candidate_hash, p_session_id, p_expected_generation, v_verdict, p_receipt)
  on conflict (review_hash) do nothing;
  if v_verdict = 'PASS' and v_candidate.eligibility = 'MISSING_REVIEW' then
    update destruktion_meta.federated_candidate_receipt set eligibility = 'ELIGIBLE' where candidate_hash = p_candidate_hash;
  elsif v_verdict = 'FAIL' then
    update destruktion_meta.federated_candidate_receipt set eligibility = 'REJECTED' where candidate_hash = p_candidate_hash;
  end if;
  update destruktion_meta.federated_session set last_seen_at = now() where session_id = p_session_id;
  return jsonb_build_object('review_hash', p_review_hash, 'candidate_hash', p_candidate_hash, 'verdict', v_verdict);
end;
$$;

create or replace function public.metaengine_federation_submit_conflict_v1(
  p_session_id text,
  p_expected_generation bigint,
  p_conflict_hash text,
  p_epoch_id text,
  p_payload jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_session destruktion_meta.federated_session%rowtype;
  v_slot_generation bigint;
begin
  if p_conflict_hash !~ '^[0-9a-f]{64}$' then raise exception 'FEDERATION_CONFLICT_HASH_INVALID'; end if;
  select * into v_session from destruktion_meta.federated_session s where s.session_id = p_session_id;
  select sl.lease_generation into v_slot_generation from destruktion_meta.federated_slot sl where sl.slot_id = v_session.slot_id;
  if v_session.session_id is null or v_session.revoked or v_session.released_at is not null or v_session.epoch_id is distinct from p_epoch_id or v_session.lease_generation is distinct from p_expected_generation or v_slot_generation is distinct from p_expected_generation then
    raise exception 'FEDERATION_CONFLICT_FENCED';
  end if;
  insert into destruktion_meta.federated_conflict_event(conflict_hash, epoch_id, conflict_class, left_candidate_hash, right_candidate_hash, resolution_receipt_hash, payload)
  values (
    p_conflict_hash,
    p_epoch_id,
    coalesce(p_payload ->> 'conflict_class', 'UNSPECIFIED'),
    nullif(p_payload ->> 'left_candidate_hash',''),
    nullif(p_payload ->> 'right_candidate_hash',''),
    nullif(p_payload ->> 'resolution_receipt_hash',''),
    p_payload
  ) on conflict (conflict_hash) do nothing;
  return jsonb_build_object('conflict_hash', p_conflict_hash, 'accepted', true);
end;
$$;

create or replace function public.metaengine_federation_propose_integration_v1(
  p_session_id text,
  p_expected_generation bigint,
  p_decision_hash text,
  p_epoch_id text,
  p_candidate_hash text,
  p_decision text,
  p_reason text
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_session destruktion_meta.federated_session%rowtype;
  v_candidate destruktion_meta.federated_candidate_receipt%rowtype;
  v_slot_generation bigint;
  v_risk text;
  v_current_review boolean;
begin
  if p_decision_hash !~ '^[0-9a-f]{64}$' then raise exception 'FEDERATION_DECISION_HASH_INVALID'; end if;
  if p_decision not in ('INCLUDE','EXCLUDE','CONFLICT_TASK','STALE') then raise exception 'FEDERATION_DECISION_INVALID'; end if;
  select * into v_session from destruktion_meta.federated_session s where s.session_id = p_session_id;
  select sl.lease_generation into v_slot_generation from destruktion_meta.federated_slot sl where sl.slot_id = v_session.slot_id;
  if v_session.session_id is null or v_session.slot_id <> 'C0' or v_session.revoked or v_session.released_at is not null or v_session.epoch_id is distinct from p_epoch_id or v_session.lease_generation is distinct from p_expected_generation or v_slot_generation is distinct from p_expected_generation then
    raise exception 'FEDERATION_SYNCHRONIZER_FENCED';
  end if;
  if p_candidate_hash is not null then
    select * into v_candidate from destruktion_meta.federated_candidate_receipt c where c.candidate_hash = p_candidate_hash;
    if v_candidate.candidate_hash is null then raise exception 'FEDERATION_CANDIDATE_UNKNOWN'; end if;
  end if;
  if p_decision = 'INCLUDE' then
    if v_candidate.eligibility is distinct from 'ELIGIBLE' then raise exception 'FEDERATION_CANDIDATE_NOT_ELIGIBLE'; end if;
    if exists (
      select 1 from destruktion_meta.federated_session cs
      join destruktion_meta.federated_slot sl on sl.slot_id = cs.slot_id
      where cs.session_id = v_candidate.session_id
        and (cs.revoked or cs.released_at is not null or cs.lease_generation <> sl.lease_generation)
    ) then raise exception 'FEDERATION_CANDIDATE_STALE'; end if;
    select coalesce(t.envelope -> 'base_task' ->> 'risk_class', t.envelope ->> 'risk_class', 'NORMAL') into v_risk from destruktion_meta.federated_task t where t.task_hash = v_candidate.task_hash;
    if v_risk in ('HIGH','RELEASE') then
      select exists (
        select 1
        from destruktion_meta.federated_review_receipt r
        join destruktion_meta.federated_session rs on rs.session_id = r.session_id
        join destruktion_meta.federated_slot sl on sl.slot_id = rs.slot_id
        where r.candidate_hash = p_candidate_hash
          and r.verdict = 'PASS'
          and rs.slot_id = 'C6'
          and rs.revoked = false
          and rs.released_at is null
          and r.lease_generation = rs.lease_generation
          and rs.lease_generation = sl.lease_generation
      ) into v_current_review;
      if coalesce(v_current_review,false) = false then raise exception 'FEDERATION_REVIEW_STALE_OR_MISSING'; end if;
    end if;
  end if;
  insert into destruktion_meta.federated_integration_decision(decision_hash, epoch_id, candidate_hash, decision, reason)
  values (p_decision_hash, p_epoch_id, p_candidate_hash, p_decision, p_reason)
  on conflict (decision_hash) do nothing;
  return jsonb_build_object('decision_hash', p_decision_hash, 'decision', p_decision, 'accepted', true);
end;
$$;

create or replace function public.metaengine_federation_publish_snapshot_v1(
  p_session_id text,
  p_expected_generation bigint,
  p_snapshot_hash text,
  p_epoch_id text,
  p_snapshot jsonb,
  p_checkpoint_proposal_hash text
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_session destruktion_meta.federated_session%rowtype;
  v_slot_generation bigint;
begin
  if p_snapshot_hash !~ '^[0-9a-f]{64}$' then raise exception 'FEDERATION_SNAPSHOT_HASH_INVALID'; end if;
  if p_checkpoint_proposal_hash is not null and p_checkpoint_proposal_hash !~ '^[0-9a-f]{64}$' then raise exception 'FEDERATION_PROPOSAL_HASH_INVALID'; end if;
  select * into v_session from destruktion_meta.federated_session s where s.session_id = p_session_id;
  select sl.lease_generation into v_slot_generation from destruktion_meta.federated_slot sl where sl.slot_id = v_session.slot_id;
  if v_session.session_id is null or v_session.slot_id <> 'C0' or v_session.revoked or v_session.released_at is not null or v_session.epoch_id is distinct from p_epoch_id or v_session.lease_generation is distinct from p_expected_generation or v_slot_generation is distinct from p_expected_generation then
    raise exception 'FEDERATION_SYNCHRONIZER_FENCED';
  end if;
  insert into destruktion_meta.federated_sync_snapshot(snapshot_hash, epoch_id, snapshot, checkpoint_proposal_hash)
  values (p_snapshot_hash, p_epoch_id, p_snapshot, p_checkpoint_proposal_hash)
  on conflict (snapshot_hash) do nothing;
  return jsonb_build_object('snapshot_hash', p_snapshot_hash, 'accepted', true);
end;
$$;

-- Internal control-plane RPCs. They are intentionally not part of the chat-facing MCP allowlist.
create or replace function public.metaengine_federation_open_epoch_v1(
  p_epoch_id text,
  p_base_checkpoint_id text,
  p_base_payload_root text,
  p_federation_policy_hash text,
  p_role_catalog_hash text,
  p_producer_concurrency integer
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
begin
  insert into destruktion_meta.federated_epoch(epoch_id, base_checkpoint_id, base_payload_root, federation_policy_hash, role_catalog_hash, producer_concurrency, state)
  values (p_epoch_id, p_base_checkpoint_id, p_base_payload_root, p_federation_policy_hash, p_role_catalog_hash, p_producer_concurrency, 'OPEN')
  on conflict (epoch_id) do nothing;
  return jsonb_build_object('epoch_id', p_epoch_id, 'state', 'OPEN');
end;
$$;

create or replace function public.metaengine_federation_seed_task_v1(
  p_task_hash text,
  p_epoch_id text,
  p_task_version integer,
  p_owner_slot text,
  p_role_profile_hash text,
  p_base_checkpoint_id text,
  p_envelope jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_role_slot text;
  v_epoch_checkpoint text;
begin
  if p_task_hash !~ '^[0-9a-f]{64}$' then raise exception 'FEDERATION_TASK_HASH_INVALID'; end if;
  select g.slot_id into v_role_slot from destruktion_meta.federated_role_genome g where g.role_profile_hash = p_role_profile_hash;
  if v_role_slot is distinct from p_owner_slot then raise exception 'FEDERATION_TASK_ROLE_MISMATCH'; end if;
  select e.base_checkpoint_id into v_epoch_checkpoint from destruktion_meta.federated_epoch e where e.epoch_id = p_epoch_id and e.state = 'OPEN';
  if v_epoch_checkpoint is null or v_epoch_checkpoint is distinct from p_base_checkpoint_id then raise exception 'FEDERATION_TASK_CHECKPOINT_MISMATCH'; end if;
  insert into destruktion_meta.federated_task(task_hash, epoch_id, task_version, owner_slot, role_profile_hash, base_checkpoint_id, envelope, state)
  values (p_task_hash, p_epoch_id, p_task_version, p_owner_slot, p_role_profile_hash, p_base_checkpoint_id, p_envelope, 'OPEN')
  on conflict (task_hash) do nothing;
  return jsonb_build_object('task_hash', p_task_hash, 'state', 'OPEN');
end;
$$;

create or replace function public.metaengine_federation_seed_role_genome_v1(
  p_role_profile_hash text,
  p_slot_id text,
  p_genome_version text,
  p_parent_profile_hash text,
  p_hard_genome jsonb,
  p_soft_genome jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
begin
  if p_role_profile_hash !~ '^[0-9a-f]{64}$' then raise exception 'FEDERATION_ROLE_HASH_INVALID'; end if;
  if p_slot_id not in ('C0','C1','C2','C3','C4','C5','C6','C7') then raise exception 'FEDERATION_SLOT_INVALID'; end if;
  insert into destruktion_meta.federated_role_genome(role_profile_hash, slot_id, genome_version, parent_profile_hash, hard_genome, soft_genome)
  values (p_role_profile_hash, p_slot_id, p_genome_version, p_parent_profile_hash, p_hard_genome, p_soft_genome)
  on conflict (role_profile_hash) do nothing;
  return jsonb_build_object('role_profile_hash', p_role_profile_hash, 'slot_id', p_slot_id, 'genome_version', p_genome_version);
end;
$$;

create or replace function public.metaengine_federation_reclaim_slot_v1(p_epoch_id text, p_slot_id text, p_expected_generation bigint)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_generation bigint;
begin
  if p_slot_id not in ('C0','C1','C2','C3','C4','C5','C6','C7') then raise exception 'FEDERATION_SLOT_INVALID'; end if;
  select s.lease_generation into v_generation from destruktion_meta.federated_slot s where s.slot_id = p_slot_id for update;
  if v_generation is distinct from p_expected_generation then raise exception 'FEDERATION_FENCE_MISMATCH'; end if;
  update destruktion_meta.federated_session
  set revoked = true, released_at = coalesce(released_at, now()), last_seen_at = now()
  where epoch_id = p_epoch_id and slot_id = p_slot_id and revoked = false and released_at is null;
  update destruktion_meta.federated_assignment a
  set assignment_state = 'STALE_FENCED'
  where a.session_id in (select s.session_id from destruktion_meta.federated_session s where s.epoch_id = p_epoch_id and s.slot_id = p_slot_id)
    and a.assignment_state = 'CLAIMED';
  v_generation := v_generation + 1;
  update destruktion_meta.federated_slot
  set lease_generation = v_generation, state = 'RECLAIMABLE'
  where slot_id = p_slot_id;
  return jsonb_build_object('epoch_id', p_epoch_id, 'slot_id', p_slot_id, 'lease_generation', v_generation, 'reclaimed', true);
end;
$$;

-- Function privileges: never rely on default PUBLIC execute.
revoke all on function public.metaengine_federation_status_v1(text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_status_v1(text) to service_role;

revoke all on function public.metaengine_federation_slot_catalog_v1() from public, anon, authenticated;
grant execute on function public.metaengine_federation_slot_catalog_v1() to service_role;

revoke all on function public.metaengine_federation_session_status_v1(text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_session_status_v1(text) to service_role;

revoke all on function public.metaengine_federation_epoch_status_v1(text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_epoch_status_v1(text) to service_role;

revoke all on function public.metaengine_federation_task_get_v1(text,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_task_get_v1(text,text) to service_role;

revoke all on function public.metaengine_federation_task_dependencies_v1(text,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_task_dependencies_v1(text,text) to service_role;

revoke all on function public.metaengine_federation_candidate_status_v1(text,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_candidate_status_v1(text,text) to service_role;

revoke all on function public.metaengine_federation_conflict_status_v1(text,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_conflict_status_v1(text,text) to service_role;

revoke all on function public.metaengine_federation_sync_snapshot_get_v1(text,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_sync_snapshot_get_v1(text,text) to service_role;

revoke all on function public.metaengine_federation_register_v1(text,text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_register_v1(text,text,text,text,text,text) to service_role;

revoke all on function public.metaengine_federation_release_v1(text,bigint) from public, anon, authenticated;
grant execute on function public.metaengine_federation_release_v1(text,bigint) to service_role;

revoke all on function public.metaengine_federation_claim_task_v1(text,text,bigint) from public, anon, authenticated;
grant execute on function public.metaengine_federation_claim_task_v1(text,text,bigint) to service_role;

revoke all on function public.metaengine_federation_progress_v1(text,text,bigint,jsonb) from public, anon, authenticated;
grant execute on function public.metaengine_federation_progress_v1(text,text,bigint,jsonb) to service_role;

revoke all on function public.metaengine_federation_submit_candidate_v1(text,bigint,text,text,jsonb) from public, anon, authenticated;
grant execute on function public.metaengine_federation_submit_candidate_v1(text,bigint,text,text,jsonb) to service_role;

revoke all on function public.metaengine_federation_submit_review_v1(text,bigint,text,text,jsonb) from public, anon, authenticated;
grant execute on function public.metaengine_federation_submit_review_v1(text,bigint,text,text,jsonb) to service_role;

revoke all on function public.metaengine_federation_submit_conflict_v1(text,bigint,text,text,jsonb) from public, anon, authenticated;
grant execute on function public.metaengine_federation_submit_conflict_v1(text,bigint,text,text,jsonb) to service_role;

revoke all on function public.metaengine_federation_propose_integration_v1(text,bigint,text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_propose_integration_v1(text,bigint,text,text,text,text,text) to service_role;

revoke all on function public.metaengine_federation_publish_snapshot_v1(text,bigint,text,text,jsonb,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_publish_snapshot_v1(text,bigint,text,text,jsonb,text) to service_role;

revoke all on function public.metaengine_federation_open_epoch_v1(text,text,text,text,text,integer) from public, anon, authenticated;
grant execute on function public.metaengine_federation_open_epoch_v1(text,text,text,text,text,integer) to service_role;

revoke all on function public.metaengine_federation_seed_task_v1(text,text,integer,text,text,text,jsonb) from public, anon, authenticated;
grant execute on function public.metaengine_federation_seed_task_v1(text,text,integer,text,text,text,jsonb) to service_role;

revoke all on function public.metaengine_federation_seed_role_genome_v1(text,text,text,text,jsonb,jsonb) from public, anon, authenticated;
grant execute on function public.metaengine_federation_seed_role_genome_v1(text,text,text,text,jsonb,jsonb) to service_role;

revoke all on function public.metaengine_federation_reclaim_slot_v1(text,text,bigint) from public, anon, authenticated;
grant execute on function public.metaengine_federation_reclaim_slot_v1(text,text,bigint) to service_role;

