import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeDiscoveryLedger } from '../../studio/discovery-ledger.mjs';

function report(runIds, sha = 'report-a') {
  return {
    generated_at: '2026-08-11T00:00:00Z', report_sha256: sha,
    cases: [{
      case_id: 'RSC-X', source_id: 'SRC', selector: 'span:1',
      support: { run_ids: runIds, seeds: runIds.map(x => `seed-${x}`), runtimes: ['DECL'], cross_runtime_only: false },
      signals: { distinct_unitizations: 2, resistance_runs: runIds.length, residual_runs: runIds.length, revision_pressure_runs: runIds.length },
      incompatible_unitizations: [{ signature_sha256: 'u1' }, { signature_sha256: 'u2' }],
      target_hypothesis: { registry_section: 'generative_gestures', operator_id: 'GX1', basis: 'COMMON' },
    }],
  };
}

test('ledger records first discovery without pretending longitudinal recurrence', () => {
  const ledger = mergeDiscoveryLedger(null, report(['R1', 'R2']), { session_id: 'S1' });
  assert.equal(ledger.cases['RSC-X'].occurrence_count, 1);
  assert.equal(ledger.cases['RSC-X'].recurrence_state, 'DISCOVERED_NOT_YET_LONGITUDINALLY_RECURRING');
});

test('identical report evidence is deduplicated', () => {
  let ledger = mergeDiscoveryLedger(null, report(['R1', 'R2'], 'same'), { session_id: 'S1' });
  ledger = mergeDiscoveryLedger(ledger, report(['R1', 'R2'], 'same'), { session_id: 'S2' });
  assert.equal(ledger.cases['RSC-X'].occurrence_count, 1);
});

test('new independent run evidence upgrades recurrence state', () => {
  let ledger = mergeDiscoveryLedger(null, report(['R1', 'R2'], 'a'), { session_id: 'S1' });
  ledger = mergeDiscoveryLedger(ledger, report(['R2', 'R3'], 'b'), { session_id: 'S2' });
  assert.equal(ledger.cases['RSC-X'].occurrence_count, 2);
  assert.equal(ledger.cases['RSC-X'].unique_run_ids.length, 3);
  assert.equal(ledger.cases['RSC-X'].recurrence_state, 'RECURRING_ACROSS_DISCOVERY_SESSIONS');
  assert.equal(ledger.recurring_case_count, 1);
});
