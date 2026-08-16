import { createHash } from 'node:crypto';
import { access, copyFile, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { classificationMetrics, bootstrapClassification, canonicalBenchmarkSha256 } from '../../src/benchmark.mjs';
import { createEngine } from '../../src/engine.mjs';
import {
  validateExternalValidationCampaign,
  validateExternalSystemPredictions,
  validateSemanticChallenge,
  validateSemanticChallengeResults,
  validateExternalValidationResult,
} from './validator.mjs';

export const REQUIRED_PHENOMENA = [
  'NEGATION',
  'QUOTED_OPPONENT',
  'ATTRIBUTION_SHIFT',
  'MODALITY_WEAKENING',
  'PARAPHRASE',
  'TRANSLATION',
  'DECOY_TERMINOLOGY',
];
const STATUSES = ['SUPPORTED', 'QUALIFIED', 'REJECTED', 'INSUFFICIENT'];
const RESULT_CEILING = 'SAMPLE_BOUND_EXTERNAL_COMPARISON_NOT_GENERAL_HERMENEUTIC_TRUTH_OR_CORE_PROMOTION';

function sha256(value) { return createHash('sha256').update(value).digest('hex'); }
function nowIso(value) { return value ?? new Date().toISOString().replace(/\.\d{3}Z$/u, 'Z'); }
function jsonBytes(value) { return Buffer.from(`${JSON.stringify(value, null, 2)}\n`, 'utf8'); }
async function readJson(file) { return JSON.parse(await readFile(file, 'utf8')); }
async function exists(file) { try { await access(file); return true; } catch { return false; } }
async function requireNewDirectory(directory) {
  try { await stat(directory); throw new Error(`Output directory already exists: ${directory}`); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
}
function assertNoIssues(name, issues) {
  if (!issues.length) return;
  throw new Error(`${name}_SCHEMA_FAILED: ${issues.slice(0, 12).map((x) => `${x.at}: ${x.message}`).join('; ')}`);
}
function sameMembers(left, right) {
  if (left.length !== right.length) return false;
  const a = [...left].sort(); const b = [...right].sort();
  return a.every((value, index) => value === b[index]);
}
function duplicateValues(values) {
  const seen = new Set(); const dup = new Set();
  for (const value of values) { if (seen.has(value)) dup.add(value); seen.add(value); }
  return [...dup].sort();
}
function slug(value) { return String(value).replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'system'; }
function campaignIdentity(campaign) {
  return { campaign_version: campaign.campaign_version, campaign_id: campaign.campaign_id, created_at: campaign.created_at, benchmark: campaign.benchmark, unit_ids: campaign.unit_ids, required_adversarial_phenomena: campaign.required_adversarial_phenomena, claim_ceiling: campaign.claim_ceiling };
}

function externalSystemTemplate(campaign) {
  return {
    predictions_version: 'DESTRUKTION-EXTERNAL-SYSTEM-PREDICTIONS-1.0',
    campaign_id: campaign.campaign_id,
    benchmark_id: campaign.benchmark.benchmark_id,
    system: {
      system_id: 'REPLACE_WITH_SYSTEM_ID',
      kind: 'FRONTIER_LLM_BASELINE',
      name: 'REPLACE_WITH_SYSTEM_NAME',
      model_or_version: 'REPLACE_WITH_EXACT_MODEL_OR_VERSION',
      protocol_id: 'REPLACE_WITH_FROZEN_PROMPT_OR_PROTOCOL_ID',
    },
    independence: {
      independent_of_dae_development: true,
      dae_outputs_seen: false,
      gold_seen: false,
      benchmark_annotations_seen: false,
      system_prompt_contains_dae_output: false,
    },
    generated_at: campaign.created_at,
    predictions: campaign.unit_ids.map((unit_id) => ({ unit_id, status: null, confidence: null })),
    claim_ceiling: 'EXTERNAL_SYSTEM_PREDICTIONS_NOT_GOLD_OR_INDEPENDENT_VALIDATION_BY_THEMSELVES',
  };
}

function challengeTemplate(campaign) {
  return {
    challenge_version: 'DESTRUKTION-SEMANTIC-CHALLENGE-1.0',
    campaign_id: campaign.campaign_id,
    benchmark_id: campaign.benchmark.benchmark_id,
    author: {
      id: 'REPLACE_WITH_INDEPENDENT_CHALLENGE_AUTHOR',
      independent_of_dae_development: true,
      dae_predictions_seen: false,
      gold_seen: false,
    },
    created_at: campaign.created_at,
    cases: REQUIRED_PHENOMENA.map((phenomenon, index) => ({
      case_id: `CH-${String(index + 1).padStart(3, '0')}-${phenomenon}`,
      phenomenon,
      anchor_unit_id: campaign.unit_ids[index % campaign.unit_ids.length],
      variant_text: 'REPLACE_WITH_INDEPENDENTLY_AUTHORED_VARIANT',
      relation_to_anchor: ['PARAPHRASE', 'TRANSLATION'].includes(phenomenon) ? 'PRESERVE' : 'ALLOWED_SET_ONLY',
      allowed_variant_statuses: ['INSUFFICIENT'],
      rationale: 'REPLACE_WITH_SOURCE_GROUNDED_EXPECTATION_AND_WHY_THIS_VARIANT_TESTS_THE_PHENOMENON',
      evidence_refs: [],
    })),
    claim_ceiling: 'INDEPENDENT_ADVERSARIAL_EXPECTATIONS_NOT_GOLD_FOR_UNSEEN_PHILOSOPHICAL_TRUTH',
  };
}


function challengeResultTemplate(campaign, challenge, systemId) {
  return {
    results_version: 'DESTRUKTION-SEMANTIC-CHALLENGE-RESULTS-1.0',
    campaign_id: campaign.campaign_id,
    challenge_sha256: 'FILLED_AT_FREEZE',
    system_id: systemId,
    generated_at: campaign.created_at,
    predictions: challenge.cases.map((item) => ({ case_id: item.case_id, status: null, confidence: null })),
    claim_ceiling: 'POST_FREEZE_SYSTEM_RESPONSES_TO_FROZEN_SEMANTIC_CHALLENGE',
  };
}

function campaignStatus(campaign) {
  return `# External validation campaign ${campaign.campaign_id}\n\nStatus: **${campaign.status}**.\n\nThis layer does not create external evidence. It freezes strong-baseline predictions and an independently authored semantic challenge before gold is opened. A complete result still requires independent human annotations/adjudicated gold from the CORE benchmark and post-freeze challenge predictions.\n\nRequired adversarial phenomena: ${campaign.required_adversarial_phenomena.join(', ')}.\n\nClaim ceiling: \`${campaign.claim_ceiling}\`.\n`;
}

export async function initExternalValidationCampaign(benchmarkDirectory, outputDirectory, options = {}) {
  const benchmarkRoot = path.resolve(benchmarkDirectory);
  const out = path.resolve(outputDirectory);
  await requireNewDirectory(out);
  const [manifestBytes, lockBytes, predictionsBytes] = await Promise.all([
    readFile(path.join(benchmarkRoot, 'benchmark_manifest.json')),
    readFile(path.join(benchmarkRoot, 'benchmark_lock.json')),
    readFile(path.join(benchmarkRoot, 'sealed_predictions.json')),
  ]);
  const manifest = JSON.parse(manifestBytes.toString('utf8'));
  const lock = JSON.parse(lockBytes.toString('utf8'));
  const predictions = JSON.parse(predictionsBytes.toString('utf8'));
  const canonicalManifest = canonicalBenchmarkSha256(manifest);
  if (canonicalManifest !== lock.manifest_sha256) throw new Error('BENCHMARK_MANIFEST_FIXITY_FAILED');
  if (sha256(predictionsBytes) !== lock.sealed_predictions_sha256) throw new Error('SEALED_PREDICTIONS_FIXITY_FAILED');
  if (manifest.benchmark_id !== predictions.benchmark_id || manifest.benchmark_id !== lock.benchmark_id) throw new Error('BENCHMARK_ID_MISMATCH');
  const primary = predictions.systems.find((system) => system.system_id === 'DAE_PRIMARY');
  if (!primary) throw new Error('DAE_PRIMARY_MISSING');
  const unitIds = manifest.units.map((unit) => unit.unit_id);
  if (!sameMembers(unitIds, primary.predictions.map((entry) => entry.unit_id))) throw new Error('DAE_PRIMARY_UNIT_SET_MISMATCH');
  const createdAt = nowIso(options.generatedAt);
  const campaignSeed = JSON.stringify({ benchmark_id: manifest.benchmark_id, manifest_sha256: lock.manifest_sha256, created_at: createdAt });
  const campaign = {
    campaign_version: 'DESTRUKTION-EXTERNAL-VALIDATION-1.0',
    campaign_id: `XVAL-${sha256(campaignSeed).slice(0, 16).toUpperCase()}`,
    created_at: createdAt,
    benchmark: {
      benchmark_id: manifest.benchmark_id,
      manifest_sha256: lock.manifest_sha256,
      sealed_predictions_sha256: lock.sealed_predictions_sha256,
      unit_count: unitIds.length,
      minimum_units: manifest.evaluation_plan?.minimum_units ?? 80,
      source_directory: path.relative(out, benchmarkRoot) || '.',
    },
    unit_ids: unitIds,
    required_adversarial_phenomena: REQUIRED_PHENOMENA,
    status: 'OPEN_FOR_EXTERNAL_SYSTEMS',
    claim_ceiling: 'VALIDATION_PROTOCOL_AND_FIXITY_ENVELOPE_NOT_EXTERNAL_VALIDATION_RESULT',
  };
  assertNoIssues('EXTERNAL_VALIDATION_CAMPAIGN', await validateExternalValidationCampaign(campaign));
  const daeSnapshot = {
    predictions_version: predictions.predictions_version,
    benchmark_id: predictions.benchmark_id,
    manifest_sha256: predictions.manifest_sha256,
    system: primary,
    claim_ceiling: 'FROZEN_DAE_PRIMARY_REFERENCE_FOR_EXTERNAL_COMPARISON',
  };
  await mkdir(path.join(out, 'templates'), { recursive: true });
  await mkdir(path.join(out, 'frozen'), { recursive: true });
  await Promise.all([
    writeFile(path.join(out, 'campaign.json'), jsonBytes(campaign), { flag: 'wx' }),
    writeFile(path.join(out, 'dae_primary_snapshot.json'), jsonBytes(daeSnapshot), { flag: 'wx' }),
    writeFile(path.join(out, 'templates', 'external_system.template.json'), jsonBytes(externalSystemTemplate(campaign)), { flag: 'wx' }),
    writeFile(path.join(out, 'templates', 'semantic_challenge.template.json'), jsonBytes(challengeTemplate(campaign)), { flag: 'wx' }),
    writeFile(path.join(out, 'VALIDATION_STATUS.md'), campaignStatus(campaign), { flag: 'wx' }),
  ]);
  return { campaign, output_dir: out, status: campaign.status };
}

function validateFilledSystem(campaign, payload) {
  const errors = [];
  if (payload.campaign_id !== campaign.campaign_id) errors.push('CAMPAIGN_ID_MISMATCH');
  if (payload.benchmark_id !== campaign.benchmark.benchmark_id) errors.push('BENCHMARK_ID_MISMATCH');
  if (payload.system.system_id === 'DAE_PRIMARY') errors.push('EXTERNAL_SYSTEM_ID_COLLIDES_WITH_DAE_PRIMARY');
  const ids = payload.predictions.map((entry) => entry.unit_id);
  if (!sameMembers(ids, campaign.unit_ids)) errors.push('PREDICTION_UNIT_SET_MISMATCH');
  if (duplicateValues(ids).length) errors.push('DUPLICATE_PREDICTION_UNIT_ID');
  if (payload.predictions.some((entry) => !STATUSES.includes(entry.status) || typeof entry.confidence !== 'number')) errors.push('UNFILLED_OR_INVALID_PREDICTIONS');
  return errors;
}

function validateChallengeCoverage(campaign, challenge) {
  const errors = [];
  if (challenge.campaign_id !== campaign.campaign_id) errors.push('CAMPAIGN_ID_MISMATCH');
  if (challenge.benchmark_id !== campaign.benchmark.benchmark_id) errors.push('BENCHMARK_ID_MISMATCH');
  const phenomena = new Set(challenge.cases.map((entry) => entry.phenomenon));
  for (const required of campaign.required_adversarial_phenomena) if (!phenomena.has(required)) errors.push(`MISSING_PHENOMENON:${required}`);
  if (duplicateValues(challenge.cases.map((entry) => entry.case_id)).length) errors.push('DUPLICATE_CHALLENGE_CASE_ID');
  if (challenge.cases.some((entry) => !campaign.unit_ids.includes(entry.anchor_unit_id))) errors.push('UNKNOWN_ANCHOR_UNIT_ID');
  if (challenge.cases.some((entry) => entry.variant_text.startsWith('REPLACE_WITH_') || entry.rationale.startsWith('REPLACE_WITH_'))) errors.push('UNFILLED_CHALLENGE_TEMPLATE');
  return errors;
}

export async function freezeExternalValidationCampaign(campaignDirectory, systemFiles, challengeFile, options = {}) {
  const root = path.resolve(campaignDirectory);
  const campaignFile = path.join(root, 'campaign.json');
  const campaign = await readJson(campaignFile);
  assertNoIssues('EXTERNAL_VALIDATION_CAMPAIGN', await validateExternalValidationCampaign(campaign));
  if (campaign.status !== 'OPEN_FOR_EXTERNAL_SYSTEMS') throw new Error(`CAMPAIGN_NOT_OPEN:${campaign.status}`);
  if (!Array.isArray(systemFiles) || !systemFiles.length) throw new Error('AT_LEAST_ONE_STRONG_EXTERNAL_SYSTEM_REQUIRED');
  if (!challengeFile) throw new Error('SEMANTIC_CHALLENGE_REQUIRED');
  const systems = [];
  const seenIds = new Set();
  for (const file of systemFiles) {
    const bytes = await readFile(path.resolve(file));
    const payload = JSON.parse(bytes.toString('utf8'));
    assertNoIssues('EXTERNAL_SYSTEM_PREDICTIONS', await validateExternalSystemPredictions(payload));
    const semanticErrors = validateFilledSystem(campaign, payload);
    if (semanticErrors.length) throw new Error(`EXTERNAL_SYSTEM_INVALID:${semanticErrors.join(',')}`);
    if (seenIds.has(payload.system.system_id)) throw new Error(`DUPLICATE_EXTERNAL_SYSTEM_ID:${payload.system.system_id}`);
    seenIds.add(payload.system.system_id);
    systems.push({ file: path.resolve(file), bytes, payload, hash: sha256(bytes) });
  }
  const challengeBytes = await readFile(path.resolve(challengeFile));
  const challenge = JSON.parse(challengeBytes.toString('utf8'));
  assertNoIssues('SEMANTIC_CHALLENGE', await validateSemanticChallenge(challenge));
  const challengeErrors = validateChallengeCoverage(campaign, challenge);
  if (challengeErrors.length) throw new Error(`SEMANTIC_CHALLENGE_INVALID:${challengeErrors.join(',')}`);
  const benchmarkRoot = path.resolve(root, campaign.benchmark.source_directory);
  const possibleGold = [path.join(benchmarkRoot, 'gold.json'), path.join(benchmarkRoot, 'adjudicated_gold.json')];
  if ((await Promise.all(possibleGold.map(exists))).some(Boolean)) throw new Error('GOLD_ALREADY_PRESENT_BEFORE_EXTERNAL_FREEZE');
  const frozenDir = path.join(root, 'frozen');
  await mkdir(path.join(frozenDir, 'systems'), { recursive: true });
  const copiedSystems = [];
  for (const system of systems) {
    const filename = `${slug(system.payload.system.system_id)}.json`;
    const target = path.join(frozenDir, 'systems', filename);
    await writeFile(target, system.bytes, { flag: 'wx' });
    copiedSystems.push({ system_id: system.payload.system.system_id, file: `systems/${filename}`, sha256: system.hash });
  }
  const challengeTarget = path.join(frozenDir, 'semantic_challenge.json');
  await writeFile(challengeTarget, challengeBytes, { flag: 'wx' });
  const freeze = {
    freeze_version: 'DESTRUKTION-EXTERNAL-VALIDATION-FREEZE-1.0',
    campaign_id: campaign.campaign_id,
    benchmark_id: campaign.benchmark.benchmark_id,
    frozen_at: nowIso(options.generatedAt),
    timestamp_authority: 'LOCAL_SYSTEM_CLOCK_UNTRUSTED',
    campaign_identity_sha256: sha256(JSON.stringify(campaignIdentity(campaign))),
    dae_primary_snapshot_sha256: sha256(await readFile(path.join(root, 'dae_primary_snapshot.json'))),
    systems: copiedSystems,
    semantic_challenge: { file: 'semantic_challenge.json', sha256: sha256(challengeBytes), case_count: challenge.cases.length },
    chronology_attestation: {
      gold_absent_in_benchmark_directory_at_freeze: true,
      external_systems_attest_gold_unseen: true,
      challenge_author_attests_gold_and_dae_predictions_unseen: true,
    },
    claim_ceiling: 'LOCAL_PRE_GOLD_FIXITY_LOCK_NOT_PUBLIC_PREREGISTRATION_OR_PROOF_OF_HUMAN_INDEPENDENCE',
  };
  await writeFile(path.join(frozenDir, 'freeze_lock.json'), jsonBytes(freeze), { flag: 'wx' });
  const resultTemplateDir = path.join(root, 'post_freeze_templates');
  await mkdir(resultTemplateDir, { recursive: true });
  for (const systemId of ['DAE_PRIMARY', ...systems.map((entry) => entry.payload.system.system_id)]) {
    const template = challengeResultTemplate(campaign, challenge, systemId);
    template.challenge_sha256 = freeze.semantic_challenge.sha256;
    await writeFile(path.join(resultTemplateDir, `${slug(systemId)}.semantic_challenge_results.template.json`), jsonBytes(template), { flag: 'wx' });
  }
  const updated = { ...campaign, status: 'FROZEN_BEFORE_GOLD' };
  await writeFile(campaignFile, jsonBytes(updated));
  await writeFile(path.join(root, 'VALIDATION_STATUS.md'), campaignStatus(updated));
  return { campaign: updated, freeze, status: updated.status };
}

async function loadFrozenCampaign(root) {
  const campaign = await readJson(path.join(root, 'campaign.json'));
  assertNoIssues('EXTERNAL_VALIDATION_CAMPAIGN', await validateExternalValidationCampaign(campaign));
  if (campaign.status !== 'FROZEN_BEFORE_GOLD' && campaign.status !== 'EVALUATED') throw new Error(`CAMPAIGN_NOT_FROZEN:${campaign.status}`);
  const freeze = await readJson(path.join(root, 'frozen', 'freeze_lock.json'));
  const issues = [];
  if (freeze.campaign_id !== campaign.campaign_id) issues.push('FREEZE_CAMPAIGN_ID_MISMATCH');
  if (freeze.campaign_identity_sha256 !== sha256(JSON.stringify(campaignIdentity(campaign)))) issues.push('CAMPAIGN_IDENTITY_FIXITY_FAILED');
  const daeBytes = await readFile(path.join(root, 'dae_primary_snapshot.json'));
  if (sha256(daeBytes) !== freeze.dae_primary_snapshot_sha256) issues.push('DAE_PRIMARY_FIXITY_FAILED');
  const systems = [];
  for (const entry of freeze.systems) {
    const file = path.join(root, 'frozen', entry.file);
    const bytes = await readFile(file);
    if (sha256(bytes) !== entry.sha256) issues.push(`EXTERNAL_SYSTEM_FIXITY_FAILED:${entry.system_id}`);
    const payload = JSON.parse(bytes.toString('utf8'));
    systems.push(payload);
  }
  const challengeBytes = await readFile(path.join(root, 'frozen', freeze.semantic_challenge.file));
  if (sha256(challengeBytes) !== freeze.semantic_challenge.sha256) issues.push('SEMANTIC_CHALLENGE_FIXITY_FAILED');
  const challenge = JSON.parse(challengeBytes.toString('utf8'));
  return { campaign, freeze, systems, challenge, dae: JSON.parse(daeBytes.toString('utf8')), issues };
}

function adversarialMetrics(challenge, systemResults, anchorPredictions) {
  const byCase = new Map(systemResults.predictions.map((entry) => [entry.case_id, entry]));
  const anchor = new Map(anchorPredictions.map((entry) => [entry.unit_id, entry]));
  const cases = [];
  const byPhenomenon = {};
  let passed = 0;
  for (const item of challenge.cases) {
    const prediction = byCase.get(item.case_id);
    const anchorPrediction = anchor.get(item.anchor_unit_id);
    let relationPass = true;
    if (item.relation_to_anchor === 'PRESERVE') relationPass = prediction.status === anchorPrediction?.status;
    if (item.relation_to_anchor === 'CHANGE_REQUIRED') relationPass = prediction.status !== anchorPrediction?.status;
    if (item.relation_to_anchor === 'ABSTAIN_OR_QUALIFY') relationPass = ['QUALIFIED', 'INSUFFICIENT'].includes(prediction.status);
    const allowedPass = item.allowed_variant_statuses.includes(prediction.status);
    const pass = relationPass && allowedPass;
    if (pass) passed += 1;
    const record = { case_id: item.case_id, phenomenon: item.phenomenon, predicted_status: prediction.status, confidence: prediction.confidence, relation_pass: relationPass, allowed_status_pass: allowedPass, passed: pass };
    cases.push(record);
    byPhenomenon[item.phenomenon] ??= { total: 0, passed: 0 };
    byPhenomenon[item.phenomenon].total += 1;
    if (pass) byPhenomenon[item.phenomenon].passed += 1;
  }
  for (const value of Object.values(byPhenomenon)) value.pass_rate = value.passed / value.total;
  return { case_count: cases.length, passed, pass_rate: cases.length ? passed / cases.length : 0, by_phenomenon: byPhenomenon, cases };
}

function dominanceVector(system) {
  const m = system.metrics;
  return {
    macro_f1: m.macro_f1,
    balanced_accuracy: m.balanced_accuracy,
    safety: 1 - m.dangerous_overpromotion.rate,
    calibration: 1 - m.calibration.expected_calibration_error,
    coverage: m.abstention.coverage,
    adversarial: system.adversarial?.pass_rate ?? null,
  };
}
function dominates(left, right) {
  const a = dominanceVector(left); const b = dominanceVector(right);
  const keys = Object.keys(a);
  if (keys.some((key) => a[key] === null || b[key] === null)) return false;
  const weak = keys.every((key) => a[key] >= b[key]);
  const strict = keys.some((key) => a[key] > b[key]);
  return weak && strict;
}
function paretoSystems(systems) {
  const entries = Object.entries(systems);
  return entries.filter(([id, value]) => !entries.some(([otherId, other]) => otherId !== id && dominates(other, value))).map(([id]) => id).sort();
}

function externalReport(result) {
  const lines = [
    `# External Hermeneutic Validation — ${result.campaign_id}`,
    '',
    `Outcome: **${result.outcome}**.`,
    '',
    `Claim ceiling: \`${result.claim_ceiling}\`.`,
    '',
  ];
  if (result.issues?.length) {
    lines.push('## Issues', '');
    for (const item of result.issues) lines.push(`- ${item.severity} \`${item.code}\`: ${item.message}`);
    lines.push('');
  }
  if (Object.keys(result.systems ?? {}).length) {
    lines.push('## Frozen-sample comparison', '', '| System | Macro-F1 | Balanced acc. | Dangerous overpromotion | ECE | Coverage | Adversarial |', '|---|---:|---:|---:|---:|---:|---:|');
    for (const [id, system] of Object.entries(result.systems)) lines.push(`| ${id} | ${system.metrics.macro_f1.toFixed(3)} | ${system.metrics.balanced_accuracy.toFixed(3)} | ${system.metrics.dangerous_overpromotion.rate.toFixed(3)} | ${system.metrics.calibration.expected_calibration_error.toFixed(3)} | ${system.metrics.abstention.coverage.toFixed(3)} | ${system.adversarial ? system.adversarial.pass_rate.toFixed(3) : 'NA'} |`);
    lines.push('', `Pareto front: ${result.pareto_front.map((x) => `\`${x}\``).join(', ') || 'none'}.`, '');
  }
  lines.push('## Anti-self-confirmation audit', '', `- exact DAE↔gold agreement: ${result.self_confirmation_audit?.dae_gold_exact_agreement_rate ?? 'NA'}`, `- prediction-imprint review: ${result.self_confirmation_audit?.prediction_imprint_review_required ? 'REQUIRED' : 'not triggered'}`, `- scalar global winner: **forbidden**; comparison is Pareto/multi-objective.`, '');
  return `${lines.join('\n')}\n`;
}

export async function evaluateExternalValidationCampaign(campaignDirectory, goldFile, adversarialResultFiles, outputDirectory, options = {}) {
  const root = path.resolve(campaignDirectory);
  const out = path.resolve(outputDirectory);
  await requireNewDirectory(out);
  const frozen = await loadFrozenCampaign(root);
  const issues = frozen.issues.map((code) => ({ severity: 'ERROR', code, message: 'Frozen validation artifact changed after lock creation.' }));
  if (issues.length) {
    const invalid = {
      result_version: 'DESTRUKTION-EXTERNAL-VALIDATION-RESULT-1.0', campaign_id: frozen.campaign.campaign_id, evaluated_at: nowIso(options.generatedAt), outcome: 'INVALID_CAMPAIGN', systems: {}, pareto_front: [], self_confirmation_audit: {}, issues, claim_ceiling: RESULT_CEILING,
    };
    await mkdir(out, { recursive: true });
    await writeFile(path.join(out, 'external_validation_result.json'), jsonBytes(invalid));
    await writeFile(path.join(out, 'EXTERNAL_VALIDATION_REPORT.md'), externalReport(invalid));
    return invalid;
  }
  if (!goldFile) throw new Error('ADJUDICATED_GOLD_REQUIRED');
  const gold = await readJson(path.resolve(goldFile));
  const engine = await createEngine();
  const goldSchemaIssues = engine.structural.validateBenchmarkGold(gold);
  if (goldSchemaIssues.length) throw new Error(`GOLD_SCHEMA_FAILED:${goldSchemaIssues.slice(0, 8).map((x) => `${x.code}:${x.at}`).join(',')}`);
  let coreBenchmarkResult = null;
  let independentEvidenceAvailable = false;
  if (options.coreBenchmarkResultFile) {
    coreBenchmarkResult = await readJson(path.resolve(options.coreBenchmarkResultFile));
    const coreResultIssues = engine.structural.validateBenchmarkResult(coreBenchmarkResult);
    if (coreResultIssues.length) throw new Error(`CORE_BENCHMARK_RESULT_SCHEMA_FAILED:${coreResultIssues.slice(0, 8).map((x) => `${x.code}:${x.at}`).join(',')}`);
    if (coreBenchmarkResult.benchmark_id !== frozen.campaign.benchmark.benchmark_id || coreBenchmarkResult.manifest_sha256 !== frozen.campaign.benchmark.manifest_sha256) throw new Error('CORE_BENCHMARK_RESULT_IDENTITY_MISMATCH');
    const expectedGoldHash = coreBenchmarkResult.inputs?.gold_file?.sha256;
    const actualGoldHash = sha256(await readFile(path.resolve(goldFile)));
    if (!expectedGoldHash || expectedGoldHash !== actualGoldHash) throw new Error('CORE_BENCHMARK_RESULT_GOLD_FIXITY_MISMATCH');
    independentEvidenceAvailable = ['BLOCKED_UNDERPOWERED', 'FAIL_RELIABILITY', 'FAIL_PROMOTION_GATE', 'PASS_PROMOTION_GATE'].includes(coreBenchmarkResult.outcome)
      && coreBenchmarkResult.agreement !== null && coreBenchmarkResult.systems !== null;
  }
  if (gold.benchmark_id !== frozen.campaign.benchmark.benchmark_id || gold.manifest_sha256 !== frozen.campaign.benchmark.manifest_sha256) throw new Error('GOLD_BENCHMARK_MISMATCH');
  const goldIds = gold.units.map((entry) => entry.unit_id);
  if (!sameMembers(goldIds, frozen.campaign.unit_ids)) throw new Error('GOLD_UNIT_SET_MISMATCH');
  const goldById = new Map(gold.units.map((entry) => [entry.unit_id, entry.gold_status]));
  if (gold.units.some((entry) => !STATUSES.includes(entry.gold_status))) throw new Error('GOLD_HAS_UNFILLED_STATUS');
  const adversarialBySystem = new Map();
  for (const file of adversarialResultFiles ?? []) {
    const payload = await readJson(path.resolve(file));
    assertNoIssues('SEMANTIC_CHALLENGE_RESULTS', await validateSemanticChallengeResults(payload));
    if (payload.campaign_id !== frozen.campaign.campaign_id || payload.challenge_sha256 !== frozen.freeze.semantic_challenge.sha256) throw new Error(`ADVERSARIAL_RESULT_MISMATCH:${file}`);
    if (adversarialBySystem.has(payload.system_id)) throw new Error(`DUPLICATE_ADVERSARIAL_SYSTEM:${payload.system_id}`);
    if (!sameMembers(payload.predictions.map((x) => x.case_id), frozen.challenge.cases.map((x) => x.case_id))) throw new Error(`ADVERSARIAL_CASE_SET_MISMATCH:${payload.system_id}`);
    adversarialBySystem.set(payload.system_id, payload);
  }
  const daePredictions = frozen.dae.system.predictions;
  const systemPayloads = [{
    system_id: 'DAE_PRIMARY', predictions: daePredictions,
  }, ...frozen.systems.map((entry) => ({ system_id: entry.system.system_id, predictions: entry.predictions }))];
  const systems = {};
  for (const system of systemPayloads) {
    const byId = new Map(system.predictions.map((entry) => [entry.unit_id, entry]));
    const ordered = frozen.campaign.unit_ids.map((unitId) => byId.get(unitId));
    const goldOrdered = frozen.campaign.unit_ids.map((unitId) => goldById.get(unitId));
    const metrics = classificationMetrics(ordered.map((entry) => entry.status), goldOrdered, ordered.map((entry) => entry.confidence));
    metrics.bootstrap = bootstrapClassification(ordered.map((entry) => entry.status), goldOrdered, ordered.map((entry) => entry.confidence), Number(options.bootstrapIterations ?? 500), `${frozen.campaign.campaign_id}:${system.system_id}`);
    const advPayload = adversarialBySystem.get(system.system_id);
    systems[system.system_id] = {
      metrics,
      adversarial: advPayload ? adversarialMetrics(frozen.challenge, advPayload, ordered) : null,
    };
  }
  const missingAdv = Object.keys(systems).filter((systemId) => !systems[systemId].adversarial);
  if (missingAdv.length) issues.push({ severity: 'ERROR', code: 'ADVERSARIAL_RESULTS_REQUIRED_FOR_ALL_SYSTEMS', message: `Missing challenge predictions for: ${missingAdv.join(', ')}` });
  if (!options.coreBenchmarkResultFile) issues.push({ severity: 'ERROR', code: 'CORE_INDEPENDENT_BENCHMARK_RESULT_REQUIRED', message: 'A CORE BENCHMARK_RESULT.json generated from independent annotations and adjudicated gold is required.' });
  else if (!independentEvidenceAvailable) issues.push({ severity: 'ERROR', code: 'CORE_INDEPENDENT_EVIDENCE_NOT_AVAILABLE', message: `CORE benchmark outcome ${coreBenchmarkResult?.outcome ?? 'UNKNOWN'} does not establish that independent annotations and gold were evaluated.` });
  const unitCount = frozen.campaign.unit_ids.length;
  if (unitCount < frozen.campaign.benchmark.minimum_units) issues.push({ severity: 'REVIEW', code: 'BENCHMARK_UNDERPOWERED', message: `${unitCount} units < frozen minimum ${frozen.campaign.benchmark.minimum_units}.` });
  const daeGoldAgreement = daePredictions.filter((entry) => goldById.get(entry.unit_id) === entry.status).length / unitCount;
  const externalExact = frozen.systems.map((system) => ({ system_id: system.system.system_id, exact_agreement_rate: system.predictions.filter((entry) => goldById.get(entry.unit_id) === entry.status).length / unitCount }));
  const imprintReview = daeGoldAgreement === 1 && externalExact.some((entry) => entry.exact_agreement_rate < 1);
  if (imprintReview) issues.push({ severity: 'REVIEW', code: 'EXACT_DAE_GOLD_MATCH_REQUIRES_PREDICTION_IMPRINT_REVIEW', message: 'Gold exactly matches DAE while at least one frozen external system differs. This is not proof of leakage, but requires provenance review before promotion claims.' });
  const pareto = missingAdv.length ? [] : paretoSystems(systems);
  let outcome = 'BLOCKED_PENDING_EXTERNAL_DATA';
  if (!missingAdv.length && independentEvidenceAvailable) {
    const daeOnFront = pareto.includes('DAE_PRIMARY');
    const daeDominated = Object.entries(systems).some(([id, system]) => id !== 'DAE_PRIMARY' && dominates(system, systems.DAE_PRIMARY));
    if (daeDominated) outcome = 'DAE_DOMINATED_ON_FROZEN_SAMPLE';
    else if (daeOnFront && pareto.length === 1) outcome = 'DAE_PARETO_NONDOMINATED_ON_FROZEN_SAMPLE';
    else outcome = 'TRADEOFF_UNRESOLVED_ON_FROZEN_SAMPLE';
  }
  const result = {
    result_version: 'DESTRUKTION-EXTERNAL-VALIDATION-RESULT-1.0',
    campaign_id: frozen.campaign.campaign_id,
    evaluated_at: nowIso(options.generatedAt),
    outcome,
    benchmark: { benchmark_id: frozen.campaign.benchmark.benchmark_id, unit_count: unitCount, minimum_units: frozen.campaign.benchmark.minimum_units },
    core_independent_benchmark: coreBenchmarkResult ? {
      outcome: coreBenchmarkResult.outcome,
      promotion_gate_passed: coreBenchmarkResult.promotion_gate?.passed ?? false,
      agreement_available: coreBenchmarkResult.agreement !== null,
      result_file_sha256: sha256(await readFile(path.resolve(options.coreBenchmarkResultFile))),
    } : null,
    systems,
    pareto_front: pareto,
    self_confirmation_audit: {
      dae_gold_exact_agreement_rate: daeGoldAgreement,
      external_gold_exact_agreement: externalExact,
      prediction_imprint_review_required: imprintReview,
      note: 'Exact agreement is only a review signal; independence still depends on real external collection and source-grounded adjudication.',
    },
    comparison_policy: {
      scalar_global_winner_forbidden: true,
      dimensions: ['macro_f1', 'balanced_accuracy', '1-dangerous_overpromotion', '1-ECE', 'coverage', 'adversarial_pass_rate'],
      selection: 'PARETO_NONDOMINANCE',
    },
    issues,
    claim_ceiling: RESULT_CEILING,
  };
  assertNoIssues('EXTERNAL_VALIDATION_RESULT', await validateExternalValidationResult(result));
  await mkdir(out, { recursive: true });
  await writeFile(path.join(out, 'external_validation_result.json'), jsonBytes(result), { flag: 'wx' });
  await writeFile(path.join(out, 'EXTERNAL_VALIDATION_REPORT.md'), externalReport(result), { flag: 'wx' });
  const updated = { ...frozen.campaign, status: 'EVALUATED' };
  await writeFile(path.join(root, 'campaign.json'), jsonBytes(updated));
  await writeFile(path.join(root, 'VALIDATION_STATUS.md'), campaignStatus(updated));
  return result;
}

export async function externalValidationStatus(campaignDirectory) {
  const root = path.resolve(campaignDirectory);
  const campaign = await readJson(path.join(root, 'campaign.json'));
  const output = { campaign_id: campaign.campaign_id, status: campaign.status, benchmark: campaign.benchmark, frozen: await exists(path.join(root, 'frozen', 'freeze_lock.json')) };
  if (output.frozen) {
    const freeze = await readJson(path.join(root, 'frozen', 'freeze_lock.json'));
    output.external_systems = freeze.systems.map((x) => x.system_id);
    output.challenge_cases = freeze.semantic_challenge.case_count;
  }
  return output;
}
