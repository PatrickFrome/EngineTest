import assert from 'node:assert/strict';
import test from 'node:test';
import { FederationApiClient } from '../src/federation_client.ts';

const SECRET = ['svc', 'role', 'sentinel', '9f31'].join('-');

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

test('fixed client calls only the hard-coded federation status RPC and keeps secret outbound-only', async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchImpl: typeof fetch = async (input, init) => {
    calls.push({ url: String(input), init });
    return jsonResponse({ ok: true, echoed: 'safe' });
  };
  const client = new FederationApiClient({
    supabaseUrl: 'https://example.supabase.co',
    serviceRoleKey: SECRET,
    fetchImpl,
  });
  const result = await client.federation_status({ epoch_id: 'epoch-1' });
  assert.deepEqual(result, { ok: true, echoed: 'safe' });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://example.supabase.co/rest/v1/rpc/metaengine_federation_status_v1');
  const headers = new Headers(calls[0].init?.headers);
  assert.equal(headers.get('authorization'), `Bearer ${SECRET}`);
  assert.equal(headers.get('apikey'), SECRET);
  assert.doesNotMatch(JSON.stringify(result), new RegExp(SECRET));
});

test('client exposes fixed methods but no generic rpc/execute/sql method', () => {
  const names = Object.getOwnPropertyNames(FederationApiClient.prototype);
  for (const forbidden of ['rpc', 'execute', 'sql', 'query']) assert.equal(names.includes(forbidden), false);
  for (const required of ['federation_status','slot_catalog','session_status','epoch_status','task_get','task_dependencies','candidate_status','conflict_status','sync_snapshot_get','federation_register','session_release','task_claim','task_progress','candidate_submit','review_submit','conflict_submit','integration_propose','sync_snapshot_publish']) {
    assert.equal(names.includes(required), true, `missing method ${required}`);
  }
});

test('upstream error body is not reflected and cannot leak service key', async () => {
  const fetchImpl: typeof fetch = async () => new Response(`database exploded ${SECRET}`, { status: 500 });
  const client = new FederationApiClient({
    supabaseUrl: 'https://example.supabase.co/',
    serviceRoleKey: SECRET,
    fetchImpl,
  });
  await assert.rejects(
    () => client.epoch_status({ epoch_id: 'epoch-1' }),
    (error: unknown) => {
      assert.ok(error instanceof Error);
      assert.match(error.message, /FEDERATION_RPC_ERROR:500/);
      assert.doesNotMatch(error.message, new RegExp(SECRET));
      assert.doesNotMatch(error.message, /database exploded/);
      return true;
    },
  );
});

import { createFederationToolHandlers } from '../src/federation_tools.ts';

test('P3 candidate submit is rejected before any client call', async () => {
  let calls = 0;
  const client = new Proxy({}, {
    get() { return async () => { calls += 1; return { ok: true }; }; },
  }) as any;
  const handlers = createFederationToolHandlers(client);
  await assert.rejects(
    () => handlers.candidate_submit({
      privacyClass: 'P3',
      session_id: 's1',
      expected_generation: 1,
      candidate_hash: 'a'.repeat(64),
      task_hash: 'b'.repeat(64),
      receipt: { source: 'private code' },
    }),
    /P3_EXTERNAL_DENIED/,
  );
  assert.equal(calls, 0);
});

test('P2 candidate submit strips source/path/objective/patch before client call', async () => {
  let seen: any = null;
  const client = new Proxy({}, {
    get(_target, prop) {
      return async (input: unknown) => { seen = { prop, input }; return { accepted: true, source: 'upstream-body', candidate_hash: 'a'.repeat(64) }; };
    },
  }) as any;
  const handlers = createFederationToolHandlers(client);
  const result = await handlers.candidate_submit({
    privacyClass: 'P2',
    session_id: 's1',
    expected_generation: 1,
    candidate_hash: 'a'.repeat(64),
    task_hash: 'b'.repeat(64),
    receipt: {
      objective: 'hidden',
      source: 'hidden',
      path: '/hidden/file.py',
      patch: 'hidden patch',
      verifierHash: 'c'.repeat(64),
      metrics: { tests: 8 },
    },
  });
  assert.equal(seen.prop, 'candidate_submit');
  assert.deepEqual(seen.input.receipt, { verifierHash: 'c'.repeat(64), metrics: { tests: 8 } });
  assert.deepEqual(result, { accepted: true, candidate_hash: 'a'.repeat(64) });
});

test('open blind group hides sibling candidate without network lookup', async () => {
  let calls = 0;
  const client = new Proxy({}, {
    get() { return async () => { calls += 1; return { receipt: { summary: 'sibling' } }; }; },
  }) as any;
  const handlers = createFederationToolHandlers(client);
  const result = await handlers.candidate_status({
    privacyClass: 'P1',
    session_id: 'session-c1',
    candidate_hash: 'd'.repeat(64),
    blind_group_open: true,
    caller_candidate_hash: 'e'.repeat(64),
  });
  assert.deepEqual(result, { blindGroupOpen: true, visible: false });
  assert.equal(calls, 0);
});

test('fixed chat client does not expose D6-G0 internal finalization methods', () => {
  const names = Object.getOwnPropertyNames(FederationApiClient.prototype);
  for (const forbidden of ['finalize_epoch_internal', 'finalization_get_internal', 'finalize', 'epoch_close', 'recovery_cut']) {
    assert.equal(names.includes(forbidden), false, `unexpected internal method ${forbidden}`);
  }
});
