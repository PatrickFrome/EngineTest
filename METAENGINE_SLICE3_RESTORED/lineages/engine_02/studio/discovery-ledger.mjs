import { createHash } from 'node:crypto';

function hash(value) { return createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex'); }
function uniq(values) { return [...new Set(values.filter(v => v !== undefined && v !== null && v !== ''))].sort(); }

function occurrenceFingerprint(discoveryCase, context) {
  return hash({
    case_id: discoveryCase.case_id,
    report_sha256: context.report_sha256,
    run_ids: discoveryCase.support.run_ids,
    signatures: discoveryCase.incompatible_unitizations.map(u => u.signature_sha256).sort(),
  });
}

export function mergeDiscoveryLedger(existing, report, context = {}) {
  const now = context.generated_at || report.generated_at || new Date().toISOString();
  const ledger = existing && existing.discovery_ledger_version === 'DAE-RESISTANCE-CASE-LEDGER-1.0'
    ? structuredClone(existing)
    : { discovery_ledger_version: 'DAE-RESISTANCE-CASE-LEDGER-1.0', created_at: now, updated_at: now, cases: {} };
  ledger.updated_at = now;
  for (const c of report.cases ?? []) {
    const prior = ledger.cases[c.case_id] ?? {
      case_id: c.case_id,
      source_id: c.source_id,
      selector: c.selector,
      first_seen: now,
      last_seen: now,
      occurrences: [],
      unique_run_ids: [],
      unique_seeds: [],
      unique_runtimes: [],
      unitization_signatures: [],
      target_history: [],
    };
    const fingerprint = occurrenceFingerprint(c, { ...context, report_sha256: report.report_sha256 });
    if (!prior.occurrences.some(o => o.occurrence_fingerprint_sha256 === fingerprint)) {
      prior.occurrences.push({
        occurrence_fingerprint_sha256: fingerprint,
        report_sha256: report.report_sha256,
        session_id: context.session_id ?? null,
        observed_at: now,
        run_ids: c.support.run_ids,
        seeds: c.support.seeds,
        runtimes: c.support.runtimes,
        cross_runtime_only: c.support.cross_runtime_only,
        distinct_unitizations: c.signals.distinct_unitizations,
        resistance_runs: c.signals.resistance_runs,
        residual_runs: c.signals.residual_runs,
        revision_pressure_runs: c.signals.revision_pressure_runs,
        unitization_signatures: c.incompatible_unitizations.map(u => u.signature_sha256).sort(),
        target_hypothesis: c.target_hypothesis,
      });
    }
    prior.last_seen = now;
    prior.unique_run_ids = uniq([...prior.unique_run_ids, ...c.support.run_ids]);
    prior.unique_seeds = uniq([...prior.unique_seeds, ...c.support.seeds]);
    prior.unique_runtimes = uniq([...prior.unique_runtimes, ...c.support.runtimes]);
    prior.unitization_signatures = uniq([...prior.unitization_signatures, ...c.incompatible_unitizations.map(u => u.signature_sha256)]);
    if (c.target_hypothesis) {
      const targetKey = `${c.target_hypothesis.registry_section}/${c.target_hypothesis.operator_id}/${c.target_hypothesis.basis}`;
      if (!prior.target_history.some(t => t.key === targetKey)) prior.target_history.push({ key: targetKey, ...c.target_hypothesis, first_seen: now });
    }
    prior.occurrence_count = prior.occurrences.length;
    prior.recurrence_state = prior.occurrence_count >= 2 && prior.unique_run_ids.length >= 3
      ? 'RECURRING_ACROSS_DISCOVERY_SESSIONS'
      : 'DISCOVERED_NOT_YET_LONGITUDINALLY_RECURRING';
    prior.claim_ceiling = 'LONGITUDINAL_STRUCTURAL_RECURRENCE_NOT_SOURCE_SEMANTICS_OR_MUTATION_VALIDITY';
    ledger.cases[c.case_id] = prior;
  }
  ledger.case_count = Object.keys(ledger.cases).length;
  ledger.recurring_case_count = Object.values(ledger.cases).filter(c => c.recurrence_state === 'RECURRING_ACROSS_DISCOVERY_SESSIONS').length;
  return ledger;
}

function list(values) { return values?.length ? values.map(v => `\`${v}\``).join(', ') : 'none'; }
export function renderDiscoveryLedgerMarkdown(ledger) {
  const cases = Object.values(ledger.cases ?? {}).sort((a, b) => b.occurrence_count - a.occurrence_count || a.case_id.localeCompare(b.case_id));
  const lines = [
    '# Resistant-Source Case Ledger', '',
    `- Contract: \`${ledger.discovery_ledger_version}\``,
    `- Cases: **${ledger.case_count ?? cases.length}**`,
    `- Longitudinally recurring: **${ledger.recurring_case_count ?? 0}**`, '',
    '> The ledger deduplicates identical discovery evidence. Recurrence means the structural anomaly returned in distinct run evidence; it still does not establish source meaning or validate a mutation.', '',
  ];
  for (const c of cases) {
    lines.push(`## ${c.case_id}`, '',
      `- State: **${c.recurrence_state}**`,
      `- Source: \`${c.source_id}\``,
      `- Selector: \`${c.selector}\``,
      `- Discovery occurrences: **${c.occurrence_count}**`,
      `- Unique runs: **${c.unique_run_ids.length}**`,
      `- Seeds: ${list(c.unique_seeds)}`,
      `- Runtimes: ${list(c.unique_runtimes)}`,
      `- Rival signatures seen: **${c.unitization_signatures.length}**`,
      `- Target hypotheses: ${c.target_history.length ? c.target_history.map(t => `\`${t.registry_section}/${t.operator_id}\``).join(', ') : 'none'}`, '');
  }
  return `${lines.join('\n')}\n`;
}
