-- Metaengine Stage D6-G0 Immutable Epoch Finalization.
-- This is a forward-only companion migration to federated_chat_fabric_d6.sql.
-- It does not alter canonical checkpoint/champion/policy authority.

create table destruktion_meta.federated_epoch_finalization (
  finalization_hash text primary key check (finalization_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null unique references destruktion_meta.federated_epoch(epoch_id),
  final_snapshot_hash text not null references destruktion_meta.federated_sync_snapshot(snapshot_hash),
  recovery_cut_hash text not null check (recovery_cut_hash ~ '^[0-9a-f]{64}$'),
  recovery_cut jsonb not null,
  finalized_by_session_id text not null references destruktion_meta.federated_session(session_id),
  finalized_by_generation bigint not null check (finalized_by_generation >= 0),
  protocol_version text not null,
  finalized_at timestamptz not null default now()
);

create index idx_fed_finalization_snapshot
  on destruktion_meta.federated_epoch_finalization(final_snapshot_hash);
create index idx_fed_finalization_session
  on destruktion_meta.federated_epoch_finalization(finalized_by_session_id);

alter table destruktion_meta.federated_epoch_finalization enable row level security;
alter table destruktion_meta.federated_epoch_finalization force row level security;
revoke all on table destruktion_meta.federated_epoch_finalization from public, anon, authenticated;
revoke all on table destruktion_meta.federated_epoch_finalization from service_role;
grant select, insert on table destruktion_meta.federated_epoch_finalization to service_role;
revoke update, delete on table destruktion_meta.federated_epoch_finalization from service_role;

create or replace function destruktion_meta.metaengine_federation_finalization_immutable_guard()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
begin
  raise exception 'FEDERATION_FINALIZATION_IMMUTABLE';
end;
$$;

revoke all on function destruktion_meta.metaengine_federation_finalization_immutable_guard() from public, anon, authenticated;
grant execute on function destruktion_meta.metaengine_federation_finalization_immutable_guard() to service_role;

drop trigger if exists federated_epoch_finalization_immutable on destruktion_meta.federated_epoch_finalization;
create trigger federated_epoch_finalization_immutable
before update or delete on destruktion_meta.federated_epoch_finalization
for each row execute function destruktion_meta.metaengine_federation_finalization_immutable_guard();

create or replace function public.metaengine_federation_finalization_get_v1(p_epoch_id text)
returns jsonb
language sql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
  select to_jsonb(f)
  from destruktion_meta.federated_epoch_finalization f
  where f.epoch_id = p_epoch_id;
$$;

create or replace function public.metaengine_federation_finalize_epoch_v1(
  p_session_id text,
  p_expected_generation bigint,
  p_epoch_id text,
  p_finalization_hash text,
  p_final_snapshot_hash text,
  p_recovery_cut_hash text,
  p_recovery_cut jsonb,
  p_protocol_version text
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_epoch destruktion_meta.federated_epoch%rowtype;
  v_session destruktion_meta.federated_session%rowtype;
  v_slot_generation bigint;
  v_snapshot destruktion_meta.federated_sync_snapshot%rowtype;
  v_existing destruktion_meta.federated_epoch_finalization%rowtype;
  v_live_cut jsonb;
begin
  if p_finalization_hash !~ '^[0-9a-f]{64}$'
     or p_final_snapshot_hash !~ '^[0-9a-f]{64}$'
     or p_recovery_cut_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'FEDERATION_FINALIZATION_HASH_INVALID';
  end if;
  if p_protocol_version is distinct from 'D6.FINALIZATION.1' then
    raise exception 'FEDERATION_FINALIZATION_VERSION_UNSUPPORTED';
  end if;
  if p_epoch_id is null or p_epoch_id = '' or p_session_id is null or p_session_id = '' then
    raise exception 'FEDERATION_FINALIZATION_IDENTITY_INVALID';
  end if;
  if p_expected_generation < 0 then
    raise exception 'FEDERATION_FINALIZATION_GENERATION_INVALID';
  end if;

  -- Idempotence is checked before terminal-state rejection.
  select * into v_existing
  from destruktion_meta.federated_epoch_finalization f
  where f.epoch_id = p_epoch_id;
  if v_existing.epoch_id is not null then
    if v_existing.finalization_hash = p_finalization_hash
       and v_existing.final_snapshot_hash = p_final_snapshot_hash
       and v_existing.recovery_cut_hash = p_recovery_cut_hash
       and v_existing.protocol_version = p_protocol_version then
      return jsonb_build_object(
        'epoch_id', p_epoch_id,
        'finalization_hash', v_existing.finalization_hash,
        'final_snapshot_hash', v_existing.final_snapshot_hash,
        'recovery_cut_hash', v_existing.recovery_cut_hash,
        'already_finalized', true
      );
    end if;
    raise exception 'FEDERATION_FINALIZATION_CONFLICT';
  end if;

  select * into v_epoch
  from destruktion_meta.federated_epoch e
  where e.epoch_id = p_epoch_id
  for update;
  if v_epoch.epoch_id is null then
    raise exception 'FEDERATION_EPOCH_UNKNOWN';
  end if;
  if v_epoch.state in ('CLOSED','ABORTED') then
    raise exception 'FEDERATION_EPOCH_IMMUTABLE';
  end if;
  if v_epoch.state not in ('OPEN','INTEGRATING') then
    raise exception 'FEDERATION_EPOCH_NOT_FINALIZABLE';
  end if;

  select * into v_session
  from destruktion_meta.federated_session s
  where s.session_id = p_session_id
  for update;
  if v_session.session_id is null
     or v_session.epoch_id is distinct from p_epoch_id
     or v_session.slot_id <> 'C0' then
    raise exception 'FEDERATION_FINALIZER_FORBIDDEN';
  end if;
  select sl.lease_generation into v_slot_generation
  from destruktion_meta.federated_slot sl
  where sl.slot_id = 'C0'
  for update;
  if v_session.revoked
     or v_session.released_at is not null
     or v_session.lease_generation is distinct from p_expected_generation
     or v_slot_generation is distinct from p_expected_generation then
    raise exception 'FEDERATION_SYNCHRONIZER_FENCED';
  end if;

  select * into v_snapshot
  from destruktion_meta.federated_sync_snapshot ss
  where ss.snapshot_hash = p_final_snapshot_hash
    and ss.epoch_id = p_epoch_id;
  if v_snapshot.snapshot_hash is null then
    raise exception 'FEDERATION_FINAL_SNAPSHOT_INVALID';
  end if;

  select jsonb_build_object(
    'cut_version', 'D6.FINALIZATION.1',
    'epoch', jsonb_build_object(
      'epoch_id', v_epoch.epoch_id,
      'base_checkpoint_id', v_epoch.base_checkpoint_id,
      'base_payload_root', v_epoch.base_payload_root,
      'federation_policy_hash', v_epoch.federation_policy_hash,
      'role_catalog_hash', v_epoch.role_catalog_hash,
      'producer_concurrency', v_epoch.producer_concurrency
    ),
    'tasks', coalesce((
      select jsonb_agg(jsonb_build_object(
        'task_hash', t.task_hash,
        'base_task_id', t.envelope -> 'base_task' ->> 'task_id',
        'task_version', t.task_version,
        'owner_slot', t.owner_slot,
        'lease_generation', coalesce((t.envelope ->> 'lease_generation')::bigint, 0),
        'role_profile_hash', t.role_profile_hash,
        'dependency_task_ids', coalesce(t.envelope -> 'dependency_task_ids', '[]'::jsonb),
        'write_set', coalesce(t.envelope -> 'write_set', '[]'::jsonb),
        'interface_set', coalesce(t.envelope -> 'interface_set', '[]'::jsonb),
        'risk_class', coalesce(t.envelope -> 'base_task' ->> 'risk_class', t.envelope ->> 'risk_class', 'NORMAL'),
        'privacy_class', coalesce(t.envelope -> 'base_task' ->> 'privacy_class', t.envelope ->> 'privacy_class', 'P1'),
        'review_slots', coalesce(t.envelope -> 'review_slots', '[]'::jsonb)
      ) order by t.task_hash)
      from destruktion_meta.federated_task t
      where t.epoch_id = p_epoch_id
    ), '[]'::jsonb),
    'assignments', coalesce((
      select jsonb_agg(jsonb_build_object(
        'assignment_id', a.assignment_id,
        'task_hash', a.task_hash,
        'session_id', a.session_id,
        'lease_generation', a.lease_generation,
        'assignment_state', a.assignment_state
      ) order by a.assignment_id)
      from destruktion_meta.federated_assignment a
      join destruktion_meta.federated_task t on t.task_hash = a.task_hash
      where t.epoch_id = p_epoch_id
    ), '[]'::jsonb),
    'candidates', coalesce((
      select jsonb_agg(jsonb_build_object(
        'candidate_hash', c.candidate_hash,
        'task_hash', c.task_hash,
        'task_version', coalesce((c.receipt ->> 'task_version')::integer, t.task_version),
        'session_id', c.session_id,
        'lease_generation', c.lease_generation,
        'role_profile_hash', coalesce(c.receipt ->> 'role_profile_hash', s.role_profile_hash),
        'eligibility', c.eligibility,
        'verification_hashes', coalesce(c.receipt -> 'verification_hashes', '[]'::jsonb),
        'changed_paths', coalesce(c.receipt -> 'changed_paths', '[]'::jsonb),
        'interface_changes', coalesce(c.receipt -> 'interface_changes', '[]'::jsonb),
        'claims', coalesce(c.receipt -> 'claims', '[]'::jsonb),
        'risks', coalesce(c.receipt -> 'risks', '[]'::jsonb),
        'dependency_observations', coalesce(c.receipt -> 'dependency_observations', '[]'::jsonb),
        'summary', coalesce(c.receipt ->> 'summary', ''),
        'privacy_class', coalesce(t.envelope -> 'base_task' ->> 'privacy_class', t.envelope ->> 'privacy_class', 'P1')
      ) order by c.candidate_hash)
      from destruktion_meta.federated_candidate_receipt c
      join destruktion_meta.federated_task t on t.task_hash = c.task_hash
      join destruktion_meta.federated_session s on s.session_id = c.session_id
      where t.epoch_id = p_epoch_id
    ), '[]'::jsonb),
    'reviews', coalesce((
      select jsonb_agg(jsonb_build_object(
        'review_hash', r.review_hash,
        'candidate_hash', r.candidate_hash,
        'reviewer_slot', coalesce(r.receipt ->> 'reviewer_slot', r.receipt ->> 'slot_id', rs.slot_id),
        'session_id', r.session_id,
        'lease_generation', r.lease_generation,
        'reviewer_role_profile_hash', coalesce(r.receipt ->> 'reviewer_role_profile_hash', rs.role_profile_hash),
        'verdict', r.verdict,
        'verification_hashes', coalesce(r.receipt -> 'verification_hashes', '[]'::jsonb),
        'privacy_class', coalesce(t.envelope -> 'base_task' ->> 'privacy_class', t.envelope ->> 'privacy_class', 'P1')
      ) order by r.review_hash)
      from destruktion_meta.federated_review_receipt r
      join destruktion_meta.federated_candidate_receipt c on c.candidate_hash = r.candidate_hash
      join destruktion_meta.federated_task t on t.task_hash = c.task_hash
      join destruktion_meta.federated_session rs on rs.session_id = r.session_id
      where t.epoch_id = p_epoch_id
    ), '[]'::jsonb),
    'conflicts', coalesce((
      select jsonb_agg(jsonb_build_object(
        'conflict_hash', ce.conflict_hash,
        'conflict_class', ce.conflict_class,
        'left_ref', ce.left_candidate_hash,
        'right_ref', ce.right_candidate_hash,
        'resolved', (ce.resolution_receipt_hash is not null)
      ) order by ce.conflict_hash)
      from destruktion_meta.federated_conflict_event ce
      where ce.epoch_id = p_epoch_id
    ), '[]'::jsonb),
    'integration_decisions', coalesce((
      select jsonb_agg(jsonb_build_object(
        'decision_hash', d.decision_hash,
        'candidate_hash', d.candidate_hash,
        'decision', d.decision,
        'reason', d.reason
      ) order by d.decision_hash)
      from destruktion_meta.federated_integration_decision d
      where d.epoch_id = p_epoch_id
    ), '[]'::jsonb),
    'participant_witnesses', coalesce((
      select jsonb_agg(jsonb_build_object(
        'slot_id', s.slot_id,
        'session_id', s.session_id,
        'lease_generation', s.lease_generation,
        'role_profile_hash', s.role_profile_hash,
        'revoked', s.revoked,
        'released_at', to_jsonb(s.released_at)
      ) order by s.slot_id, s.session_id)
      from destruktion_meta.federated_session s
      where s.epoch_id = p_epoch_id
    ), '[]'::jsonb),
    'terminal_snapshot', jsonb_build_object(
      'snapshot_hash', v_snapshot.snapshot_hash,
      'snapshot', v_snapshot.snapshot
    )
  ) into v_live_cut;

  if v_live_cut is distinct from p_recovery_cut then
    raise exception 'FEDERATION_FINALIZATION_CUT_DRIFT';
  end if;
  if p_recovery_cut -> 'terminal_snapshot' ->> 'snapshot_hash' is distinct from p_final_snapshot_hash
     or p_recovery_cut -> 'terminal_snapshot' -> 'snapshot' is distinct from v_snapshot.snapshot then
    raise exception 'FEDERATION_FINAL_SNAPSHOT_INVALID';
  end if;

  insert into destruktion_meta.federated_epoch_finalization(
    finalization_hash, epoch_id, final_snapshot_hash, recovery_cut_hash, recovery_cut,
    finalized_by_session_id, finalized_by_generation, protocol_version
  ) values (
    p_finalization_hash, p_epoch_id, p_final_snapshot_hash, p_recovery_cut_hash, p_recovery_cut,
    p_session_id, p_expected_generation, p_protocol_version
  );

  update destruktion_meta.federated_epoch
  set state = 'CLOSED', closed_at = now()
  where epoch_id = p_epoch_id;

  update destruktion_meta.federated_session
  set revoked = true,
      released_at = coalesce(released_at, now()),
      last_seen_at = now()
  where epoch_id = p_epoch_id
    and (revoked = false or released_at is null);

  update destruktion_meta.federated_assignment a
  set assignment_state = 'RELEASED'
  where a.assignment_state = 'CLAIMED'
    and a.task_hash in (
      select t.task_hash from destruktion_meta.federated_task t where t.epoch_id = p_epoch_id
    );

  update destruktion_meta.federated_slot sl
  set state = case when sl.slot_id = 'C6' then 'REVIEW_ONLY' else 'IDLE' end
  where sl.slot_id in (
    select distinct s.slot_id from destruktion_meta.federated_session s where s.epoch_id = p_epoch_id
  )
    and not exists (
      select 1 from destruktion_meta.federated_session active
      where active.slot_id = sl.slot_id
        and active.revoked = false
        and active.released_at is null
    );

  return jsonb_build_object(
    'epoch_id', p_epoch_id,
    'finalization_hash', p_finalization_hash,
    'final_snapshot_hash', p_final_snapshot_hash,
    'recovery_cut_hash', p_recovery_cut_hash,
    'already_finalized', false
  );
end;
$$;

-- Function privileges: never rely on default PUBLIC execute.
revoke all on function public.metaengine_federation_finalization_get_v1(text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_finalization_get_v1(text) to service_role;

revoke all on function public.metaengine_federation_finalize_epoch_v1(text,bigint,text,text,text,text,jsonb,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_finalize_epoch_v1(text,bigint,text,text,text,text,jsonb,text) to service_role;


-- CLOSED/ABORTED epoch mutation barriers.

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
  if v_epoch_state in ('CLOSED','ABORTED') then
    raise exception 'FEDERATION_EPOCH_IMMUTABLE';
  end if;
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
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_task t join destruktion_meta.federated_epoch e on e.epoch_id=t.epoch_id where t.task_hash=p_task_hash;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_task t join destruktion_meta.federated_epoch e on e.epoch_id=t.epoch_id where t.task_hash=p_task_hash;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_task t join destruktion_meta.federated_epoch e on e.epoch_id=t.epoch_id where t.task_hash=p_task_hash;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_candidate_receipt c join destruktion_meta.federated_task t on t.task_hash=c.task_hash join destruktion_meta.federated_epoch e on e.epoch_id=t.epoch_id where c.candidate_hash=p_candidate_hash;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_epoch e where e.epoch_id=p_epoch_id;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_epoch e where e.epoch_id=p_epoch_id;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_epoch e where e.epoch_id=p_epoch_id;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_epoch e where e.epoch_id=p_epoch_id;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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

create or replace function public.metaengine_federation_reclaim_slot_v1(p_epoch_id text, p_slot_id text, p_expected_generation bigint)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_generation bigint;
  v_epoch_state text;
begin
  select e.state into v_epoch_state from destruktion_meta.federated_epoch e where e.epoch_id=p_epoch_id;
  if v_epoch_state in ('CLOSED','ABORTED') then raise exception 'FEDERATION_EPOCH_IMMUTABLE'; end if;
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
