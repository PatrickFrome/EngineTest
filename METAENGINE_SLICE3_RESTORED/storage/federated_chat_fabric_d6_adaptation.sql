-- Metaengine Stage D6-G1 Finalized-Epoch Shadow Adaptation.
-- Forward-only companion migration after federated_chat_fabric_d6_finalization.sql.
-- Persists deterministic adaptation receipts only; never materializes shadow Role Genomes.

create table destruktion_meta.federated_adaptation_receipt (
  adaptation_receipt_hash text primary key check (adaptation_receipt_hash ~ '^[0-9a-f]{64}$'),
  adaptation_input_hash text not null unique check (adaptation_input_hash ~ '^[0-9a-f]{64}$'),
  protocol_version text not null check (protocol_version = 'D6.ADAPTATION.1'),
  evidence_finalization_hashes jsonb not null check (jsonb_typeof(evidence_finalization_hashes) = 'array'),
  evidence_metrics_hash text not null check (evidence_metrics_hash ~ '^[0-9a-f]{64}$'),
  status text not null check (status in (
    'HOLD_INSUFFICIENT_EVIDENCE',
    'HOLD_UNOBSERVED_METRIC',
    'SHADOW_PROPOSAL_READY',
    'SHADOW_REPLAY_PASS',
    'SHADOW_REPLAY_FAIL'
  )),
  receipt jsonb not null,
  created_at timestamptz not null default now()
);

create index idx_fed_adaptation_created_at
  on destruktion_meta.federated_adaptation_receipt(created_at);

alter table destruktion_meta.federated_adaptation_receipt enable row level security;
alter table destruktion_meta.federated_adaptation_receipt force row level security;
revoke all on table destruktion_meta.federated_adaptation_receipt from public, anon, authenticated;
revoke all on table destruktion_meta.federated_adaptation_receipt from service_role;
grant select, insert on table destruktion_meta.federated_adaptation_receipt to service_role;
revoke update, delete, truncate on table destruktion_meta.federated_adaptation_receipt from service_role;

-- Tighten legacy role tables to their intended append-only runtime semantics.
revoke update, delete, truncate on table destruktion_meta.federated_role_genome from service_role;
revoke update, delete, truncate on table destruktion_meta.federated_role_outcome from service_role;

create or replace function destruktion_meta.metaengine_federation_adaptation_immutable_guard()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
begin
  raise exception 'FEDERATION_ADAPTATION_IMMUTABLE';
end;
$$;

revoke all on function destruktion_meta.metaengine_federation_adaptation_immutable_guard() from public, anon, authenticated;
grant execute on function destruktion_meta.metaengine_federation_adaptation_immutable_guard() to service_role;

drop trigger if exists federated_adaptation_immutable on destruktion_meta.federated_adaptation_receipt;
create trigger federated_adaptation_immutable
before update or delete on destruktion_meta.federated_adaptation_receipt
for each row execute function destruktion_meta.metaengine_federation_adaptation_immutable_guard();

create or replace function public.metaengine_federation_adaptation_receipt_get_v1(
  p_adaptation_input_hash text
)
returns jsonb
language sql
security invoker
set search_path = pg_catalog, destruktion_meta
stable
as $$
  select to_jsonb(r)
  from destruktion_meta.federated_adaptation_receipt r
  where r.adaptation_input_hash = p_adaptation_input_hash;
$$;

create or replace function public.metaengine_federation_record_adaptation_receipt_v1(
  p_adaptation_receipt_hash text,
  p_adaptation_input_hash text,
  p_protocol_version text,
  p_evidence_finalization_hashes jsonb,
  p_evidence_metrics_hash text,
  p_status text,
  p_receipt jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, destruktion_meta
as $$
declare
  v_existing destruktion_meta.federated_adaptation_receipt%rowtype;
  v_evidence_count integer;
begin
  if p_adaptation_receipt_hash !~ '^[0-9a-f]{64}$'
     or p_adaptation_input_hash !~ '^[0-9a-f]{64}$'
     or p_evidence_metrics_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'FEDERATION_ADAPTATION_HASH_INVALID';
  end if;
  if p_protocol_version is distinct from 'D6.ADAPTATION.1' then
    raise exception 'FEDERATION_ADAPTATION_PROTOCOL_UNSUPPORTED';
  end if;
  if p_status not in (
    'HOLD_INSUFFICIENT_EVIDENCE',
    'HOLD_UNOBSERVED_METRIC',
    'SHADOW_PROPOSAL_READY',
    'SHADOW_REPLAY_PASS',
    'SHADOW_REPLAY_FAIL'
  ) then
    raise exception 'FEDERATION_ADAPTATION_STATUS_INVALID';
  end if;
  if jsonb_typeof(p_evidence_finalization_hashes) is distinct from 'array'
     or jsonb_array_length(p_evidence_finalization_hashes) = 0 then
    raise exception 'FEDERATION_ADAPTATION_FINALIZED_EVIDENCE_REQUIRED';
  end if;
  if exists (
    select 1
    from jsonb_array_elements_text(p_evidence_finalization_hashes) as evidence(finalization_hash)
    where evidence.finalization_hash !~ '^[0-9a-f]{64}$'
  ) then
    raise exception 'FEDERATION_ADAPTATION_HASH_INVALID';
  end if;
  select count(distinct evidence.finalization_hash)
  into v_evidence_count
  from jsonb_array_elements_text(p_evidence_finalization_hashes) as evidence(finalization_hash);
  if v_evidence_count <> jsonb_array_length(p_evidence_finalization_hashes) then
    raise exception 'FEDERATION_ADAPTATION_FINALIZED_EVIDENCE_REQUIRED';
  end if;
  if exists (
    select 1
    from jsonb_array_elements_text(p_evidence_finalization_hashes) as evidence(finalization_hash)
    left join destruktion_meta.federated_epoch_finalization f
      on f.finalization_hash = evidence.finalization_hash
    where f.finalization_hash is null
  ) then
    raise exception 'FEDERATION_ADAPTATION_FINALIZED_EVIDENCE_REQUIRED';
  end if;
  if jsonb_typeof(p_receipt) is distinct from 'object'
     or p_receipt ->> 'adaptation_receipt_hash' is distinct from p_adaptation_receipt_hash
     or p_receipt ->> 'adaptation_input_hash' is distinct from p_adaptation_input_hash
     or p_receipt ->> 'protocol_version' is distinct from p_protocol_version
     or p_receipt ->> 'status' is distinct from p_status then
    raise exception 'FEDERATION_ADAPTATION_RECEIPT_HASH_MISMATCH';
  end if;

  -- Serialize all writes for one deterministic input identity, including first insert.
  perform pg_advisory_xact_lock(hashtext(p_adaptation_input_hash));

  select * into v_existing
  from destruktion_meta.federated_adaptation_receipt r
  where r.adaptation_input_hash = p_adaptation_input_hash
  for update;

  if v_existing.adaptation_input_hash is not null then
    if v_existing.adaptation_receipt_hash = p_adaptation_receipt_hash
       and v_existing.protocol_version = p_protocol_version
       and v_existing.evidence_finalization_hashes = p_evidence_finalization_hashes
       and v_existing.evidence_metrics_hash = p_evidence_metrics_hash
       and v_existing.status = p_status
       and v_existing.receipt = p_receipt then
      return jsonb_build_object(
        'status', 'ALREADY_RECORDED',
        'adaptation_input_hash', v_existing.adaptation_input_hash,
        'adaptation_receipt_hash', v_existing.adaptation_receipt_hash
      );
    end if;
    raise exception 'FEDERATION_ADAPTATION_NONDETERMINISTIC';
  end if;

  insert into destruktion_meta.federated_adaptation_receipt(
    adaptation_receipt_hash,
    adaptation_input_hash,
    protocol_version,
    evidence_finalization_hashes,
    evidence_metrics_hash,
    status,
    receipt
  ) values (
    p_adaptation_receipt_hash,
    p_adaptation_input_hash,
    p_protocol_version,
    p_evidence_finalization_hashes,
    p_evidence_metrics_hash,
    p_status,
    p_receipt
  );

  return jsonb_build_object(
    'status', 'RECORDED',
    'adaptation_input_hash', p_adaptation_input_hash,
    'adaptation_receipt_hash', p_adaptation_receipt_hash
  );
end;
$$;

-- Function privileges: never rely on default PUBLIC execute.
revoke all on function public.metaengine_federation_adaptation_receipt_get_v1(text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_adaptation_receipt_get_v1(text) to service_role;

revoke all on function public.metaengine_federation_record_adaptation_receipt_v1(text,text,text,jsonb,text,text,jsonb) from public, anon, authenticated;
grant execute on function public.metaengine_federation_record_adaptation_receipt_v1(text,text,text,jsonb,text,text,jsonb) to service_role;
