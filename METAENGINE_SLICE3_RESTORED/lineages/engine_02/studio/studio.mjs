#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { access, copyFile, mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { constants as fsConstants } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import readline from 'node:readline/promises';
import process from 'node:process';
import { gateOperatorDelta } from '../mutation/operator-mutation-engine.mjs';
import { validateDeclarativeGestures } from '../src/generative-gesture-runtime.mjs';
import { compareLivingAnalyses, renderLivingComparisonMarkdown } from './living-comparator.mjs';
import { discoverResistance, renderResistanceDiscoveryMarkdown } from '../discovery/resistant-source-discovery.mjs';
import { mergeDiscoveryLedger, renderDiscoveryLedgerMarkdown } from './discovery-ledger.mjs';
import { createEngine } from '../src/engine.mjs';
import { runMicroLocalOperatorEcology } from './compat/micro-local-operator-ecology-0.9.mjs';
import { runIndependentFamilyEcology } from './independent-family/independent-family-ecology.mjs';
import { runEcologyDownstream } from './independent-family/ecology-downstream.mjs';
import { runIndependentFamilyProbe } from './independent-family/family-probe.mjs';
import { initExternalValidationCampaign, freezeExternalValidationCampaign, evaluateExternalValidationCampaign, externalValidationStatus } from './validation/external-validation.mjs';
import { buildHoldoutArchitectureBenchmark, auditHoldoutArchitectureBenchmark } from './validation/holdout-architecture.mjs';

const STUDIO_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(STUDIO_DIR, '..');
const WORKSPACE = path.join(ROOT, 'workspace');
const RUNS = path.join(WORKSPACE, 'runs');
const EXPERIMENTS = path.join(WORKSPACE, 'experiments');
const DELTAS = path.join(WORKSPACE, 'operator-deltas');
const SNAPSHOTS = path.join(WORKSPACE, 'snapshots');
const OPERATOR_REGISTRIES = path.join(WORKSPACE, 'operator-registries');
const DISCOVERY_CASES = path.join(WORKSPACE, 'discovery-cases');
const DISCOVERY_LEDGER = path.join(DISCOVERY_CASES, 'CASE_LEDGER.json');
const DISCOVERY_LEDGER_MD = path.join(DISCOVERY_CASES, 'CASE_LEDGER.md');
const MUTATION_POLICY = path.join(ROOT, 'config', 'operator_mutation_policy.json');
const BASELINE_OPERATOR_REGISTRY = path.join(ROOT, 'config', 'living_operator_registry.json');
const DECLARATIVE_OPERATOR_REGISTRY = path.join(ROOT, 'config', 'living_operator_registry.declarative.json');
const HISTORICAL_09_OPERATOR_REGISTRY = path.join(ROOT, 'studio', 'compat', 'living_operator_registry.0.9.json');
const CORE_CLI = path.join(ROOT, 'bin', 'destruktion.mjs');
const DECLARATIVE_CLI = path.join(ROOT, 'bin', 'destruktion-declarative.mjs');

const HELP = `Destruktion Studio 0.9 — Frozen Holdout Benchmark

Usage:
  node studio/studio.mjs                    Interactive menu
  node studio/studio.mjs doctor             Check runtime, fixity and optional DOCX support
  node studio/studio.mjs setup              Try locked npm install; bundled validator keeps offline mode usable
  node studio/studio.mjs card               Show portable project card (engine if available)
  node studio/studio.mjs session:new <name> Create an immutable run workspace
  node studio/studio.mjs cycle:docx <file.docx> --job <job.json> [--seed <text>] [--profile <profile.json>]
  node studio/studio.mjs analyze:text <file.txt|file.md>
  node studio/studio.mjs run:living <refinery-dir> [--seed <text>]
  node studio/studio.mjs run:living-declarative <refinery-dir> [--seed <text>]
  node studio/studio.mjs run:living-mutant <refinery-dir> --registry <candidate.json> [--seed <text>]
  node studio/studio.mjs run:living-mutant-declarative <refinery-dir> --registry <candidate.json> [--seed <text>]
  node studio/studio.mjs compare:living <refinery-dir> --registry <candidate.json> [--seed <text>]
  node studio/studio.mjs discover:resistance <living_analysis.json|dir>... [--registry <registry.json>] [--min-support <n>] [--min-resistance <n>] [--min-unitizations <n>]
  node studio/studio.mjs discover:history      Show persistent resistant-source recurrence ledger
  node studio/studio.mjs regress:operator <manifest.json> --out <dir>
  node studio/studio.mjs compete:operators <manifest.json> --out <dir>
  node studio/studio.mjs ecology:open-set <hypothesis_bank.json> --out <dir>
  node studio/studio.mjs ecology:regression <micro_local_operator_ecology_manifest.json> --out <dir>
  node studio/studio.mjs ecology:independent <independent_family_ecology_manifest.json> --out <dir>
  node studio/studio.mjs ecology:downstream <independent micro_local_ecology_result.json> --out <dir>
  node studio/studio.mjs family:probe <source.docx> --out <dir> [--language <tag>]
  node studio/studio.mjs validation:init <benchmark-dir> --out <campaign-dir>
  node studio/studio.mjs validation:freeze <campaign-dir> --system <predictions.json> [--system <...>] --challenge <challenge.json>
  node studio/studio.mjs validation:evaluate <campaign-dir> --gold <gold.json> --core-result <BENCHMARK_RESULT.json> --adversarial <results.json> [--adversarial <...>] --out <dir>
  node studio/studio.mjs validation:status <campaign-dir>
  node studio/studio.mjs validation:holdout-build <HOLDOUT_SOURCE_FREEZE.json> --pipelines <dir> --out <benchmark-dir>
  node studio/studio.mjs validation:holdout-audit <benchmark-dir>
  node studio/studio.mjs ecology:micro <hypothesis_bank.json> --out <dir>    Alias for ecology:open-set
  node studio/studio.mjs run:expert <refinery-dir> [--profile <profile.json>]
  node studio/studio.mjs experiment:new <name>
  node studio/studio.mjs delta:new <name>
  node studio/studio.mjs delta:gate <operator_delta.json> [--registry <registry.json>] [--out <dir>]
  node studio/studio.mjs delta:promote <gate-output-dir>
  node studio/studio.mjs snapshot [label]
  node studio/studio.mjs status
  node studio/studio.mjs core <args...>      Pass through to the original DAE CLI

Operator mutation is candidate-based and reversible. Studio 0.9 preserves the frozen DAE 0.10 open-set baseline and adds an experimental independent interrogative-family ecology: processual-hermeneutic family probing, source-birth verification, cross-family local composition, polyphonic synthesis gates, and downstream living/expert boundary preservation. The stronger 0.9 localization-loss regression remains a separate compatibility audit.

Studio discovery remains non-promoting: resistant-source cases and independent-family probes may seed hypotheses, but neither is promotion-ready. The DAE 0.10 registry is the default mutation/discovery reference; all 66 frozen 0.10 portable assets remain untouched. Independent-family 0.10 regression artifacts are treated as a behavioral oracle because their source runtime was not supplied. The historical 0.9 registry is retained as a comparison control. External validation is deliberately non-promoting: it freezes strong baselines and adversarial challenges before gold, compares systems on a Pareto front, and treats exact DAE↔gold agreement as a review signal rather than proof. Studio 0.9 adds a separate 81-unit frozen passage holdout selected before DAE execution; its passages are embargoed from tuning until independent coder annotations, adjudicated gold, and the first primary evaluation are frozen.
`

function nowIso() { return new Date().toISOString(); }
function stamp() { return nowIso().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z'); }
function slugify(value = 'run') {
  const s = String(value).normalize('NFKD')
    .replace(/[^\p{L}\p{N}._-]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
  return s.slice(0, 64) || 'run';
}
function sha256(bytes) { return createHash('sha256').update(bytes).digest('hex'); }
async function exists(file) { try { await access(file, fsConstants.F_OK); return true; } catch { return false; } }
async function ensureWorkspace() {
  for (const d of [WORKSPACE, RUNS, EXPERIMENTS, DELTAS, SNAPSHOTS, OPERATOR_REGISTRIES, DISCOVERY_CASES, path.join(WORKSPACE, 'inputs')]) await mkdir(d, { recursive: true });
}
function opt(args, flag) {
  const i = args.indexOf(flag);
  return i >= 0 ? args[i + 1] : undefined;
}
function hasFlag(args, flag) { return args.includes(flag); }
function valuesForFlag(args, flag) {
  const values = [];
  for (let i = 0; i < args.length; i += 1) if (args[i] === flag && args[i + 1] && !args[i + 1].startsWith('--')) values.push(args[i + 1]);
  return values;
}
function positional(args, flagsWithValues = []) {
  const skip = new Set();
  for (const flag of flagsWithValues) {
    for (let i = 0; i < args.length; i += 1) {
      if (args[i] === flag) { skip.add(i); skip.add(i + 1); }
    }
  }
  return args.filter((x, i) => !skip.has(i) && !x.startsWith('--'));
}
function commandExists(command, args = ['--version']) {
  const r = spawnSync(command, args, { encoding: 'utf8', shell: false, windowsHide: true });
  return { ok: r.status === 0, status: r.status, stdout: (r.stdout || '').trim(), stderr: (r.stderr || '').trim(), error: r.error?.message };
}
async function readJson(file) { return JSON.parse(await readFile(file, 'utf8')); }
async function writeJson(file, data) { await writeFile(file, `${JSON.stringify(data, null, 2)}\n`, 'utf8'); }

async function portableFixityCheck() {
  const file = path.join(ROOT, 'PORTABLE_PROJECT.json');
  const manifest = await readJson(file);
  const problems = [];
  let checked = 0;
  for (const asset of manifest.required_assets || []) {
    const target = path.join(ROOT, asset.path);
    try {
      const bytes = await readFile(target);
      checked += 1;
      if (bytes.length !== asset.size_bytes) problems.push(`${asset.path}: size ${bytes.length} != ${asset.size_bytes}`);
      const digest = sha256(bytes);
      if (digest !== asset.sha256) problems.push(`${asset.path}: sha256 mismatch`);
    } catch (e) {
      problems.push(`${asset.path}: ${e.message}`);
    }
  }
  return { ok: problems.length === 0, checked, problems, manifest };
}

async function doctor({ quiet = false } = {}) {
  await ensureWorkspace();
  const nodeMajor = Number(process.versions.node.split('.')[0]);
  const npm = commandExists(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['--version']);
  const libre = commandExists(process.platform === 'win32' ? 'soffice.exe' : 'soffice', ['--version']);
  const libreAlt = libre.ok ? libre : commandExists(process.platform === 'win32' ? 'libreoffice.exe' : 'libreoffice', ['--version']);
  const ajvInstalled = await exists(path.join(ROOT, 'node_modules', 'ajv', 'package.json'));
  const ajvFallback = await exists(path.join(ROOT, 'vendor', 'ajv-compat', '2020.mjs'));
  const validatorAvailable = ajvInstalled || ajvFallback;
  const independentFamilyAssets = [
    path.join(ROOT, 'studio', 'independent-family', 'family-signal-runtime.mjs'),
    path.join(ROOT, 'studio', 'independent-family', 'independent-family-ecology.mjs'),
    path.join(ROOT, 'studio', 'independent-family', 'ecology-downstream.mjs'),
    path.join(ROOT, 'studio', 'independent-family', 'family-probe.mjs'),
    path.join(ROOT, 'studio', 'schemas', 'independent_family_ecology_manifest.schema.json'),
    path.join(ROOT, 'experiments', 'independent-family-ecology-0.10', 'micro_local_ecology_manifest.json'),
  ];
  const independentFamilyReady = (await Promise.all(independentFamilyAssets.map(exists))).every(Boolean);
  const externalValidationAssets = [
    path.join(ROOT, 'studio', 'validation', 'external-validation.mjs'),
    path.join(ROOT, 'studio', 'validation', 'validator.mjs'),
    path.join(ROOT, 'studio', 'schemas', 'external_validation_campaign.schema.json'),
    path.join(ROOT, 'studio', 'schemas', 'external_system_predictions.schema.json'),
    path.join(ROOT, 'studio', 'schemas', 'semantic_challenge_manifest.schema.json'),
    path.join(ROOT, 'studio', 'schemas', 'semantic_challenge_results.schema.json'),
    path.join(ROOT, 'studio', 'schemas', 'external_validation_result.schema.json'),
  ];
  const externalValidationReady = (await Promise.all(externalValidationAssets.map(exists))).every(Boolean);
  const holdoutDir = path.join(ROOT, 'experiments', 'external-validation-0.9', 'frozen-architecture-holdout');
  const holdoutAssets = [path.join(ROOT, 'studio', 'validation', 'holdout-architecture.mjs'), path.join(holdoutDir, 'holdout_manifest.json'), path.join(holdoutDir, 'HOLDOUT_LOCK.json')];
  const holdoutFilesReady = (await Promise.all(holdoutAssets.map(exists))).every(Boolean);
  const holdoutAudit = holdoutFilesReady ? await auditHoldoutArchitectureBenchmark(holdoutDir) : { status: 'MISSING', unit_count: 0, issues: ['missing Studio 0.9 holdout assets'] };
  const holdoutReady = holdoutAudit.status === 'PASS' && holdoutAudit.unit_count >= 80;
  const fixity = await portableFixityCheck();
  let declarativeErrors = [];
  try { declarativeErrors = validateDeclarativeGestures(await readJson(DECLARATIVE_OPERATOR_REGISTRY)); }
  catch (error) { declarativeErrors = [error.message]; }
  let writable = true;
  try {
    const probe = path.join(WORKSPACE, `.write-probe-${process.pid}`);
    await writeFile(probe, 'ok', 'utf8');
    const { unlink } = await import('node:fs/promises');
    await unlink(probe);
  } catch { writable = false; }

  const checks = [
    { name: 'Node.js >= 20', ok: nodeMajor >= 20, detail: process.versions.node },
    { name: 'npm', ok: npm.ok, detail: npm.ok ? npm.stdout : (npm.error || npm.stderr || 'not found') },
    { name: 'workspace writable', ok: writable, detail: WORKSPACE },
    { name: 'portable asset fixity', ok: fixity.ok, detail: `${fixity.checked} required assets checked` },
    { name: 'declarative gesture registry', ok: declarativeErrors.length === 0, detail: declarativeErrors.length ? declarativeErrors[0] : 'GX grammar compiles' },
    { name: 'resistant-source discovery', ok: true, detail: 'structural detector + non-promotable delta seeds + longitudinal ledger' },
    { name: 'independent-family ecology', ok: independentFamilyReady, detail: independentFamilyReady ? 'processual family probe + source-birth gate + cross-family ecology + downstream abstention' : 'missing Studio 0.7 independent-family assets' },
    { name: 'external validation / anti-self-confirmation', ok: externalValidationReady, detail: externalValidationReady ? 'pre-gold freeze + strong external baselines + semantic adversarial suite + Pareto comparison' : 'missing Studio 0.8 validation assets' },
    { name: 'frozen passage holdout', ok: holdoutReady, detail: holdoutReady ? `${holdoutAudit.unit_count} passage×hypothesis units; fixity PASS; independent labels pending` : `not ready: ${holdoutAudit.issues.join(', ')}` },
    { name: 'structural validator backend', ok: validatorAvailable, detail: ajvInstalled ? 'package ajv@8.17.1' : (ajvFallback ? 'bundled ajv-compat fallback (offline-ready)' : 'missing') },
    { name: 'LibreOffice / soffice', ok: libreAlt.ok, optional: true, detail: libreAlt.ok ? (libreAlt.stdout || 'available') : 'optional; required for DOCX rendering pipeline' },
  ];
  const coreReady = checks.filter(x => !x.optional).every(x => x.ok);
  const docxReady = coreReady && libreAlt.ok;
  const result = { studio_version: '0.9.0-frozen-holdout', checked_at: nowIso(), root: ROOT, core_ready: coreReady, docx_ready: docxReady, checks, fixity_problems: fixity.problems };
  if (!quiet) {
    console.log('Destruktion Studio — doctor');
    for (const c of checks) console.log(`${c.ok ? '✓' : (c.optional ? '○' : '✗')} ${c.name}: ${c.detail}`);
    if (fixity.problems.length) for (const p of fixity.problems.slice(0, 20)) console.log(`  ! ${p}`);
    console.log(`\nCORE runtime: ${coreReady ? 'READY' : 'NOT READY'}${docxReady ? ' · DOCX pipeline READY' : ''}`);
    if (!validatorAvailable) console.log('No JSON Schema backend is available. Restore vendor/ajv-compat or run npm ci.');
  }
  return result;
}

async function runProcess(command, args, { cwd = ROOT, logFile, env = {} } = {}) {
  if (logFile) await writeFile(logFile, `# ${nowIso()}\n${command} ${args.map(JSON.stringify).join(' ')}\n\n`, { flag: 'a' });
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, stdio: ['inherit', 'pipe', 'pipe'], shell: false, windowsHide: true, env: { ...process.env, ...env } });
    child.stdout.on('data', d => { process.stdout.write(d); if (logFile) writeFile(logFile, d, { flag: 'a' }).catch(() => {}); });
    child.stderr.on('data', d => { process.stderr.write(d); if (logFile) writeFile(logFile, d, { flag: 'a' }).catch(() => {}); });
    child.on('error', reject);
    child.on('close', code => code === 0 ? resolve(0) : reject(new Error(`${command} exited with code ${code}`)));
  });
}

async function runCore(args, options = {}) {
  const d = await doctor({ quiet: true });
  if (!d.core_ready) throw new Error('CORE runtime is not ready. Run `node studio/studio.mjs doctor` and `setup`.');
  return runProcess(process.execPath, [CORE_CLI, ...args], options);
}

async function runDeclarative(args, options = {}) {
  const d = await doctor({ quiet: true });
  if (!d.core_ready) throw new Error('Declarative living runtime needs the same locked CORE dependencies. Run setup first.');
  return runProcess(process.execPath, [DECLARATIVE_CLI, ...args], options);
}

async function setup() {
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  console.log('Trying locked dependencies with npm ci…');
  try {
    await runProcess(npmCmd, ['ci', '--ignore-scripts', '--no-audit', '--no-fund'], { cwd: ROOT });
  } catch (error) {
    const current = await doctor({ quiet: true });
    if (!current.core_ready) throw error;
    console.warn(`npm ci unavailable (${error.message}). Continuing with the bundled offline validator backend.`);
  }
  await doctor();
}

async function projectCard() {
  const d = await doctor({ quiet: true });
  if (d.core_ready) return runCore(['portable-card']);
  const manifest = await readJson(path.join(ROOT, 'PORTABLE_PROJECT.json'));
  console.log(`${manifest.title}\nportable=${manifest.portable_project_version} engine=${manifest.engine_version}\nentrypoint=${manifest.entrypoint}\nmandatory_etymology=${manifest.invariants?.mandatory_etymology}\nnext=${manifest.current_state?.next_stage ?? 'see portable/PROJECT_STATE.md'}\n\nEngine card is unavailable until dependencies are installed.`);
}

async function createSession(name, extra = {}) {
  await ensureWorkspace();
  const baseId = `${stamp()}_${slugify(name)}`;
  let id = baseId;
  let dir = path.join(RUNS, id);
  let collision = 1;
  while (await exists(dir)) {
    id = `${baseId}_${collision}`;
    dir = path.join(RUNS, id);
    collision += 1;
  }
  await mkdir(path.join(dir, 'input'), { recursive: true });
  await mkdir(path.join(dir, '05-review'), { recursive: true });
  const pkg = await readJson(path.join(ROOT, 'package.json'));
  const meta = {
    studio_session_version: '1.0',
    session_id: id,
    created_at: nowIso(),
    project_version: pkg.version,
    status: 'CREATED',
    ...extra,
  };
  await writeJson(path.join(dir, 'run.json'), meta);
  await writeFile(path.join(dir, 'NOTES.md'), `# Notes — ${id}\n\n## Question\n\n\n## Observations\n\n\n## Resistant source spans\n\n\n## Operator mutations proposed\n\n\n## Reopening condition\n\n`, 'utf8');
  return { id, dir, meta };
}

async function updateSession(session, patch) {
  const file = path.join(session.dir, 'run.json');
  const current = await readJson(file);
  const next = { ...current, ...patch, updated_at: nowIso() };
  await writeJson(file, next);
  return next;
}

async function copyInput(source, destDir, preferredName) {
  const abs = path.resolve(source);
  const st = await stat(abs);
  if (!st.isFile()) throw new Error(`Input is not a regular file: ${source}`);
  const dest = path.join(destDir, preferredName || path.basename(abs));
  await copyFile(abs, dest);
  return dest;
}

async function cycleDocx(args) {
  const pos = positional(args, ['--job', '--seed', '--profile', '--provider', '--model']);
  if (pos.length !== 1) throw new Error('cycle:docx requires exactly one DOCX file.');
  const job = opt(args, '--job');
  if (!job) throw new Error('cycle:docx requires --job <job.json>.');
  const source = path.resolve(pos[0]);
  const seed = opt(args, '--seed') || `studio-${slugify(path.basename(source, path.extname(source)))}`;
  const profile = opt(args, '--profile');
  const provider = opt(args, '--provider');
  const model = opt(args, '--model');
  const allowTransfer = hasFlag(args, '--allow-external-source-transfer');
  const session = await createSession(path.basename(source, path.extname(source)), { mode: 'FULL_DOCX', seed, source_original: source, job_original: path.resolve(job) });
  const log = path.join(session.dir, 'COMMANDS.log');
  const localSource = await copyInput(source, path.join(session.dir, 'input'), 'source.docx');
  const localJob = await copyInput(job, path.join(session.dir, 'input'), 'job.json');
  let localProfile;
  if (profile) localProfile = await copyInput(profile, path.join(session.dir, 'input'), 'expert-profile.json');
  await updateSession(session, { status: 'RUNNING' });

  const page = path.join(session.dir, '01-page-run');
  const refinery = path.join(session.dir, '02-refinery');
  const living = path.join(session.dir, '03-living');
  const expert = path.join(session.dir, '04-expert');
  try {
    console.log(`\nSession: ${session.id}`);
    console.log('1/4 DOCX intake…');
    await runCore(['analyze-docx', localSource, '--job', localJob, '--out', page], { logFile: log });
    console.log('\n2/4 Corpus refinery…');
    await runCore(['refine-docx', localSource, '--job', localJob, '--page-run', page, '--out', refinery], { logFile: log });
    console.log('\n3/4 Living nonlinear cycle…');
    await runCore(['living-cycle', refinery, '--seed', seed, '--out', living], { logFile: log });
    console.log('\n4/4 Run-bound expert cycle…');
    const expertArgs = ['expert-cycle', refinery, '--out', expert, '--docx', localSource];
    if (localProfile) expertArgs.push('--profile', localProfile);
    if (provider) expertArgs.push('--provider', provider);
    if (model) expertArgs.push('--model', model);
    if (allowTransfer) expertArgs.push('--allow-external-source-transfer');
    await runCore(expertArgs, { logFile: log });
    await updateSession(session, { status: 'COMPLETE', outputs: { page, refinery, living, expert } });
    await writeFile(path.join(session.dir, 'STATUS.md'), `# Session complete\n\n- ID: \`${session.id}\`\n- Living: \`03-living/PHILOSOPHICAL_FIELD_NOTE.md\`\n- Living audit: \`03-living/LIVING_ANALYTICS.md\`\n- Expert: \`04-expert/FINAL_ANALYTICS.md\`\n- Notes: \`NOTES.md\`\n\nThe engine output is run-bound and does not establish philosophical truth or external validation.\n`, 'utf8');
    console.log(`\n✓ COMPLETE: ${session.dir}`);
  } catch (e) {
    await updateSession(session, { status: 'FAILED', error: e.message });
    await writeFile(path.join(session.dir, 'STATUS.md'), `# Session failed\n\n${e.message}\n\nSee \`COMMANDS.log\`.\n`, 'utf8');
    throw e;
  }
}

async function analyzeTextStudio(args) {
  const pos = positional(args);
  if (pos.length !== 1) throw new Error('analyze:text requires one .txt or .md source.');
  const source = path.resolve(pos[0]);
  const session = await createSession(path.basename(source, path.extname(source)), { mode: 'TEXT_CANDIDATES', source_original: source });
  const localSource = await copyInput(source, path.join(session.dir, 'input'));
  const out = path.join(session.dir, '01-analysis');
  const log = path.join(session.dir, 'COMMANDS.log');
  try {
    await updateSession(session, { status: 'RUNNING' });
    await runCore(['analyze', localSource, '--out', out], { logFile: log });
    await updateSession(session, { status: 'COMPLETE', outputs: { analysis: out } });
    console.log(`✓ COMPLETE: ${session.dir}`);
  } catch (e) { await updateSession(session, { status: 'FAILED', error: e.message }); throw e; }
}

async function livingStudio(args) {
  const pos = positional(args, ['--seed']);
  if (pos.length !== 1) throw new Error('run:living requires one refinery directory.');
  const refinery = path.resolve(pos[0]);
  const seed = opt(args, '--seed') || `studio-${Date.now()}`;
  const session = await createSession(`living-${path.basename(refinery)}`, { mode: 'LIVING_ONLY', refinery_original: refinery, seed });
  const out = path.join(session.dir, '03-living');
  await updateSession(session, { status: 'RUNNING' });
  try {
    await runCore(['living-cycle', refinery, '--seed', seed, '--out', out], { logFile: path.join(session.dir, 'COMMANDS.log') });
    await updateSession(session, { status: 'COMPLETE', outputs: { living: out } });
    console.log(`✓ COMPLETE: ${session.dir}`);
  } catch (e) { await updateSession(session, { status: 'FAILED', error: e.message }); throw e; }
}


async function livingDeclarativeStudio(args) {
  const pos = positional(args, ['--seed']);
  if (pos.length !== 1) throw new Error('run:living-declarative requires one refinery directory.');
  const refinery = path.resolve(pos[0]);
  const seed = opt(args, '--seed') || `studio-declarative-${Date.now()}`;
  const session = await createSession(`living-declarative-${path.basename(refinery)}`, { mode: 'LIVING_DECLARATIVE', refinery_original: refinery, seed });
  const out = path.join(session.dir, '03-living-declarative');
  await updateSession(session, { status: 'RUNNING' });
  try {
    await runCore(['living-cycle', refinery, '--registry', DECLARATIVE_OPERATOR_REGISTRY, '--seed', seed, '--out', out], { logFile: path.join(session.dir, 'COMMANDS.log') });
    await updateSession(session, { status: 'COMPLETE', outputs: { living_declarative: out }, operator_registry: DECLARATIVE_OPERATOR_REGISTRY });
    console.log(`✓ DECLARATIVE COMPLETE: ${session.dir}`);
  } catch (e) { await updateSession(session, { status: 'FAILED', error: e.message }); throw e; }
}



async function candidateReceipt(registryFile) {
  const dir = path.dirname(registryFile);
  const directReceipt = path.join(dir, 'mutation_receipt.json');
  const activation = path.join(dir, 'ACTIVATION.json');
  if (await exists(directReceipt)) {
    const receipt = await readJson(directReceipt);
    if (receipt?.decision?.promotion_ready !== true) throw new Error('Candidate registry is not promotion-ready according to mutation_receipt.json.');
    const registryObject = await readJson(registryFile);
    if (receipt.candidate_registry_sha256 && sha256(JSON.stringify(registryObject)) !== receipt.candidate_registry_sha256) throw new Error('Candidate registry canonical hash does not match mutation receipt.');
    return { source: directReceipt, receipt };
  }
  if (await exists(activation)) {
    const manifest = await readJson(activation);
    const bytes = await readFile(registryFile);
    if (manifest.registry_sha256 !== sha256(bytes)) throw new Error('Promoted registry hash does not match ACTIVATION.json.');
    if (manifest.promotion_ready !== true) throw new Error('ACTIVATION.json does not mark this registry promotion-ready.');
    return { source: activation, receipt: manifest };
  }
  throw new Error('Mutant living run requires a gated/promoted registry with mutation_receipt.json or ACTIVATION.json beside it.');
}

async function livingMutantStudio(args) {
  const pos = positional(args, ['--seed', '--registry']);
  if (pos.length !== 1) throw new Error('run:living-mutant requires one refinery directory.');
  const registryArg = opt(args, '--registry');
  if (!registryArg) throw new Error('run:living-mutant requires --registry <candidate.json>.');
  const refinery = path.resolve(pos[0]);
  const registry = path.resolve(registryArg);
  const receipt = await candidateReceipt(registry);
  const seed = opt(args, '--seed') || `studio-mutant-${Date.now()}`;
  const session = await createSession(`living-mutant-${path.basename(refinery)}`, {
    mode: 'LIVING_MUTANT', refinery_original: refinery, seed,
    operator_registry: registry, mutation_receipt: receipt.source,
  });
  const out = path.join(session.dir, '03-living-mutant');
  const localRegistryDir = path.join(session.dir, 'operator-registry');
  await mkdir(localRegistryDir, { recursive: true });
  const localRegistry = path.join(localRegistryDir, 'living_operator_registry.json');
  await copyFile(registry, localRegistry);
  await writeJson(path.join(localRegistryDir, 'MUTATION_CONTEXT.json'), {
    studio_mutation_context_version: '1.0',
    created_at: nowIso(),
    registry_original: registry,
    registry_sha256: sha256(await readFile(registry)),
    receipt_source: receipt.source,
    baseline_registry_sha256: sha256(await readFile(BASELINE_OPERATOR_REGISTRY)),
    injection_scope: 'THIS_LIVING_PROCESS_ONLY',
    baseline_registry_rewritten: false,
  });
  await updateSession(session, { status: 'RUNNING' });
  try {
    await runCore(['living-cycle', refinery, '--registry', localRegistry, '--seed', seed, '--out', out], {
      logFile: path.join(session.dir, 'COMMANDS.log'),
    });
    await updateSession(session, { status: 'COMPLETE', outputs: { living_mutant: out, operator_registry: localRegistry } });
    console.log(`✓ MUTANT COMPLETE: ${session.dir}`);
  } catch (e) { await updateSession(session, { status: 'FAILED', error: e.message }); throw e; }
}

async function livingMutantDeclarativeStudio(args) {
  const pos = positional(args, ['--seed', '--registry']);
  if (pos.length !== 1) throw new Error('run:living-mutant-declarative requires one refinery directory.');
  const registryArg = opt(args, '--registry');
  if (!registryArg) throw new Error('run:living-mutant-declarative requires --registry <candidate.json>.');
  const refinery = path.resolve(pos[0]);
  const registry = path.resolve(registryArg);
  const receipt = await candidateReceipt(registry);
  const registryObject = await readJson(registry);
  const compileErrors = validateDeclarativeGestures(registryObject);
  if (compileErrors.length) throw new Error(`Candidate declarative registry does not compile: ${compileErrors.join(' | ')}`);
  const seed = opt(args, '--seed') || `studio-mutant-declarative-${Date.now()}`;
  const session = await createSession(`living-mutant-declarative-${path.basename(refinery)}`, { mode: 'LIVING_MUTANT_DECLARATIVE', refinery_original: refinery, seed, operator_registry: registry, mutation_receipt: receipt.source });
  const out = path.join(session.dir, '03-living-mutant-declarative');
  const localRegistryDir = path.join(session.dir, 'operator-registry');
  await mkdir(localRegistryDir, { recursive: true });
  const localRegistry = path.join(localRegistryDir, 'living_operator_registry.declarative.json');
  await copyFile(registry, localRegistry);
  await writeJson(path.join(localRegistryDir, 'MUTATION_CONTEXT.json'), {
    studio_mutation_context_version: '1.1', created_at: nowIso(), registry_original: registry,
    registry_sha256: sha256(await readFile(registry)), receipt_source: receipt.source,
    historical_09_registry_sha256: sha256(await readFile(HISTORICAL_09_OPERATOR_REGISTRY)),
    frozen_010_registry_sha256: sha256(await readFile(DECLARATIVE_OPERATOR_REGISTRY)),
    injection_scope: 'THIS_DECLARATIVE_LIVING_PROCESS_ONLY', baseline_registry_rewritten: false,
  });
  await updateSession(session, { status: 'RUNNING' });
  try {
    await runCore(['living-cycle', refinery, '--registry', localRegistry, '--seed', seed, '--out', out], { logFile: path.join(session.dir, 'COMMANDS.log') });
    await updateSession(session, { status: 'COMPLETE', outputs: { living_mutant_declarative: out, operator_registry: localRegistry } });
    console.log(`✓ MUTANT DECLARATIVE COMPLETE: ${session.dir}`);
  } catch (e) { await updateSession(session, { status: 'FAILED', error: e.message }); throw e; }
}


async function compareLivingStudio(args) {
  const pos = positional(args, ['--seed', '--registry']);
  if (pos.length !== 1) throw new Error('compare:living requires one refinery directory.');
  const registryArg = opt(args, '--registry');
  if (!registryArg) throw new Error('compare:living requires --registry <accepted declarative candidate.json>.');
  const refinery = path.resolve(pos[0]);
  const registry = path.resolve(registryArg);
  const receipt = await candidateReceipt(registry);
  const registryObject = await readJson(registry);
  const compileErrors = validateDeclarativeGestures(registryObject);
  if (compileErrors.length) throw new Error(`Candidate declarative registry does not compile: ${compileErrors.join(' | ')}`);
  if (!String(registryObject.runtime_contract?.runtime ?? '').startsWith('DAE-LIVING-DECLARATIVE')) throw new Error('compare:living requires a DAE-LIVING-DECLARATIVE candidate registry.');
  const seed = opt(args, '--seed') || `studio-abc-${Date.now()}`;
  const session = await createSession(`living-abc-${path.basename(refinery)}`, {
    mode: 'LIVING_A_B_C_COMPARISON', refinery_original: refinery, seed,
    operator_registry: registry, mutation_receipt: receipt.source,
    comparison_contract: 'DAE-LIVING-COMPARISON-1.1-OPENSET',
  });
  const baselineOut = path.join(session.dir, '03-living-baseline');
  const declarativeOut = path.join(session.dir, '04-living-declarative');
  const mutantOut = path.join(session.dir, '05-living-mutant-declarative');
  const comparisonOut = path.join(session.dir, '06-comparison');
  const localRegistryDir = path.join(session.dir, 'operator-registry');
  const log = path.join(session.dir, 'COMMANDS.log');
  await mkdir(localRegistryDir, { recursive: true });
  await mkdir(comparisonOut, { recursive: true });
  const localRegistry = path.join(localRegistryDir, 'living_operator_registry.declarative.json');
  await copyFile(registry, localRegistry);
  await writeJson(path.join(localRegistryDir, 'MUTATION_CONTEXT.json'), {
    studio_mutation_context_version: '1.2', created_at: nowIso(), registry_original: registry,
    registry_sha256: sha256(await readFile(registry)), receipt_source: receipt.source,
    historical_09_registry_sha256: sha256(await readFile(HISTORICAL_09_OPERATOR_REGISTRY)),
    frozen_010_registry_sha256: sha256(await readFile(DECLARATIVE_OPERATOR_REGISTRY)),
    injection_scope: 'A_B_C_MUTANT_PROCESS_ONLY', baseline_registry_rewritten: false,
  });
  await updateSession(session, { status: 'RUNNING' });
  try {
    console.log(`\nA/B/C comparison session: ${session.id}`);
    console.log('1/4 Historical 0.9 registry control…');
    await runCore(['living-cycle', refinery, '--registry', HISTORICAL_09_OPERATOR_REGISTRY, '--seed', seed, '--out', baselineOut], { logFile: log });
    console.log('\n2/4 Frozen 0.10 open-set baseline…');
    await runCore(['living-cycle', refinery, '--registry', DECLARATIVE_OPERATOR_REGISTRY, '--seed', seed, '--out', declarativeOut], { logFile: log });
    console.log('\n3/4 Mutant 0.10 candidate…');
    await runCore(['living-cycle', refinery, '--registry', localRegistry, '--seed', seed, '--out', mutantOut], { logFile: log });
    console.log('\n4/4 Structural comparison…');
    const [baseline, declarative, mutant] = await Promise.all([
      readJson(path.join(baselineOut, 'living_analysis.json')),
      readJson(path.join(declarativeOut, 'living_analysis.json')),
      readJson(path.join(mutantOut, 'living_analysis.json')),
    ]);
    const comparison = compareLivingAnalyses({ baseline, declarative, mutant });
    if (!comparison.comparison_contract.same_seed_observed) throw new Error('A/B/C comparison control violated: outputs do not report the same seed.');
    await writeJson(path.join(comparisonOut, 'LIVING_COMPARISON.json'), comparison);
    await writeFile(path.join(comparisonOut, 'LIVING_COMPARISON.md'), renderLivingComparisonMarkdown(comparison), 'utf8');
    await updateSession(session, {
      status: 'COMPLETE',
      outputs: { living_baseline: baselineOut, living_declarative: declarativeOut, living_mutant_declarative: mutantOut, comparison: comparisonOut, operator_registry: localRegistry },
      comparison_summary: { mutation_effect_observed: comparison.mutation_effect_observed, structural_diversity: comparison.structural_diversity },
    });
    await writeFile(path.join(session.dir, 'STATUS.md'), `# A/B/C comparison complete\n\n- ID: \`${session.id}\`\n- Seed: \`${seed}\`\n- Baseline: \`03-living-baseline/\`\n- Declarative: \`04-living-declarative/\`\n- Mutant: \`05-living-mutant-declarative/\`\n- Comparison: \`06-comparison/LIVING_COMPARISON.md\`\n- Mutation effect observed: **${comparison.mutation_effect_observed}**\n- Structural diversity: **${comparison.structural_diversity}/3**\n\nStructural difference is not a philosophical truth score.\n`, 'utf8');
    console.log(`✓ A/B/C COMPLETE: ${session.dir}`);
    console.log(`mutation_effect_observed=${comparison.mutation_effect_observed} structural_diversity=${comparison.structural_diversity}/3`);
    return comparison;
  } catch (e) {
    await updateSession(session, { status: 'FAILED', error: e.message });
    await writeFile(path.join(session.dir, 'STATUS.md'), `# A/B/C comparison failed\n\n${e.message}\n\nSee \`COMMANDS.log\`.\n`, 'utf8');
    throw e;
  }
}


async function ecologyRegressionStudio(args) {
  const pos = positional(args, ['--out']);
  if (pos.length !== 1) throw new Error('ecology:regression requires one 0.9 micro-local ecology manifest.');
  const outArg = opt(args, '--out');
  if (!outArg) throw new Error('ecology:regression requires --out <new-directory>.');
  const manifest = path.resolve(pos[0]);
  const out = path.resolve(outArg);
  const engine = await createEngine();
  const result = await runMicroLocalOperatorEcology(engine, manifest, out);
  console.log(`MICRO-LOCAL REGRESSION  outcome=${result.result.outcome}`);
  console.log(`windows=${result.result.summary.windows} localization_loss=${result.result.summary.localization_loss_count} synthesis=${result.result.synthesis.decision}`);
  console.log(`report=${result.files.report}`);
  return result;
}


async function ecologyIndependentStudio(args) {
  const pos = positional(args, ['--out']);
  if (pos.length !== 1) throw new Error('ecology:independent requires one independent-family ecology manifest.');
  const outArg = opt(args, '--out');
  if (!outArg) throw new Error('ecology:independent requires --out <new-directory>.');
  const engine = await createEngine();
  const result = await runIndependentFamilyEcology(engine, path.resolve(pos[0]), path.resolve(outArg));
  console.log(`INDEPENDENT-FAMILY ECOLOGY  outcome=${result.result.outcome}`);
  console.log(`births=${result.result.summary.source_births_confirmed}/${result.result.summary.candidates} windows=${result.result.summary.expectations_passed}/${result.result.summary.expected_windows} synthesis=${result.result.synthesis.decision}`);
  console.log(`report=${result.files.report}`);
  return result;
}

async function ecologyDownstreamStudio(args) {
  const pos = positional(args, ['--out']);
  if (pos.length !== 1) throw new Error('ecology:downstream requires one independent-family micro_local_ecology_result.json.');
  const outArg = opt(args, '--out');
  if (!outArg) throw new Error('ecology:downstream requires --out <new-directory>.');
  const result = await runEcologyDownstream(path.resolve(pos[0]), path.resolve(outArg));
  console.log(`ECOLOGY DOWNSTREAM  outcome=${result.result.outcome}`);
  console.log(`windows=${result.result.summary.windows} residuals=${result.result.summary.local_residual_nodes} open_boundaries=${result.result.summary.open_boundaries} global_thesis=${result.result.summary.global_thesis_allowed}`);
  console.log(`report=${result.files.report}`);
  return result;
}

async function familyProbeStudio(args) {
  const pos = positional(args, ['--out', '--language']);
  if (pos.length !== 1) throw new Error('family:probe requires one DOCX source.');
  const outArg = opt(args, '--out');
  if (!outArg) throw new Error('family:probe requires --out <new-directory>.');
  const result = await runIndependentFamilyProbe(path.resolve(pos[0]), path.resolve(outArg), { documentLanguage: opt(args, '--language') ?? 'und' });
  const candidate = result.result.family_candidate;
  console.log(`INDEPENDENT-FAMILY PROBE  candidate=${candidate?.candidate ?? 'NONE'} status=${candidate?.status ?? 'NO_PROCESSUAL_FAMILY_PRESSURE'}`);
  console.log(`windows=${result.result.local_windows.length} output=${result.files.result}`);
  console.log('Claim ceiling: family probe only; source birth and promotion remain forbidden until independent validation.');
  return result;
}



async function validationHoldoutBuildStudio(args) {
  const pos = positional(args, ['--pipelines', '--out']);
  if (pos.length !== 1) throw new Error('validation:holdout-build requires one HOLDOUT_SOURCE_FREEZE.json.');
  const pipelines = opt(args, '--pipelines');
  const out = opt(args, '--out');
  if (!pipelines || !out) throw new Error('validation:holdout-build requires --pipelines <dir> and --out <new-directory>.');
  const result = await buildHoldoutArchitectureBenchmark(path.resolve(pos[0]), path.resolve(pipelines), path.resolve(out));
  console.log(`FROZEN HOLDOUT  benchmark=${result.manifest.benchmark_id} units=${result.manifest.unit_count} sources=${result.manifest.source_count}`);
  console.log(`status=SIZE_GATE_READY / BLOCKED_PENDING_INDEPENDENT_LABELS`);
  console.log(`predictions=${Object.entries(result.prediction_counts).map(([k,v]) => `${k}:${v}`).join(' ')}`);
  return result;
}

async function validationHoldoutAuditStudio(args) {
  const pos = positional(args);
  if (pos.length !== 1) throw new Error('validation:holdout-audit requires one benchmark directory.');
  const result = await auditHoldoutArchitectureBenchmark(path.resolve(pos[0]));
  console.log(`FROZEN HOLDOUT AUDIT  status=${result.status} units=${result.unit_count ?? 0} issues=${result.issues.length}`);
  if (result.issues.length) console.log(result.issues.join('\n'));
  return result;
}

async function validationInitStudio(args) {
  const pos = positional(args, ['--out']);
  if (pos.length !== 1) throw new Error('validation:init requires one CORE benchmark directory.');
  const out = opt(args, '--out');
  if (!out) throw new Error('validation:init requires --out <new-campaign-directory>.');
  const result = await initExternalValidationCampaign(path.resolve(pos[0]), path.resolve(out));
  console.log(`EXTERNAL VALIDATION  campaign=${result.campaign.campaign_id} status=${result.status}`);
  console.log(`template system=${path.join(result.output_dir, 'templates', 'external_system.template.json')}`);
  console.log(`template challenge=${path.join(result.output_dir, 'templates', 'semantic_challenge.template.json')}`);
  return result;
}

async function validationFreezeStudio(args) {
  const pos = positional(args, ['--system', '--challenge']);
  if (pos.length !== 1) throw new Error('validation:freeze requires one campaign directory.');
  const systems = valuesForFlag(args, '--system').map((file) => path.resolve(file));
  const challenge = opt(args, '--challenge');
  if (!systems.length) throw new Error('validation:freeze requires at least one --system <predictions.json>.');
  if (!challenge) throw new Error('validation:freeze requires --challenge <semantic_challenge.json>.');
  const result = await freezeExternalValidationCampaign(path.resolve(pos[0]), systems, path.resolve(challenge));
  console.log(`EXTERNAL VALIDATION FROZEN  campaign=${result.campaign.campaign_id} systems=${result.freeze.systems.length} cases=${result.freeze.semantic_challenge.case_count}`);
  console.log('Claim ceiling: local pre-gold fixity lock; not public preregistration or proof of human independence.');
  return result;
}

async function validationEvaluateStudio(args) {
  const pos = positional(args, ['--gold', '--core-result', '--adversarial', '--out']);
  if (pos.length !== 1) throw new Error('validation:evaluate requires one campaign directory.');
  const gold = opt(args, '--gold');
  const coreResult = opt(args, '--core-result');
  const out = opt(args, '--out');
  if (!gold || !coreResult || !out) throw new Error('validation:evaluate requires --gold <gold.json>, --core-result <BENCHMARK_RESULT.json> and --out <new-directory>.');
  const adversarial = valuesForFlag(args, '--adversarial').map((file) => path.resolve(file));
  const result = await evaluateExternalValidationCampaign(path.resolve(pos[0]), path.resolve(gold), adversarial, path.resolve(out), { coreBenchmarkResultFile: path.resolve(coreResult) });
  console.log(`EXTERNAL VALIDATION RESULT  outcome=${result.outcome}`);
  console.log(`pareto=${result.pareto_front.join(',') || 'none'} issues=${result.issues.length}`);
  console.log(`report=${path.join(path.resolve(out), 'EXTERNAL_VALIDATION_REPORT.md')}`);
  return result;
}

async function validationStatusStudio(args) {
  const pos = positional(args);
  if (pos.length !== 1) throw new Error('validation:status requires one campaign directory.');
  const result = await externalValidationStatus(path.resolve(pos[0]));
  console.log(JSON.stringify(result, null, 2));
  return result;
}

async function expertStudio(args) {
  const pos = positional(args, ['--profile', '--provider', '--model']);
  if (pos.length !== 1) throw new Error('run:expert requires one refinery directory.');
  const refinery = path.resolve(pos[0]);
  const profile = opt(args, '--profile');
  const provider = opt(args, '--provider');
  const model = opt(args, '--model');
  const session = await createSession(`expert-${path.basename(refinery)}`, { mode: 'EXPERT_ONLY', refinery_original: refinery });
  const out = path.join(session.dir, '04-expert');
  const coreArgs = ['expert-cycle', refinery, '--out', out];
  if (profile) coreArgs.push('--profile', path.resolve(profile));
  if (provider) coreArgs.push('--provider', provider);
  if (model) coreArgs.push('--model', model);
  if (hasFlag(args, '--allow-external-source-transfer')) coreArgs.push('--allow-external-source-transfer');
  await updateSession(session, { status: 'RUNNING' });
  try {
    await runCore(coreArgs, { logFile: path.join(session.dir, 'COMMANDS.log') });
    await updateSession(session, { status: 'COMPLETE', outputs: { expert: out } });
    console.log(`✓ COMPLETE: ${session.dir}`);
  } catch (e) { await updateSession(session, { status: 'FAILED', error: e.message }); throw e; }
}

async function experimentNew(name) {
  if (!name) throw new Error('experiment:new requires a name.');
  await ensureWorkspace();
  const slug = slugify(name);
  const dir = path.join(EXPERIMENTS, `${stamp()}_${slug}`);
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, 'README.md'), `# Experiment — ${name}\n\n## Research question\n\n\n## Source boundary\n\n\n## Competing reconstructions\n\n### A\n\n\n### B\n\n\n## Discriminator\n\n\n## Expected gain (GG1–GG7)\n\n\n## Failure condition\n\n\n## Result\n\n`, 'utf8');
  await writeJson(path.join(dir, 'experiment.json'), {
    studio_experiment_version: '1.0', created_at: nowIso(), name, status: 'PLANNED',
    principle: 'Discovery does not equal justification; resistant material may alter the operator.',
    source_spans: [], competing_unitizations: [], operator_candidates: [], gains: [], reopening_condition: null,
  });
  console.log(`Created: ${dir}`);
}

async function deltaNew(name) {
  if (!name) throw new Error('delta:new requires a name.');
  await ensureWorkspace();
  const slug = slugify(name);
  const dir = path.join(DELTAS, `${stamp()}_${slug}`);
  await mkdir(dir, { recursive: true });
  const deltaId = `DELTA-${slugify(name).replace(/[^a-z0-9._-]/g, '-').toUpperCase()}-${Date.now().toString(36).toUpperCase()}`;
  await writeJson(path.join(dir, 'operator_delta.json'), {
    operator_delta_version: 'DAE-OPERATOR-DELTA-1.0',
    delta_id: deltaId,
    created_at: nowIso(),
    name,
    status: 'DRAFT',
    resistant_source: { source_id: '', selector: '', span_sha256: null, why_resistant: '' },
    incompatible_unitizations: [
      { unitization_id: 'U-A', description: '', analytic_consequence: '' },
      { unitization_id: 'U-B', description: '', analytic_consequence: '' },
    ],
    target: { registry_section: 'conditional_families', operator_id: '' },
    observed_failure: { failure_type: 'RIVAL_UNITIZATION_COLLAPSE', description: '', lost_distinction: '' },
    mutation: {
      kind: 'SPLIT', proposal: '', cost: '', reversibility: '',
      variants: [
        { new_id: '', changes: {}, unitization_refs: ['U-A'] },
        { new_id: '', changes: {}, unitization_refs: ['U-B'] },
      ],
    },
    before_after_test: {
      fixture: { source_id: '', selector: '', same_material: true, probe_text: '' },
      before_observation: '', after_observation: '',
      new_gains: ['GG1_NEW_DISTINCTION'], discriminator: '',
      traceability: { before_routes: 1, after_routes: 1 },
      negative_tests: [{ name: 'Baseline negative case', passed: false, note: 'Set true only after the test actually passes.' }],
    },
    acceptance_gate: {
      new_distinction_required: true,
      source_traceability_must_not_degrade: true,
      negative_tests_must_not_regress: true,
    },
  });
  await writeFile(path.join(dir, 'README.md'), `# Operator delta — ${name}\n\nThis is an executable RESISTANT-SOURCE / OPERATOR-MUTATION contract.\n\nThe delta is not accepted because it exists. Fill the resistant source, two incompatible unitizations, target operator, explicit failure, reversible mutation and same-material before/after test. Then run:\n\n\`\`\`bash\nnode studio/studio.mjs delta:gate "${path.join(dir, 'operator_delta.json')}"\n\`\`\`\n\nIf the gate returns ACCEPTED_CANDIDATE, promote it to the candidate library with \`delta:promote\`. The baseline registry is never overwritten.\n`, 'utf8');
  console.log(`Created: ${dir}`);
}

async function deltaGate(args) {
  const pos = positional(args, ['--out', '--registry']);
  if (pos.length !== 1) throw new Error('delta:gate requires one operator_delta.json.');
  const deltaFile = path.resolve(pos[0]);
  const outArg = opt(args, '--out');
  const registryArg = opt(args, '--registry');
  const gateRegistry = registryArg ? path.resolve(registryArg) : DECLARATIVE_OPERATOR_REGISTRY;
  const out = outArg ? path.resolve(outArg) : path.join(path.dirname(deltaFile), `gate-${stamp()}`);
  const result = await gateOperatorDelta(deltaFile, gateRegistry, MUTATION_POLICY, out);
  console.log(`Mutation gate: ${result.receipt.decision.decision}`);
  console.log(`promotion_ready=${result.receipt.decision.promotion_ready} runtime_reachability=${result.receipt.runtime_reachability}`);
  console.log(`registry=${gateRegistry}`);
  console.log(`output=${out}`);
  for (const i of result.receipt.issues) console.log(`${i.severity.padEnd(6)} ${i.code}: ${i.message}`);
  return result;
}

async function deltaPromote(args) {
  if (args.length !== 1) throw new Error('delta:promote requires one gate-output directory.');
  await ensureWorkspace();
  const gateDir = path.resolve(args[0]);
  const receiptFile = path.join(gateDir, 'mutation_receipt.json');
  const candidateFile = path.join(gateDir, 'candidate_living_operator_registry.json');
  if (!(await exists(receiptFile)) || !(await exists(candidateFile))) throw new Error('Gate output must contain mutation_receipt.json and candidate_living_operator_registry.json.');
  const receipt = await readJson(receiptFile);
  const gatedDeltaFile = path.join(gateDir, 'operator_delta.gated.json');
  const gatedDelta = await exists(gatedDeltaFile) ? await readJson(gatedDeltaFile) : null;
  const openSetBirth = gatedDelta?.mutation?.kind === 'ADD_OPERATOR';
  if (receipt?.decision?.promotion_ready !== true) throw new Error(`Delta is not promotion-ready: ${receipt?.decision?.decision ?? 'UNKNOWN'}.`);
  const candidateBytes = await readFile(candidateFile);
  const candidateObject = JSON.parse(candidateBytes.toString('utf8'));
  if (sha256(JSON.stringify(candidateObject)) !== receipt.candidate_registry_sha256) throw new Error('Candidate registry canonical hash mismatch against mutation receipt.');
  const slug = slugify(receipt.delta_id || 'candidate');
  const dir = path.join(OPERATOR_REGISTRIES, `${stamp()}_${slug}`);
  await mkdir(dir, { recursive: false });
  const promoted = path.join(dir, 'living_operator_registry.json');
  await copyFile(candidateFile, promoted);
  await copyFile(receiptFile, path.join(dir, 'mutation_receipt.json'));
  if (await exists(path.join(gateDir, 'rollback_target.json'))) await copyFile(path.join(gateDir, 'rollback_target.json'), path.join(dir, 'rollback_target.json'));
  await writeJson(path.join(dir, 'ACTIVATION.json'), {
    studio_operator_activation_version: '1.0',
    created_at: nowIso(),
    delta_id: receipt.delta_id,
    promotion_ready: true,
    registry_sha256: sha256(candidateBytes),
    baseline_registry_sha256: receipt.baseline_registry_sha256,
    activation_scope: 'SESSION_PROCESS_ONLY',
    baseline_registry_rewritten: false,
    rollback_file: 'rollback_target.json',
    runtime_contract: candidateObject.runtime_contract?.runtime ?? 'BASELINE_OR_UNKNOWN',
    open_set_semantic_review: openSetBirth ? {
      status: 'REQUIRED_BEFORE_ANY_CORE_OR_UNIVERSALIZATION_CLAIM',
      reason: '0.10 open-set birth is recurrence/co-occurrence based and can self-confirm on negation, quotation, attribution or lexical decoys.',
      required_axes: ['PREDICATE_AND_POLARITY', 'ATTRIBUTION_AND_QUOTED_OPPONENT', 'MODALITY', 'ARGUMENTATIVE_ROLE', 'PARAPHRASE_OR_TRANSLATION_PERTURBATION', 'DECOY_TERMINOLOGY_NEGATIVE_CONTROL'],
      candidate_may_run_experimentally: true,
      candidate_is_not_core: true,
    } : null,
  });
  console.log(`Promoted candidate: ${dir}`);
  if (openSetBirth) console.log('Open-set semantic review: REQUIRED before any CORE/universalization claim; experimental execution remains allowed.');
  const runCommand = String(candidateObject.runtime_contract?.runtime ?? '').startsWith('DAE-LIVING-DECLARATIVE') ? 'run:living-mutant-declarative' : 'run:living-mutant';
  console.log(`Run experimentally with: node studio/studio.mjs ${runCommand} <refinery-dir> --registry "${promoted}"`);
  return dir;
}


async function findLivingAnalysisFiles(inputPath, depth = 0) {
  const resolved = path.resolve(inputPath);
  const info = await stat(resolved);
  if (info.isFile()) {
    if (path.basename(resolved).toLowerCase() !== 'living_analysis.json') {
      try {
        const parsed = await readJson(resolved);
        if (parsed?.graph?.nodes && parsed?.constellations && parsed?.source?.source_id) return [resolved];
      } catch {}
      throw new Error(`Not a living analysis JSON: ${resolved}`);
    }
    return [resolved];
  }
  if (!info.isDirectory()) throw new Error(`Unsupported discovery input: ${resolved}`);
  if (depth > 8) return [];
  const direct = path.join(resolved, 'living_analysis.json');
  if (await exists(direct)) return [direct];
  const found = [];
  for (const entry of await readdir(resolved, { withFileTypes: true })) {
    if (!entry.isDirectory() || ['node_modules', '.git'].includes(entry.name)) continue;
    found.push(...await findLivingAnalysisFiles(path.join(resolved, entry.name), depth + 1));
  }
  return found;
}

function positiveInteger(value, fallback, name) {
  if (value === undefined) return fallback;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${name} must be a positive integer.`);
  return parsed;
}

async function resistanceDiscoveryStudio(args) {
  const flags = ['--registry', '--min-support', '--min-resistance', '--min-unitizations'];
  const inputs = positional(args, flags);
  if (!inputs.length) throw new Error('discover:resistance requires at least one living_analysis.json file or directory.');
  const registryPath = path.resolve(opt(args, '--registry') || DECLARATIVE_OPERATOR_REGISTRY);
  const registry = await readJson(registryPath);
  const compileErrors = String(registry.runtime_contract?.runtime ?? '').startsWith('DAE-LIVING-DECLARATIVE') ? validateDeclarativeGestures(registry) : [];
  if (compileErrors.length) throw new Error(`Discovery reference registry does not compile: ${compileErrors.join(' | ')}`);
  const files = [...new Set((await Promise.all(inputs.map(input => findLivingAnalysisFiles(input)))).flat())].sort();
  if (!files.length) throw new Error('No living_analysis.json files were found under the supplied inputs.');
  const analyses = await Promise.all(files.map(readJson));
  const policy = {
    min_analysis_support: positiveInteger(opt(args, '--min-support'), 2, '--min-support'),
    min_resistance_runs: positiveInteger(opt(args, '--min-resistance'), 2, '--min-resistance'),
    min_distinct_unitizations: positiveInteger(opt(args, '--min-unitizations'), 2, '--min-unitizations'),
  };
  const report = discoverResistance({ analyses, registry, policy });
  const session = await createSession(`resistance-discovery-${analyses[0]?.source?.source_id || 'mixed'}`, {
    mode: 'RESISTANT_SOURCE_DISCOVERY',
    discovery_contract: report.resistance_discovery_version,
    analysis_inputs: files,
    registry_reference: registryPath,
    registry_sha256: sha256(await readFile(registryPath)),
    promotion_from_discovery_forbidden: true,
  });
  const out = path.join(session.dir, '07-resistance-discovery');
  const casesDir = path.join(out, 'cases');
  await mkdir(casesDir, { recursive: true });
  await writeJson(path.join(out, 'RESISTANCE_DISCOVERY.json'), report);
  await writeFile(path.join(out, 'RESISTANCE_DISCOVERY.md'), renderResistanceDiscoveryMarkdown(report), 'utf8');
  const inputManifest = [];
  for (const file of files) {
    const bytes = await readFile(file);
    const analysis = JSON.parse(bytes.toString('utf8'));
    inputManifest.push({
      path: file,
      sha256: sha256(bytes),
      run_id: analysis.run_id ?? null,
      source_id: analysis.source?.source_id ?? null,
      seed: analysis.seed ?? null,
      runtime: analysis.operator_registry?.runtime ?? null,
    });
  }
  await writeJson(path.join(out, 'DISCOVERY_INPUTS.json'), {
    discovery_input_manifest_version: 'DAE-RESISTANCE-DISCOVERY-INPUTS-1.0',
    created_at: nowIso(), registry_reference: registryPath,
    registry_sha256: sha256(await readFile(registryPath)), inputs: inputManifest,
  });
  for (const c of report.cases) {
    const caseDir = path.join(casesDir, c.case_id);
    await mkdir(caseDir, { recursive: true });
    await writeJson(path.join(caseDir, 'case.json'), c);
    await writeJson(path.join(caseDir, 'operator_delta_seed.json'), c.operator_delta_seed);
    await writeFile(path.join(caseDir, 'README.md'), `# ${c.case_id}\n\n- Source: \`${c.source_id}\`\n- Selector: \`${c.selector}\`\n- Status: **${c.status}**\n- Suggested target: ${c.target_hypothesis ? `\`${c.target_hypothesis.registry_section}/${c.target_hypothesis.operator_id}\`` : 'unresolved'}\n\nThe generated \`operator_delta_seed.json\` is deliberately non-gateable and has \`promotion_forbidden=true\`. Inspect the source span, author executable mutation variants, provide a source-grounded discriminator, then create a real operator_delta and use \`delta:gate\`.\n`, 'utf8');
  }
  const existingLedger = await exists(DISCOVERY_LEDGER) ? await readJson(DISCOVERY_LEDGER) : null;
  const ledger = mergeDiscoveryLedger(existingLedger, report, { session_id: session.id, generated_at: nowIso() });
  await writeJson(DISCOVERY_LEDGER, ledger);
  await writeFile(DISCOVERY_LEDGER_MD, renderDiscoveryLedgerMarkdown(ledger), 'utf8');
  for (const c of report.cases) {
    const persistentCaseDir = path.join(DISCOVERY_CASES, c.case_id);
    await mkdir(persistentCaseDir, { recursive: true });
    await writeJson(path.join(persistentCaseDir, 'history.json'), ledger.cases[c.case_id]);
    await writeJson(path.join(persistentCaseDir, 'latest_operator_delta_seed.json'), c.operator_delta_seed);
  }
  await updateSession(session, {
    status: 'COMPLETE',
    outputs: { resistance_discovery: out, discovery_ledger: DISCOVERY_LEDGER },
    discovery_summary: report.summary,
    longitudinal_summary: { recurring_case_count: ledger.recurring_case_count, case_count: ledger.case_count },
  });
  await writeFile(path.join(session.dir, 'STATUS.md'), `# Resistant-source discovery complete\n\n- Inputs: **${files.length}** living analyses\n- Cases: **${report.summary.resistant_cases}**\n- Output: \`07-resistance-discovery/RESISTANCE_DISCOVERY.md\`\n- Promotion from discovery: **FORBIDDEN**\n\nDiscovery detects structural recurrence only. Source semantics and operator validity remain review-bound.\n`, 'utf8');
  console.log(`✓ DISCOVERY COMPLETE: ${session.dir}`);
  console.log(`  analyses=${files.length} cases=${report.summary.resistant_cases}`);
  if (report.summary.cases_cross_runtime_only) console.log(`  review: ${report.summary.cases_cross_runtime_only} case(s) are cross-runtime-only on one seed and need independent reproduction.`);
  return { session, report };
}

async function discoveryHistory() {
  if (!(await exists(DISCOVERY_LEDGER))) { console.log('No resistant-source discovery history yet.'); return; }
  const ledger = await readJson(DISCOVERY_LEDGER);
  console.log(renderDiscoveryLedgerMarkdown(ledger));
}

async function collectFiles(dir, rel = '') {
  const out = [];
  const entries = await readdir(path.join(dir, rel), { withFileTypes: true });
  for (const entry of entries) {
    const r = path.join(rel, entry.name);
    const posix = r.split(path.sep).join('/');
    if (entry.isDirectory()) {
      if (['node_modules', 'workspace', '.git'].includes(entry.name)) continue;
      out.push(...await collectFiles(dir, r));
    } else if (entry.isFile()) out.push(posix);
  }
  return out;
}

async function snapshot(label = 'snapshot') {
  await ensureWorkspace();
  const scopes = ['src', 'config', 'schemas', 'portable', 'docs', 'bin', 'studio', 'mutation', 'discovery', 'development'];
  let files = ['package.json', 'PORTABLE_PROJECT.json', 'PORTABLE_CHAT_PROJECT.md', '00_START_HERE.md', 'AGENTS.md'];
  for (const scope of scopes) if (await exists(path.join(ROOT, scope))) files.push(...await collectFiles(ROOT, scope));
  files = [...new Set(files)].sort();
  const assets = [];
  const treeHash = createHash('sha256');
  for (const rel of files) {
    const bytes = await readFile(path.join(ROOT, rel));
    const digest = sha256(bytes);
    assets.push({ path: rel, size_bytes: bytes.length, sha256: digest });
    treeHash.update(rel); treeHash.update('\0'); treeHash.update(digest); treeHash.update('\n');
  }
  const data = { studio_snapshot_version: '1.0', created_at: nowIso(), label, project_root: '.', file_count: assets.length, tree_sha256: treeHash.digest('hex'), assets };
  const target = path.join(SNAPSHOTS, `${stamp()}_${slugify(label)}.json`);
  await writeJson(target, data);
  console.log(`Snapshot: ${target}\nfiles=${data.file_count} tree_sha256=${data.tree_sha256}`);
  return target;
}

async function status() {
  await ensureWorkspace();
  const entries = (await readdir(RUNS, { withFileTypes: true })).filter(e => e.isDirectory()).map(e => e.name).sort().reverse();
  if (!entries.length) { console.log('No Studio runs yet.'); return; }
  console.log('Recent Studio runs:');
  for (const name of entries.slice(0, 20)) {
    try {
      const meta = await readJson(path.join(RUNS, name, 'run.json'));
      console.log(`${String(meta.status || 'UNKNOWN').padEnd(10)} ${name}  ${meta.mode || ''}`);
    } catch { console.log(`UNKNOWN    ${name}`); }
  }
}

async function interactive() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    console.log('\nDestruktion Studio 0.9 — Frozen Holdout Benchmark');
    console.log('1. Doctor / integrity check');
    console.log('2. Project card');
    console.log('3. New empty research session');
    console.log('4. Full DOCX cycle');
    console.log('5. Living cycle — frozen 0.10 open-set baseline');
    console.log('6. Living cycle — explicit declarative 0.10 registry');
    console.log('7. Living cycle — declarative accepted mutant');
    console.log('8. Living cycle — legacy mutant registry');
    console.log('9. A/B/C compare historical 0.9 → frozen 0.10 → mutant');
    console.log('10. Discover recurrent resistant-source patterns');
    console.log('11. Resistant-source recurrence history');
    console.log('12. Expert cycle from refinery');
    console.log('13. New experiment scaffold');
    console.log('14. New operator-delta contract');
    console.log('15. Gate operator delta (declarative registry by default)');
    console.log('16. Promote accepted candidate registry');
    console.log('17. Snapshot development surface');
    console.log('18. Recent run status');
    console.log('19. Cross-corpus operator regression');
    console.log('20. Local operator competition');
    console.log('21. Open-set micro-local routing (0.10)');
    console.log('22. Localization-loss micro-local regression (0.9 preserved)');
    console.log('23. Independent-family micro-local ecology (0.10 regression oracle)');
    console.log('24. Ecology downstream polyphony-preserving adapter');
    console.log('25. Independent interrogative-family probe');
    console.log('26. External validation — initialize campaign');
    console.log('27. External validation — freeze strong baselines + challenge');
    console.log('28. External validation — evaluate against gold + adversarial results');
    console.log('29. External validation — campaign status');
    console.log('0. Exit');
    const choice = (await rl.question('\nSelect: ')).trim();
    if (choice === '1') return doctor();
    if (choice === '2') return projectCard();
    if (choice === '3') return createSession(await rl.question('Session name: ')).then(s => console.log(`Created: ${s.dir}`));
    if (choice === '4') {
      const source = await rl.question('DOCX path: '); const job = await rl.question('Job JSON path: '); const seed = await rl.question('Seed (blank = automatic): ');
      const a = [source, '--job', job]; if (seed.trim()) a.push('--seed', seed.trim()); return cycleDocx(a);
    }
    if (choice === '5') { const r = await rl.question('Refinery directory: '); const seed = await rl.question('Seed (blank = automatic): '); const a=[r]; if(seed.trim()) a.push('--seed',seed.trim()); return livingStudio(a); }
    if (choice === '6') { const r = await rl.question('Refinery directory: '); const seed = await rl.question('Seed (blank = automatic): '); const a=[r]; if(seed.trim()) a.push('--seed',seed.trim()); return livingDeclarativeStudio(a); }
    if (choice === '7') { const r = await rl.question('Refinery directory: '); const reg = await rl.question('Accepted declarative candidate registry JSON: '); const seed = await rl.question('Seed (blank = automatic): '); const a=[r,'--registry',reg]; if(seed.trim()) a.push('--seed',seed.trim()); return livingMutantDeclarativeStudio(a); }
    if (choice === '8') { const r = await rl.question('Refinery directory: '); const reg = await rl.question('Accepted legacy candidate registry JSON: '); const seed = await rl.question('Seed (blank = automatic): '); const a=[r,'--registry',reg]; if(seed.trim()) a.push('--seed',seed.trim()); return livingMutantStudio(a); }
    if (choice === '9') { const r = await rl.question('Refinery directory: '); const reg = await rl.question('Accepted declarative candidate registry JSON: '); const seed = await rl.question('Shared seed (blank = automatic): '); const a=[r,'--registry',reg]; if(seed.trim()) a.push('--seed',seed.trim()); return compareLivingStudio(a); }
    if (choice === '10') { const paths = await rl.question('Living analysis files/directories (semicolon-separated): '); const reg = await rl.question('Reference registry JSON (blank = declarative baseline): '); const a=paths.split(';').map(x=>x.trim()).filter(Boolean); if(reg.trim()) a.push('--registry',reg.trim()); return resistanceDiscoveryStudio(a); }
    if (choice === '11') return discoveryHistory();
    if (choice === '12') { const r = await rl.question('Refinery directory: '); const p = await rl.question('Profile JSON (blank = automatic): '); const a=[r]; if(p.trim()) a.push('--profile',p.trim()); return expertStudio(a); }
    if (choice === '13') return experimentNew(await rl.question('Experiment name: '));
    if (choice === '14') return deltaNew(await rl.question('Delta name: '));
    if (choice === '15') { const f = await rl.question('operator_delta.json path: '); const reg = await rl.question('Registry JSON (blank = declarative baseline): '); const a=[f]; if(reg.trim()) a.push('--registry',reg.trim()); return deltaGate(a); }
    if (choice === '16') { const d = await rl.question('Gate output directory: '); return deltaPromote([d]); }
    if (choice === '17') return snapshot((await rl.question('Snapshot label: ')).trim() || 'manual');
    if (choice === '18') return status();
    if (choice === '19') { const m = await rl.question('Regression manifest JSON: '); const o = await rl.question('Output directory: '); return runCore(['operator-regression',m,'--out',o]); }
    if (choice === '20') { const m = await rl.question('Competition manifest JSON: '); const o = await rl.question('Output directory: '); return runCore(['operator-competition',m,'--out',o]); }
    if (choice === '21') { const m = await rl.question('Hypothesis bank JSON: '); const o = await rl.question('Output directory: '); return runCore(['micro-local-ecology',m,'--out',o]); }
    if (choice === '22') { const m = await rl.question('0.9 micro-local regression manifest JSON: '); const o = await rl.question('Output directory: '); return ecologyRegressionStudio([m,'--out',o]); }
    if (choice === '23') { const m = await rl.question('Independent-family ecology manifest JSON: '); const o = await rl.question('Output directory: '); return ecologyIndependentStudio([m,'--out',o]); }
    if (choice === '24') { const m = await rl.question('Independent-family ecology result JSON: '); const o = await rl.question('Output directory: '); return ecologyDownstreamStudio([m,'--out',o]); }
    if (choice === '25') { const f = await rl.question('DOCX source: '); const o = await rl.question('Output directory: '); return familyProbeStudio([f,'--out',o]); }
    if (choice === '26') { const b = await rl.question('CORE benchmark directory: '); const o = await rl.question('Campaign output directory: '); return validationInitStudio([b,'--out',o]); }
    if (choice === '27') { const c = await rl.question('Campaign directory: '); const ss = await rl.question('External system prediction JSON files (semicolon-separated): '); const ch = await rl.question('Semantic challenge JSON: '); const a=[c]; for (const f of ss.split(';').map(x=>x.trim()).filter(Boolean)) a.push('--system',f); a.push('--challenge',ch); return validationFreezeStudio(a); }
    if (choice === '28') { const c = await rl.question('Campaign directory: '); const g = await rl.question('Adjudicated gold JSON: '); const cr = await rl.question('CORE BENCHMARK_RESULT.json: '); const aa = await rl.question('Adversarial result JSON files (semicolon-separated): '); const o = await rl.question('Evaluation output directory: '); const a=[c,'--gold',g,'--core-result',cr]; for (const f of aa.split(';').map(x=>x.trim()).filter(Boolean)) a.push('--adversarial',f); a.push('--out',o); return validationEvaluateStudio(a); }
    if (choice === '29') { const c = await rl.question('Campaign directory: '); return validationStatusStudio([c]); }
    if (choice === '0') return;
    console.log('Unknown selection.');
  } finally { rl.close(); }
}

async function main(argv) {
  await ensureWorkspace();
  const [command, ...args] = argv;
  if (!command) return interactive();
  if (['help', '--help', '-h'].includes(command)) { console.log(HELP); return; }
  if (command === 'doctor') return doctor();
  if (command === 'setup') return setup();
  if (command === 'card') return projectCard();
  if (command === 'status') return status();
  if (command === 'session:new') { const s = await createSession(args.join(' ') || 'session'); console.log(`Created: ${s.dir}`); return; }
  if (command === 'cycle:docx') return cycleDocx(args);
  if (command === 'analyze:text') return analyzeTextStudio(args);
  if (command === 'run:living') return livingStudio(args);
  if (command === 'run:living-declarative') return livingDeclarativeStudio(args);
  if (command === 'run:living-mutant') return livingMutantStudio(args);
  if (command === 'run:living-mutant-declarative') return livingMutantDeclarativeStudio(args);
  if (command === 'compare:living') return compareLivingStudio(args);
  if (command === 'discover:resistance') return resistanceDiscoveryStudio(args);
  if (command === 'discover:history') return discoveryHistory();
  if (command === 'regress:operator') return runCore(['operator-regression', ...args]);
  if (command === 'compete:operators') return runCore(['operator-competition', ...args]);
  if (command === 'ecology:open-set' || command === 'ecology:micro') return runCore(['micro-local-ecology', ...args]);
  if (command === 'ecology:regression') return ecologyRegressionStudio(args);
  if (command === 'ecology:independent') return ecologyIndependentStudio(args);
  if (command === 'ecology:downstream') return ecologyDownstreamStudio(args);
  if (command === 'family:probe') return familyProbeStudio(args);
  if (command === 'validation:init') return validationInitStudio(args);
  if (command === 'validation:freeze') return validationFreezeStudio(args);
  if (command === 'validation:evaluate') return validationEvaluateStudio(args);
  if (command === 'validation:status') return validationStatusStudio(args);
  if (command === 'validation:holdout-build') return validationHoldoutBuildStudio(args);
  if (command === 'validation:holdout-audit') return validationHoldoutAuditStudio(args);
  if (command === 'run:expert') return expertStudio(args);
  if (command === 'experiment:new') return experimentNew(args.join(' '));
  if (command === 'delta:new') return deltaNew(args.join(' '));
  if (command === 'delta:gate') return deltaGate(args);
  if (command === 'delta:promote') return deltaPromote(args);
  if (command === 'snapshot') return snapshot(args.join(' ') || 'manual');
  if (command === 'core') return runCore(args);
  throw new Error(`Unknown Studio command '${command}'.\n\n${HELP}`);
}

main(process.argv.slice(2)).catch(error => {
  console.error(`STUDIO FATAL: ${error.stack || error.message}`);
  process.exitCode = 2;
});
