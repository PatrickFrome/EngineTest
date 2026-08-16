import { createHash } from 'node:crypto';

const DISCOVERY_VERSION = 'DAE-RESISTANCE-DISCOVERY-1.0';
const DELTA_SEED_VERSION = 'DAE-DISCOVERED-DELTA-SEED-1.0';
const CLAIM_CEILING = 'STRUCTURAL_RESISTANCE_HYPOTHESIS_NOT_SOURCE_SEMANTICS_OPERATOR_VALIDITY_OR_PHILOSOPHICAL_TRUTH';

const DEFAULT_POLICY = Object.freeze({
  min_analysis_support: 2,
  min_resistance_runs: 2,
  min_distinct_unitizations: 2,
  pressure_roles: [
    'RESIDUAL_CANDIDATE', 'OPEN_RESIDUAL', 'REVISION_TRIGGER', 'SELF_CRITIQUE',
    'REVERSE_TEST', 'MUTATION', 'RESEARCH_BRANCH', 'COUNTERGENETIC_FORK',
    'SOURCE_RESISTANCE', 'REPRESENTATION_FAILURE', 'OPERATOR_DELTA',
  ],
  residual_roles: ['RESIDUAL_CANDIDATE', 'OPEN_RESIDUAL', 'SOURCE_RESISTANCE'],
  revision_roles: ['REVISION_TRIGGER', 'MUTATION', 'SELF_CRITIQUE', 'REVERSE_TEST', 'REPRESENTATION_FAILURE', 'OPERATOR_DELTA'],
  unitization_roles: [
    'DECONFLATION', 'RESIDUAL_CANDIDATE', 'OPEN_RESIDUAL', 'REVISION_TRIGGER',
    'SELF_CRITIQUE', 'REVERSE_TEST', 'MUTATION', 'COUNTERGENETIC_FORK',
    'RIVAL_RECONSTRUCTION', 'POLYPHONIC_FIELD', 'FORMAL_INDICATION', 'RESEARCH_BRANCH',
    'SOURCE_RESISTANCE', 'REPRESENTATION_FAILURE', 'OPERATOR_DELTA',
  ],
});

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function hash(value) { return createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex'); }
function uniq(values) { return [...new Set(values.filter(v => v !== undefined && v !== null && v !== ''))].sort(); }
function histogram(values) {
  const out = {};
  for (const value of values.filter(v => v !== undefined && v !== null && v !== '')) out[value] = (out[value] ?? 0) + 1;
  return Object.fromEntries(Object.entries(out).sort(([a], [b]) => a.localeCompare(b)));
}
function intersection(arrays) {
  if (!arrays.length) return [];
  const [first, ...rest] = arrays.map(a => new Set(a));
  return [...first].filter(v => rest.every(s => s.has(v))).sort();
}
function compactId(value) {
  return String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/gu, '').toUpperCase()
    .replace(/[^A-Z0-9]+/gu, '-').replace(/^-+|-+$/gu, '').slice(0, 64) || 'CASE';
}
function asArray(value) { return Array.isArray(value) ? value : []; }
function roleNodes(nodes, roles) { const allowed = new Set(roles); return nodes.filter(n => allowed.has(n.role)); }

export function validateDiscoveryInput(analysis, label = 'analysis') {
  const issues = [];
  if (!analysis || typeof analysis !== 'object') issues.push(`${label}: analysis must be an object`);
  if (!analysis?.source?.source_id) issues.push(`${label}: source.source_id is required`);
  if (!analysis?.run_id) issues.push(`${label}: run_id is required`);
  if (!Array.isArray(analysis?.graph?.nodes)) issues.push(`${label}: graph.nodes is required`);
  if (!Array.isArray(analysis?.constellations)) issues.push(`${label}: constellations is required`);
  return issues;
}

function observationFromConstellation(analysis, constellation, policy) {
  const nodes = asArray(analysis.graph.nodes).filter(n => n.constellation_id === constellation.constellation_id);
  const selectors = uniq(nodes.flatMap(n => asArray(n?.source_basis?.selectors)));
  if (!selectors.length) return [];
  const pressure = roleNodes(nodes, policy.pressure_roles);
  const residual = roleNodes(nodes, policy.residual_roles);
  const revision = roleNodes(nodes, policy.revision_roles);
  const unitizationNodes = roleNodes(nodes, policy.unitization_roles);
  const roles = uniq(unitizationNodes.map(n => n.role));
  const pressureGenerators = uniq(pressure.map(n => n.generated_by));
  const unitizationGenerators = uniq(unitizationNodes.map(n => n.generated_by));
  const residualKinds = uniq(nodes.map(n => n.residual_kind));
  const families = uniq(constellation.activated_families ?? []);
  const gestures = uniq(constellation.activated_gestures ?? []);
  const signatureView = {
    roles,
    pressure_generators: pressureGenerators,
    unitization_generators: unitizationGenerators,
    activated_families: families,
    residual_kinds: residualKinds,
  };
  const signature = hash(signatureView);
  const sourceId = analysis.source.source_id;
  const runtime = analysis.operator_registry?.runtime ?? 'UNKNOWN_RUNTIME';
  const seed = analysis.seed ?? 'NO_SEED';
  return selectors.map(selector => ({
    source_id: sourceId,
    selector,
    run_id: analysis.run_id,
    seed,
    runtime,
    registry_sha256: analysis.operator_registry?.sha256 ?? null,
    constellation_id: constellation.constellation_id,
    topic_id: constellation.topic_id ?? null,
    hypothesis_id: nodes.find(n => n?.source_basis?.hypothesis_id)?.source_basis?.hypothesis_id ?? null,
    roles,
    pressure_generators: pressureGenerators,
    unitization_generators: unitizationGenerators,
    activated_families: families,
    activated_gestures: gestures,
    residual_kinds: residualKinds,
    pressure_node_count: pressure.length,
    residual_node_count: residual.length,
    revision_node_count: revision.length,
    node_ids: unitizationNodes.map(n => n.node_id).sort(),
    proposition_hashes: unitizationNodes.map(n => hash(String(n.proposition ?? ''))).sort(),
    unitization_signature_sha256: signature,
    structural_view: signatureView,
    sufficient_openness_missing: uniq(analysis.sufficient_openness?.missing ?? []),
  }));
}

function registryIds(registry) {
  return {
    generative_gestures: new Set(asArray(registry?.generative_gestures).map(x => x.gesture_id)),
    conditional_families: new Set(asArray(registry?.conditional_families).map(x => x.family_id)),
    supporting_operation_vocabulary: new Set(asArray(registry?.supporting_operation_vocabulary).map(x => x.operator_id)),
  };
}

function targetFromUnitizations(unitizations, registry) {
  const ids = registryIds(registry);
  const generatorGroups = unitizations.map(u => u.pressure_generators.filter(id => ids.generative_gestures.has(id)));
  const commonGenerators = intersection(generatorGroups.filter(a => a.length));
  if (commonGenerators.length) {
    const support = histogram(unitizations.flatMap(u => u.observations.flatMap(o => o.pressure_generators.filter(id => ids.generative_gestures.has(id)))));
    const operatorId = [...commonGenerators].sort((a, b) => (support[b] ?? 0) - (support[a] ?? 0) || a.localeCompare(b))[0];
    return { registry_section: 'generative_gestures', operator_id: operatorId, basis: 'COMMON_PRESSURE_GENERATOR_ACROSS_UNITIZATIONS' };
  }
  const familyGroups = unitizations.map(u => u.activated_families.filter(id => ids.conditional_families.has(id)));
  const commonFamilies = intersection(familyGroups.filter(a => a.length));
  if (commonFamilies.length) {
    const support = histogram(unitizations.flatMap(u => u.observations.flatMap(o => o.activated_families.filter(id => ids.conditional_families.has(id)))));
    const operatorId = [...commonFamilies].sort((a, b) => (support[b] ?? 0) - (support[a] ?? 0) || a.localeCompare(b))[0];
    return { registry_section: 'conditional_families', operator_id: operatorId, basis: 'COMMON_CONDITIONAL_FAMILY_ACROSS_UNITIZATIONS' };
  }
  const allGenerators = histogram(unitizations.flatMap(u => u.observations.flatMap(o => o.pressure_generators.filter(id => ids.generative_gestures.has(id)))));
  const rankedGenerators = Object.entries(allGenerators).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (rankedGenerators.length && rankedGenerators[0][1] >= 2) return { registry_section: 'generative_gestures', operator_id: rankedGenerators[0][0], basis: 'RECURRENT_PRESSURE_GENERATOR_REVIEW_REQUIRED' };
  const allFamilies = histogram(unitizations.flatMap(u => u.observations.flatMap(o => o.activated_families.filter(id => ids.conditional_families.has(id)))));
  const rankedFamilies = Object.entries(allFamilies).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (rankedFamilies.length && rankedFamilies[0][1] >= 2) return { registry_section: 'conditional_families', operator_id: rankedFamilies[0][0], basis: 'RECURRENT_CONDITIONAL_FAMILY_REVIEW_REQUIRED' };
  return null;
}

function summarizeUnitization(signature, observations, index) {
  const roles = uniq(observations.flatMap(o => o.roles));
  const pressureGenerators = uniq(observations.flatMap(o => o.pressure_generators));
  const unitizationGenerators = uniq(observations.flatMap(o => o.unitization_generators));
  const families = uniq(observations.flatMap(o => o.activated_families));
  const residualKinds = uniq(observations.flatMap(o => o.residual_kinds));
  const runs = uniq(observations.map(o => o.run_id));
  const seeds = uniq(observations.map(o => o.seed));
  const runtimes = uniq(observations.map(o => o.runtime));
  const description = `Structural routing ${index + 1}: roles [${roles.join(', ') || 'none'}], pressure generators [${pressureGenerators.join(', ') || 'none'}], families [${families.join(', ') || 'none'}].`;
  const consequence = `This routing produces residual/revision pressure through [${pressureGenerators.join(', ') || unitizationGenerators.join(', ') || 'unresolved operator'}] with residual kinds [${residualKinds.join(', ') || 'none'}]; it must not be collapsed with a rival routing before source review.`;
  return {
    unitization_id: `U-DISC-${index + 1}`,
    signature_sha256: signature,
    support: { observations: observations.length, runs: runs.length, run_ids: runs, seeds, runtimes },
    roles,
    pressure_generators: pressureGenerators,
    unitization_generators: unitizationGenerators,
    activated_families: families,
    residual_kinds: residualKinds,
    description,
    analytic_consequence: consequence,
    observations: observations.map(o => ({
      run_id: o.run_id, seed: o.seed, runtime: o.runtime, constellation_id: o.constellation_id,
      topic_id: o.topic_id, roles: o.roles, pressure_generators: o.pressure_generators,
      activated_families: o.activated_families, residual_kinds: o.residual_kinds,
    })),
  };
}

function caseFromGroup(key, observations, registry, policy) {
  const bySignature = new Map();
  for (const obs of observations) {
    const arr = bySignature.get(obs.unitization_signature_sha256) ?? [];
    arr.push(obs); bySignature.set(obs.unitization_signature_sha256, arr);
  }
  const unitizations = [...bySignature.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([signature, obs], index) => summarizeUnitization(signature, obs, index));
  const runIds = uniq(observations.map(o => o.run_id));
  const seeds = uniq(observations.map(o => o.seed));
  const runtimes = uniq(observations.map(o => o.runtime));
  const resistanceRuns = uniq(observations.filter(o => o.pressure_node_count > 0 || o.sufficient_openness_missing.length).map(o => o.run_id));
  const residualRuns = uniq(observations.filter(o => o.residual_node_count > 0).map(o => o.run_id));
  const revisionRuns = uniq(observations.filter(o => o.revision_node_count > 0).map(o => o.run_id));
  const qualifies = runIds.length >= policy.min_analysis_support
    && resistanceRuns.length >= policy.min_resistance_runs
    && unitizations.length >= policy.min_distinct_unitizations;
  if (!qualifies) return null;
  const [sourceId, selector] = key.split('\u241f');
  const target = targetFromUnitizations(unitizations, registry);
  const caseId = `RSC-${compactId(sourceId)}-${hash(selector).slice(0, 10).toUpperCase()}`;
  const crossRuntimeOnly = seeds.length === 1 && runtimes.length > 1;
  const reviewRequirements = [
    'Inspect the actual source span at the selector; generated propositions are not source semantics.',
    'State the lost distinction in source-grounded language rather than structural role names.',
    'Provide a discriminator that can decide between the rival unitizations on the same material.',
    'Author executable mutation changes/variants and run the existing operator-delta gate.',
    'Run same-material before/after and negative tests; discovery cannot mark its own proposal promotion-ready.',
  ];
  if (crossRuntimeOnly) reviewRequirements.unshift('The divergence is cross-runtime with one seed; reproduce across an additional seed or independent run before treating recurrence as robust.');
  return {
    case_id: caseId,
    source_id: sourceId,
    selector,
    status: 'DISCOVERY_HYPOTHESIS_REVIEW_REQUIRED',
    support: {
      observations: observations.length,
      runs: runIds.length,
      run_ids: runIds,
      seeds,
      runtimes,
      cross_runtime_only: crossRuntimeOnly,
    },
    signals: {
      distinct_unitizations: unitizations.length,
      resistance_runs: resistanceRuns.length,
      residual_runs: residualRuns.length,
      revision_pressure_runs: revisionRuns.length,
      recurrent_openness_missing: histogram(observations.flatMap(o => o.sufficient_openness_missing)),
      pressure_generators: histogram(observations.flatMap(o => o.pressure_generators)),
      activated_families: histogram(observations.flatMap(o => o.activated_families)),
      residual_kinds: histogram(observations.flatMap(o => o.residual_kinds)),
    },
    incompatible_unitizations: unitizations,
    target_hypothesis: target,
    mutation_hypothesis: target ? {
      kind: unitizations.length >= 2 ? 'SPLIT' : 'REVISE',
      target,
      rationale: `The same source selector repeatedly reaches ${unitizations.length} structurally distinct routings under resistance/revision pressure. The target is a hypothesis inferred from recurrent operator participation, not a source-grounded diagnosis.`,
      automation_level: 'DRAFT_ONLY_NO_AUTO_ACCEPT',
    } : {
      kind: 'UNRESOLVED',
      target: null,
      rationale: 'No single mutable registry operator recurrently spans the rival routings. Human review must localize the failure before a delta can be authored.',
      automation_level: 'DRAFT_ONLY_NO_AUTO_ACCEPT',
    },
    review_requirements: reviewRequirements,
    claim_ceiling: CLAIM_CEILING,
  };
}

export function createOperatorDeltaSeed(discoveryCase) {
  const target = discoveryCase.target_hypothesis;
  const unitizations = discoveryCase.incompatible_unitizations.map((u, index) => ({
    unitization_id: `U-${index + 1}`,
    description: u.description,
    analytic_consequence: u.analytic_consequence,
    discovery_signature_sha256: u.signature_sha256,
  }));
  const seed = {
    discovery_delta_seed_version: DELTA_SEED_VERSION,
    source_case_id: discoveryCase.case_id,
    gateable: false,
    promotion_forbidden: true,
    why_not_gateable: [
      'Discovery observes structural divergence but does not inspect or quote the source span.',
      'The lost distinction and discriminator still require source-grounded formulation.',
      'Executable mutation changes/variants are intentionally absent.',
      'The after-observation and negative tests do not exist until a mutant is actually run.',
    ],
    suggested_delta: {
      operator_delta_version: 'DAE-OPERATOR-DELTA-1.0',
      delta_id: `DELTA-DISCOVERY-${hash(discoveryCase.case_id).slice(0, 12).toUpperCase()}`,
      name: `Review ${discoveryCase.case_id}: rival source unitizations`,
      resistant_source: {
        source_id: discoveryCase.source_id,
        selector: discoveryCase.selector,
        span_sha256: null,
        why_resistant: `STRUCTURAL_HYPOTHESIS_ONLY: ${discoveryCase.signals.distinct_unitizations} rival routings recur with resistance/revision pressure. Replace this sentence after reading the source span.`,
      },
      incompatible_unitizations: unitizations,
      target: target ? { registry_section: target.registry_section, operator_id: target.operator_id } : { registry_section: 'REVIEW_REQUIRED', operator_id: 'REVIEW_REQUIRED' },
      observed_failure: {
        failure_type: 'DISCOVERED_RIVAL_UNITIZATION_CANDIDATE',
        description: 'STRUCTURAL_HYPOTHESIS_ONLY: recurrent rival routings were detected for one source selector.',
        lost_distinction: 'REVIEW_REQUIRED_SOURCE_GROUNDED_DISTINCTION',
      },
      mutation: {
        kind: discoveryCase.mutation_hypothesis.kind === 'SPLIT' ? 'SPLIT' : 'REVISE',
        proposal: 'REVIEW_REQUIRED: author an executable mutation after source inspection.',
        cost: 'REVIEW_REQUIRED: state what analytical capacity or simplicity the mutation sacrifices.',
        reversibility: 'Restore the baseline registry from the gate rollback target; baseline must never be overwritten.',
        variants: [],
      },
      before_after_test: {
        fixture: {
          source_id: discoveryCase.source_id,
          selector: discoveryCase.selector,
          same_material: true,
          probe_text: 'REVIEW_REQUIRED_SOURCE_TEXT_NOT_EMBEDDED_BY_DISCOVERY',
        },
        before_observation: `${discoveryCase.signals.distinct_unitizations} rival structural routings recur before mutation.`,
        after_observation: 'REVIEW_REQUIRED_AFTER_REAL_MUTANT_RUN',
        new_gains: ['GG1_NEW_DISTINCTION'],
        discriminator: 'REVIEW_REQUIRED_SOURCE_GROUNDED_DISCRIMINATOR',
        traceability: { before_routes: 1, after_routes: Math.max(2, discoveryCase.signals.distinct_unitizations) },
        negative_tests: [{ name: 'REVIEW_REQUIRED_REAL_NEGATIVE_TEST', passed: false, note: 'Discovery cannot certify its own proposal.' }],
      },
      acceptance_gate: {
        new_distinction_required: true,
        source_traceability_must_not_degrade: true,
        negative_tests_must_not_regress: true,
      },
    },
    next_actions: discoveryCase.review_requirements,
    claim_ceiling: CLAIM_CEILING,
  };
  return seed;
}

export function discoverResistance({ analyses, registry, policy = {} }) {
  if (!Array.isArray(analyses) || analyses.length < 1) throw new Error('discoverResistance requires analyses[]');
  const mergedPolicy = { ...clone(DEFAULT_POLICY), ...clone(policy) };
  const issues = analyses.flatMap((a, i) => validateDiscoveryInput(a, `analyses[${i}]`));
  if (issues.length) throw new Error(`RESISTANCE_DISCOVERY_INVALID_INPUT: ${issues.join(' | ')}`);
  const observations = [];
  for (const analysis of analyses) {
    for (const constellation of analysis.constellations) observations.push(...observationFromConstellation(analysis, constellation, mergedPolicy));
  }
  const groups = new Map();
  for (const obs of observations) {
    const key = `${obs.source_id}\u241f${obs.selector}`;
    const arr = groups.get(key) ?? []; arr.push(obs); groups.set(key, arr);
  }
  const cases = [...groups.entries()].map(([key, obs]) => caseFromGroup(key, obs, registry, mergedPolicy)).filter(Boolean)
    .sort((a, b) => b.support.runs - a.support.runs || b.signals.distinct_unitizations - a.signals.distinct_unitizations || a.case_id.localeCompare(b.case_id));
  for (const c of cases) c.operator_delta_seed = createOperatorDeltaSeed(c);
  const sourceIds = uniq(analyses.map(a => a.source.source_id));
  const report = {
    resistance_discovery_version: DISCOVERY_VERSION,
    generated_at: new Date().toISOString(),
    discovery_contract: {
      same_selector_grouping: true,
      automatic_source_semantics_claimed: false,
      automatic_operator_acceptance: false,
      promotion_from_discovery_forbidden: true,
      structural_anomaly_is_not_philosophical_truth: true,
      source_text_embedded: false,
    },
    policy: mergedPolicy,
    input: {
      analyses: analyses.length,
      run_ids: uniq(analyses.map(a => a.run_id)),
      source_ids: sourceIds,
      same_source: sourceIds.length === 1,
      seeds: uniq(analyses.map(a => a.seed ?? 'NO_SEED')),
      runtimes: uniq(analyses.map(a => a.operator_registry?.runtime ?? 'UNKNOWN_RUNTIME')),
      observations: observations.length,
      selectors_observed: groups.size,
    },
    summary: {
      resistant_cases: cases.length,
      cases_with_target_hypothesis: cases.filter(c => c.target_hypothesis).length,
      cases_cross_runtime_only: cases.filter(c => c.support.cross_runtime_only).length,
    },
    cases,
    claim_ceiling: CLAIM_CEILING,
  };
  report.report_sha256 = hash({ ...report, generated_at: null, report_sha256: undefined });
  return report;
}

function list(values) { return values?.length ? values.map(v => `\`${v}\``).join(', ') : 'none'; }
export function renderResistanceDiscoveryMarkdown(report) {
  const lines = [
    '# Resistant-Source Discovery Report', '',
    `- Contract: \`${report.resistance_discovery_version}\``,
    `- Analyses: **${report.input.analyses}**`,
    `- Selectors observed: **${report.input.selectors_observed}**`,
    `- Resistant cases: **${report.summary.resistant_cases}**`,
    `- Same source across inputs: **${report.input.same_source}**`, '',
    '> This engine detects recurrent structural resistance, not the meaning of the source. A discovery case cannot promote itself and is not an operator-delta acceptance decision.', '',
  ];
  if (!report.cases.length) {
    lines.push('## Result', '', 'No selector met the configured recurrence + rival-unitization threshold.', '');
  }
  for (const c of report.cases) {
    lines.push(`## ${c.case_id}`, '',
      `- Source: \`${c.source_id}\``,
      `- Selector: \`${c.selector}\``,
      `- Runs: **${c.support.runs}**`,
      `- Seeds: ${list(c.support.seeds)}`,
      `- Runtimes: ${list(c.support.runtimes)}`,
      `- Distinct structural unitizations: **${c.signals.distinct_unitizations}**`,
      `- Resistance runs: **${c.signals.resistance_runs}**`,
      `- Residual runs: **${c.signals.residual_runs}**`,
      `- Revision-pressure runs: **${c.signals.revision_pressure_runs}**`,
      `- Cross-runtime only: **${c.support.cross_runtime_only}**`,
      `- Target hypothesis: ${c.target_hypothesis ? `\`${c.target_hypothesis.registry_section}/${c.target_hypothesis.operator_id}\` (${c.target_hypothesis.basis})` : 'unresolved'}`, '',
      '### Rival unitizations', '');
    for (const u of c.incompatible_unitizations) {
      lines.push(`- **${u.unitization_id}** — ${u.description}`, `  - consequence: ${u.analytic_consequence}`, `  - runs: ${list(u.support.run_ids)}`);
    }
    lines.push('', '### Review gate before any mutation', '');
    c.review_requirements.forEach((r, i) => lines.push(`${i + 1}. ${r}`));
    lines.push('');
  }
  lines.push('## Epistemic discipline', '',
    '1. Recurrence is evidence that the current analytical routing deserves review; it is not evidence that the source itself contains the inferred distinction.',
    '2. Rival structural signatures are candidate unitizations, not automatically valid interpretations.',
    '3. The generated `operator_delta_seed` is deliberately non-gateable and has `promotion_forbidden=true`.',
    '4. Only the existing mutation gate may produce an `ACCEPTED_CANDIDATE`, and only after source-grounded before/after and negative tests.', '',
    `Claim ceiling: \`${report.claim_ceiling}\``, '');
  return `${lines.join('\n')}\n`;
}
