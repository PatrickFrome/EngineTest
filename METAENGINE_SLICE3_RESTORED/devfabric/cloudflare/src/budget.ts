export const FREE_LIMITS = Object.freeze({
  workerRequestsPerDay: 100_000,
  workerCpuMsPerInvocation: 10,
  d1RowsReadPerDay: 5_000_000,
  d1RowsWrittenPerDay: 100_000,
  d1StorageGb: 5,
  r2StorageGbMonth: 10,
  r2ClassAPerMonth: 1_000_000,
  r2ClassBPerMonth: 10_000_000,
  workflowStepsPerDay: 3_000,
  workflowStorageGbMonth: 1,
  workersAiNeuronsPerDay: 10_000,
});

export type BudgetSnapshot = {
  workerRequestsRemaining?: number | null;
  d1RowsReadRemaining?: number | null;
  d1RowsWrittenRemaining?: number | null;
  r2ClassARemaining?: number | null;
  r2ClassBRemaining?: number | null;
  workflowStepsRemaining?: number | null;
  workersAiNeuronsRemaining?: number | null;
};

export type BudgetCost = {
  workerRequests?: number;
  d1RowsRead?: number;
  d1RowsWritten?: number;
  r2ClassA?: number;
  r2ClassB?: number;
  workflowSteps?: number;
  workersAiNeurons?: number;
};

const mappings: Array<[keyof BudgetCost, keyof BudgetSnapshot]> = [
  ['workerRequests', 'workerRequestsRemaining'],
  ['d1RowsRead', 'd1RowsReadRemaining'],
  ['d1RowsWritten', 'd1RowsWrittenRemaining'],
  ['r2ClassA', 'r2ClassARemaining'],
  ['r2ClassB', 'r2ClassBRemaining'],
  ['workflowSteps', 'workflowStepsRemaining'],
  ['workersAiNeurons', 'workersAiNeuronsRemaining'],
];

export function budgetDecision(snapshot: BudgetSnapshot, cost: BudgetCost): { eligible: boolean; reason: 'OK' | 'QUOTA_UNKNOWN' | 'QUOTA_EXHAUSTED' } {
  for (const [costKey, remainingKey] of mappings) {
    const requested = cost[costKey] ?? 0;
    if (requested <= 0) continue;
    const remaining = snapshot[remainingKey];
    if (remaining === null || remaining === undefined) return { eligible: false, reason: 'QUOTA_UNKNOWN' };
    if (remaining < requested) return { eligible: false, reason: 'QUOTA_EXHAUSTED' };
  }
  return { eligible: true, reason: 'OK' };
}
