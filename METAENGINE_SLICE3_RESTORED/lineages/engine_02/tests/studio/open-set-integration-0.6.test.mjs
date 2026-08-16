import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { createEngine } from '../../src/engine.mjs';
import { evaluateMicroLocalEcology } from '../../src/micro-local-ecology.mjs';
import { evaluateOperatorDelta } from '../../mutation/operator-mutation-engine.mjs';
import { runMicroLocalOperatorEcology } from '../../studio/compat/micro-local-operator-ecology-0.9.mjs';

const readJson = (file) => readFile(new URL(file, import.meta.url), 'utf8').then(JSON.parse);

test('0.10 open-set micro-local router preserves UNKNOWN_OPERATOR_FAMILY as a local rival', async () => {
  const engine = await createEngine();
  const bank = await readJson('../../experiments/open-set-hermeneutics-0.10/refinery/hypothesis_bank.json');
  const result = evaluateMicroLocalEcology(bank);
  assert.equal(result.outcome, 'MICRO_LOCAL_ROUTING_AVAILABLE');
  assert.ok(result.counts.open_set_only + result.counts.rival_routes > 0);
  assert.equal(engine.structural.validateMicroLocalEcologyResult(result).length, 0);
  assert.ok(result.routes.every((route) => ['OPEN_SET_LOCAL_CANDIDATE', 'KEEP_KNOWN_AND_OPEN_SET_RIVALS', 'KNOWN_PROFILE_LOCAL', 'ABSTAIN_LOCAL'].includes(route.decision)));
});

test('preserved 0.9 ecology still rejects global collapse when localization would be lost', async () => {
  const engine = await createEngine();
  const parent = await mkdtemp(path.join(tmpdir(), 'destruktion-ecology-compat-'));
  const out = path.join(parent, 'run');
  try {
    const result = await runMicroLocalOperatorEcology(
      engine,
      path.resolve('experiments/micro-local-operator-ecology-0.9/micro_local_operator_ecology_manifest.json'),
      out,
      { generatedAt: '2026-08-11T20:00:00Z' },
    );
    assert.equal(result.result.outcome, 'PASSES_MICRO_LOCAL_OPERATOR_ECOLOGY_REGRESSION');
    assert.equal(result.result.synthesis.decision, 'REJECT_GLOBAL_COLLAPSE_PRESERVE_WINDOW_PROVENANCE');
    assert.equal(result.result.summary.localization_loss_count, 4);
  } finally {
    await rm(parent, { recursive: true, force: true });
  }
});

test('ADD_OPERATOR births an executable open-set family without mutating frozen 0.10 registry', async () => {
  const [registry, policy, delta] = await Promise.all([
    readJson('../../config/living_operator_registry.json'),
    readJson('../../config/operator_mutation_policy.json'),
    readJson('../../fixtures/mutation/open-set-add-family.pass.json'),
  ]);
  const baseline = JSON.stringify(registry);
  const result = await evaluateOperatorDelta({ delta, registry, policy });
  assert.equal(result.receipt.runtime_reachability, 'FULL');
  assert.equal(result.receipt.decision.decision, 'ACCEPTED_CANDIDATE');
  assert.equal(JSON.stringify(registry), baseline);
  assert.ok(result.candidateRegistry.conditional_families.some((family) => family.family_id === delta.mutation.new_operator.family_id));
  assert.equal(result.receipt.executable_probe.before.active, false);
  assert.equal(result.receipt.executable_probe.after[0].active, true);
});
