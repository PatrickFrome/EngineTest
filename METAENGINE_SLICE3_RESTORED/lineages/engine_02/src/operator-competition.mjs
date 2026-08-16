import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

function resolveAgainst(base, value) {
  return path.isAbsolute(value) ? value : path.resolve(base, value);
}

function primarySourceCandidate(bank) {
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

function setDifference(left, right) {
  const rightSet = new Set(right);
  return left.filter((item) => !rightSet.has(item));
}

function setIntersection(left, right) {
  const rightSet = new Set(right);
  return left.filter((item) => rightSet.has(item));
}

function unique(values) {
  return [...new Set(values)];
}

export function evaluateCandidateOnTarget(candidate, targetHints, birth) {
  const requiredMatched = setIntersection(candidate.required_profile_hints, targetHints);
  const requiredMissing = setDifference(candidate.required_profile_hints, targetHints);
  const optionalMatched = setIntersection(candidate.optional_profile_hints ?? [], targetHints);
  const incompatiblePresent = setIntersection(candidate.incompatible_profile_hints ?? [], targetHints);
  const matchedHints = unique([...requiredMatched, ...optionalMatched]);
  const distinctionGain = requiredMatched.length * 4 + optionalMatched.length * 2;
  const distortionLoss = requiredMissing.length * 5 + incompatiblePresent.length * 4;
  const complexityCost = Math.max(0, candidate.required_profile_hints.length + (candidate.optional_profile_hints ?? []).length - 1);
  const score = distinctionGain - distortionLoss - complexityCost;
  const viable = Boolean(
    birth.source_birth_confirmed
    && requiredMissing.length === 0
    && incompatiblePresent.length === 0
    && score >= 3
  );
  return {
    candidate_id: candidate.candidate_id,
    label: candidate.label,
    origin_corpus_id: candidate.origin_corpus_id,
    source_birth_confirmed: birth.source_birth_confirmed,
    source_operator: candidate.source_operator,
    required_matched: requiredMatched,
    required_missing: requiredMissing,
    optional_matched: optionalMatched,
    incompatible_present: incompatiblePresent,
    matched_hints: matchedHints,
    distinction_gain: distinctionGain,
    distortion_loss: distortionLoss,
    complexity_cost: complexityCost,
    score,
    viable,
  };
}

function unionCoverage(evaluations) {
  return unique(evaluations.flatMap((item) => item.matched_hints));
}

function sortEvaluations(evaluations) {
  return [...evaluations].sort((a, b) => b.score - a.score
    || b.matched_hints.length - a.matched_hints.length
    || a.candidate_id.localeCompare(b.candidate_id));
}

export function decideCompetitionTarget(targetHints, evaluations, scoring = {}) {
  const viable = sortEvaluations(evaluations.filter((item) => item.viable));
  const dominanceMargin = Number(scoring.dominance_margin ?? 2);
  const compositionGain = Number(scoring.composition_gain_threshold ?? 1);

  if (!targetHints.length || !viable.length) {
    return {
      decision: "ABSTAIN_UNRESOLVED",
      selected_candidates: [],
      covered_hints: [],
      residual_hints: [...targetHints],
      rationale: targetHints.length
        ? "No source-born candidate met the local viability threshold without required-hint loss or incompatible-hint distortion."
        : "The target emitted no operator-profile hints; source resistance alone is insufficient to force an operator choice.",
    };
  }

  const best = viable[0];
  const bestCoverage = new Set(best.matched_hints);
  const targetSet = new Set(targetHints);
  const bestCoversAll = [...targetSet].every((hint) => bestCoverage.has(hint));
  const second = viable[1];

  if (bestCoversAll && (!second || best.score >= second.score + dominanceMargin || second.matched_hints.every((hint) => bestCoverage.has(hint)))) {
    return {
      decision: "SELECT_LOCAL_WINNER",
      selected_candidates: [best.candidate_id],
      covered_hints: [...bestCoverage],
      residual_hints: setDifference(targetHints, [...bestCoverage]),
      rationale: "One source-born operator profile covers the local target without additional composition gain.",
    };
  }

  const chosen = [];
  const covered = new Set();
  let remaining = [...viable];
  while (remaining.length) {
    const ranked = remaining
      .map((item) => ({
        item,
        marginal: item.matched_hints.filter((hint) => !covered.has(hint)).length,
      }))
      .sort((a, b) => b.marginal - a.marginal || b.item.score - a.item.score || a.item.candidate_id.localeCompare(b.item.candidate_id));
    const next = ranked[0];
    if (!next || next.marginal <= 0) break;
    chosen.push(next.item);
    for (const hint of next.item.matched_hints) covered.add(hint);
    remaining = remaining.filter((item) => item.candidate_id !== next.item.candidate_id);
    if ([...targetSet].every((hint) => covered.has(hint))) break;
  }

  const compositionCoverage = unionCoverage(chosen);
  if (chosen.length > 1 && compositionCoverage.length >= best.matched_hints.length + compositionGain) {
    return {
      decision: "LOCAL_COMPOSITION",
      selected_candidates: chosen.map((item) => item.candidate_id),
      covered_hints: compositionCoverage,
      residual_hints: setDifference(targetHints, compositionCoverage),
      rationale: "Multiple source-born operators add non-redundant local distinctions; composition is retained without promoting a global meta-ontology.",
    };
  }

  if (second && Math.abs(best.score - second.score) < dominanceMargin) {
    return {
      decision: "KEEP_RIVALS_UNRESOLVED",
      selected_candidates: [best.candidate_id, second.candidate_id],
      covered_hints: unionCoverage([best, second]),
      residual_hints: setDifference(targetHints, unionCoverage([best, second])),
      rationale: "Competing profiles remain too close under the current source-bounded gain/loss model; selection is suspended rather than fabricated.",
    };
  }

  return {
    decision: "SELECT_LOCAL_WINNER",
    selected_candidates: [best.candidate_id],
    covered_hints: best.matched_hints,
    residual_hints: setDifference(targetHints, best.matched_hints),
    rationale: "The highest-scoring viable candidate dominates the local competition, but only for this target corpus.",
  };
}

async function validateCandidateBirth(engine, base, candidate) {
  const refinery = resolveAgainst(base, candidate.origin_refinery_directory);
  const livingFile = resolveAgainst(base, candidate.origin_living_analysis_file);
  const [bank, living] = await Promise.all([
    readJson(path.join(refinery, "hypothesis_bank.json")),
    readJson(livingFile),
  ]);
  const bankIssues = engine.structural.validateHypothesisBank(bank);
  if (bankIssues.length) throw new Error(`OPERATOR_COMPETITION_ORIGIN_BANK_INVALID ${candidate.candidate_id}: ${JSON.stringify(bankIssues, null, 2)}`);
  const livingIssues = engine.structural.validateLivingAnalysis(living);
  if (livingIssues.length) throw new Error(`OPERATOR_COMPETITION_ORIGIN_LIVING_INVALID ${candidate.candidate_id}: ${JSON.stringify(livingIssues, null, 2)}`);
  const sourceCandidate = primarySourceCandidate(bank);
  const originHints = sourceCandidate.profile_hints ?? [];
  const requiredBirthHints = candidate.birth_profile_hints ?? candidate.required_profile_hints;
  const missingBirthHints = setDifference(requiredBirthHints, originHints);
  const mutation = mutationFound(living, candidate.source_operator);
  return {
    candidate_id: candidate.candidate_id,
    origin_corpus_id: candidate.origin_corpus_id,
    origin_operator_candidate: sourceCandidate.candidate ?? "UNRESOLVED",
    origin_profile_hints: originHints,
    required_birth_hints: requiredBirthHints,
    missing_birth_hints: missingBirthHints,
    origin_mutation_found: mutation,
    source_birth_confirmed: sourceCandidate.candidate === candidate.source_operator && mutation && missingBirthHints.length === 0,
  };
}

function expectationCheck(target, decision) {
  const expectedCandidates = [...(target.expected_selected_candidates ?? [])].sort();
  const observedCandidates = [...decision.selected_candidates].sort();
  const decisionPass = decision.decision === target.expected_decision;
  const candidatesPass = expectedCandidates.length === observedCandidates.length
    && expectedCandidates.every((item, index) => item === observedCandidates[index]);
  return {
    expectation_pass: decisionPass && candidatesPass,
    checks: [
      {
        check: "EXPECTED_DECISION",
        passed: decisionPass,
        observed: decision.decision,
        expected: target.expected_decision,
      },
      {
        check: "EXPECTED_SELECTED_CANDIDATES",
        passed: candidatesPass,
        observed: observedCandidates.join(",") || "NONE",
        expected: expectedCandidates.join(",") || "NONE",
      },
    ],
  };
}

function renderMarkdown(result) {
  const targetRows = result.target_results.map((item) => `| ${item.corpus_id} | ${item.profile_hints.join(", ") || "—"} | ${item.decision} | ${item.selected_candidates.join(", ") || "—"} | ${item.residual_hints.join(", ") || "—"} | ${item.expectation_pass ? "PASS" : "FAIL"} |`).join("\n");
  const birthRows = result.candidate_births.map((item) => `| ${item.candidate_id} | ${item.origin_corpus_id} | ${item.origin_profile_hints.join(", ") || "—"} | ${item.origin_mutation_found ? "yes" : "no"} | ${item.source_birth_confirmed ? "PASS" : "FAIL"} |`).join("\n");
  return `# Operator competition / composition / selection\n\nOutcome: **${result.outcome}**\n\nRouting policy: **${result.routing_policy}**  \nPromotion status: **${result.promotion_status}**\n\n## Source-birth audit\n\n| Candidate | Origin | Origin profile hints | Origin mutation | Birth |\n|---|---|---|---|---|\n${birthRows}\n\n## Target competitions\n\n| Corpus | Target hints | Decision | Selected/composed operators | Residual | Expectation |\n|---|---|---|---|---|---|\n${targetRows}\n\n## Summary\n\n- candidates: ${result.summary.candidates}\n- source-born candidates confirmed: ${result.summary.source_births_confirmed}/${result.summary.candidates}\n- targets: ${result.summary.targets}\n- preregistered expectations passed: ${result.summary.expectations_passed}/${result.summary.targets}\n- local winners: ${result.summary.local_winners}\n- local compositions: ${result.summary.local_compositions}\n- unresolved rival sets: ${result.summary.unresolved_rivals}\n- abstentions: ${result.summary.abstentions}\n\n## Claim ceiling\n\n${result.claim_ceiling}\n\nCompetition scores are internal source-bounded routing heuristics. A local win does **not** establish philosophical truth, universal operator superiority, or CORE promotion. Composition means only that distinct source-linked profiles add non-redundant local coverage under this benchmark.\n`;
}

export async function runOperatorCompetition(engine, manifestFile, outputDirectory, options = {}) {
  const manifestPath = path.resolve(manifestFile);
  const manifest = await readJson(manifestPath);
  const manifestIssues = engine.structural.validateOperatorCompetitionManifest(manifest);
  if (manifestIssues.length) throw new Error(`OPERATOR_COMPETITION_MANIFEST_INVALID: ${JSON.stringify(manifestIssues, null, 2)}`);
  const base = path.dirname(manifestPath);

  const candidateBirths = [];
  for (const candidate of manifest.candidates) candidateBirths.push(await validateCandidateBirth(engine, base, candidate));
  const birthsById = new Map(candidateBirths.map((item) => [item.candidate_id, item]));

  const targetResults = [];
  for (const target of manifest.targets) {
    const refinery = resolveAgainst(base, target.refinery_directory);
    const bank = await readJson(path.join(refinery, "hypothesis_bank.json"));
    const bankIssues = engine.structural.validateHypothesisBank(bank);
    if (bankIssues.length) throw new Error(`OPERATOR_COMPETITION_TARGET_BANK_INVALID ${target.corpus_id}: ${JSON.stringify(bankIssues, null, 2)}`);
    const targetCandidate = primarySourceCandidate(bank);
    const profileHints = targetCandidate.profile_hints ?? [];
    const evaluations = manifest.candidates.map((candidate) => evaluateCandidateOnTarget(candidate, profileHints, birthsById.get(candidate.candidate_id)));
    const decision = decideCompetitionTarget(profileHints, evaluations, manifest.scoring);
    const expectation = expectationCheck(target, decision);
    targetResults.push({
      corpus_id: target.corpus_id,
      label: target.label,
      profile_hints: profileHints,
      source_operator_candidate: targetCandidate.candidate ?? "UNRESOLVED",
      candidate_evaluations: evaluations,
      ...decision,
      ...expectation,
    });
  }

  const sourceBirthsConfirmed = candidateBirths.filter((item) => item.source_birth_confirmed).length;
  const expectationsPassed = targetResults.filter((item) => item.expectation_pass).length;
  const allPassed = sourceBirthsConfirmed === candidateBirths.length && expectationsPassed === targetResults.length;
  const result = {
    result_version: "DAE-OPERATOR-COMPETITION-RESULT-1.0",
    engine_version: engine.context.engineVersion,
    generated_at: String(options.generatedAt ?? new Date().toISOString()),
    outcome: allPassed ? "PASSES_LOCAL_OPERATOR_ECOLOGY_REGRESSION" : "REVIEW_OPERATOR_ECOLOGY",
    routing_policy: "LOCAL_SELECTION_COMPOSITION_OR_ABSTENTION_WITHOUT_GLOBAL_ONTOLOGY",
    promotion_status: "EXPERIMENTAL_NOT_CORE",
    candidate_births: candidateBirths,
    target_results: targetResults,
    summary: {
      candidates: candidateBirths.length,
      source_births_confirmed: sourceBirthsConfirmed,
      targets: targetResults.length,
      expectations_passed: expectationsPassed,
      local_winners: targetResults.filter((item) => item.decision === "SELECT_LOCAL_WINNER").length,
      local_compositions: targetResults.filter((item) => item.decision === "LOCAL_COMPOSITION").length,
      unresolved_rivals: targetResults.filter((item) => item.decision === "KEEP_RIVALS_UNRESOLVED").length,
      abstentions: targetResults.filter((item) => item.decision === "ABSTAIN_UNRESOLVED").length,
    },
    claim_ceiling: "INTERNAL_SOURCE_BOUNDED_OPERATOR_COMPETITION_NOT_EXTERNAL_SEMANTIC_VALIDATION_OR_CORE_PROMOTION",
  };
  const resultIssues = engine.structural.validateOperatorCompetitionResult(result);
  if (resultIssues.length) throw new Error(`OPERATOR_COMPETITION_RESULT_INVALID: ${JSON.stringify(resultIssues, null, 2)}`);

  const out = path.resolve(outputDirectory);
  await mkdir(out, { recursive: false });
  const jsonFile = path.join(out, "operator_competition_result.json");
  const mdFile = path.join(out, "OPERATOR_COMPETITION_REPORT.md");
  await Promise.all([
    writeFile(jsonFile, `${JSON.stringify(result, null, 2)}\n`, "utf8"),
    writeFile(mdFile, renderMarkdown(result), "utf8"),
  ]);
  return { result, output_dir: out, files: { json: jsonFile, report: mdFile } };
}
