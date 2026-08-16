import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { evaluateOperatorDelta } from '../../mutation/operator-mutation-engine.mjs';

const readJson = file => readFile(new URL(file, import.meta.url), 'utf8').then(JSON.parse);
const [registry, policy, delta] = await Promise.all([
  readJson('../../config/living_operator_registry.json'),
  readJson('../../config/operator_mutation_policy.json'),
  readJson('../../fixtures/mutation/mediation-compression-split.pass.json'),
]);

test('resistant-source split passes the mutation gate without editing baseline registry', async () => {
  const baseline = JSON.stringify(registry);
  const result = await evaluateOperatorDelta({ delta, registry, policy });
  assert.equal(result.receipt.decision.decision, 'ACCEPTED_CANDIDATE', JSON.stringify(result.receipt.issues, null, 2));
  assert.equal(result.receipt.decision.promotion_ready, true);
  assert.equal(result.receipt.runtime_reachability, 'FULL');
  assert.equal(JSON.stringify(registry), baseline, 'baseline registry mutated in memory');
  assert(!result.candidateRegistry.conditional_families.some(f => f.family_id === 'F-MEDIATION-COMPRESSION'));
  assert(result.candidateRegistry.conditional_families.some(f => f.family_id === 'F-MEDIATION-ORIENTATION'));
  assert(result.candidateRegistry.conditional_families.some(f => f.family_id === 'F-MEDIATION-SUBSTITUTION'));
});

test('novel wording without GG1 cannot be promoted', async () => {
  const weak = structuredClone(delta);
  weak.delta_id = 'DELTA-NO-GG1-001';
  weak.before_after_test.new_gains = ['GG2_NEW_RELATION'];
  const result = await evaluateOperatorDelta({ delta: weak, registry, policy });
  assert.equal(result.receipt.decision.promotion_ready, false);
  assert(result.receipt.issues.some(i => i.code === 'GG1_REQUIRED_FOR_PROMOTION'));
});

test('traceability regression blocks promotion', async () => {
  const weak = structuredClone(delta);
  weak.delta_id = 'DELTA-TRACE-REGRESSION-001';
  weak.before_after_test.traceability = { before_routes: 2, after_routes: 1 };
  const result = await evaluateOperatorDelta({ delta: weak, registry, policy });
  assert.equal(result.receipt.decision.promotion_ready, false);
  assert(result.receipt.issues.some(i => i.code === 'TRACEABILITY_REGRESSION'));
});

test('declarative 0.10 makes GX revision fully reachable rather than review-only', async () => {
  const revised = structuredClone(delta);
  revised.delta_id = 'DELTA-GESTURE-REVISE-010';
  revised.target = { registry_section: 'generative_gestures', operator_id: 'GX1' };
  revised.mutation = {
    kind: 'REVISE',
    proposal: 'Revise the residual question while leaving baseline assets untouched.',
    cost: 'Changes the prompt surface.',
    reversibility: 'Restore GX1 from rollback_target.json.',
    changes: { question: 'Which excluded phenomenon is produced by this very success?' }
  };
  const result = await evaluateOperatorDelta({ delta: revised, registry, policy });
  assert.equal(result.receipt.runtime_reachability, 'FULL');
  assert.equal(result.receipt.decision.promotion_ready, true, JSON.stringify(result.receipt.issues, null, 2));
});
