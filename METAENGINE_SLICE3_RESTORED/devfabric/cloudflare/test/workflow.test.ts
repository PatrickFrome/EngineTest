import test from 'node:test';
import assert from 'node:assert/strict';
import { buildWorkflowPlan } from '../src/workflow_core.ts';

test('workflow stores references, not source or patch bodies', () => {
  const plan = buildWorkflowPlan({ taskHash: 'a'.repeat(64), candidateHash: 'b'.repeat(64), privacyClass: 'P1' });
  const text = JSON.stringify(plan);
  assert.equal(text.includes('sourceBody'), false);
  assert.equal(text.includes('patchBody'), false);
  assert.deepEqual(plan.steps.map((x) => x.name), ['lease', 'request_verification', 'record_reference']);
});

test('workflow fails closed when free step budget is unknown or exhausted', () => {
  assert.equal(buildWorkflowPlan({ taskHash: 'a'.repeat(64), candidateHash: 'b'.repeat(64), privacyClass: 'P1', workflowStepsRemaining: null }).status, 'QUOTA_EXHAUSTED');
  assert.equal(buildWorkflowPlan({ taskHash: 'a'.repeat(64), candidateHash: 'b'.repeat(64), privacyClass: 'P1', workflowStepsRemaining: 2 }).status, 'QUOTA_EXHAUSTED');
});
