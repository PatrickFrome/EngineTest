import { canonicalSha256 } from './hash.ts';
import type { PrivacyClass } from './mcp_contract.ts';

export function workersAiEligibility(privacyClass: PrivacyClass, neuronsRemaining: number | null): { eligible: boolean; reason: 'OK' | 'PRIVACY_DENIED' | 'QUOTA_UNKNOWN' | 'QUOTA_EXHAUSTED' } {
  if (privacyClass !== 'P0' && privacyClass !== 'P1') return { eligible: false, reason: 'PRIVACY_DENIED' };
  if (neuronsRemaining === null) return { eligible: false, reason: 'QUOTA_UNKNOWN' };
  if (neuronsRemaining <= 0) return { eligible: false, reason: 'QUOTA_EXHAUSTED' };
  return { eligible: true, reason: 'OK' };
}

export type ReviewRef = { taskHash: string; candidateHash: string; verifierHash: string; privacyClass: 'P0' | 'P1' };
export function buildReviewPrompt(ref: ReviewRef): string {
  return JSON.stringify({
    purpose: 'metadata_only_candidate_critique',
    task_hash: ref.taskHash,
    candidate_hash: ref.candidateHash,
    verifier_hash: ref.verifierHash,
    criteria: ['consistency', 'risk_flags', 'verification_followup'],
    rule: 'Do not infer or request source code, secrets, patch bodies, or canonical promotion.',
  });
}


export interface WorkersAILike {
  run(model: string, input: { prompt: string }): Promise<unknown>;
}

export async function runWorkersAiReview(ai: WorkersAILike, ref: ReviewRef, neuronsRemaining: number | null) {
  const decision = workersAiEligibility(ref.privacyClass, neuronsRemaining);
  if (!decision.eligible) throw new Error(decision.reason);
  const model = '@cf/meta/llama-3.2-1b-instruct';
  const raw = await ai.run(model, { prompt: buildReviewPrompt(ref) });
  let review = '';
  if (raw && typeof raw === 'object' && 'response' in raw && typeof (raw as { response?: unknown }).response === 'string') {
    review = (raw as { response: string }).response.slice(0, 4000);
  } else {
    review = JSON.stringify(raw).slice(0, 4000);
  }
  const payload = {
    provider: 'workers_ai',
    model,
    authority: 'ADVISORY_ONLY',
    autoPromote: false,
    taskHash: ref.taskHash,
    candidateHash: ref.candidateHash,
    verifierHash: ref.verifierHash,
    review,
  };
  return { ...payload, receiptHash: await canonicalSha256(payload) };
}
