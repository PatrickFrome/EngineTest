import path from "node:path";
import { countIssues, issue, sortIssues } from "./issues.mjs";
import { readJson } from "./paths.mjs";

function applicable(argument, claims, scheme, issues, index) {
  let ready = true;
  for (const [premiseIndex, premise] of argument.premises.entries()) {
    const claim = claims.get(premise.claim_id);
    if (!claim) {
      issues.push(issue("ERROR", "ARGUMENT_PREMISE_UNKNOWN", `/arguments/${index}/premises/${premiseIndex}/claim_id`, `${premise.claim_id} is not a claim in this bundle.`));
      ready = false;
      continue;
    }
    if (premise.role === "EXCEPTION") {
      if (claim.status === "ACCEPTED") ready = false;
    } else if (claim.status !== "ACCEPTED") {
      ready = false;
      issues.push(issue("REVIEW", "ARGUMENT_PREMISE_NOT_ACCEPTED", `/arguments/${index}/premises/${premiseIndex}`, `${premise.claim_id} is ${claim.status}; the argument is not currently applicable.`));
    }
  }
  const supplied = new Map(argument.critical_questions.map((question) => [question.id, question]));
  for (const required of scheme.critical_questions) {
    const answer = supplied.get(required.id);
    if (!answer) {
      issues.push(issue("ERROR", "CRITICAL_QUESTION_MISSING", `/arguments/${index}/critical_questions`, `${required.id} is required by ${scheme.id}.`));
      ready = false;
    } else if (answer.status === "OPEN") {
      issues.push(issue("REVIEW", "CRITICAL_QUESTION_OPEN", `/arguments/${index}/critical_questions/${required.id}`, required.prompt));
      ready = false;
    } else if (answer.status === "ANSWERED" && !(answer.evidence_refs?.length)) {
      issues.push(issue("REVIEW", "CRITICAL_QUESTION_EVIDENCE_MISSING", `/arguments/${index}/critical_questions/${required.id}/evidence_refs`, `Answered ${required.id} has no evidence reference.`));
      ready = false;
    }
  }
  for (const question of argument.critical_questions) {
    if (!scheme.critical_questions.some((required) => required.id === question.id)) {
      issues.push(issue("WARNING", "CRITICAL_QUESTION_UNREGISTERED", `/arguments/${index}/critical_questions/${question.id}`, `${question.id} is not registered for ${scheme.id}.`));
    }
  }
  return ready;
}

export async function validateArgumentBundle(engine, bundleFile) {
  const absolute = path.resolve(bundleFile);
  const bundle = await readJson(absolute);
  const issues = [...engine.structural.validateArgumentBundle(bundle)];
  if (issues.length) return finish(absolute, bundle, issues, []);

  const claimIds = bundle.claims.map((claim) => claim.id);
  const argumentIds = bundle.arguments.map((argument) => argument.id);
  if (new Set(claimIds).size !== claimIds.length) issues.push(issue("ERROR", "DUPLICATE_CLAIM_ID", "/claims", "Claim identifiers must be unique."));
  if (new Set(argumentIds).size !== argumentIds.length) issues.push(issue("ERROR", "DUPLICATE_ARGUMENT_ID", "/arguments", "Argument identifiers must be unique."));
  const claims = new Map(bundle.claims.map((claim) => [claim.id, claim]));
  const schemes = new Map(engine.context.argumentSchemeRegistry.schemes.map((scheme) => [scheme.id, scheme]));
  const evaluated = [];

  for (const [index, argument] of bundle.arguments.entries()) {
    const scheme = schemes.get(argument.scheme_id);
    if (!claims.has(argument.conclusion)) issues.push(issue("ERROR", "ARGUMENT_CONCLUSION_UNKNOWN", `/arguments/${index}/conclusion`, `${argument.conclusion} is absent from claims.`));
    if (!scheme) {
      issues.push(issue("ERROR", "ARGUMENT_SCHEME_UNKNOWN", `/arguments/${index}/scheme_id`, `${argument.scheme_id} is absent from the scheme registry.`));
      evaluated.push({ argument_id: argument.id, applicable: false });
      continue;
    }
    evaluated.push({ argument_id: argument.id, applicable: applicable(argument, claims, scheme, issues, index), direction: argument.direction, conclusion: argument.conclusion, scheme_id: scheme.id });
  }

  const issueResults = [];
  for (const [index, item] of bundle.issues.entries()) {
    if (!claims.has(item.claim_id)) {
      issues.push(issue("ERROR", "ISSUE_CLAIM_UNKNOWN", `/issues/${index}/claim_id`, `${item.claim_id} is absent from claims.`));
      continue;
    }
    const relevant = evaluated.filter((argument) => argument.conclusion === item.claim_id && argument.applicable);
    const pro = relevant.filter((argument) => argument.direction === "PRO");
    const con = relevant.filter((argument) => argument.direction === "CON");
    let status;
    if (item.proof_standard === "SCINTILLA") status = pro.length ? (con.length ? "CONTESTED" : "SUPPORTED") : con.length ? "REJECTED" : "UNSUPPORTED";
    else status = pro.length && !con.length ? "SUPPORTED" : con.length && !pro.length ? "REJECTED" : pro.length && con.length ? "CONTESTED" : "UNSUPPORTED";
    if (evaluated.some((argument) => argument.conclusion === item.claim_id && !argument.applicable) && ["UNSUPPORTED", "CONTESTED"].includes(status)) status = "SUSPENDED";
    if (item.declared_status && item.declared_status !== status) issues.push(issue("ERROR", "ARGUMENT_STATUS_MISMATCH", `/issues/${index}/declared_status`, `Declared ${item.declared_status}, graph derives ${status}.`));
    issueResults.push({ claim_id: item.claim_id, proof_standard: item.proof_standard, status, applicable_pro: pro.map((argument) => argument.argument_id), applicable_con: con.map((argument) => argument.argument_id) });
  }
  return finish(absolute, bundle, issues, issueResults, evaluated);
}

function finish(file, bundle, issues, issueResults, argumentsEvaluated = []) {
  const sorted = sortIssues(issues);
  return {
    file,
    bundle_id: bundle?.bundle_id ?? null,
    conformant: !sorted.some((item) => item.severity === "ERROR"),
    review_required: sorted.some((item) => item.severity === "REVIEW") || issueResults.some((item) => ["CONTESTED", "SUSPENDED", "UNSUPPORTED"].includes(item.status)),
    counts: countIssues(sorted),
    issues: sorted,
    issue_results: issueResults,
    arguments_evaluated: argumentsEvaluated,
    claim_ceiling: "GRAPH_INTERNAL_ACCEPTABILITY_NOT_TRUTH",
  };
}
