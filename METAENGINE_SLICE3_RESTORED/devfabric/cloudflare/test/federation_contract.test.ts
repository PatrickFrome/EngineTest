import assert from 'node:assert/strict';
import test from 'node:test';
import {
  FEDERATION_TOOL_NAMES,
  assertFederationToolSurface,
  normalizeSha256,
  projectFederationPayload,
} from '../src/federation_contract.ts';

const EXPECTED = [
  'federation_status',
  'slot_catalog',
  'session_status',
  'epoch_status',
  'task_get',
  'task_dependencies',
  'candidate_status',
  'conflict_status',
  'sync_snapshot_get',
  'federation_register',
  'session_release',
  'task_claim',
  'task_progress',
  'candidate_submit',
  'review_submit',
  'conflict_submit',
  'integration_propose',
  'sync_snapshot_publish',
] as const;

test('federation tool surface is exact and contains no privileged escape hatch', () => {
  assert.deepEqual(FEDERATION_TOOL_NAMES, EXPECTED);
  assert.equal(assertFederationToolSurface(FEDERATION_TOOL_NAMES), true);
  for (const name of FEDERATION_TOOL_NAMES) {
    assert.doesNotMatch(name, /sql|shell|promote|champion|secret|file_write/i);
  }
});

test('digest normalization is strict lower-case sha256', () => {
  assert.equal(normalizeSha256('A'.repeat(64)), 'a'.repeat(64));
  assert.throws(() => normalizeSha256('not-a-digest'), /INVALID_SHA256/);
});

test('P3 external payload is rejected and P2 removes source bodies and paths', () => {
  assert.throws(() => projectFederationPayload('P3', { taskHash: 'a'.repeat(64) }), /P3_EXTERNAL_DENIED/);
  assert.deepEqual(
    projectFederationPayload('P2', {
      taskHash: 'a'.repeat(64),
      candidateHash: 'b'.repeat(64),
      objective: 'hidden objective',
      source: 'hidden source',
      path: '/private/file.py',
      patch: 'hidden patch',
      riskClass: 'HIGH',
      metrics: { tests: 12 },
    }),
    {
      taskHash: 'a'.repeat(64),
      candidateHash: 'b'.repeat(64),
      riskClass: 'HIGH',
      metrics: { tests: 12 },
    },
  );
});

test('D6-G0 internal finalization operations never enter chat-facing federation tools', () => {
  assert.equal(FEDERATION_TOOL_NAMES.length, 18);
  for (const forbidden of ['finalize', 'finalization_get', 'epoch_close', 'recovery_cut']) {
    assert.equal(FEDERATION_TOOL_NAMES.some((name) => name.includes(forbidden)), false, `leaked ${forbidden}`);
  }
});
