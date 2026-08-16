import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { validateDeclarativeGestures } from '../src/generative-gesture-runtime.mjs';

const GG = new Set([
  'GG1_NEW_DISTINCTION', 'GG2_NEW_RELATION', 'GG2_NEW_QUESTION', 'GG3_NEW_RIVAL',
  'GG4_NEW_TEST', 'GG4_REVERSAL', 'GG5_NEW_RESIDUAL', 'GG5_NEW_PHENOMENON', 'GG6_NEW_RESEARCH_BRANCH', 'GG6_BRANCH_PRODUCTIVITY', 'GG7_OPERATOR_EVOLUTION',
]);
const KINDS = new Set(['SUSPEND', 'SPLIT', 'REVISE', 'ADD_CONDITION', 'ADD_OPERATOR']);
const SECTIONS = new Set(['generative_gestures', 'supporting_operation_vocabulary', 'conditional_families']);
const ID_FIELD = {
  generative_gestures: 'gesture_id',
  supporting_operation_vocabulary: 'operator_id',
  conditional_families: 'family_id',
};

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function hash(value) { return createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex'); }
function norm(value = '') { return String(value).normalize('NFKC').toLocaleLowerCase('und').replace(/\s+/gu, ' ').trim(); }
function issue(severity, code, message, detail = {}) { return { severity, code, message, ...detail }; }
function isObject(value) { return value && typeof value === 'object' && !Array.isArray(value); }
function unique(values) { return [...new Set(values)]; }

function triggerMatches(text, trigger) {
  const t = norm(trigger);
  if (!t) return false;
  return norm(text).includes(t);
}

function runtimeReachability(section, kind, registry) {
  if (section === 'conditional_families') return 'FULL';
  if (section === 'generative_gestures' && kind === 'SUSPEND') return 'FULL';
  if (section === 'generative_gestures') {
    const declarative = String(registry?.runtime_contract?.runtime ?? '').startsWith('DAE-LIVING-DECLARATIVE');
    if (declarative && ['REVISE', 'SPLIT', 'ADD_OPERATOR'].includes(kind)) return 'FULL';
    return 'PARTIAL';
  }
  return 'NONE';
}

function baseValidation(delta) {
  const issues = [];
  if (!isObject(delta)) return [issue('ERROR', 'DELTA_NOT_OBJECT', 'operator_delta must be a JSON object.')];
  if (delta.operator_delta_version !== 'DAE-OPERATOR-DELTA-1.0') issues.push(issue('ERROR', 'DELTA_VERSION', 'operator_delta_version must be DAE-OPERATOR-DELTA-1.0.'));
  if (!String(delta.delta_id ?? '').startsWith('DELTA-')) issues.push(issue('ERROR', 'DELTA_ID', 'delta_id must start with DELTA-.'));
  if (!String(delta.name ?? '').trim()) issues.push(issue('ERROR', 'DELTA_NAME', 'name is required.'));
  if (!isObject(delta.resistant_source)) issues.push(issue('ERROR', 'RESISTANT_SOURCE', 'resistant_source is required.'));
  else {
    for (const key of ['source_id', 'selector', 'why_resistant']) if (!String(delta.resistant_source[key] ?? '').trim()) issues.push(issue('ERROR', 'RESISTANT_SOURCE_FIELD', `resistant_source.${key} is required.`));
  }
  if (!Array.isArray(delta.incompatible_unitizations) || delta.incompatible_unitizations.length < 2) issues.push(issue('ERROR', 'UNITIZATIONS_MIN_2', 'At least two incompatible unitizations are required.'));
  else {
    const ids = delta.incompatible_unitizations.map(x => String(x?.unitization_id ?? '').trim());
    if (ids.some(x => !x)) issues.push(issue('ERROR', 'UNITIZATION_ID', 'Every unitization needs unitization_id.'));
    if (new Set(ids).size !== ids.length) issues.push(issue('ERROR', 'UNITIZATION_DUPLICATE', 'unitization_id values must be unique.'));
    const descriptions = delta.incompatible_unitizations.map(x => norm(x?.description));
    const consequences = delta.incompatible_unitizations.map(x => norm(x?.analytic_consequence));
    if (new Set(descriptions).size < 2 || new Set(consequences).size < 2) issues.push(issue('ERROR', 'UNITIZATIONS_NOT_CONTRASTIVE', 'Unitizations must differ in both description and analytic consequence.'));
  }
  if (!isObject(delta.target) || !SECTIONS.has(delta.target.registry_section) || !String(delta.target.operator_id ?? '').trim()) issues.push(issue('ERROR', 'TARGET', 'target must name a supported registry_section and operator_id.'));
  if (!isObject(delta.observed_failure) || !String(delta.observed_failure.description ?? '').trim() || !String(delta.observed_failure.lost_distinction ?? '').trim()) issues.push(issue('ERROR', 'OBSERVED_FAILURE', 'observed_failure must describe the failure and lost distinction.'));
  if (!isObject(delta.mutation) || !KINDS.has(delta.mutation.kind)) issues.push(issue('ERROR', 'MUTATION_KIND', 'mutation.kind must be SUSPEND, SPLIT, REVISE, ADD_CONDITION or ADD_OPERATOR.'));
  else {
    for (const key of ['proposal', 'cost', 'reversibility']) if (!String(delta.mutation[key] ?? '').trim()) issues.push(issue('ERROR', 'MUTATION_FIELD', `mutation.${key} is required.`));
    if (delta.mutation.kind === 'ADD_OPERATOR' && !isObject(delta.mutation.new_operator)) issues.push(issue('ERROR', 'NEW_OPERATOR_REQUIRED', 'ADD_OPERATOR requires mutation.new_operator.'));
  }
  const ba = delta.before_after_test;
  if (!isObject(ba) || !isObject(ba.fixture)) issues.push(issue('ERROR', 'FIXTURE', 'before_after_test.fixture is required.'));
  else {
    if (ba.fixture.same_material !== true) issues.push(issue('ERROR', 'FIXTURE_NOT_SAME_MATERIAL', 'before/after must use the same material.'));
    if (!String(ba.fixture.probe_text ?? '').trim()) issues.push(issue('ERROR', 'FIXTURE_PROBE_TEXT', 'fixture.probe_text is required for executable mutation probing.'));
    if (delta.resistant_source && (ba.fixture.source_id !== delta.resistant_source.source_id || ba.fixture.selector !== delta.resistant_source.selector)) issues.push(issue('ERROR', 'FIXTURE_SOURCE_MISMATCH', 'The before/after fixture must point to the same resistant source selector.'));
    if (!String(ba.before_observation ?? '').trim() || !String(ba.after_observation ?? '').trim() || norm(ba.before_observation) === norm(ba.after_observation)) issues.push(issue('ERROR', 'BEFORE_AFTER_NOT_CONTRASTIVE', 'Before and after observations must be non-empty and different.'));
    if (!Array.isArray(ba.new_gains) || !ba.new_gains.length || ba.new_gains.some(g => !GG.has(g))) issues.push(issue('ERROR', 'NEW_GAIN_REQUIRED', 'At least one valid GG1-GG6 gain is required.'));
    if (!String(ba.discriminator ?? '').trim()) issues.push(issue('ERROR', 'DISCRIMINATOR_REQUIRED', 'A discriminator is required; novelty alone is insufficient.'));
    if (!isObject(ba.traceability)) issues.push(issue('ERROR', 'TRACEABILITY_REQUIRED', 'before_after_test.traceability is required.'));
    else if (!Number.isInteger(ba.traceability.before_routes) || !Number.isInteger(ba.traceability.after_routes) || ba.traceability.after_routes < ba.traceability.before_routes) issues.push(issue('ERROR', 'TRACEABILITY_REGRESSION', 'after_routes must be an integer greater than or equal to before_routes.'));
    if (!Array.isArray(ba.negative_tests) || !ba.negative_tests.length) issues.push(issue('ERROR', 'NEGATIVE_TEST_REQUIRED', 'At least one negative test is required.'));
    else if (ba.negative_tests.some(t => t?.passed !== true)) issues.push(issue('ERROR', 'NEGATIVE_TEST_REGRESSION', 'All declared negative tests must pass.'));
  }
  const gate = delta.acceptance_gate;
  if (!isObject(gate) || gate.new_distinction_required !== true || gate.source_traceability_must_not_degrade !== true || gate.negative_tests_must_not_regress !== true) issues.push(issue('ERROR', 'GATE_CONTRACT', 'All acceptance gate invariants must be true.'));
  return issues;
}

function locate(registry, target) {
  const section = target.registry_section;
  const idField = ID_FIELD[section];
  const list = registry?.[section];
  if (!Array.isArray(list)) return { error: `Registry section ${section} is missing.` };
  const index = list.findIndex(entry => entry?.[idField] === target.operator_id);
  if (index < 0) return { error: `${target.operator_id} not found in ${section}.` };
  return { section, idField, list, index, value: list[index] };
}

function allowedFields(policy, section) {
  return new Set(policy?.executable_sections?.[section]?.allowed_change_fields ?? []);
}

function checkChangeFields(changes, allowed, issues) {
  if (!isObject(changes) || !Object.keys(changes).length) {
    issues.push(issue('ERROR', 'MUTATION_CHANGES_REQUIRED', 'mutation.changes must be a non-empty object.'));
    return;
  }
  for (const key of Object.keys(changes)) if (!allowed.has(key)) issues.push(issue('ERROR', 'MUTATION_FIELD_FORBIDDEN', `Field ${key} is not mutable in this registry section.`, { field: key }));
}

function applyMutation(registry, delta, policy) {
  const candidate = clone(registry);
  const section = delta.target.registry_section;
  const idField = ID_FIELD[section];
  const list = candidate?.[section];
  if (!Array.isArray(list)) throw new Error(`Registry section ${section} is missing.`);
  const mutation = delta.mutation;
  const allowed = allowedFields(policy, section);
  const semanticIssues = [];
  let afterTargets = [];
  let original = null;
  let found = null;

  if (mutation.kind === 'ADD_OPERATOR') {
    const proposed = clone(mutation.new_operator ?? {});
    const newId = String(proposed?.[idField] ?? '').trim();
    if (!newId) semanticIssues.push(issue('ERROR', 'NEW_OPERATOR_ID_REQUIRED', `ADD_OPERATOR requires mutation.new_operator.${idField}.`));
    const allowedAddFields = new Set([idField, ...allowed]);
    for (const key of Object.keys(proposed)) if (!allowedAddFields.has(key)) semanticIssues.push(issue('ERROR', 'NEW_OPERATOR_FIELD_FORBIDDEN', `Field ${key} is not allowed when adding to ${section}.`, { field: key }));
    if (newId && list.some((entry) => entry?.[idField] === newId)) semanticIssues.push(issue('ERROR', 'CANDIDATE_DUPLICATE_ID', `ADD_OPERATOR would duplicate ${newId} in ${section}.`));
    original = { [idField]: '__ABSENT__', protocol_refs: [] };
    if (!semanticIssues.some((entry) => entry.code === 'CANDIDATE_DUPLICATE_ID' || entry.code === 'NEW_OPERATOR_ID_REQUIRED')) {
      list.push(proposed);
      afterTargets = [proposed];
    }
  } else {
    found = locate(candidate, delta.target);
    if (found.error) throw new Error(found.error);
    original = clone(found.value);
    if (mutation.kind === 'SUSPEND') {
      found.list.splice(found.index, 1);
    } else if (mutation.kind === 'REVISE') {
      checkChangeFields(mutation.changes, allowed, semanticIssues);
      const revised = { ...found.value, ...clone(mutation.changes ?? {}) };
      revised[idField] = original[idField];
      found.list[found.index] = revised;
      afterTargets = [revised];
    } else if (mutation.kind === 'ADD_CONDITION') {
      if (section !== 'conditional_families') semanticIssues.push(issue('ERROR', 'ADD_CONDITION_RUNTIME_UNSUPPORTED', 'ADD_CONDITION currently targets trigger arrays and remains executable only for conditional_families; declarative gesture conditions should be changed with REVISE.'));
      const additions = unique((mutation.trigger_additions ?? []).map(norm).filter(Boolean));
      const removals = new Set((mutation.trigger_removals ?? []).map(norm).filter(Boolean));
      if (!additions.length && !removals.size) semanticIssues.push(issue('ERROR', 'CONDITION_DELTA_EMPTY', 'ADD_CONDITION requires trigger_additions and/or trigger_removals.'));
      const existing = (found.value.triggers ?? []).filter(t => !removals.has(norm(t)));
      const triggers = unique([...existing, ...additions]);
      if (!triggers.length) semanticIssues.push(issue('ERROR', 'CONDITION_REMOVES_ALL_TRIGGERS', 'A conditional family cannot be left without triggers; use SUSPEND instead.'));
      const revised = { ...found.value, triggers };
      found.list[found.index] = revised;
      afterTargets = [revised];
    } else if (mutation.kind === 'SPLIT') {
      const variants = mutation.variants ?? [];
      if (!Array.isArray(variants) || variants.length < 2) semanticIssues.push(issue('ERROR', 'SPLIT_VARIANTS_MIN_2', 'SPLIT requires at least two variants.'));
      const unitIds = new Set((delta.incompatible_unitizations ?? []).map(x => x.unitization_id));
      const covered = new Set();
      const produced = [];
      for (const variant of variants) {
        checkChangeFields(variant?.changes, allowed, semanticIssues);
        const refs = variant?.unitization_refs ?? [];
        for (const ref of refs) {
          if (!unitIds.has(ref)) semanticIssues.push(issue('ERROR', 'SPLIT_UNKNOWN_UNITIZATION', `Variant ${variant?.new_id} references unknown unitization ${ref}.`));
          covered.add(ref);
        }
        if (!String(variant?.new_id ?? '').trim()) continue;
        const v = { ...clone(original), ...clone(variant.changes ?? {}), [idField]: variant.new_id };
        produced.push(v);
      }
      for (const id of unitIds) if (!covered.has(id)) semanticIssues.push(issue('ERROR', 'SPLIT_UNITIZATION_UNCOVERED', `SPLIT does not cover unitization ${id}.`));
      found.list.splice(found.index, 1, ...produced);
      afterTargets = produced;
    }
  }

  const ids = candidate[section].map(x => x?.[idField]).filter(Boolean);
  if (new Set(ids).size !== ids.length && !semanticIssues.some((entry) => entry.code === 'CANDIDATE_DUPLICATE_ID')) semanticIssues.push(issue('ERROR', 'CANDIDATE_DUPLICATE_ID', `Mutation produces duplicate IDs in ${section}.`));
  if (section === 'conditional_families') {
    for (const target of afterTargets) {
      if (!Array.isArray(target.triggers) || !target.triggers.length) semanticIssues.push(issue('ERROR', 'CANDIDATE_FAMILY_NO_TRIGGERS', `${target.family_id} has no triggers.`));
      for (const key of ['diagnostic', 'constructive_move', 'self_risk', 'positive_model']) if (!String(target[key] ?? '').trim()) semanticIssues.push(issue('ERROR', 'CANDIDATE_FAMILY_REQUIRED_FIELD', `${target.family_id}.${key} is empty.`));
    }
  }
  if (section === 'generative_gestures' && String(candidate?.runtime_contract?.runtime ?? '').startsWith('DAE-LIVING-DECLARATIVE')) {
    for (const message of validateDeclarativeGestures(candidate)) semanticIssues.push(issue('ERROR', 'DECLARATIVE_GESTURE_INVALID', message));
  }
  return { candidate, original, afterTargets, semanticIssues };
}

function protocolRefs(entry) { return new Set(Array.isArray(entry?.protocol_refs) ? entry.protocol_refs : []); }
function protocolCoveragePreserved(original, afterTargets, kind) {
  if (kind === 'SUSPEND') return true;
  const before = protocolRefs(original);
  const after = new Set(afterTargets.flatMap(x => [...protocolRefs(x)]));
  return [...before].every(ref => after.has(ref));
}

function executableProbe(section, original, afterTargets, delta) {
  const probe = delta.before_after_test.fixture.probe_text;
  if (section === 'conditional_families') {
    const beforeMatches = (original?.triggers ?? []).filter(t => triggerMatches(probe, t));
    const afterMatches = afterTargets.map(target => ({
      operator_id: target.family_id,
      matches: (target.triggers ?? []).filter(t => triggerMatches(probe, t)),
    }));
    return {
      probe_text_sha256: hash(probe),
      before: { operator_id: original?.family_id ?? '__ABSENT__', active: beforeMatches.length > 0, matched_triggers: beforeMatches },
      after: afterTargets.length ? afterMatches.map(x => ({ ...x, active: x.matches.length > 0 })) : [],
      behavior_changed: hash(original) !== hash(afterTargets),
    };
  }
  return {
    probe_text_sha256: hash(probe),
    before: { operator_id: original?.[ID_FIELD[section]], present: true },
    after: afterTargets.map(x => ({ operator_id: x?.[ID_FIELD[section]], present: true })),
    behavior_changed: hash(original) !== hash(afterTargets),
  };
}

function summarizeDecision(issues, reachability, delta, builtins) {
  const errors = issues.filter(x => x.severity === 'ERROR');
  const newDistinction = delta.before_after_test?.new_gains?.includes('GG1_NEW_DISTINCTION');
  const gates = {
    structurally_and_semantically_valid: errors.length === 0,
    resistant_source_bound_to_same_fixture: !issues.some(x => ['FIXTURE_SOURCE_MISMATCH', 'FIXTURE_NOT_SAME_MATERIAL'].includes(x.code)),
    incompatible_unitizations_present: !issues.some(x => x.code.startsWith('UNITIZATION')),
    new_distinction_present: Boolean(newDistinction),
    source_traceability_non_degrading: !issues.some(x => ['TRACEABILITY_REGRESSION', 'PROTOCOL_TRACEABILITY_REGRESSION'].includes(x.code)),
    negative_tests_pass: !issues.some(x => x.code === 'NEGATIVE_TEST_REGRESSION') && builtins.every(t => t.passed),
    runtime_reachability_full: reachability === 'FULL',
    mutation_effect_observed: builtins.find(t => t.name === 'candidate differs from baseline')?.passed === true,
  };
  const all = Object.values(gates).every(Boolean);
  return {
    decision: all ? 'ACCEPTED_CANDIDATE' : (errors.length ? 'REJECTED' : 'REVIEW'),
    promotion_ready: all,
    gates,
    reason: all
      ? 'The delta changes an executable operator under a same-source before/after fixture, adds GG1, preserves traceability and passes negative gates.'
      : 'The delta remains non-promotable until every machine gate is satisfied; generative interest alone is insufficient.',
  };
}

export async function evaluateOperatorDelta({ delta, registry, policy }) {
  const issues = baseValidation(delta);
  let mutationResult = null;
  let reachability = 'NONE';
  let probe = null;
  const builtins = [];

  if (!issues.some(x => ['TARGET', 'MUTATION_KIND'].includes(x.code))) {
    const adding = delta.mutation.kind === 'ADD_OPERATOR';
    const found = adding ? { error: null } : locate(registry, delta.target);
    if (found.error) issues.push(issue('ERROR', 'TARGET_NOT_FOUND', found.error));
    else {
      reachability = runtimeReachability(delta.target.registry_section, delta.mutation.kind, registry);
      try {
        mutationResult = applyMutation(registry, delta, policy);
        issues.push(...mutationResult.semanticIssues);
        const preservesRefs = protocolCoveragePreserved(mutationResult.original, mutationResult.afterTargets, delta.mutation.kind);
        if (!preservesRefs) issues.push(issue('ERROR', 'PROTOCOL_TRACEABILITY_REGRESSION', 'The candidate drops protocol_refs carried by the baseline operator.'));
        probe = executableProbe(delta.target.registry_section, mutationResult.original, mutationResult.afterTargets, delta);
        builtins.push({ name: 'candidate differs from baseline', passed: hash(mutationResult.original) !== hash(mutationResult.afterTargets) });
        builtins.push({ name: 'operator ids unique after mutation', passed: !mutationResult.semanticIssues.some(x => x.code === 'CANDIDATE_DUPLICATE_ID') });
        builtins.push({ name: 'protocol refs preserved or suspension explicit', passed: preservesRefs });
        builtins.push({ name: 'same source fixture enforced', passed: !issues.some(x => ['FIXTURE_SOURCE_MISMATCH', 'FIXTURE_NOT_SAME_MATERIAL'].includes(x.code)) });
      } catch (error) {
        issues.push(issue('ERROR', 'MUTATION_APPLY_FAILED', error.message));
      }
    }
  }

  if (reachability !== 'FULL') issues.push(issue('REVIEW', 'RUNTIME_REACHABILITY_NOT_FULL', `Target mutation has ${reachability} runtime reachability in the selected living runtime; it cannot be promoted as an executable operator mutation.`));
  if (!delta.before_after_test?.new_gains?.includes('GG1_NEW_DISTINCTION')) issues.push(issue('ERROR', 'GG1_REQUIRED_FOR_PROMOTION', 'Operator mutation must create a new distinction (GG1), not merely a stylistic or rhetorical difference.'));

  const decision = summarizeDecision(issues, reachability, delta, builtins);
  const receipt = {
    mutation_engine_version: 'DAE-OPERATOR-MUTATION-1.3',
    evaluated_at: new Date().toISOString(),
    delta_id: delta.delta_id,
    baseline_registry_sha256: hash(registry),
    candidate_registry_sha256: mutationResult ? hash(mutationResult.candidate) : null,
    target_before_sha256: mutationResult ? hash(mutationResult.original) : null,
    target_after_sha256: mutationResult ? hash(mutationResult.afterTargets) : null,
    runtime_reachability: reachability,
    executable_probe: probe,
    built_in_negative_tests: builtins,
    decision,
    counts: {
      ERROR: issues.filter(x => x.severity === 'ERROR').length,
      REVIEW: issues.filter(x => x.severity === 'REVIEW').length,
      WARNING: issues.filter(x => x.severity === 'WARNING').length,
    },
    issues,
  };
  return { receipt, candidateRegistry: mutationResult?.candidate ?? null, originalTarget: mutationResult?.original ?? null, afterTargets: mutationResult?.afterTargets ?? [] };
}

function markdown(delta, receipt) {
  const lines = [
    `# Operator Mutation Gate — ${delta.name}`,
    '',
    `**Decision:** \`${receipt.decision.decision}\`  `,
    `**Promotion ready:** \`${receipt.decision.promotion_ready}\`  `,
    `**Runtime reachability:** \`${receipt.runtime_reachability}\``,
    '',
    '## Resistant source', '',
    `- Source: \`${delta.resistant_source.source_id}\``,
    `- Selector: \`${delta.resistant_source.selector}\``,
    `- Resistance: ${delta.resistant_source.why_resistant}`,
    '',
    '## Incompatible unitizations', '',
    ...delta.incompatible_unitizations.flatMap(u => [`- **${u.unitization_id}:** ${u.description}`, `  - Consequence: ${u.analytic_consequence}`]),
    '',
    '## Mutation', '',
    `- Target: \`${delta.target.registry_section}/${delta.target.operator_id}\``,
    `- Kind: \`${delta.mutation.kind}\``,
    `- Proposal: ${delta.mutation.proposal}`,
    `- Cost: ${delta.mutation.cost}`,
    `- Rollback: ${delta.mutation.reversibility}`,
    '',
    '## Machine gates', '',
    ...Object.entries(receipt.decision.gates).map(([key, value]) => `- ${value ? '✓' : '✗'} ${key}`),
    '',
    '## Built-in negative tests', '',
    ...(receipt.built_in_negative_tests.length ? receipt.built_in_negative_tests.map(t => `- ${t.passed ? '✓' : '✗'} ${t.name}`) : ['- No built-in tests executed.']),
    '',
    '## Issues', '',
    ...(receipt.issues.length ? receipt.issues.map(i => `- **${i.severity} ${i.code}:** ${i.message}`) : ['- None.']),
    '',
    '## Interpretation', '', receipt.decision.reason, '',
    '> An accepted candidate is not silently installed into the baseline registry. Promotion is a separate explicit action, and rollback remains possible from the stored before-target.', '',
  ];
  return lines.join('\n');
}

export async function gateOperatorDelta(deltaFile, registryFile, policyFile, outputDir) {
  const [delta, registry, policy] = await Promise.all([
    readFile(deltaFile, 'utf8').then(JSON.parse),
    readFile(registryFile, 'utf8').then(JSON.parse),
    readFile(policyFile, 'utf8').then(JSON.parse),
  ]);
  const result = await evaluateOperatorDelta({ delta, registry, policy });
  await mkdir(outputDir, { recursive: false });
  const gated = { ...delta, status: result.receipt.decision.decision };
  const files = {
    gated_delta: path.join(outputDir, 'operator_delta.gated.json'),
    receipt: path.join(outputDir, 'mutation_receipt.json'),
    report: path.join(outputDir, 'MUTATION_REPORT.md'),
    rollback: path.join(outputDir, 'rollback_target.json'),
    candidate: result.candidateRegistry ? path.join(outputDir, 'candidate_living_operator_registry.json') : null,
  };
  await Promise.all([
    writeFile(files.gated_delta, `${JSON.stringify(gated, null, 2)}\n`),
    writeFile(files.receipt, `${JSON.stringify(result.receipt, null, 2)}\n`),
    writeFile(files.report, `${markdown(delta, result.receipt)}\n`),
    writeFile(files.rollback, `${JSON.stringify(delta.mutation.kind === 'ADD_OPERATOR' ? { delta_id: delta.delta_id, target: delta.target, rollback_action: 'REMOVE_ADDED_OPERATOR', added_operator_id: result.afterTargets[0]?.[ID_FIELD[delta.target.registry_section]] ?? delta.mutation.new_operator?.[ID_FIELD[delta.target.registry_section]], restore: null } : { delta_id: delta.delta_id, target: delta.target, rollback_action: 'RESTORE_TARGET', restore: result.originalTarget }, null, 2)}\n`),
    ...(files.candidate ? [writeFile(files.candidate, `${JSON.stringify(result.candidateRegistry, null, 2)}\n`)] : []),
  ]);
  return { ...result, outputDir, files };
}
