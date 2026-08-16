import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { projectPath } from "./paths.mjs";

async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

function resolveAgainst(base, value) {
  return path.isAbsolute(value) ? value : path.resolve(base, value);
}

function sourceCandidate(bank) {
  const sourceHypothesis = (bank.hypotheses ?? []).find((item) => item.origin === "SOURCE_FORCED_REGISTRY_RESISTANCE");
  return sourceHypothesis?.operator_candidate ?? bank.source_resistance?.operator_candidate ?? {
    family: "UNRESOLVED",
    candidate: "UNRESOLVED",
    profile_hints: [],
  };
}

function mutationFound(living, candidateOperator) {
  return (living.method_mutations ?? []).some((mutation) => mutation.candidate === candidateOperator);
}

function corpusChecks(entry, bank, living, candidateOperator) {
  const resistance = bank.source_resistance ?? {};
  const candidate = sourceCandidate(bank);
  const hints = candidate.profile_hints ?? [];
  const found = mutationFound(living, candidateOperator);
  const checks = [];
  const add = (check, passed, observed, expected) => checks.push({ check, passed, observed: String(observed), expected: String(expected) });

  add(
    "SOURCE_CENTRALITY_AVAILABLE",
    (resistance.central_terms ?? []).length >= 3,
    (resistance.central_terms ?? []).length,
    ">=3 source-central terms"
  );
  add(
    "CANDIDATE_MUTATION_EXPECTATION",
    found === entry.expected_mutation,
    found,
    entry.expected_mutation
  );
  for (const expectedHint of entry.expected_profile_hints ?? []) {
    add(
      `PROFILE_HINT_${expectedHint}`,
      hints.includes(expectedHint),
      hints.join(",") || "NONE",
      expectedHint
    );
  }
  if (entry.control_role === "NEGATIVE_CONTROL") {
    add(
      "NEGATIVE_CONTROL_DISCRIMINATION",
      candidate.candidate !== candidateOperator && !found,
      `${candidate.candidate}; mutation=${found}`,
      `candidate != ${candidateOperator}; mutation=false`
    );
  }
  if (["ORIGIN_POSITIVE", "TRANSFER_POSITIVE"].includes(entry.control_role)) {
    add(
      "POSITIVE_TRANSFER_ACTIVATION",
      candidate.candidate === candidateOperator && found,
      `${candidate.candidate}; mutation=${found}`,
      `${candidateOperator}; mutation=true`
    );
  }
  if (entry.control_role === "MIXED_CONTROL") {
    add(
      "MIXED_CONTROL_NON_COLLAPSE",
      hints.includes("LOCAL_MODE_VARIATION") || hints.includes("ASYMMETRIC_DEPENDENCE"),
      hints.join(",") || "NONE",
      "LOCAL_MODE_VARIATION or ASYMMETRIC_DEPENDENCE"
    );
  }

  return {
    corpus_id: entry.corpus_id,
    label: entry.label,
    control_role: entry.control_role,
    central_terms: resistance.central_terms ?? [],
    coverage_ratio: Number(resistance.coverage_ratio ?? 1),
    operator_candidate: candidate.candidate ?? "UNRESOLVED",
    profile_hints: hints,
    candidate_mutation_found: found,
    expectation_pass: checks.every((item) => item.passed),
    checks,
  };
}

export function decideOperatorRegressionOutcome(entries, results) {
  const byId = new Map(results.map((item) => [item.corpus_id, item]));
  const origin = entries.filter((entry) => entry.control_role === "ORIGIN_POSITIVE").map((entry) => byId.get(entry.corpus_id));
  const transfers = entries.filter((entry) => entry.control_role === "TRANSFER_POSITIVE").map((entry) => byId.get(entry.corpus_id));
  const negatives = entries.filter((entry) => entry.control_role === "NEGATIVE_CONTROL").map((entry) => byId.get(entry.corpus_id));
  const mixed = entries.filter((entry) => entry.control_role === "MIXED_CONTROL").map((entry) => byId.get(entry.corpus_id));
  const originPassed = origin.length > 0 && origin.every((item) => item?.expectation_pass);
  const positiveTransferPassed = transfers.filter((item) => item?.expectation_pass).length;
  const negativePassed = negatives.filter((item) => item?.expectation_pass).length;
  const mixedPassed = mixed.filter((item) => item?.expectation_pass).length;
  const overgeneralization = negatives.some((item) => item?.candidate_mutation_found);

  let outcome = "REVIEW_MIXED";
  if (overgeneralization) outcome = "QUARANTINE_OVERGENERALIZATION";
  else if (!positiveTransferPassed) outcome = "RETIRE_NO_TRANSFER";
  else if (originPassed
    && positiveTransferPassed === transfers.length
    && negativePassed === negatives.length
    && mixedPassed === mixed.length
    && results.every((item) => item.expectation_pass)) outcome = "SURVIVES_CROSS_CORPUS_REGRESSION";

  const actionByOutcome = {
    SURVIVES_CROSS_CORPUS_REGRESSION: {
      recommended_action: "RETAIN_EXPERIMENTAL_FOR_FURTHER_REGRESSION",
      operator_state: "EXPERIMENTAL_TRANSFERABLE",
    },
    QUARANTINE_OVERGENERALIZATION: {
      recommended_action: "QUARANTINE_FROM_DEFAULT_ROUTING",
      operator_state: "QUARANTINED",
    },
    RETIRE_NO_TRANSFER: {
      recommended_action: "RETIRE_CANDIDATE",
      operator_state: "RETIRED",
    },
    REVIEW_MIXED: {
      recommended_action: "REVISE_AND_RERUN",
      operator_state: "EXPERIMENTAL_UNRESOLVED",
    },
  };

  return {
    outcome,
    ...actionByOutcome[outcome],
    summary: {
      corpora: results.length,
      expectations_passed: results.filter((item) => item.expectation_pass).length,
      positive_transfer_passed: positiveTransferPassed,
      negative_controls_passed: negativePassed,
      mixed_controls_passed: mixedPassed,
      origin_passed: originPassed,
      overgeneralization_detected: overgeneralization,
    },
  };
}

function renderMarkdown(result) {
  const rows = result.corpus_results.map((item) => `| ${item.corpus_id} | ${item.control_role} | ${item.central_terms.length} | ${item.operator_candidate} | ${item.profile_hints.join(", ") || "—"} | ${item.candidate_mutation_found ? "yes" : "no"} | ${item.expectation_pass ? "PASS" : "FAIL"} |`).join("\n");
  return `# Operator cross-corpus regression\n\nCandidate: \`${result.candidate_operator}\`\n\nOutcome: **${result.outcome}**\n\nOperator state: **${result.operator_state}**  \nRecommended action: **${result.recommended_action}**  \nPromotion status: **${result.promotion_status}**\n\n| Corpus | Role | Central terms | Candidate | Profile hints | Mutation | Expectation |\n|---|---|---:|---|---|---|---|\n${rows}\n\n## Summary\n\n- corpora: ${result.summary.corpora}\n- expectations passed: ${result.summary.expectations_passed}/${result.summary.corpora}\n- positive transfers passed: ${result.summary.positive_transfer_passed}\n- negative controls passed: ${result.summary.negative_controls_passed}\n- mixed controls passed: ${result.summary.mixed_controls_passed}\n- origin passed: ${result.summary.origin_passed}\n- overgeneralization detected: ${result.summary.overgeneralization_detected}\n\n## Claim ceiling\n\n${result.claim_ceiling}\n\nA regression pass means that the experimental operator showed source-linked transfer and discrimination under the preregistered controls. It does **not** validate relation-first ontology, establish philosophical truth, or promote the operator into frozen CORE.\n`;
}

export async function runOperatorRegression(engine, manifestFile, outputDirectory, options = {}) {
  const manifestPath = path.resolve(manifestFile);
  const manifest = await readJson(manifestPath);
  const manifestIssues = engine.structural.validateOperatorRegressionManifest(manifest);
  if (manifestIssues.length) throw new Error(`OPERATOR_REGRESSION_MANIFEST_INVALID: ${JSON.stringify(manifestIssues, null, 2)}`);
  const base = path.dirname(manifestPath);
  const corpusResults = [];
  for (const entry of manifest.corpora) {
    const refinery = resolveAgainst(base, entry.refinery_directory);
    const livingFile = resolveAgainst(base, entry.living_analysis_file);
    const [bank, living] = await Promise.all([
      readJson(path.join(refinery, "hypothesis_bank.json")),
      readJson(livingFile),
    ]);
    const bankIssues = engine.structural.validateHypothesisBank(bank);
    if (bankIssues.length) throw new Error(`OPERATOR_REGRESSION_BANK_INVALID ${entry.corpus_id}: ${JSON.stringify(bankIssues, null, 2)}`);
    const livingIssues = engine.structural.validateLivingAnalysis(living);
    if (livingIssues.length) throw new Error(`OPERATOR_REGRESSION_LIVING_INVALID ${entry.corpus_id}: ${JSON.stringify(livingIssues, null, 2)}`);
    corpusResults.push(corpusChecks(entry, bank, living, manifest.candidate_operator));
  }
  const decision = decideOperatorRegressionOutcome(manifest.corpora, corpusResults);
  const result = {
    result_version: "DAE-OPERATOR-REGRESSION-RESULT-1.1",
    engine_version: engine.context.engineVersion,
    generated_at: String(options.generatedAt ?? new Date().toISOString()),
    candidate_operator: manifest.candidate_operator,
    outcome: decision.outcome,
    operator_state: decision.operator_state,
    recommended_action: decision.recommended_action,
    promotion_status: "EXPERIMENTAL_NOT_CORE",
    corpus_results: corpusResults,
    summary: decision.summary,
    claim_ceiling: "INTERNAL_CROSS_CORPUS_OPERATOR_REGRESSION_NOT_EXTERNAL_PHILOSOPHICAL_VALIDATION_OR_CORE_PROMOTION",
  };
  const resultIssues = engine.structural.validateOperatorRegressionResult(result);
  if (resultIssues.length) throw new Error(`OPERATOR_REGRESSION_RESULT_INVALID: ${JSON.stringify(resultIssues, null, 2)}`);
  const out = path.resolve(outputDirectory);
  await mkdir(out, { recursive: false });
  const jsonFile = path.join(out, "operator_regression_result.json");
  const mdFile = path.join(out, "OPERATOR_REGRESSION_REPORT.md");
  await Promise.all([
    writeFile(jsonFile, `${JSON.stringify(result, null, 2)}\n`, "utf8"),
    writeFile(mdFile, renderMarkdown(result), "utf8"),
  ]);
  return { result, output_dir: out, files: { json: jsonFile, report: mdFile } };
}
