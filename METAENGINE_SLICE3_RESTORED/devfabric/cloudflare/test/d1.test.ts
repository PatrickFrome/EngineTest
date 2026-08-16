import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { acquireLeaseDecision, isEphemeralSchemaSafe } from '../src/d1.ts';

const schema = fs.readFileSync(new URL('../migrations/0001_ephemeral_router.sql', import.meta.url), 'utf8');

test('D1 schema is ephemeral only and contains no canonical policy/champion state', () => {
  assert.equal(isEphemeralSchemaSafe(schema), true);
  const lower = schema.toLowerCase();
  for (const bad of ['architecture_policy', 'champion', 'canonical_checkpoint', 'service_role']) assert.equal(lower.includes(bad), false);
});

test('lease CAS is idempotent for same owner/version and rejects stale owner', () => {
  const now = 1000;
  assert.equal(acquireLeaseDecision(null, { ownerHash: 'x', expectedVersion: 0, ttlMs: 1000, nowMs: now }).status, 'ACQUIRED');
  assert.equal(acquireLeaseDecision({ ownerHash: 'x', version: 1, expiresAtMs: 2000 }, { ownerHash: 'x', expectedVersion: 1, ttlMs: 1000, nowMs: now }).status, 'RENEWED');
  assert.equal(acquireLeaseDecision({ ownerHash: 'y', version: 2, expiresAtMs: 2000 }, { ownerHash: 'x', expectedVersion: 1, ttlMs: 1000, nowMs: now }).status, 'CONFLICT');
});
