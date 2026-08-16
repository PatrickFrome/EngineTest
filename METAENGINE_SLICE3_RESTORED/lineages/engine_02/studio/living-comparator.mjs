import { createHash } from 'node:crypto';

function sha256(text) { return createHash('sha256').update(text).digest('hex'); }
function histogram(items) {
  const out = {};
  for (const item of items.filter(v => v !== undefined && v !== null && v !== '')) out[item] = (out[item] ?? 0) + 1;
  return Object.fromEntries(Object.entries(out).sort(([a], [b]) => a.localeCompare(b)));
}
function keys(obj) { return Object.keys(obj ?? {}).sort(); }
function setDiff(a, b) { const bs = new Set(b); return a.filter(x => !bs.has(x)); }
function sum(obj) { return Object.values(obj ?? {}).reduce((a, b) => a + Number(b || 0), 0); }
function numericDelta(a, b) {
  const result = {};
  for (const key of [...new Set([...keys(a), ...keys(b)])].sort()) result[key] = Number(b?.[key] ?? 0) - Number(a?.[key] ?? 0);
  return result;
}
function stableStructuralView(summary) {
  return {
    counts: summary.counts,
    roles: summary.roles,
    generators: summary.generators,
    relations: summary.relations,
    residual_kinds: summary.residual_kinds,
    generative_gains: summary.generative_gains,
    openness: summary.openness,
    branch_pressure: summary.branch_pressure,
  };
}

export function summarizeLivingAnalysis(label, analysis) {
  if (!analysis?.graph?.nodes || !analysis?.graph?.edges) throw new Error(`${label}: invalid living analysis; graph.nodes/edges required`);
  const nodes = analysis.graph.nodes;
  const edges = analysis.graph.edges;
  const roles = histogram(nodes.map(n => n.role));
  const generators = histogram(nodes.map(n => n.generated_by));
  const relations = histogram(edges.map(e => e.relation));
  const residualKinds = histogram(nodes.map(n => n.residual_kind));
  const gains = histogram(nodes.flatMap(n => n.generative_gains ?? []));
  const activeGestureIds = keys(generators).filter(id => /^GX/i.test(id));
  const branchPressure = {
    research_branch_nodes: roles.RESEARCH_BRANCH ?? 0,
    revision_trigger_nodes: roles.REVISION_TRIGGER ?? 0,
    open_residual_nodes: roles.OPEN_RESIDUAL ?? 0,
    reverse_test_nodes: roles.REVERSE_TEST ?? 0,
    self_critique_nodes: roles.SELF_CRITIQUE ?? 0,
    mutation_nodes: roles.MUTATION ?? 0,
    cross_constellation_edges: relations.CROSSES_CONSTELLATION ?? 0,
    reopens_edges: relations.REOPENS ?? 0,
    mutates_into_edges: relations.MUTATES_INTO ?? 0,
    disputes_edges: relations.DISPUTES ?? 0,
  };
  const openness = {
    satisfied: Boolean(analysis.sufficient_openness?.satisfied),
    criteria: analysis.sufficient_openness?.criteria ?? {},
    missing: [...(analysis.sufficient_openness?.missing ?? [])].sort(),
  };
  const summary = {
    label,
    run_id: analysis.run_id ?? null,
    seed: analysis.seed ?? null,
    runtime: analysis.operator_registry?.runtime ?? null,
    registry_sha256: analysis.operator_registry?.sha256 ?? null,
    counts: {
      constellations: analysis.constellations?.length ?? 0,
      nodes: nodes.length,
      edges: edges.length,
      retired_operators: analysis.graph.retired_operators?.length ?? 0,
      activated_family_slots: (analysis.constellations ?? []).reduce((n, c) => n + (c.activated_families?.length ?? 0), 0),
    },
    roles,
    generators,
    active_gesture_ids: activeGestureIds,
    relations,
    residual_kinds: residualKinds,
    generative_gains: gains,
    branch_pressure: branchPressure,
    openness,
  };
  summary.structural_fingerprint_sha256 = sha256(JSON.stringify(stableStructuralView(summary)));
  return summary;
}

export function compareLivingPair(from, to) {
  return {
    from: from.label,
    to: to.label,
    structural_change: from.structural_fingerprint_sha256 !== to.structural_fingerprint_sha256,
    counts_delta: numericDelta(from.counts, to.counts),
    branch_pressure_delta: numericDelta(from.branch_pressure, to.branch_pressure),
    added_roles: setDiff(keys(to.roles), keys(from.roles)),
    removed_roles: setDiff(keys(from.roles), keys(to.roles)),
    role_count_delta: numericDelta(from.roles, to.roles),
    added_generators: setDiff(keys(to.generators), keys(from.generators)),
    removed_generators: setDiff(keys(from.generators), keys(to.generators)),
    generator_count_delta: numericDelta(from.generators, to.generators),
    added_relations: setDiff(keys(to.relations), keys(from.relations)),
    removed_relations: setDiff(keys(from.relations), keys(to.relations)),
    relation_count_delta: numericDelta(from.relations, to.relations),
    added_residual_kinds: setDiff(keys(to.residual_kinds), keys(from.residual_kinds)),
    removed_residual_kinds: setDiff(keys(from.residual_kinds), keys(to.residual_kinds)),
    gain_count_delta: numericDelta(from.generative_gains, to.generative_gains),
    openness: {
      from_satisfied: from.openness.satisfied,
      to_satisfied: to.openness.satisfied,
      newly_satisfied_criteria: keys(to.openness.criteria).filter(k => to.openness.criteria[k] && !from.openness.criteria[k]),
      newly_missing_criteria: keys(from.openness.criteria).filter(k => from.openness.criteria[k] && !to.openness.criteria[k]),
    },
  };
}

export function compareLivingAnalyses({ baseline, declarative, mutant }) {
  const summaries = {
    baseline: summarizeLivingAnalysis('baseline', baseline),
    declarative: summarizeLivingAnalysis('declarative', declarative),
    mutant: summarizeLivingAnalysis('mutant', mutant),
  };
  const sameSeed = new Set(Object.values(summaries).map(s => s.seed)).size === 1;
  const result = {
    living_comparison_version: 'DAE-LIVING-COMPARISON-1.0',
    comparison_contract: {
      same_source_required: true,
      same_seed_required: true,
      same_seed_observed: sameSeed,
      interpretation: 'Structural difference is evidence of changed analytical movement, not evidence of philosophical superiority or truth.',
    },
    summaries,
    transitions: {
      baseline_to_declarative: compareLivingPair(summaries.baseline, summaries.declarative),
      declarative_to_mutant: compareLivingPair(summaries.declarative, summaries.mutant),
      baseline_to_mutant: compareLivingPair(summaries.baseline, summaries.mutant),
    },
  };
  result.mutation_effect_observed = result.transitions.declarative_to_mutant.structural_change;
  result.structural_diversity = new Set(Object.values(summaries).map(s => s.structural_fingerprint_sha256)).size;
  return result;
}

function signed(n) { return n > 0 ? `+${n}` : String(n); }
function compactNonzero(obj) {
  const entries = Object.entries(obj ?? {}).filter(([, v]) => Number(v) !== 0);
  return entries.length ? entries.map(([k, v]) => `\`${k}\` ${signed(v)}`).join(', ') : 'none';
}
function list(items) { return items?.length ? items.map(x => `\`${x}\``).join(', ') : 'none'; }

export function renderLivingComparisonMarkdown(comparison) {
  const { summaries: s, transitions: t } = comparison;
  const lines = [
    '# Living Runtime A/B/C Comparison', '',
    `- Contract: \`${comparison.living_comparison_version}\``,
    `- Same seed observed: **${comparison.comparison_contract.same_seed_observed}**`,
    `- Structural diversity: **${comparison.structural_diversity}/3**`,
    `- Declarative mutation effect observed: **${comparison.mutation_effect_observed}**`, '',
    '> Structural change is not a truth score. The report asks whether the grammar of analytical movement changed under controlled source/seed conditions.', '',
    '## Runtime summaries', '',
    '| Mode | Runtime | Nodes | Edges | Constellations | Open | Structural fingerprint |',
    '|---|---|---:|---:|---:|---|---|',
  ];
  for (const key of ['baseline', 'declarative', 'mutant']) {
    const x = s[key];
    lines.push(`| ${key} | \`${x.runtime ?? 'unknown'}\` | ${x.counts.nodes} | ${x.counts.edges} | ${x.counts.constellations} | ${x.openness.satisfied} | \`${x.structural_fingerprint_sha256.slice(0, 12)}…\` |`);
  }
  lines.push('', '## Controlled transitions', '');
  for (const [name, x] of Object.entries(t)) {
    lines.push(`### ${name.replaceAll('_', ' → ')}`, '');
    lines.push(`- Structural change: **${x.structural_change}**`);
    lines.push(`- Count deltas: ${compactNonzero(x.counts_delta)}`);
    lines.push(`- Branch/revision deltas: ${compactNonzero(x.branch_pressure_delta)}`);
    lines.push(`- Added generators: ${list(x.added_generators)}`);
    lines.push(`- Removed generators: ${list(x.removed_generators)}`);
    lines.push(`- Added roles: ${list(x.added_roles)}`);
    lines.push(`- Removed roles: ${list(x.removed_roles)}`);
    lines.push(`- Added relations: ${list(x.added_relations)}`);
    lines.push(`- Removed relations: ${list(x.removed_relations)}`);
    lines.push(`- Newly satisfied openness criteria: ${list(x.openness.newly_satisfied_criteria)}`);
    lines.push(`- Newly missing openness criteria: ${list(x.openness.newly_missing_criteria)}`, '');
  }
  lines.push('## Interpretation discipline', '',
    '1. More nodes or edges do not count as a gain by themselves.',
    '2. A mutation is behaviorally visible only when the declarative → mutant structural fingerprint changes.',
    '3. Loss of roles, residual kinds, reverse pressure or reopening conditions is recorded as a cost, not hidden by aggregate growth.',
    '4. Philosophical evaluation still requires source-grounded review; this comparator measures runtime behavior only.', '');
  return `${lines.join('\n')}\n`;
}
