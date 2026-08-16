import type { PrivacyClass } from './mcp_contract.ts';

export type WorkflowInput = {
  taskHash: string;
  candidateHash: string;
  privacyClass: PrivacyClass;
  workflowStepsRemaining?: number | null;
};

type WorkflowStep = { name: 'lease' | 'request_verification' | 'record_reference'; ref: string };
export type WorkflowPlan = { status: 'READY' | 'QUOTA_EXHAUSTED'; steps: WorkflowStep[] };

export function buildWorkflowPlan(input: WorkflowInput): WorkflowPlan {
  if (input.privacyClass === 'P3') throw new Error('P3_EXTERNAL_DENIED');
  if (!/^[a-f0-9]{64}$/i.test(input.taskHash) || !/^[a-f0-9]{64}$/i.test(input.candidateHash)) throw new Error('INVALID_SHA256');
  const remaining = input.workflowStepsRemaining;
  if (remaining === null || (remaining !== undefined && remaining < 3)) return { status: 'QUOTA_EXHAUSTED', steps: [] };
  return {
    status: 'READY',
    steps: [
      { name: 'lease', ref: input.taskHash.toLowerCase() },
      { name: 'request_verification', ref: input.candidateHash.toLowerCase() },
      { name: 'record_reference', ref: input.candidateHash.toLowerCase() },
    ],
  };
}
