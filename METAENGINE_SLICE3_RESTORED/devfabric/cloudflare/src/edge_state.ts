import { canonicalSha256 } from './hash.ts';
import { sanitizeTaskReference, type TaskReference } from './mcp_contract.ts';
import type { BudgetSnapshot } from './budget.ts';

export interface D1StatementLike {
  bind(...values: unknown[]): D1StatementLike;
  run(): Promise<{ success: boolean }>;
  first<T>(): Promise<T | null>;
  all<T>(): Promise<{ results: T[] }>;
}

export interface D1DatabaseLike {
  prepare(sql: string): D1StatementLike;
}

export async function createTaskRef(db: D1DatabaseLike, input: TaskReference, nowMs: number) {
  const ref = sanitizeTaskReference(input);
  const taskRef = `task:${ref.taskHash}`;
  const sql = `INSERT INTO task_refs(task_hash, task_ref, privacy_class, status, created_at_ms, updated_at_ms)
    VALUES (?, ?, ?, 'READY', ?, ?)
    ON CONFLICT(task_hash) DO UPDATE SET
      task_ref = excluded.task_ref,
      privacy_class = excluded.privacy_class,
      updated_at_ms = excluded.updated_at_ms`;
  const result = await db.prepare(sql).bind(ref.taskHash, taskRef, ref.privacyClass, nowMs, nowMs).run();
  if (!result.success) throw new Error('D1_TASK_REF_WRITE_FAILED');
  const payload = { taskHash: ref.taskHash, taskRef, privacyClass: ref.privacyClass, kind: ref.kind, status: 'READY' as const };
  return { ...payload, receiptHash: await canonicalSha256(payload) };
}

type QuotaRow = {
  worker_requests_remaining: number | null;
  d1_rows_read_remaining: number | null;
  d1_rows_written_remaining: number | null;
  r2_class_a_remaining: number | null;
  r2_class_b_remaining: number | null;
  workflow_steps_remaining: number | null;
  workers_ai_neurons_remaining: number | null;
};

export async function readQuotaSnapshot(db: D1DatabaseLike): Promise<BudgetSnapshot> {
  const row = await db.prepare(`SELECT worker_requests_remaining, d1_rows_read_remaining, d1_rows_written_remaining,
    r2_class_a_remaining, r2_class_b_remaining, workflow_steps_remaining, workers_ai_neurons_remaining
    FROM quota_snapshots WHERE id = 1`).first<QuotaRow>();
  if (!row) {
    return {
      workerRequestsRemaining: null,
      d1RowsReadRemaining: null,
      d1RowsWrittenRemaining: null,
      r2ClassARemaining: null,
      r2ClassBRemaining: null,
      workflowStepsRemaining: null,
      workersAiNeuronsRemaining: null,
    };
  }
  return {
    workerRequestsRemaining: row.worker_requests_remaining,
    d1RowsReadRemaining: row.d1_rows_read_remaining,
    d1RowsWrittenRemaining: row.d1_rows_written_remaining,
    r2ClassARemaining: row.r2_class_a_remaining,
    r2ClassBRemaining: row.r2_class_b_remaining,
    workflowStepsRemaining: row.workflow_steps_remaining,
    workersAiNeuronsRemaining: row.workers_ai_neurons_remaining,
  };
}

export async function createVerificationRequest(db: D1DatabaseLike, taskHash: string, candidateHash: string, nowMs: number) {
  if (!/^[a-f0-9]{64}$/i.test(taskHash) || !/^[a-f0-9]{64}$/i.test(candidateHash)) throw new Error('INVALID_SHA256');
  const payload = {
    taskHash: taskHash.toLowerCase(),
    candidateHash: candidateHash.toLowerCase(),
    createdAtMs: nowMs,
    status: 'PENDING' as const,
  };
  const requestHash = await canonicalSha256(payload);
  const result = await db.prepare(`INSERT INTO verification_requests(request_hash, task_hash, candidate_hash, status, created_at_ms)
    VALUES (?, ?, ?, 'PENDING', ?)
    ON CONFLICT(request_hash) DO NOTHING`).bind(requestHash, payload.taskHash, payload.candidateHash, nowMs).run();
  if (!result.success) throw new Error('D1_VERIFICATION_REQUEST_WRITE_FAILED');
  return { ...payload, requestHash };
}

export async function readTaskStatus(db: D1DatabaseLike, taskHash: string) {
  if (!/^[a-f0-9]{64}$/i.test(taskHash)) throw new Error('INVALID_SHA256');
  return db.prepare(`SELECT task_hash, task_ref, privacy_class, status, created_at_ms, updated_at_ms FROM task_refs WHERE task_hash = ?`)
    .bind(taskHash.toLowerCase()).first<Record<string, unknown>>();
}

export async function listCandidateRefs(db: D1DatabaseLike, taskHash: string) {
  if (!/^[a-f0-9]{64}$/i.test(taskHash)) throw new Error('INVALID_SHA256');
  const result = await db.prepare(`SELECT candidate_hash, verifier_hash, status, created_at_ms FROM candidate_refs WHERE task_hash = ? ORDER BY created_at_ms, candidate_hash`)
    .bind(taskHash.toLowerCase()).all<Record<string, unknown>>();
  return result.results;
}
