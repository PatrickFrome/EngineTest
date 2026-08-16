import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { countIssues, issue, sortIssues } from "./issues.mjs";
import { readJson } from "./paths.mjs";

function finish(file, run, protocol, issues, flags) {
  const sorted = sortIssues(issues);
  const counts = countIssues(sorted);
  let outcome = counts.ERROR ? "FAIL" : flags.suspend ? "SUSPEND" : counts.REVIEW ? "REVIEW" : "PASS";
  if (run.declared_outcome && run.declared_outcome !== outcome) {
    sorted.push(issue("ERROR", "PROTOCOL_OUTCOME_MISMATCH", "/declared_outcome", `Declared ${run.declared_outcome}, derived ${outcome}.`));
    outcome = "FAIL";
  }
  const finalIssues = sortIssues(sorted);
  return {
    file,
    run_id: run.run_id ?? null,
    protocol_id: protocol?.id ?? run.protocol_id ?? null,
    protocol_title: protocol?.title_ru ?? null,
    outcome,
    conformant: !finalIssues.some((item) => item.severity === "ERROR"),
    review_required: finalIssues.some((item) => item.severity === "REVIEW"),
    counts: countIssues(finalIssues),
    issues: finalIssues,
    claim_ceiling: "PROTOCOL_CONFORMANCE_AND_REVIEW_ROUTING_ONLY",
  };
}

export async function validateProtocolRun(engine, runFile) {
  const absolute = path.resolve(runFile);
  const run = await readJson(absolute);
  const issues = [...engine.structural.validateProtocolRun(run)];
  const registry = engine.context.protocolRegistry;
  const protocol = registry.protocols.find((item) => item.id === run.protocol_id);
  const flags = { suspend: false };
  if (issues.length) return finish(absolute, run, protocol, issues, flags);

  if (!protocol) {
    issues.push(issue("ERROR", "UNKNOWN_PROTOCOL", "/protocol_id", `${run.protocol_id} is absent from ${registry.registry_version}.`));
    return finish(absolute, run, null, issues, flags);
  }
  if (run.protocol_version !== protocol.version) {
    issues.push(issue("ERROR", "PROTOCOL_VERSION_MISMATCH", "/protocol_version", `Run uses ${run.protocol_version}; registry requires ${protocol.version}.`));
  }
  if (protocol.status === "OPTIONAL_ARCHIVAL_DERIVATIVE" && run.mode !== "ARCHIVAL_REVIEW") {
    issues.push(issue("ERROR", "ARCHIVAL_PROTOCOL_MODE_REQUIRED", "/mode", "An archival derivative cannot silently become active policy; use ARCHIVAL_REVIEW explicitly."));
  }

  const checkIds = new Set(protocol.checks.map((check) => check.id));
  for (const answerId of Object.keys(run.answers)) {
    if (!checkIds.has(answerId)) issues.push(issue("ERROR", "UNKNOWN_PROTOCOL_CHECK", `/answers/${answerId}`, `Check ${answerId} is not defined by ${protocol.id}.`));
  }

  for (const check of protocol.checks) {
    const answer = run.answers[check.id];
    const at = `/answers/${check.id}`;
    if (!answer) {
      if (check.required) issues.push(issue("ERROR", "PROTOCOL_ANSWER_MISSING", at, `Required check is unanswered: ${check.prompt}`));
      continue;
    }
    if (answer.status === "NA") {
      if (!answer.note?.trim()) issues.push(issue("ERROR", "PROTOCOL_NA_REASON_REQUIRED", `${at}/note`, "NA requires an explicit applicability rationale."));
      if (check.required) issues.push(issue("REVIEW", "PROTOCOL_REQUIRED_CHECK_NA", at, `Required check marked NA: ${check.prompt}`));
      continue;
    }
    if (answer.status === "UNKNOWN") {
      flags.suspend = true;
      issues.push(issue("REVIEW", "PROTOCOL_CHECK_UNKNOWN", at, `Required evidence or judgment is unresolved: ${check.prompt}`));
      continue;
    }
    if (answer.status === "YES" && check.evidence_required && !(answer.evidence_refs?.length)) {
      issues.push(issue("ERROR", "PROTOCOL_EVIDENCE_REQUIRED", `${at}/evidence_refs`, `YES requires at least one evidence reference: ${check.prompt}`));
    }
    if (check.human_judgment && answer.status === "YES") {
      if (!answer.reviewed_by || !answer.reviewed_at) {
        issues.push(issue("REVIEW", "HUMAN_JUDGMENT_UNATTESTED", at, `Interpretive check needs reviewer identity and timestamp: ${check.prompt}`));
      }
    }
    if (answer.status === "NO") {
      if (check.on_no === "FAIL") issues.push(issue("ERROR", "PROTOCOL_BLOCKING_FAILURE", at, check.prompt));
      else {
        if (check.on_no === "SUSPEND") flags.suspend = true;
        issues.push(issue("REVIEW", check.on_no === "SUSPEND" ? "PROTOCOL_SUSPENDED" : "PROTOCOL_NEGATIVE_REVIEW", at, check.prompt));
      }
    }
  }

  if (run.deviations?.length) {
    issues.push(issue("REVIEW", "PROTOCOL_DEVIATIONS_RECORDED", "/deviations", `${run.deviations.length} deviation(s) require impact review.`));
  }
  return finish(absolute, run, protocol, issues, flags);
}

export async function initProtocolRun(engine, protocolId, outputFile) {
  const protocol = engine.context.protocolRegistry.protocols.find((item) => item.id === protocolId);
  if (!protocol) throw new Error(`Unknown protocol '${protocolId}'.`);
  const absolute = path.resolve(outputFile);
  await mkdir(path.dirname(absolute), { recursive: true });
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const template = {
    run_version: "DAE-PROTOCOL-RUN-1.0",
    run_id: `${protocol.id}-RUN-001`,
    protocol_id: protocol.id,
    protocol_version: protocol.version,
    subject: { id: "REPLACE-ME", description: "Describe the exact claim, case or research object.", source_refs: [] },
    operator: { agent_id: "REPLACE-ME", role: "researcher" },
    started_at: now,
    mode: protocol.status === "OPTIONAL_ARCHIVAL_DERIVATIVE" ? "ARCHIVAL_REVIEW" : "NORMAL",
    answers: Object.fromEntries(protocol.checks.map((check) => [check.id, {
      status: "UNKNOWN",
      evidence_refs: [],
      note: check.prompt,
    }])),
  };
  await writeFile(absolute, `${JSON.stringify(template, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
  return { output_file: absolute, protocol };
}
