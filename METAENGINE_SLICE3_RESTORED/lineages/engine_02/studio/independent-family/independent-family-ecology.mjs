import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { headingBoundedWindows, readDocxSegments } from "./family-signal-runtime.mjs";
import { validateIndependentFamilyManifest, validateIndependentFamilyResult } from "./validator.mjs";

function unique(values) { return [...new Set(values)]; }
function sha256(bytes) { return createHash("sha256").update(bytes).digest("hex"); }

async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

function resolveFromManifest(manifestFile, relativePath) {
  return path.resolve(path.dirname(manifestFile), relativePath);
}

async function verifyCandidateBirth(candidate, manifestFile) {
  const refinery = resolveFromManifest(manifestFile, candidate.origin_refinery_directory);
  const living = resolveFromManifest(manifestFile, candidate.origin_living_analysis_file);
  const [bank, analysis] = await Promise.all([
    readJson(path.join(refinery, "hypothesis_bank.json")),
    readJson(living),
  ]);
  const origin = bank?.source_resistance?.operator_candidate ?? {};
  const originHints = unique(origin.profile_hints ?? []);
  const required = unique(candidate.birth_profile_hints ?? candidate.required_profile_hints ?? []);
  const missing = required.filter((hint) => !originHints.includes(hint));
  const mutationFound = (analysis.method_mutations ?? []).some((mutation) => mutation.candidate === candidate.source_operator);
  return {
    candidate_id: candidate.candidate_id,
    origin_corpus_id: candidate.origin_corpus_id,
    origin_operator_candidate: origin.candidate ?? "UNRESOLVED",
    origin_profile_hints: originHints,
    required_birth_hints: required,
    missing_birth_hints: missing,
    origin_mutation_found: mutationFound,
    source_birth_confirmed: missing.length === 0 && mutationFound,
  };
}

function candidateEvaluation(candidate, birth, hints) {
  const required = unique(candidate.required_profile_hints ?? []);
  const optional = unique(candidate.optional_profile_hints ?? []);
  const incompatible = unique(candidate.incompatible_profile_hints ?? []);
  const requiredMatched = required.filter((hint) => hints.includes(hint));
  const requiredMissing = required.filter((hint) => !hints.includes(hint));
  const optionalMatched = optional.filter((hint) => hints.includes(hint));
  const incompatiblePresent = incompatible.filter((hint) => hints.includes(hint));
  const matched = unique([...requiredMatched, ...optionalMatched]);
  const distinctionGain = requiredMatched.length * 4 + optionalMatched.length * 2;
  const distortionLoss = requiredMissing.length * 5 + incompatiblePresent.length * 6;
  const complexityCost = optional.length ? 1 : 0;
  const score = distinctionGain - distortionLoss - complexityCost;
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
    matched_hints: matched,
    distinction_gain: distinctionGain,
    distortion_loss: distortionLoss,
    complexity_cost: complexityCost,
    score,
    viable: birth.source_birth_confirmed && requiredMissing.length === 0 && incompatiblePresent.length === 0 && distinctionGain > 0,
  };
}

function bestComposition(evaluations, allHints, threshold) {
  const viable = evaluations.filter((item) => item.viable);
  let best = null;
  for (let i = 0; i < viable.length; i += 1) {
    for (let j = i + 1; j < viable.length; j += 1) {
      const pair = [viable[i], viable[j]];
      const covered = unique(pair.flatMap((item) => item.matched_hints));
      const bestSingleCoverage = Math.max(...pair.map((item) => item.matched_hints.length));
      const compositionGain = covered.length - bestSingleCoverage;
      const residual = allHints.filter((hint) => !covered.includes(hint));
      const score = pair.reduce((sum, item) => sum + item.score, 0);
      const candidate = { pair, covered, residual, compositionGain, score };
      if (!best
        || candidate.residual.length < best.residual.length
        || (candidate.residual.length === best.residual.length && candidate.compositionGain > best.compositionGain)
        || (candidate.residual.length === best.residual.length && candidate.compositionGain === best.compositionGain && candidate.score > best.score)) {
        best = candidate;
      }
    }
  }
  if (!best || best.compositionGain < threshold) return null;
  return best;
}

function decideWindow(window, candidateDefs, births, scoring) {
  const hints = unique(window.profile_hints ?? []);
  const evaluations = candidateDefs.map((candidate) => candidateEvaluation(
    candidate,
    births.find((birth) => birth.candidate_id === candidate.candidate_id),
    hints,
  ));
  const viable = evaluations.filter((item) => item.viable).sort((a, b) => b.score - a.score || b.matched_hints.length - a.matched_hints.length || a.candidate_id.localeCompare(b.candidate_id));

  if (!hints.length) {
    return {
      ...window,
      candidate_evaluations: evaluations,
      decision: "ABSTAIN_UNRESOLVED",
      selected_candidates: [],
      covered_hints: [],
      residual_hints: [],
      rationale: "The target emitted no operator-profile hints; source resistance alone is insufficient to force an operator choice.",
    };
  }
  if (!viable.length) {
    return {
      ...window,
      candidate_evaluations: evaluations,
      decision: "ABSTAIN_UNRESOLVED",
      selected_candidates: [],
      covered_hints: [],
      residual_hints: hints,
      rationale: "No source-born candidate satisfies the required local hints without incompatible pressure; abstention preserves the unresolved field.",
    };
  }

  const completeSingles = viable.filter((item) => hints.every((hint) => item.matched_hints.includes(hint)));
  if (completeSingles.length) {
    const winner = completeSingles[0];
    return {
      ...window,
      candidate_evaluations: evaluations,
      decision: "SELECT_LOCAL_WINNER",
      selected_candidates: [winner.candidate_id],
      covered_hints: winner.matched_hints,
      residual_hints: hints.filter((hint) => !winner.matched_hints.includes(hint)),
      rationale: "One source-born operator profile covers the local target without additional composition gain.",
    };
  }

  const composition = bestComposition(evaluations, hints, Number(scoring.composition_gain_threshold ?? 1));
  if (composition && composition.residual.length === 0) {
    return {
      ...window,
      candidate_evaluations: evaluations,
      decision: "LOCAL_COMPOSITION",
      selected_candidates: composition.pair.map((item) => item.candidate_id),
      covered_hints: composition.covered,
      residual_hints: composition.residual,
      rationale: "Multiple source-born operators add non-redundant local distinctions; composition is retained without promoting a global meta-ontology.",
    };
  }

  if (viable.length === 1 || (viable[0].score - viable[1].score) >= Number(scoring.dominance_margin ?? 2)) {
    const winner = viable[0];
    return {
      ...window,
      candidate_evaluations: evaluations,
      decision: "SELECT_LOCAL_WINNER",
      selected_candidates: [winner.candidate_id],
      covered_hints: winner.matched_hints,
      residual_hints: hints.filter((hint) => !winner.matched_hints.includes(hint)),
      rationale: "One locally dominant source-born operator is retained while uncovered hints remain explicit residuals.",
    };
  }

  const rivals = viable.slice(0, 2);
  const covered = unique(rivals.flatMap((item) => item.matched_hints));
  return {
    ...window,
    candidate_evaluations: evaluations,
    decision: "KEEP_RIVALS_UNRESOLVED",
    selected_candidates: rivals.map((item) => item.candidate_id),
    covered_hints: covered,
    residual_hints: hints.filter((hint) => !covered.includes(hint)),
    rationale: "Several viable families remain locally non-equivalent without enough gain for composition or enough margin for selection.",
  };
}

function signature(window) {
  const selected = window.selected_candidates.length ? window.selected_candidates.join("+") : "NONE";
  const profile = window.profile_hints.length ? [...window.profile_hints].sort().join("+") : "NONE";
  const unserved = window.unserved_signal_families.length ? [...window.unserved_signal_families].sort().join("+") : "NONE";
  const active = window.active_signal_families.length ? [...window.active_signal_families].sort().join("+") : "NONE";
  return `${window.decision}:${selected}:PROFILE=${profile}:UNSERVED=${unserved}:ACTIVE=${active}`;
}

function buildBoundaries(windows) {
  const boundaries = [];
  for (let index = 1; index < windows.length; index += 1) {
    const left = windows[index - 1];
    const right = windows[index];
    const a = new Set(left.selected_candidates);
    const b = new Set(right.selected_candidates);
    const overlap = [...a].filter((item) => b.has(item)).length;
    let boundaryType = "OPERATOR_REGIME_SHIFT";
    let unresolved = false;
    if (right.decision === "ABSTAIN_UNRESOLVED" || left.decision === "ABSTAIN_UNRESOLVED" || right.decision === "KEEP_RIVALS_UNRESOLVED") {
      boundaryType = "OPEN_BOUNDARY";
      unresolved = true;
    } else if (overlap > 0 && (a.size !== b.size || [...a].some((item) => !b.has(item)))) {
      boundaryType = "PARTIAL_OPERATOR_OVERLAP";
    } else if (signature(left) === signature(right)) {
      boundaryType = "STABLE_LOCAL_REGIME";
    }
    boundaries.push({
      boundary_id: `MB-${String(index).padStart(3, "0")}`,
      from_window_id: left.window_id,
      to_window_id: right.window_id,
      boundary_type: boundaryType,
      from_signature: signature(left),
      to_signature: signature(right),
      unresolved,
    });
  }
  return boundaries;
}

function buildProvenanceGraph(windows, candidateDefs, boundaries) {
  const nodes = [
    ...windows.map((window) => ({ node_id: window.window_id, node_type: "ARGUMENT_WINDOW", selector_ids: window.paragraph_segment_ids })),
    ...candidateDefs.map((candidate) => ({ node_id: `OP-${candidate.candidate_id}`, node_type: "SOURCE_BORN_OPERATOR", selector_ids: [] })),
  ];
  const edges = [];
  let counter = 1;
  for (const window of windows) {
    for (const selected of window.selected_candidates) {
      edges.push({ edge_id: `ME-${String(counter++).padStart(4, "0")}`, from: window.window_id, to: `OP-${selected}`, relation: "LOCALLY_ROUTED_BY" });
    }
  }
  for (const boundary of boundaries) {
    edges.push({ edge_id: `ME-${String(counter++).padStart(4, "0")}`, from: boundary.from_window_id, to: boundary.to_window_id, relation: boundary.boundary_type });
  }
  return { nodes, edges, raw_text_included: false };
}

function expectedChecks(window, expected) {
  if (!expected) return { expectation_pass: false, checks: [{ check: "EXPECTED_WINDOW_PRESENT", passed: false, observed: window.heading, expected: "PREREGISTERED_HEADING" }] };
  const observedSelected = [...window.selected_candidates].sort().join(",");
  const expectedSelected = [...(expected.expected_selected_candidates ?? [])].sort().join(",");
  const checks = [
    { check: "EXPECTED_DECISION", passed: window.decision === expected.expected_decision, observed: window.decision, expected: expected.expected_decision },
    { check: "EXPECTED_SELECTED_CANDIDATES", passed: observedSelected === expectedSelected, observed: observedSelected || "NONE", expected: expectedSelected || "NONE" },
  ];
  return { expectation_pass: checks.every((item) => item.passed), checks };
}

function renderMarkdown(result) {
  const rows = result.windows.map((window) => `| ${window.window_id} | ${window.heading} | ${window.profile_hints.join(", ") || "—"} | ${window.decision} | ${window.selected_candidates.join(", ") || "—"} | ${window.residual_hints.join(", ") || "—"} | ${window.expectation_pass ? "PASS" : "FAIL"} |`).join("\n");
  const boundaryRows = result.boundaries.map((b) => `| ${b.from_window_id} → ${b.to_window_id} | ${b.boundary_type} | ${b.unresolved ? "yes" : "no"} |`).join("\n");
  return `# Independent-family micro-local operator ecology\n\nOutcome: **${result.outcome}**  \nRouting policy: **${result.routing_policy}**  \nPromotion: **${result.promotion_status}**\n\n## Argument windows\n\n| Window | Heading | Profile hints | Decision | Selected | Residual hints | Expectation |\n|---|---|---|---|---|---|---|\n${rows}\n\n## Boundaries\n\n| Transition | Boundary type | Unresolved |\n|---|---|---|\n${boundaryRows}\n\n## Synthesis gate\n\nDecision: **${result.synthesis.decision}**\n\n${result.synthesis.rationale}\n\n## Summary\n\n- source-born candidates confirmed: ${result.summary.source_births_confirmed}/${result.summary.candidates}\n- argument windows: ${result.summary.windows}\n- preregistered window expectations: ${result.summary.expectations_passed}/${result.summary.expected_windows}\n- distinct local signatures: ${result.summary.distinct_local_signatures}\n- boundaries: ${result.summary.boundaries}\n- unresolved boundaries: ${result.summary.unresolved_boundaries}\n- abstaining windows: ${result.summary.abstentions}\n\n## Claim ceiling\n\n${result.claim_ceiling}\n\nIndependent-family routing tests mechanics of locally changing the kind of question asked. It is not proof that a family is ontologically true or authorially intended.\n`;
}

export async function runIndependentFamilyEcology(engine, manifestFile, outputDirectory) {
  const manifestPath = path.resolve(manifestFile);
  const manifest = await readJson(manifestPath);
  const manifestIssues = await validateIndependentFamilyManifest(manifest);
  if (manifestIssues.length) throw new Error(`Independent-family ecology manifest invalid: ${JSON.stringify(manifestIssues, null, 2)}`);

  const sourceDocx = resolveFromManifest(manifestPath, manifest.target.source_docx);
  const sourceBytes = await readFile(sourceDocx);
  const segments = await readDocxSegments(sourceDocx, { documentLanguage: manifest.target.document_language });
  const rawWindows = headingBoundedWindows(segments, manifest.target.windowing);
  const births = await Promise.all(manifest.candidates.map((candidate) => verifyCandidateBirth(candidate, manifestPath)));
  const expectedByHeading = new Map((manifest.target.expected_windows ?? []).map((item) => [item.heading, item]));
  const windows = rawWindows.map((window) => {
    const decided = decideWindow(window, manifest.candidates, births, manifest.scoring ?? {});
    const expectation = expectedChecks(decided, expectedByHeading.get(decided.heading));
    return { ...decided, ...expectation };
  });
  const expectedHeadings = new Set((manifest.target.expected_windows ?? []).map((item) => item.heading));
  const observedHeadings = new Set(windows.map((item) => item.heading));
  const missingExpected = [...expectedHeadings].filter((heading) => !observedHeadings.has(heading));
  const unexpected = [...observedHeadings].filter((heading) => !expectedHeadings.has(heading));
  const boundaries = buildBoundaries(windows);
  const localSignatures = unique(windows.map(signature)).sort();
  const hasPolyphony = localSignatures.length > 1 || boundaries.some((b) => b.unresolved);
  const synthesisDecision = hasPolyphony ? "PRESERVE_POLYPHONIC_LOCALITY" : "SINGLE_LOCAL_REGIME_AVAILABLE";
  const synthesis = {
    decision: synthesisDecision,
    global_selected_candidates: hasPolyphony ? [] : unique(windows.flatMap((window) => window.selected_candidates)),
    local_signatures: localSignatures,
    heterogeneity_preserved: hasPolyphony,
    rationale: hasPolyphony
      ? "Distinct local operator regimes or unresolved windows are present; a single global operator would erase source-linked heterogeneity."
      : "All local windows share one stable routing signature; global reuse remains descriptive and does not promote the operator to CORE.",
    expectation_pass: synthesisDecision === manifest.target.expected_synthesis_decision,
    expected_decision: manifest.target.expected_synthesis_decision,
  };
  const summary = {
    candidates: manifest.candidates.length,
    source_births_confirmed: births.filter((birth) => birth.source_birth_confirmed).length,
    windows: windows.length,
    expected_windows: manifest.target.expected_windows.length,
    expectations_passed: windows.filter((window) => window.expectation_pass).length,
    distinct_local_signatures: localSignatures.length,
    boundaries: boundaries.length,
    unresolved_boundaries: boundaries.filter((boundary) => boundary.unresolved).length,
    abstentions: windows.filter((window) => window.decision === "ABSTAIN_UNRESOLVED").length,
    unresolved_rivals: windows.filter((window) => window.decision === "KEEP_RIVALS_UNRESOLVED").length,
    unserved_windows: windows.filter((window) => window.unserved_signal_families.length || window.residual_hints.length).length,
  };
  const passes = missingExpected.length === 0
    && unexpected.length === 0
    && summary.source_births_confirmed === summary.candidates
    && summary.expectations_passed === summary.expected_windows
    && synthesis.expectation_pass;

  const result = {
    result_version: "DAE-MICRO-LOCAL-ECOLOGY-RESULT-1.0",
    engine_version: engine?.context?.engineVersion ?? "0.10.0-alpha.1",
    generated_at: new Date().toISOString(),
    outcome: passes ? "PASSES_MICRO_LOCAL_ECOLOGY_REGRESSION" : "FAILS_MICRO_LOCAL_ECOLOGY_REGRESSION",
    routing_policy: "ARGUMENT_WINDOW_SELECTION_COMPOSITION_BOUNDARY_OR_ABSTENTION_WITH_POLYPHONIC_SYNTHESIS_GATE",
    promotion_status: "EXPERIMENTAL_NOT_CORE",
    source: {
      corpus_id: manifest.target.corpus_id,
      label: manifest.target.label,
      source_docx_sha256: sha256(sourceBytes),
      windowing_mode: manifest.target.windowing.mode,
      include_layers: manifest.target.windowing.include_layers,
      raw_text_included: false,
    },
    candidate_births: births,
    windows,
    boundaries,
    synthesis,
    provenance_graph: buildProvenanceGraph(windows, manifest.candidates, boundaries),
    preregistration: { missing_expected_headings: missingExpected, unexpected_observed_headings: unexpected },
    summary,
    claim_ceiling: "MICRO_LOCAL_ROUTING_AND_SYNTHESIS_FIDELITY_TEST_NOT_EXTERNAL_SEMANTIC_VALIDATION_OR_CORE_PROMOTION",
  };

  const resultIssues = await validateIndependentFamilyResult(result);
  if (resultIssues.length) throw new Error(`Independent-family ecology result invalid: ${JSON.stringify(resultIssues, null, 2)}`);
  const out = path.resolve(outputDirectory);
  await mkdir(out, { recursive: false });
  const files = {
    result: path.join(out, "micro_local_ecology_result.json"),
    report: path.join(out, "MICRO_LOCAL_ECOLOGY_REPORT.md"),
  };
  await Promise.all([
    writeFile(files.result, `${JSON.stringify(result, null, 2)}\n`, "utf8"),
    writeFile(files.report, renderMarkdown(result), "utf8"),
  ]);
  return { result, output_dir: out, files };
}
