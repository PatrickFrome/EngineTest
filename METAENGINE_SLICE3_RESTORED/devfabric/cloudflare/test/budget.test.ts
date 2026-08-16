import test from 'node:test';
import assert from 'node:assert/strict';
import { FREE_LIMITS, budgetDecision } from '../src/budget.ts';

test('free limits match Stage D zero-spend contract', () => {
  assert.equal(FREE_LIMITS.workerRequestsPerDay, 100000);
  assert.equal(FREE_LIMITS.d1RowsReadPerDay, 5000000);
  assert.equal(FREE_LIMITS.d1RowsWrittenPerDay, 100000);
  assert.equal(FREE_LIMITS.workflowStepsPerDay, 3000);
  assert.equal(FREE_LIMITS.workersAiNeuronsPerDay, 10000);
  assert.equal(FREE_LIMITS.r2ClassAPerMonth, 1000000);
  assert.equal(FREE_LIMITS.r2ClassBPerMonth, 10000000);
});

test('unknown quota fails closed', () => {
  assert.deepEqual(budgetDecision({ workersAiNeuronsRemaining: null }, { workersAiNeurons: 1 }), { eligible: false, reason: 'QUOTA_UNKNOWN' });
});

test('insufficient quota never falls back to paid', () => {
  assert.deepEqual(budgetDecision({ workflowStepsRemaining: 0 }, { workflowSteps: 1 }), { eligible: false, reason: 'QUOTA_EXHAUSTED' });
});
