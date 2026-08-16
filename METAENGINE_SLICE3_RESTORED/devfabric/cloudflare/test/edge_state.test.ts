import test from 'node:test';
import assert from 'node:assert/strict';
import { createTaskRef, readQuotaSnapshot, createVerificationRequest } from '../src/edge_state.ts';

class FakeStatement {
  values: unknown[] = [];
  db: FakeDB;
  sql: string;
  constructor(db: FakeDB, sql: string) { this.db = db; this.sql = sql; }
  bind(...values: unknown[]) { this.values = values; return this; }
  async run() { this.db.runs.push({ sql: this.sql, values: this.values }); return { success: true }; }
  async first<T>() { this.db.reads.push({ sql: this.sql, values: this.values }); return (this.db.firstValue ?? null) as T | null; }
  async all<T>() { this.db.reads.push({ sql: this.sql, values: this.values }); return { results: (this.db.allValues ?? []) as T[] }; }
}

class FakeDB {
  runs: Array<{sql:string, values:unknown[]}> = [];
  reads: Array<{sql:string, values:unknown[]}> = [];
  firstValue: unknown = null;
  allValues: unknown[] = [];
  prepare(sql: string) { return new FakeStatement(this, sql); }
}

test('task ref write stores only sanitized reference fields and returns content hash', async () => {
  const db = new FakeDB();
  const result = await createTaskRef(db, { taskHash: 'a'.repeat(64), privacyClass: 'P2', kind: 'code' }, 123);
  assert.equal(db.runs.length, 1);
  assert.equal(db.runs[0].values.includes('secret objective'), false);
  assert.deepEqual(db.runs[0].values.slice(0, 3), ['a'.repeat(64), 'task:a'.padEnd(69, 'a').slice(0, 69), 'P2']);
  assert.match(result.receiptHash, /^[a-f0-9]{64}$/);
});

test('missing quota row becomes an all-unknown fail-closed snapshot', async () => {
  const db = new FakeDB();
  const snapshot = await readQuotaSnapshot(db);
  assert.equal(snapshot.workflowStepsRemaining, null);
  assert.equal(snapshot.workersAiNeuronsRemaining, null);
});

test('verification request is content addressed before any workflow dispatch', async () => {
  const db = new FakeDB();
  const result = await createVerificationRequest(db, 'a'.repeat(64), 'b'.repeat(64), 456);
  assert.match(result.requestHash, /^[a-f0-9]{64}$/);
  assert.equal(db.runs.length, 1);
  assert.ok(db.runs[0].sql.toLowerCase().includes('verification_requests'));
});
