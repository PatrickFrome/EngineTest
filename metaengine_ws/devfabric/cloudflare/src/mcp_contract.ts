export type PrivacyClass = 'P0' | 'P1' | 'P2' | 'P3';
export const ALLOWED_TOOLS = Object.freeze([
  'project_read',
  'task_ref_create',
  'task_status',
  'candidate_list',
  'verification_request',
  'quota_health',
  'checkpoint_proposal_ref',
] as const);

export type AllowedTool = typeof ALLOWED_TOOLS[number];
const FORBIDDEN_FRAGMENTS = ['sql', 'shell', 'secret', 'promote', 'champion_write', 'service_role'];

export function assertSafeToolSurface(tools: readonly string[]): boolean {
  if (new Set(tools).size !== tools.length) return false;
  return tools.every((tool) => ALLOWED_TOOLS.includes(tool as AllowedTool) && FORBIDDEN_FRAGMENTS.every((x) => !tool.includes(x)));
}

export type TaskReference = { taskHash: string; privacyClass: PrivacyClass; kind: string };
export function sanitizeTaskReference(input: TaskReference): TaskReference {
  if (!/^[a-f0-9]{64}$/i.test(input.taskHash)) throw new Error('INVALID_TASK_HASH');
  if (input.privacyClass === 'P3') throw new Error('P3_EXTERNAL_DENIED');
  if (!/^[a-z0-9._-]{1,48}$/i.test(input.kind)) throw new Error('INVALID_TASK_KIND');
  return { taskHash: input.taskHash.toLowerCase(), privacyClass: input.privacyClass, kind: input.kind };
}

export function proposalReference(candidateHash: string, verifierHash: string): { candidateHash: string; verifierHash: string; autoPromote: false } {
  for (const value of [candidateHash, verifierHash]) if (!/^[a-f0-9]{64}$/i.test(value)) throw new Error('INVALID_SHA256');
  return { candidateHash: candidateHash.toLowerCase(), verifierHash: verifierHash.toLowerCase(), autoPromote: false };
}
