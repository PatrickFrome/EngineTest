const RANK = { ERROR: 0, REVIEW: 1, WARNING: 2, INFO: 3 };

export function issue(severity, code, at, message, details = undefined) {
  return { severity, code, at, message, ...(details === undefined ? {} : { details }) };
}

export function sortIssues(issues) {
  return [...issues].sort((a, b) =>
    (RANK[a.severity] ?? 9) - (RANK[b.severity] ?? 9) ||
    a.code.localeCompare(b.code) ||
    a.at.localeCompare(b.at),
  );
}

export function countIssues(issues) {
  const counts = { ERROR: 0, REVIEW: 0, WARNING: 0, INFO: 0 };
  for (const item of issues) counts[item.severity] = (counts[item.severity] ?? 0) + 1;
  return counts;
}
