export type LeaseState = { ownerHash: string; version: number; expiresAtMs: number };
export type LeaseRequest = { ownerHash: string; expectedVersion: number; ttlMs: number; nowMs: number };
export type LeaseDecision = { status: 'ACQUIRED' | 'RENEWED' | 'CONFLICT'; version?: number; expiresAtMs?: number };

export function acquireLeaseDecision(current: LeaseState | null, request: LeaseRequest): LeaseDecision {
  if (request.ttlMs <= 0 || request.ttlMs > 15 * 60_000) throw new Error('INVALID_TTL');
  if (current === null || current.expiresAtMs <= request.nowMs) {
    return { status: 'ACQUIRED', version: request.expectedVersion + 1, expiresAtMs: request.nowMs + request.ttlMs };
  }
  if (current.ownerHash === request.ownerHash && current.version === request.expectedVersion) {
    return { status: 'RENEWED', version: current.version + 1, expiresAtMs: request.nowMs + request.ttlMs };
  }
  return { status: 'CONFLICT' };
}

export function isEphemeralSchemaSafe(schema: string): boolean {
  const lower = schema.toLowerCase();
  const allowed = ['leases', 'task_refs', 'candidate_refs', 'verification_requests', 'quota_snapshots'];
  const tables = [...lower.matchAll(/create\s+table\s+if\s+not\s+exists\s+([a-z0-9_]+)/g)].map((m) => m[1]);
  return tables.length === allowed.length && tables.every((name) => allowed.includes(name)) &&
    !['architecture_policy', 'champion', 'canonical_checkpoint', 'service_role'].some((x) => lower.includes(x));
}
