import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { createEngine } from '../../src/engine.mjs';
import { initExpertBenchmark } from '../../src/benchmark.mjs';
import {
  initExternalValidationCampaign,
  freezeExternalValidationCampaign,
  evaluateExternalValidationCampaign,
  REQUIRED_PHENOMENA,
} from '../../studio/validation/external-validation.mjs';
import { projectPath } from '../../src/paths.mjs';

const generatedAt = '2026-08-11T18:00:00Z';
const engine = await createEngine();
function jsonBytes(value) { return Buffer.from(`${JSON.stringify(value, null, 2)}\n`, 'utf8'); }
function sha256(value) { return createHash('sha256').update(value).digest('hex'); }
async function readJson(file) { return JSON.parse(await readFile(file, 'utf8')); }

async function setupCampaign(temp) {
  const benchmark = path.join(temp, 'benchmark');
  const cycle = projectPath('experiments', 'heidegger-ga', 'user-dossier-ga1-1-2026', 'expert-cycle', 'expert_cycle.json');
  await initExpertBenchmark(engine, [cycle], benchmark, { generatedAt });
  const campaign = path.join(temp, 'campaign');
  await initExternalValidationCampaign(benchmark, campaign, { generatedAt });
  return { benchmark, campaign };
}

async function filledSystem(campaignDir, systemId = 'EXT-BASELINE', mutate = null) {
  const campaign = await readJson(path.join(campaignDir, 'campaign.json'));
  const dae = await readJson(path.join(campaignDir, 'dae_primary_snapshot.json'));
  const predictions = dae.system.predictions.map((entry, index) => ({ ...entry, ...(mutate?.(entry, index) ?? {}) }));
  return {
    predictions_version: 'DESTRUKTION-EXTERNAL-SYSTEM-PREDICTIONS-1.0',
    campaign_id: campaign.campaign_id,
    benchmark_id: campaign.benchmark.benchmark_id,
    system: { system_id: systemId, kind: 'FRONTIER_LLM_BASELINE', name: 'External baseline', model_or_version: 'fixture-v1', protocol_id: 'fixture-protocol-v1' },
    independence: { independent_of_dae_development: true, dae_outputs_seen: false, gold_seen: false, benchmark_annotations_seen: false, system_prompt_contains_dae_output: false },
    generated_at: generatedAt,
    predictions,
    claim_ceiling: 'EXTERNAL_SYSTEM_PREDICTIONS_NOT_GOLD_OR_INDEPENDENT_VALIDATION_BY_THEMSELVES',
  };
}

async function filledChallenge(campaignDir) {
  const campaign = await readJson(path.join(campaignDir, 'campaign.json'));
  return {
    challenge_version: 'DESTRUKTION-SEMANTIC-CHALLENGE-1.0',
    campaign_id: campaign.campaign_id,
    benchmark_id: campaign.benchmark.benchmark_id,
    author: { id: 'external-challenge-author', independent_of_dae_development: true, dae_predictions_seen: false, gold_seen: false },
    created_at: generatedAt,
    cases: REQUIRED_PHENOMENA.map((phenomenon, index) => ({
      case_id: `CH-${String(index + 1).padStart(3, '0')}`,
      phenomenon,
      anchor_unit_id: campaign.unit_ids[index % campaign.unit_ids.length],
      variant_text: `Independent adversarial ${phenomenon.toLowerCase()} variant ${index + 1}.`,
      relation_to_anchor: 'ALLOWED_SET_ONLY',
      allowed_variant_statuses: ['INSUFFICIENT'],
      rationale: `This fixture forces a conservative response under ${phenomenon} without defining philosophical truth.`,
      evidence_refs: [`FIXTURE#${index + 1}`],
    })),
    claim_ceiling: 'INDEPENDENT_ADVERSARIAL_EXPECTATIONS_NOT_GOLD_FOR_UNSEEN_PHILOSOPHICAL_TRUTH',
  };
}

async function writeFreezeInputs(temp, campaignDir, systemPayload, challengePayload) {
  const systemFile = path.join(temp, `${systemPayload.system.system_id}.json`);
  const challengeFile = path.join(temp, 'challenge.json');
  await Promise.all([writeFile(systemFile, jsonBytes(systemPayload)), writeFile(challengeFile, jsonBytes(challengePayload))]);
  return { systemFile, challengeFile };
}

async function goldMatchingDae(campaignDir) {
  const campaign = await readJson(path.join(campaignDir, 'campaign.json'));
  const dae = await readJson(path.join(campaignDir, 'dae_primary_snapshot.json'));
  const byId = new Map(dae.system.predictions.map((entry) => [entry.unit_id, entry.status]));
  return {
    gold_version: 'DAE-ADJUDICATED-GOLD-1.0',
    benchmark_id: campaign.benchmark.benchmark_id,
    manifest_sha256: campaign.benchmark.manifest_sha256,
    adjudication: {
      curator_id: 'external-curator', independent_of_system_development: true, predictions_hidden_until_gold_frozen: true,
      source_annotation_sha256: [sha256('coder-a'), sha256('coder-b')],
    },
    frozen_at: '2026-08-11T19:00:00Z',
    units: campaign.unit_ids.map((unit_id, index) => ({ unit_id, gold_status: byId.get(unit_id), adjudication_method: 'CURATOR_RESOLUTION', evidence_refs: [`SOURCE#${index + 1}`], rationale: 'Independent fixture adjudication rationale long enough for the frozen benchmark schema.' })),
    claim_ceiling: 'FROZEN_ADJUDICATED_BENCHMARK_GOLD_FOR_THIS_SAMPLE',
  };
}


async function coreResultMatchingGold(campaignDir, goldFile, outcome = 'BLOCKED_UNDERPOWERED') {
  const campaign = await readJson(path.join(campaignDir, 'campaign.json'));
  return {
    result_version: 'DAE-EMPIRICAL-BENCHMARK-RESULT-1.0',
    engine_version: engine.context.engineVersion,
    generated_at: '2026-08-11T19:05:00Z',
    benchmark_id: campaign.benchmark.benchmark_id,
    manifest_sha256: campaign.benchmark.manifest_sha256,
    outcome,
    unit_count: campaign.unit_ids.length,
    inputs: { annotation_files: [{ name: 'coder-a.json', sha256: sha256('coder-a'), coder_id: 'coder-a' }, { name: 'coder-b.json', sha256: sha256('coder-b'), coder_id: 'coder-b' }], gold_file: { name: path.basename(goldFile), sha256: sha256(await readFile(goldFile)) } },
    agreement: { metrics: { nominal: { alpha: 0.8 } } },
    systems: { DAE_PRIMARY: {} },
    comparison: {},
    promotion_gate: { passed: outcome === 'PASS_PROMOTION_GATE', eligible: outcome !== 'BLOCKED_UNDERPOWERED', checks: {} },
    issues: [],
    claim_ceiling: 'SAMPLE_BOUND_EMPIRICAL_VALIDATION_NOT_GENERAL_SEMANTIC_INFALLIBILITY',
  };
}

async function challengeResults(campaignDir, systemId, statusForCase) {
  const freeze = await readJson(path.join(campaignDir, 'frozen', 'freeze_lock.json'));
  const challenge = await readJson(path.join(campaignDir, 'frozen', 'semantic_challenge.json'));
  return {
    results_version: 'DESTRUKTION-SEMANTIC-CHALLENGE-RESULTS-1.0',
    campaign_id: challenge.campaign_id,
    challenge_sha256: freeze.semantic_challenge.sha256,
    system_id: systemId,
    generated_at: '2026-08-11T19:10:00Z',
    predictions: challenge.cases.map((item, index) => ({ case_id: item.case_id, status: statusForCase(item, index), confidence: 0.8 })),
    claim_ceiling: 'POST_FREEZE_SYSTEM_RESPONSES_TO_FROZEN_SEMANTIC_CHALLENGE',
  };
}

test('0.8 validation init creates a non-promoting campaign and templates', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-init-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const payload = await readJson(path.join(campaign, 'campaign.json'));
    assert.equal(payload.status, 'OPEN_FOR_EXTERNAL_SYSTEMS');
    assert.equal(payload.required_adversarial_phenomena.length, 7);
    assert.equal((await readJson(path.join(campaign, 'templates', 'external_system.template.json'))).predictions.length, payload.unit_ids.length);
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 freeze rejects a baseline that has seen DAE outputs', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-leak-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const system = await filledSystem(campaign);
    system.independence.dae_outputs_seen = true;
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, system, challenge);
    await assert.rejects(() => freezeExternalValidationCampaign(campaign, [systemFile], challengeFile), /EXTERNAL_SYSTEM_PREDICTIONS_SCHEMA_FAILED/);
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 freeze requires all seven anti-self-confirmation phenomena', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-phenomena-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const system = await filledSystem(campaign);
    const challenge = await filledChallenge(campaign);
    challenge.cases = challenge.cases.filter((entry) => entry.phenomenon !== 'DECOY_TERMINOLOGY');
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, system, challenge);
    await assert.rejects(() => freezeExternalValidationCampaign(campaign, [systemFile], challengeFile), /SEMANTIC_CHALLENGE/);
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 frozen external predictions are byte-fixed before gold', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-fixity-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const system = await filledSystem(campaign);
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, system, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const lock = await readJson(path.join(campaign, 'frozen', 'freeze_lock.json'));
    const frozenSystem = path.join(campaign, 'frozen', lock.systems[0].file);
    const payload = await readJson(frozenSystem);
    payload.predictions[0].status = payload.predictions[0].status === 'SUPPORTED' ? 'REJECTED' : 'SUPPORTED';
    await writeFile(frozenSystem, jsonBytes(payload));
    const gold = await goldMatchingDae(campaign);
    const goldFile = path.join(temp, 'gold.json'); await writeFile(goldFile, jsonBytes(gold));
    const out = path.join(temp, 'evaluation');
    const result = await evaluateExternalValidationCampaign(campaign, goldFile, [], out, { generatedAt });
    assert.equal(result.outcome, 'INVALID_CAMPAIGN');
    assert(result.issues.some((entry) => entry.code.startsWith('EXTERNAL_SYSTEM_FIXITY_FAILED')));
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 evaluation is blocked until every frozen system has adversarial results', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-blocked-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const system = await filledSystem(campaign);
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, system, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const gold = await goldMatchingDae(campaign); const goldFile = path.join(temp, 'gold.json'); await writeFile(goldFile, jsonBytes(gold));
    const daeAdv = await challengeResults(campaign, 'DAE_PRIMARY', () => 'INSUFFICIENT');
    const daeAdvFile = path.join(temp, 'dae-adv.json'); await writeFile(daeAdvFile, jsonBytes(daeAdv));
    const core = await coreResultMatchingGold(campaign, goldFile); const coreFile = path.join(temp, 'core-result.json'); await writeFile(coreFile, jsonBytes(core));
    const result = await evaluateExternalValidationCampaign(campaign, goldFile, [daeAdvFile], path.join(temp, 'evaluation'), { generatedAt, coreBenchmarkResultFile: coreFile });
    assert.equal(result.outcome, 'BLOCKED_PENDING_EXTERNAL_DATA');
    assert(result.issues.some((entry) => entry.code === 'ADVERSARIAL_RESULTS_REQUIRED_FOR_ALL_SYSTEMS'));
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 Pareto comparison preserves tradeoff instead of scalarizing a winner', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-pareto-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const external = await filledSystem(campaign, 'EXT-STRONG', (entry, index) => index === 0 ? { status: entry.status === 'SUPPORTED' ? 'QUALIFIED' : 'SUPPORTED', confidence: 0.7 } : { confidence: 0.85 });
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, external, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const gold = await goldMatchingDae(campaign); const goldFile = path.join(temp, 'gold.json'); await writeFile(goldFile, jsonBytes(gold));
    const daeAdv = await challengeResults(campaign, 'DAE_PRIMARY', (item, index) => index === 0 ? 'SUPPORTED' : 'INSUFFICIENT');
    const extAdv = await challengeResults(campaign, 'EXT-STRONG', () => 'INSUFFICIENT');
    const daeFile = path.join(temp, 'dae-adv.json'); const extFile = path.join(temp, 'ext-adv.json');
    await Promise.all([writeFile(daeFile, jsonBytes(daeAdv)), writeFile(extFile, jsonBytes(extAdv))]);
    const core = await coreResultMatchingGold(campaign, goldFile); const coreFile = path.join(temp, 'core-result.json'); await writeFile(coreFile, jsonBytes(core));
    const result = await evaluateExternalValidationCampaign(campaign, goldFile, [daeFile, extFile], path.join(temp, 'evaluation'), { generatedAt, coreBenchmarkResultFile: coreFile });
    assert.equal(result.outcome, 'TRADEOFF_UNRESOLVED_ON_FROZEN_SAMPLE');
    assert(result.pareto_front.includes('DAE_PRIMARY'));
    assert(result.pareto_front.includes('EXT-STRONG'));
    assert.equal(result.comparison_policy.scalar_global_winner_forbidden, true);
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 exact DAE↔gold match is a review signal, not automatic validation', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-imprint-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const external = await filledSystem(campaign, 'EXT-DIFFERENT', (entry, index) => index === 0 ? { status: entry.status === 'SUPPORTED' ? 'REJECTED' : 'SUPPORTED' } : {});
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, external, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const gold = await goldMatchingDae(campaign); const goldFile = path.join(temp, 'gold.json'); await writeFile(goldFile, jsonBytes(gold));
    const daeAdv = await challengeResults(campaign, 'DAE_PRIMARY', () => 'INSUFFICIENT');
    const extAdv = await challengeResults(campaign, 'EXT-DIFFERENT', () => 'INSUFFICIENT');
    const daeFile = path.join(temp, 'dae-adv.json'); const extFile = path.join(temp, 'ext-adv.json');
    await Promise.all([writeFile(daeFile, jsonBytes(daeAdv)), writeFile(extFile, jsonBytes(extAdv))]);
    const core = await coreResultMatchingGold(campaign, goldFile); const coreFile = path.join(temp, 'core-result.json'); await writeFile(coreFile, jsonBytes(core));
    const result = await evaluateExternalValidationCampaign(campaign, goldFile, [daeFile, extFile], path.join(temp, 'evaluation'), { generatedAt, coreBenchmarkResultFile: coreFile });
    assert.equal(result.self_confirmation_audit.dae_gold_exact_agreement_rate, 1);
    assert.equal(result.self_confirmation_audit.prediction_imprint_review_required, true);
    assert(result.issues.some((entry) => entry.code === 'EXACT_DAE_GOLD_MATCH_REQUIRES_PREDICTION_IMPRINT_REVIEW'));
    assert.notEqual(result.claim_ceiling, 'GENERAL_HERMENEUTIC_VALIDATION');
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 freeze emits post-freeze challenge result templates for DAE and external systems', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-result-templates-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const system = await filledSystem(campaign, 'EXT-TEMPLATE');
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, system, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const daeTemplate = await readJson(path.join(campaign, 'post_freeze_templates', 'DAE_PRIMARY.semantic_challenge_results.template.json'));
    const extTemplate = await readJson(path.join(campaign, 'post_freeze_templates', 'EXT-TEMPLATE.semantic_challenge_results.template.json'));
    assert.equal(daeTemplate.predictions.length, 7);
    assert.equal(extTemplate.system_id, 'EXT-TEMPLATE');
    assert.match(daeTemplate.challenge_sha256, /^[a-f0-9]{64}$/);
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 external comparison remains blocked without a CORE independent benchmark result', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-core-result-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const external = await filledSystem(campaign, 'EXT-CORE-GATE');
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, external, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const gold = await goldMatchingDae(campaign); const goldFile = path.join(temp, 'gold.json'); await writeFile(goldFile, jsonBytes(gold));
    const daeAdv = await challengeResults(campaign, 'DAE_PRIMARY', () => 'INSUFFICIENT');
    const extAdv = await challengeResults(campaign, 'EXT-CORE-GATE', () => 'INSUFFICIENT');
    const daeFile = path.join(temp, 'dae-adv.json'); const extFile = path.join(temp, 'ext-adv.json');
    await Promise.all([writeFile(daeFile, jsonBytes(daeAdv)), writeFile(extFile, jsonBytes(extAdv))]);
    const result = await evaluateExternalValidationCampaign(campaign, goldFile, [daeFile, extFile], path.join(temp, 'evaluation'), { generatedAt });
    assert.equal(result.outcome, 'BLOCKED_PENDING_EXTERNAL_DATA');
    assert(result.issues.some((entry) => entry.code === 'CORE_INDEPENDENT_BENCHMARK_RESULT_REQUIRED'));
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 campaign identity fields remain fixed after freeze even though status may change', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-campaign-fixity-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const external = await filledSystem(campaign, 'EXT-CAMPAIGN-FIXITY');
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, external, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const campaignFile = path.join(campaign, 'campaign.json');
    const mutated = await readJson(campaignFile);
    mutated.benchmark.minimum_units = 81;
    await writeFile(campaignFile, jsonBytes(mutated));
    const gold = await goldMatchingDae(campaign); const goldFile = path.join(temp, 'gold.json'); await writeFile(goldFile, jsonBytes(gold));
    const result = await evaluateExternalValidationCampaign(campaign, goldFile, [], path.join(temp, 'evaluation'), { generatedAt });
    assert.equal(result.outcome, 'INVALID_CAMPAIGN');
    assert(result.issues.some((entry) => entry.code === 'CAMPAIGN_IDENTITY_FIXITY_FAILED'));
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 reports DAE dominated when a frozen external system is no worse on every Pareto dimension', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-dominated-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const external = await filledSystem(campaign, 'EXT-DOMINATOR');
    const dae = await readJson(path.join(campaign, 'dae_primary_snapshot.json'));
    const idx = dae.system.predictions.findIndex((entry) => entry.status !== 'INSUFFICIENT');
    assert(idx >= 0);
    const original = external.predictions[idx].status;
    const replacement = ['SUPPORTED', 'QUALIFIED', 'REJECTED'].find((status) => status !== original);
    external.predictions[idx].status = replacement;
    external.predictions = external.predictions.map((entry) => ({ ...entry, confidence: 1 }));
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, external, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const campaignPayload = await readJson(path.join(campaign, 'campaign.json'));
    const gold = await goldMatchingDae(campaign);
    gold.units[idx].gold_status = replacement;
    const goldFile = path.join(temp, 'gold.json'); await writeFile(goldFile, jsonBytes(gold));
    const core = await coreResultMatchingGold(campaign, goldFile); const coreFile = path.join(temp, 'core-result.json'); await writeFile(coreFile, jsonBytes(core));
    const daeAdv = await challengeResults(campaign, 'DAE_PRIMARY', (item, index) => index === 0 ? 'SUPPORTED' : 'INSUFFICIENT');
    const extAdv = await challengeResults(campaign, 'EXT-DOMINATOR', () => 'INSUFFICIENT');
    const daeFile = path.join(temp, 'dae-adv.json'); const extFile = path.join(temp, 'ext-adv.json');
    await Promise.all([writeFile(daeFile, jsonBytes(daeAdv)), writeFile(extFile, jsonBytes(extAdv))]);
    const result = await evaluateExternalValidationCampaign(campaign, goldFile, [daeFile, extFile], path.join(temp, 'evaluation'), { generatedAt, coreBenchmarkResultFile: coreFile });
    assert.equal(result.outcome, 'DAE_DOMINATED_ON_FROZEN_SAMPLE');
    assert.equal(result.pareto_front.includes('DAE_PRIMARY'), false);
    assert(result.pareto_front.includes('EXT-DOMINATOR'));
  } finally { await rm(temp, { recursive: true, force: true }); }
});

test('0.8 can identify DAE as the sole Pareto-nondominated system without turning that into global validation', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'dae-xval-sole-pareto-'));
  try {
    const { campaign } = await setupCampaign(temp);
    const external = await filledSystem(campaign, 'EXT-WEAKER');
    const dae = await readJson(path.join(campaign, 'dae_primary_snapshot.json'));
    const idx = dae.system.predictions.findIndex((entry) => entry.status !== 'INSUFFICIENT');
    assert(idx >= 0);
    const original = external.predictions[idx].status;
    external.predictions[idx].status = ['SUPPORTED', 'QUALIFIED', 'REJECTED'].find((status) => status !== original);
    external.predictions[idx].confidence = 1;
    const challenge = await filledChallenge(campaign);
    const { systemFile, challengeFile } = await writeFreezeInputs(temp, campaign, external, challenge);
    await freezeExternalValidationCampaign(campaign, [systemFile], challengeFile, { generatedAt });
    const gold = await goldMatchingDae(campaign); const goldFile = path.join(temp, 'gold.json'); await writeFile(goldFile, jsonBytes(gold));
    const core = await coreResultMatchingGold(campaign, goldFile); const coreFile = path.join(temp, 'core-result.json'); await writeFile(coreFile, jsonBytes(core));
    const daeAdv = await challengeResults(campaign, 'DAE_PRIMARY', () => 'INSUFFICIENT');
    const extAdv = await challengeResults(campaign, 'EXT-WEAKER', (item, index) => index === 0 ? 'SUPPORTED' : 'INSUFFICIENT');
    const daeFile = path.join(temp, 'dae-adv.json'); const extFile = path.join(temp, 'ext-adv.json');
    await Promise.all([writeFile(daeFile, jsonBytes(daeAdv)), writeFile(extFile, jsonBytes(extAdv))]);
    const result = await evaluateExternalValidationCampaign(campaign, goldFile, [daeFile, extFile], path.join(temp, 'evaluation'), { generatedAt, coreBenchmarkResultFile: coreFile });
    assert.equal(result.outcome, 'DAE_PARETO_NONDOMINATED_ON_FROZEN_SAMPLE');
    assert.deepEqual(result.pareto_front, ['DAE_PRIMARY']);
    assert.equal(result.claim_ceiling, 'SAMPLE_BOUND_EXTERNAL_COMPARISON_NOT_GENERAL_HERMENEUTIC_TRUTH_OR_CORE_PROMOTION');
  } finally { await rm(temp, { recursive: true, force: true }); }
});
