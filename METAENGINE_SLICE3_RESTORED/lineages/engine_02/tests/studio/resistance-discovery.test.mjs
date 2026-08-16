import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createOperatorDeltaSeed, discoverResistance } from '../../discovery/resistant-source-discovery.mjs';
import { evaluateOperatorDelta } from '../../mutation/operator-mutation-engine.mjs';

const registry = JSON.parse(await readFile(new URL('../../config/living_operator_registry.declarative.json', import.meta.url), 'utf8'));
const policy = JSON.parse(await readFile(new URL('../../config/operator_mutation_policy.json', import.meta.url), 'utf8'));

function living({ run, seed, runtime = 'DAE-LIVING-DECLARATIVE-1.0', selector = 'span:same-001', mode = 'A', source = 'SRC-1', pressure = true }) {
  const base = [
    { node_id: `${run}-Q`, constellation_id: 'C-1', role: 'QUESTION', generated_by: 'HYPOTHESIS-SEED', residual_kind: null, proposition: 'q', source_basis: { hypothesis_id: 'H1', selectors: [selector] } },
  ];
  const variantA = [
    { node_id: `${run}-D`, constellation_id: 'C-1', role: 'DECONFLATION', generated_by: 'GX1', residual_kind: null, proposition: 'd', source_basis: { hypothesis_id: 'H1', selectors: [selector] } },
    ...(pressure ? [{ node_id: `${run}-R`, constellation_id: 'C-1', role: 'OPEN_RESIDUAL', generated_by: 'GX1', residual_kind: 'R3-R', proposition: 'r', source_basis: { hypothesis_id: 'H1', selectors: [selector] } }] : []),
  ];
  const variantB = [
    { node_id: `${run}-S`, constellation_id: 'C-1', role: 'SELF_CRITIQUE', generated_by: 'GX1', residual_kind: 'R3-R', proposition: 's', source_basis: { hypothesis_id: 'H1', selectors: [selector] } },
    ...(pressure ? [{ node_id: `${run}-V`, constellation_id: 'C-1', role: 'REVISION_TRIGGER', generated_by: 'GX6', residual_kind: 'R3-G', proposition: 'v', source_basis: { hypothesis_id: 'H1', selectors: [selector] } }] : []),
  ];
  const nodes = [...base, ...(mode === 'A' ? variantA : variantB)];
  return {
    analysis_version: 'TEST', run_id: run, seed,
    source: { source_id: source },
    operator_registry: { runtime, sha256: `sha-${runtime}` },
    graph: { nodes, edges: [] },
    constellations: [{ constellation_id: 'C-1', topic_id: 'META_CRITIQUE', activated_gestures: mode === 'A' ? ['GX1'] : ['GX1', 'GX6'], activated_families: ['F-UNDERDETERMINATION'] }],
    sufficient_openness: { satisfied: false, missing: pressure ? ['reopening_condition'] : [] },
  };
}

test('recurring same-selector resistance with rival routings becomes a review case', () => {
  const report = discoverResistance({
    analyses: [living({ run: 'R1', seed: 'A', mode: 'A' }), living({ run: 'R2', seed: 'B', mode: 'B' })],
    registry,
  });
  assert.equal(report.summary.resistant_cases, 1);
  const c = report.cases[0];
  assert.equal(c.selector, 'span:same-001');
  assert.equal(c.signals.distinct_unitizations, 2);
  assert.equal(c.support.runs, 2);
  assert.equal(c.status, 'DISCOVERY_HYPOTHESIS_REVIEW_REQUIRED');
  assert.equal(c.target_hypothesis.registry_section, 'generative_gestures');
  assert.equal(c.target_hypothesis.operator_id, 'GX1');
  assert.equal(c.mutation_hypothesis.kind, 'SPLIT');
});

test('one run is insufficient even if the run contains residual pressure', () => {
  const report = discoverResistance({ analyses: [living({ run: 'R1', seed: 'A', mode: 'A' })], registry });
  assert.equal(report.summary.resistant_cases, 0);
});

test('divergent routing without resistance pressure does not become a case', () => {
  const report = discoverResistance({
    analyses: [living({ run: 'R1', seed: 'A', mode: 'A', pressure: false }), living({ run: 'R2', seed: 'B', mode: 'B', pressure: false })],
    registry,
  });
  assert.equal(report.summary.resistant_cases, 0);
});

test('different source ids are never fused into one resistant case', () => {
  const report = discoverResistance({
    analyses: [living({ run: 'R1', seed: 'A', mode: 'A', source: 'SRC-A' }), living({ run: 'R2', seed: 'B', mode: 'B', source: 'SRC-B' })],
    registry,
  });
  assert.equal(report.summary.resistant_cases, 0);
  assert.equal(report.input.same_source, false);
});

test('discovery delta seed is deliberately non-gateable and cannot promote itself', async () => {
  const report = discoverResistance({
    analyses: [living({ run: 'R1', seed: 'A', mode: 'A' }), living({ run: 'R2', seed: 'B', mode: 'B' })],
    registry,
  });
  const seed = createOperatorDeltaSeed(report.cases[0]);
  assert.equal(seed.gateable, false);
  assert.equal(seed.promotion_forbidden, true);
  assert.equal(seed.suggested_delta.mutation.variants.length, 0);
  assert.equal(seed.suggested_delta.before_after_test.negative_tests[0].passed, false);
  const gated = await evaluateOperatorDelta({ delta: seed.suggested_delta, registry, policy });
  assert.equal(gated.receipt.decision.promotion_ready, false);
  assert.notEqual(gated.receipt.decision.decision, 'ACCEPTED_CANDIDATE');
});

test('cross-runtime single-seed divergence is exposed as weaker recurrence evidence', () => {
  const report = discoverResistance({
    analyses: [
      living({ run: 'R1', seed: 'SAME', mode: 'A', runtime: 'BASE' }),
      living({ run: 'R2', seed: 'SAME', mode: 'B', runtime: 'DECL' }),
    ],
    registry,
  });
  assert.equal(report.summary.resistant_cases, 1);
  assert.equal(report.cases[0].support.cross_runtime_only, true);
  assert.match(report.cases[0].review_requirements[0], /additional seed|independent run/i);
});
