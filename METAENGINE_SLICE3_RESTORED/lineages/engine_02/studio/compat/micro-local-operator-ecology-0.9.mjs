import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { decideCompetitionTarget, evaluateCandidateOnTarget } from "../../src/operator-competition.mjs";
import { createEcologyCompatValidator } from "./ecology-validator.mjs";

async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

function resolveAgainst(base, value) {
  return path.isAbsolute(value) ? value : path.resolve(base, value);
}

function sameSet(a, b) {
  const left = [...a].sort();
  const right = [...b].sort();
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function boundaryStatus(left, right) {
  if (left.decision === right.decision && sameSet(left.selected_candidates, right.selected_candidates)) {
    return "CONTINUOUS_LOCAL_REGIME";
  }
  const unresolved = new Set(["ABSTAIN_UNRESOLVED", "KEEP_RIVALS_UNRESOLVED"]);
  if (unresolved.has(left.decision) || unresolved.has(right.decision)) return "UNRESOLVED_BOUNDARY";
  return "PRESERVE_OPERATOR_BOUNDARY";
}

function buildProvenanceGraph(windowResults, boundaryResults) {
  const operatorIds = [...new Set(windowResults.flatMap((window) => window.selected_candidates))].sort();
  const nodes = [
    ...windowResults.map((window) => ({
      node_id: `WINDOW:${window.window_id}`,
      node_type: "MICRO_WINDOW",
      label: window.label,
      evidence_segment_ids: window.evidence_segment_ids,
      decision: window.decision,
    })),
    ...operatorIds.map((operator) => ({
      node_id: `OPERATOR:${operator}`,
      node_type: "SOURCE_BORN_OPERATOR",
      label: operator,
      evidence_segment_ids: [],
      decision: "N/A",
    })),
    ...boundaryResults.map((boundary) => ({
      node_id: `BOUNDARY:${boundary.boundary_id}`,
      node_type: "MICRO_BOUNDARY",
      label: boundary.status,
      evidence_segment_ids: [],
      decision: boundary.status,
    })),
  ];
  const edges = [];
  for (const window of windowResults) {
    for (const operator of window.selected_candidates) {
      edges.push({
        edge_type: "WINDOW_ROUTED_TO_OPERATOR",
        from: `WINDOW:${window.window_id}`,
        to: `OPERATOR:${operator}`,
      });
    }
  }
  for (const boundary of boundaryResults) {
    edges.push({
      edge_type: "WINDOW_ADJACENT_TO_WINDOW",
      from: `WINDOW:${boundary.left_window_id}`,
      to: `WINDOW:${boundary.right_window_id}`,
    });
    edges.push({
      edge_type: "BOUNDARY_ANNOTATES_TRANSITION",
      from: `BOUNDARY:${boundary.boundary_id}`,
      to: `WINDOW:${boundary.right_window_id}`,
    });
  }
  return { nodes, edges };
}

function renderMarkdown(result) {
  const windows = result.window_results.map((item) => `| ${item.window_id} | ${item.profile_hints.join(", ") || "—"} | ${item.decision} | ${item.selected_candidates.join(", ") || "—"} | ${item.provenance_pass ? "PASS" : "FAIL"} | ${item.expectation_pass ? "PASS" : "FAIL"} |`).join("\n");
  const boundaries = result.boundary_results.map((item) => `| ${item.boundary_id} | ${item.left_window_id} → ${item.right_window_id} | ${item.status} | ${item.expectation_pass ? "PASS" : "FAIL"} |`).join("\n");
  return `# Micro-local operator ecology 0.9\n\nOutcome: **${result.outcome}**\n\nRouting policy: **${result.routing_policy}**  \nPromotion status: **${result.promotion_status}**\n\n## Windows\n\n| Window | Profile hints | Decision | Selected/composed | Provenance | Expectation |\n|---|---|---|---|---|---|\n${windows}\n\n## Boundaries\n\n| Boundary | Transition | Status | Expectation |\n|---|---|---|---|\n${boundaries}\n\n## Synthesis audit\n\n- decision: **${result.synthesis.decision}**\n- globally available selected operators: ${result.synthesis.global_selected_candidates.join(", ") || "—"}\n- localization loss pairs: ${result.synthesis.localization_loss_count}\n- windows preserving local provenance: ${result.summary.windows_with_valid_provenance}/${result.summary.windows}\n- preregistered window expectations: ${result.summary.window_expectations_passed}/${result.summary.windows}\n- preregistered boundary expectations: ${result.summary.boundary_expectations_passed}/${result.summary.boundaries}\n\nA corpus-level composition is rejected whenever applying every globally selected operator to every micro-window would add unsupported local routing. The higher-level synthesis may summarize which operators occur, but it may not erase **where** each operator gained purchase or where the method abstained.\n\n## Claim ceiling\n\n${result.claim_ceiling}\n`;
}

export function auditGlobalSynthesis(windowResults) {
  const globalSelected = [...new Set(windowResults.flatMap((window) => window.selected_candidates))].sort();
  const localizationLoss = [];
  for (const window of windowResults) {
    for (const candidate of globalSelected) {
      if (!window.selected_candidates.includes(candidate)) {
        localizationLoss.push({ window_id: window.window_id, candidate_id: candidate, loss_type: "UNWARRANTED_GLOBAL_APPLICATION" });
      }
    }
  }
  const decision = localizationLoss.length
    ? "REJECT_GLOBAL_COLLAPSE_PRESERVE_WINDOW_PROVENANCE"
    : "ALLOW_LOCAL_SINGLE_OPERATOR_SYNTHESIS";
  return {
    global_selected_candidates: globalSelected,
    localization_loss_count: localizationLoss.length,
    localization_loss: localizationLoss,
    decision,
  };
}

export async function runMicroLocalOperatorEcology(engine, manifestFile, outputDirectory, options = {}) {
  const manifestPath = path.resolve(manifestFile);
  const manifest = await readJson(manifestPath);
  const compat = await createEcologyCompatValidator();
  const manifestIssues = compat.validateManifest(manifest);
  if (manifestIssues.length) throw new Error(`MICRO_LOCAL_OPERATOR_ECOLOGY_MANIFEST_INVALID: ${JSON.stringify(manifestIssues, null, 2)}`);
  const base = path.dirname(manifestPath);

  const [competitionManifest, competitionResult, segmentation] = await Promise.all([
    readJson(resolveAgainst(base, manifest.competition_manifest_file)),
    readJson(resolveAgainst(base, manifest.competition_result_file)),
    readJson(resolveAgainst(base, manifest.segmentation_manifest_file)),
  ]);
  const competitionManifestIssues = engine.structural.validateOperatorCompetitionManifest(competitionManifest);
  if (competitionManifestIssues.length) throw new Error(`MICRO_LOCAL_COMPETITION_MANIFEST_INVALID: ${JSON.stringify(competitionManifestIssues, null, 2)}`);
  const competitionResultIssues = engine.structural.validateOperatorCompetitionResult(competitionResult);
  if (competitionResultIssues.length) throw new Error(`MICRO_LOCAL_COMPETITION_RESULT_INVALID: ${JSON.stringify(competitionResultIssues, null, 2)}`);
  const segmentationIssues = engine.structural.validateSegmentationManifest(segmentation);
  if (segmentationIssues.length) throw new Error(`MICRO_LOCAL_SEGMENTATION_INVALID: ${JSON.stringify(segmentationIssues, null, 2)}`);

  const knownSegments = new Set([
    ...(segmentation.ooxml_segments ?? []).map((item) => item.segment_id),
    ...(segmentation.argument_segments ?? []).map((item) => item.argument_segment_id),
  ]);
  const birthsById = new Map(competitionResult.candidate_births.map((item) => [item.candidate_id, item]));

  const windowResults = manifest.windows.map((window) => {
    const missingSegments = window.evidence_segment_ids.filter((segmentId) => !knownSegments.has(segmentId));
    const provenancePass = missingSegments.length === 0;
    const evaluations = competitionManifest.candidates.map((candidate) => evaluateCandidateOnTarget(
      candidate,
      window.profile_hints,
      birthsById.get(candidate.candidate_id) ?? { source_birth_confirmed: false },
    ));
    const decision = decideCompetitionTarget(window.profile_hints, evaluations, manifest.scoring);
    const expectationPass = decision.decision === window.expected_decision
      && sameSet(decision.selected_candidates, window.expected_selected_candidates);
    return {
      window_id: window.window_id,
      label: window.label,
      evidence_segment_ids: window.evidence_segment_ids,
      missing_segment_ids: missingSegments,
      provenance_pass: provenancePass,
      profile_hints: window.profile_hints,
      decision: decision.decision,
      selected_candidates: decision.selected_candidates,
      residual_hints: decision.residual_hints,
      rationale: decision.rationale,
      expectation_pass: expectationPass,
    };
  });
  const windowsById = new Map(windowResults.map((item) => [item.window_id, item]));

  const boundaryResults = manifest.boundaries.map((boundary) => {
    const left = windowsById.get(boundary.left_window_id);
    const right = windowsById.get(boundary.right_window_id);
    if (!left || !right) throw new Error(`MICRO_LOCAL_BOUNDARY_WINDOW_MISSING ${boundary.boundary_id}`);
    const status = boundaryStatus(left, right);
    return {
      boundary_id: boundary.boundary_id,
      left_window_id: boundary.left_window_id,
      right_window_id: boundary.right_window_id,
      status,
      expectation_pass: status === boundary.expected_status,
    };
  });

  const synthesis = auditGlobalSynthesis(windowResults);
  synthesis.expectation_pass = synthesis.decision === manifest.synthesis.expected_decision;
  const provenanceGraph = buildProvenanceGraph(windowResults, boundaryResults);

  const summary = {
    windows: windowResults.length,
    windows_with_valid_provenance: windowResults.filter((item) => item.provenance_pass).length,
    window_expectations_passed: windowResults.filter((item) => item.expectation_pass).length,
    boundaries: boundaryResults.length,
    boundary_expectations_passed: boundaryResults.filter((item) => item.expectation_pass).length,
    local_winners: windowResults.filter((item) => item.decision === "SELECT_LOCAL_WINNER").length,
    local_compositions: windowResults.filter((item) => item.decision === "LOCAL_COMPOSITION").length,
    unresolved_rivals: windowResults.filter((item) => item.decision === "KEEP_RIVALS_UNRESOLVED").length,
    abstentions: windowResults.filter((item) => item.decision === "ABSTAIN_UNRESOLVED").length,
    localization_loss_count: synthesis.localization_loss_count,
  };
  const allPassed = summary.windows_with_valid_provenance === summary.windows
    && summary.window_expectations_passed === summary.windows
    && summary.boundary_expectations_passed === summary.boundaries
    && synthesis.expectation_pass;

  const result = {
    result_version: "DAE-MICRO-LOCAL-OPERATOR-ECOLOGY-RESULT-1.0",
    engine_version: engine.context.engineVersion,
    generated_at: String(options.generatedAt ?? new Date().toISOString()),
    outcome: allPassed ? "PASSES_MICRO_LOCAL_OPERATOR_ECOLOGY_REGRESSION" : "REVIEW_MICRO_LOCAL_OPERATOR_ECOLOGY",
    routing_policy: "WINDOW_LOCAL_SELECTION_COMPOSITION_UNRESOLVED_OR_ABSTENTION_WITH_PROVENANCE_PRESERVING_BOUNDARIES",
    promotion_status: "EXPERIMENTAL_NOT_CORE",
    corpus_id: manifest.corpus_id,
    window_results: windowResults,
    boundary_results: boundaryResults,
    synthesis,
    provenance_graph: provenanceGraph,
    summary,
    claim_ceiling: "INTERNAL_PREREGISTERED_MICRO_LOCAL_ROUTING_NOT_EXTERNAL_SEMANTIC_VALIDATION_OR_CORE_PROMOTION",
  };
  const resultIssues = compat.validateResult(result);
  if (resultIssues.length) throw new Error(`MICRO_LOCAL_OPERATOR_ECOLOGY_RESULT_INVALID: ${JSON.stringify(resultIssues, null, 2)}`);

  const out = path.resolve(outputDirectory);
  await mkdir(out, { recursive: false });
  const jsonFile = path.join(out, "micro_local_operator_ecology_result.json");
  const mdFile = path.join(out, "MICRO_LOCAL_OPERATOR_ECOLOGY_REPORT.md");
  await Promise.all([
    writeFile(jsonFile, `${JSON.stringify(result, null, 2)}\n`, "utf8"),
    writeFile(mdFile, renderMarkdown(result), "utf8"),
  ]);
  return { result, output_dir: out, files: { json: jsonFile, report: mdFile } };
}
