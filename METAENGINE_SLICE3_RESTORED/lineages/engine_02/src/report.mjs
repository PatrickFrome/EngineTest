import path from "node:path";

function status(result) {
  if (!result.conformant) return "FAIL";
  if (result.review_required) return "PASS + HUMAN REVIEW";
  return "PASS";
}

export function formatValidationReport(report) {
  const lines = [];
  for (const result of report.results) {
    lines.push(`${status(result)}  ${result.record_id ?? path.basename(result.file)}  [E:${result.counts.ERROR} R:${result.counts.REVIEW} W:${result.counts.WARNING}]`);
    for (const item of result.issues) lines.push(`  ${item.severity.padEnd(7)} ${item.code} ${item.at} — ${item.message}`);
  }
  const c = report.counts;
  lines.push("");
  lines.push(`SUMMARY files=${c.files} conformant=${c.conformant} review_required=${c.review_required} errors=${c.ERROR} reviews=${c.REVIEW} warnings=${c.WARNING}`);
  return lines.join("\n");
}

export function formatRunReport(result) {
  const lines = [`${status(result)}  run=${result.run_id ?? path.basename(result.file)}  [E:${result.counts.ERROR} R:${result.counts.REVIEW} W:${result.counts.WARNING}]`];
  for (const item of result.issues) lines.push(`  ${item.severity.padEnd(7)} ${item.code} ${item.at} — ${item.message}`);
  for (const record of result.record_results ?? []) {
    lines.push(`  RECORD ${status(record)} ${record.record_id} [E:${record.counts.ERROR} R:${record.counts.REVIEW} W:${record.counts.WARNING}]`);
  }
  return lines.join("\n");
}

export function formatProtocolReport(result) {
  const lines = [`${result.outcome}  protocol=${result.protocol_id}  run=${result.run_id ?? path.basename(result.file)}  [E:${result.counts.ERROR} R:${result.counts.REVIEW} W:${result.counts.WARNING}]`];
  if (result.protocol_title) lines.push(`  ${result.protocol_title}`);
  for (const item of result.issues) lines.push(`  ${item.severity.padEnd(7)} ${item.code} ${item.at} — ${item.message}`);
  lines.push(`  Claim ceiling: ${result.claim_ceiling}.`);
  return lines.join("\n");
}
