export type FederationPrivacyClass = 'P0' | 'P1' | 'P2' | 'P3';

export const FEDERATION_TOOL_NAMES = Object.freeze([
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
] as const);

export type FederationToolName = typeof FEDERATION_TOOL_NAMES[number];

const FORBIDDEN_TOOL_FRAGMENTS = /sql|shell|promote|champion|secret|file_write/i;
const P2_FORBIDDEN_KEYS = new Set([
  'objective',
  'source',
  'sourcecode',
  'source_code',
  'sourcebody',
  'source_body',
  'path',
  'paths',
  'patch',
  'patchbody',
  'patch_body',
  'filecontent',
  'file_content',
  'prompt',
  'body',
]);

export function assertFederationToolSurface(names: readonly string[]): boolean {
  if (names.length !== FEDERATION_TOOL_NAMES.length) return false;
  if (new Set(names).size !== names.length) return false;
  if (names.some((name) => FORBIDDEN_TOOL_FRAGMENTS.test(name))) return false;
  return names.every((name, index) => name === FEDERATION_TOOL_NAMES[index]);
}

export function normalizeSha256(value: string): string {
  if (!/^[0-9a-f]{64}$/i.test(value)) throw new Error('INVALID_SHA256');
  return value.toLowerCase();
}

function projectP2(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(projectP2);
  if (value === null || typeof value !== 'object') return value;
  const output: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (P2_FORBIDDEN_KEYS.has(key.toLowerCase())) continue;
    output[key] = projectP2(item);
  }
  return output;
}

export function projectFederationPayload<T>(privacyClass: FederationPrivacyClass, payload: T): T {
  if (privacyClass === 'P3') throw new Error('P3_EXTERNAL_DENIED');
  if (privacyClass !== 'P2') return payload;
  return projectP2(payload) as T;
}
