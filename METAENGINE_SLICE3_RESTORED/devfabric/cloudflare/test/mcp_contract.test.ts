import test from 'node:test';
import assert from 'node:assert/strict';
import { ALLOWED_TOOLS, assertSafeToolSurface, sanitizeTaskReference } from '../src/mcp_contract.ts';

const expected = [
  'project_read', 'task_ref_create', 'task_status', 'candidate_list',
  'verification_request', 'quota_health', 'checkpoint_proposal_ref'
];

test('remote MCP exposes only narrow non-canonical tools', () => {
  assert.deepEqual([...ALLOWED_TOOLS].sort(), [...expected].sort());
  assert.equal(assertSafeToolSurface(ALLOWED_TOOLS), true);
  for (const forbidden of ['sql', 'shell', 'secret', 'promote', 'champion_write']) {
    assert.equal(ALLOWED_TOOLS.some((name) => name.includes(forbidden)), false);
  }
});

test('P3 is rejected and P2 is metadata-only', () => {
  assert.throws(() => sanitizeTaskReference({ taskHash: 'a'.repeat(64), privacyClass: 'P3', kind: 'code' }), /P3_EXTERNAL_DENIED/);
  const p2 = sanitizeTaskReference({ taskHash: 'b'.repeat(64), privacyClass: 'P2', kind: 'code', objective: 'secret objective', path: '/private/file' } as never);
  assert.deepEqual(p2, { taskHash: 'b'.repeat(64), privacyClass: 'P2', kind: 'code' });
});
