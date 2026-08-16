import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { evaluateGestureActivation, emitGestureProgram, validateDeclarativeGestures } from '../../src/generative-gesture-runtime.mjs';
import { evaluateOperatorDelta } from '../../mutation/operator-mutation-engine.mjs';

const readJson = file => readFile(new URL(file, import.meta.url), 'utf8').then(JSON.parse);
const [registry, policy, delta] = await Promise.all([
  readJson('../../config/living_operator_registry.declarative.json'),
  readJson('../../config/operator_mutation_policy.json'),
  readJson('../../fixtures/mutation/gx1-declarative-split.pass.json'),
]);

function context() {
  return {
    hypothesis: { topic_id: 'META_CRITIQUE', evidence_count: 12, matched_groups: ['a', 'b'], research_question: 'What does the method suppress?' },
    lens: {
      positive_kernel: 'a stable explanatory orientation', self_critique: 'granularity may be lost', deconflation: 'exclusion and compression cost differ',
      rivals: ['rival A', 'rival B'], open: 'a live remainder', revision_trigger: 'test a resistant source', destroyed: 'necessity claim', preserved: 'motivating phenomenon',
      mutation: 'rewrite the reconstruction', counter_genealogy: 'Another genesis is possible', genealogies: { lexical: 'lex', conceptual: 'concept', problem: 'problem' },
      problem_genesis: 'problem genesis', surprise: 'unexpected collision', formal_indication: { name: 'Indicator', direction: 'toward source', negation: 'not a definition', enactment: 're-run', limit: 'source bound' },
    },
    families: [{ family_id: 'F-UNDERDETERMINATION', positive_model: 'model A' }, { family_id: 'F-VERIFICATION', positive_model: 'model B' }],
    resolution: 'RESOLVED',
    questionNode: { node_id: 'Q-1' },
    derived: { counter_genealogy_lcfirst: 'another genesis is possible', family_positive_models_top3: 'model A / model B', formal_indication_text: 'Indicator.', residual_kind: 'R3-R', resolution_qualification: '' },
  };
}

test('baseline declarative registry compiles without gesture-id-specific code', () => {
  assert.deepEqual(validateDeclarativeGestures(registry), []);
  const ctx = context();
  for (const gesture of registry.generative_gestures) {
    const result = evaluateGestureActivation(gesture, ctx);
    assert.equal(typeof result.active, 'boolean');
    assert.equal(typeof result.reason, 'string');
  }
});

test('GX4 emission program expands rivals through generic for_each', () => {
  const gesture = registry.generative_gestures.find(g => g.gesture_id === 'GX4');
  const ctx = context();
  const made = [];
  const nodes = emitGestureProgram(gesture, ctx, spec => {
    const node = { node_id: `N-${made.length + 1}`, ...spec };
    made.push(node); return node;
  });
  assert.equal(nodes.filter(n => n.role === 'RIVAL_RECONSTRUCTION').length, 2);
  assert(nodes.some(n => n.role === 'POLYPHONIC_FIELD'));
  assert(nodes.some(n => n.role === 'SURPRISE'));
});

test('generative gesture SPLIT becomes FULL and promotion-ready in declarative runtime', async () => {
  const result = await evaluateOperatorDelta({ delta, registry, policy });
  assert.equal(result.receipt.runtime_reachability, 'FULL', JSON.stringify(result.receipt.issues, null, 2));
  assert.equal(result.receipt.decision.decision, 'ACCEPTED_CANDIDATE', JSON.stringify(result.receipt.issues, null, 2));
  assert(!result.candidateRegistry.generative_gestures.some(g => g.gesture_id === 'GX1'));
  assert(result.candidateRegistry.generative_gestures.some(g => g.gesture_id === 'GX1A-EXCLUSION'));
  assert(result.candidateRegistry.generative_gestures.some(g => g.gesture_id === 'GX1B-SUCCESS-COST'));
  assert.deepEqual(validateDeclarativeGestures(result.candidateRegistry), []);
});

test('a split variant without executable emission program is rejected', async () => {
  const broken = structuredClone(delta);
  broken.delta_id = 'DELTA-GX1-BROKEN-001';
  broken.mutation.variants[1].changes.emission_program = [];
  const result = await evaluateOperatorDelta({ delta: broken, registry, policy });
  assert.equal(result.receipt.decision.promotion_ready, false);
  assert(result.receipt.issues.some(i => i.code === 'DECLARATIVE_GESTURE_INVALID'));
});
