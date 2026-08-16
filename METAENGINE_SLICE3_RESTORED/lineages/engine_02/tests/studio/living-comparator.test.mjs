import test from 'node:test';
import assert from 'node:assert/strict';
import { compareLivingAnalyses, summarizeLivingAnalysis } from '../../studio/living-comparator.mjs';

function analysis({ runtime, seed = 'same-seed', extra = false, mutated = false }) {
  const nodes = [
    { node_id: 'Q1', role: 'QUESTION', generated_by: 'QUESTION', generative_gains: [], residual_kind: null },
    { node_id: 'N1', role: 'DECONFLATION', generated_by: mutated ? 'GX1A-EXCLUSION' : 'GX1', generative_gains: ['GG1_NEW_DISTINCTION'], residual_kind: null },
    { node_id: 'N2', role: 'REVISION_TRIGGER', generated_by: 'GX6', generative_gains: ['GG6_BRANCH_PRODUCTIVITY'], residual_kind: 'R3-R' },
  ];
  if (extra) nodes.push({ node_id: 'N3', role: 'RESEARCH_BRANCH', generated_by: mutated ? 'GX1B-SUCCESS-COST' : 'GX2', generative_gains: ['GG2_NEW_QUESTION'], residual_kind: 'R3-A' });
  const edges = [
    { from: 'Q1', to: 'N1', relation: 'DECONFLATES' },
    { from: 'N1', to: 'N2', relation: 'REOPENS' },
  ];
  if (extra) edges.push({ from: 'N2', to: 'N3', relation: 'CROSSES_CONSTELLATION' });
  return {
    run_id: `run-${runtime}`,
    seed,
    operator_registry: { runtime, sha256: runtime },
    graph: { nodes, edges, retired_operators: [] },
    constellations: [{ activated_families: ['F-1'] }],
    sufficient_openness: { satisfied: true, criteria: { new_distinction: true, reopening_condition: true }, missing: [] },
  };
}

test('living comparator summarizes structural runtime behavior', () => {
  const summary = summarizeLivingAnalysis('x', analysis({ runtime: 'BASE' }));
  assert.equal(summary.counts.nodes, 3);
  assert.equal(summary.branch_pressure.revision_trigger_nodes, 1);
  assert.equal(summary.generative_gains.GG1_NEW_DISTINCTION, 1);
  assert.match(summary.structural_fingerprint_sha256, /^[a-f0-9]{64}$/);
});

test('A/B/C comparison detects declarative mutation without calling it better', () => {
  const result = compareLivingAnalyses({
    baseline: analysis({ runtime: 'BASE' }),
    declarative: analysis({ runtime: 'DECL' }),
    mutant: analysis({ runtime: 'DECL', extra: true, mutated: true }),
  });
  assert.equal(result.comparison_contract.same_seed_observed, true);
  assert.equal(result.transitions.baseline_to_declarative.structural_change, false);
  assert.equal(result.transitions.declarative_to_mutant.structural_change, true);
  assert.equal(result.mutation_effect_observed, true);
  assert(result.transitions.declarative_to_mutant.added_generators.includes('GX1A-EXCLUSION'));
  assert.equal(result.transitions.declarative_to_mutant.branch_pressure_delta.research_branch_nodes, 1);
});

test('different seeds are exposed as a comparison-control violation', () => {
  const result = compareLivingAnalyses({
    baseline: analysis({ runtime: 'BASE', seed: 'A' }),
    declarative: analysis({ runtime: 'DECL', seed: 'A' }),
    mutant: analysis({ runtime: 'DECL-M', seed: 'B', mutated: true }),
  });
  assert.equal(result.comparison_contract.same_seed_observed, false);
});
