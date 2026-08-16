import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createEngine } from '../../src/engine.mjs';
import { runLivingAnalysis } from '../../src/living-analysis-declarative.mjs';
import { validateDeclarativeGestures } from '../../src/generative-gesture-runtime.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');

async function json(rel) {
  return JSON.parse(await readFile(path.join(ROOT, rel), 'utf8'));
}

test('0.10 portable baseline remains byte-identical after Studio integration', async () => {
  const manifest = await json('PORTABLE_PROJECT.json');
  assert.equal(manifest.required_assets.length, 66);
  for (const asset of manifest.required_assets) {
    const bytes = await readFile(path.join(ROOT, asset.path));
    assert.equal(createHash('sha256').update(bytes).digest('hex'), asset.sha256, asset.path);
  }
});

test('declarative registry compiles GX7 source-resistance operator evolution', async () => {
  const registry = await json('config/living_operator_registry.declarative.json');
  assert.deepEqual(validateDeclarativeGestures(registry), []);
  const gx7 = registry.generative_gestures.find((g) => g.gesture_id === 'GX7');
  assert.ok(gx7, 'GX7 missing from declarative registry');
  const roles = new Set((gx7.emission_program ?? []).flatMap((step) => step.role ? [step.role] : []));
  for (const role of ['SOURCE_RESISTANCE', 'REPRESENTATION_FAILURE', 'OPERATOR_DELTA']) assert.ok(roles.has(role), role);
});

test('real Geviert refinery fires declarative GX7 and yields a non-promoted method mutation', async () => {
  const parent = await mkdtemp(path.join(tmpdir(), 'destruktion-gx7-'));
  const out = path.join(parent, 'living');
  try {
    const engine = await createEngine();
    const refinery = path.join(ROOT, 'experiments/cross-corpus-operator-regression-0.7/GEVIERT/refinery');
    const result = await runLivingAnalysis(engine, refinery, out, { seed: 'studio-0.6-gx7-regression' });
    assert.equal(result.validation.conformant, true);
    const analysis = result.analysis;
    const roles = new Set(analysis.graph.nodes.map((n) => n.role));
    for (const role of ['SOURCE_RESISTANCE', 'REPRESENTATION_FAILURE', 'OPERATOR_DELTA']) assert.ok(roles.has(role), role);
    assert.ok(analysis.constellations.some((c) => c.activated_gestures.includes('GX7')), 'GX7 did not activate');
    assert.equal(analysis.method_mutations.length, 1);
    assert.equal(analysis.method_mutations[0].mutation_state, 'EXPERIMENTAL_CANDIDATE_NOT_CORE');
    assert.equal(analysis.sufficient_openness.criteria.source_resistance_handled_or_explicitly_absent, true);
  } finally {
    await rm(parent, { recursive: true, force: true });
  }
});
