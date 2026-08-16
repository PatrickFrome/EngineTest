import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

function unique(values) { return [...new Set(values)]; }

export function routeMicroLocalWindow(window, sourceResistance) {
  const knownHints = window.known_profile_hints ?? [];
  const openSet = sourceResistance.open_set_candidate;
  const openSetEligible = openSet?.status === "OPEN_SET_RIVAL_REQUIRED" && (window.central_terms ?? []).length >= 2;
  if (!knownHints.length && !openSetEligible) {
    return {
      decision: "ABSTAIN_LOCAL",
      selected_candidates: [],
      rationale: "The local window provides neither a known profile hint nor enough source-signature pressure to force an open-set candidate.",
    };
  }
  if (!knownHints.length && openSetEligible) {
    return {
      decision: "OPEN_SET_LOCAL_CANDIDATE",
      selected_candidates: [openSet.candidate],
      rationale: "The local window is source-central but does not resolve into the known profile vocabulary; the unknown family remains provisional and reversible.",
    };
  }
  const knownCandidate = sourceResistance.operator_candidate?.candidate ?? "KNOWN_PROFILE_CANDIDATE";
  if (openSetEligible) {
    return {
      decision: "KEEP_KNOWN_AND_OPEN_SET_RIVALS",
      selected_candidates: unique([knownCandidate, openSet.candidate]),
      rationale: "Known profile hints are present, but open-set source pressure is retained as a rival rather than collapsed into the known ontology.",
    };
  }
  return {
    decision: "KNOWN_PROFILE_LOCAL",
    selected_candidates: [knownCandidate],
    rationale: "The local window is represented by the known profile vocabulary and no open-set rival is forced here.",
  };
}

function summarizeTransitions(routes) {
  let transitions = 0;
  for (let index = 1; index < routes.length; index += 1) {
    if (routes[index].decision !== routes[index - 1].decision
      || routes[index].selected_candidates.join("|") !== routes[index - 1].selected_candidates.join("|")) transitions += 1;
  }
  return transitions;
}

export function evaluateMicroLocalEcology(bank) {
  const sourceResistance = bank?.source_resistance ?? {};
  const windows = sourceResistance.micro_local_windows ?? [];
  const routes = windows.map((window) => ({
    window_id: window.window_id,
    segment_ids: window.segment_ids,
    ordinal_start: window.ordinal_start,
    ordinal_end: window.ordinal_end,
    central_terms: window.central_terms,
    known_profile_hints: window.known_profile_hints,
    ...routeMicroLocalWindow(window, sourceResistance),
  }));
  const counts = {
    windows: routes.length,
    known_only: routes.filter((item) => item.decision === "KNOWN_PROFILE_LOCAL").length,
    open_set_only: routes.filter((item) => item.decision === "OPEN_SET_LOCAL_CANDIDATE").length,
    rival_routes: routes.filter((item) => item.decision === "KEEP_KNOWN_AND_OPEN_SET_RIVALS").length,
    abstentions: routes.filter((item) => item.decision === "ABSTAIN_LOCAL").length,
    route_transitions: summarizeTransitions(routes),
  };
  const hasLocality = routes.length > 0;
  return {
    ecology_version: "DAE-MICRO-LOCAL-ECOLOGY-0.10",
    source_id: bank.source_id ?? "UNRESOLVED",
    source_resistance_status: sourceResistance.status ?? "UNRESOLVED",
    open_set_status: sourceResistance.open_set_status ?? sourceResistance.open_set_candidate?.status ?? "UNRESOLVED",
    routing_policy: "WINDOW_LOCAL_KNOWN_PROFILE_PLUS_OPEN_SET_RIVAL_WITH_ABSTENTION",
    routes,
    counts,
    outcome: hasLocality ? "MICRO_LOCAL_ROUTING_AVAILABLE" : "NO_MICRO_LOCAL_WINDOWS",
    claim_ceiling: "LOCAL_OPERATOR_ROUTING_HEURISTIC_NOT_PHILOSOPHICAL_TRUTH_OR_OPERATOR_PROMOTION",
  };
}

function markdown(result) {
  const rows = result.routes.map((route) => `| ${route.window_id} | ${route.central_terms.join(", ") || "—"} | ${route.known_profile_hints.join(", ") || "—"} | ${route.decision} | ${route.selected_candidates.join(", ") || "—"} |`).join("\n");
  return `# Micro-local operator ecology 0.10\n\nOutcome: **${result.outcome}**\n\n| Window | Source-central terms | Known hints | Decision | Candidate(s) |\n|---|---|---|---|---|\n${rows || "| — | — | — | ABSTAIN_LOCAL | — |"}\n\n## Counts\n\n- windows: ${result.counts.windows}\n- known-only: ${result.counts.known_only}\n- open-set-only: ${result.counts.open_set_only}\n- known/open-set rival routes: ${result.counts.rival_routes}\n- abstentions: ${result.counts.abstentions}\n- route transitions: ${result.counts.route_transitions}\n\n## Claim ceiling\n\n${result.claim_ceiling}\n\nA route transition is evidence only that the machine's local representation changed. It is not evidence that the source itself contains a corresponding ontology.\n`;
}

export async function runMicroLocalEcology(engine, hypothesisBankFile, outputDirectory) {
  const bank = JSON.parse(await readFile(path.resolve(hypothesisBankFile), "utf8"));
  const bankIssues = engine.structural.validateHypothesisBank(bank);
  if (bankIssues.length) throw new Error(`Hypothesis bank is invalid: ${JSON.stringify(bankIssues, null, 2)}`);
  const result = evaluateMicroLocalEcology(bank);
  const resultIssues = engine.structural.validateMicroLocalEcologyResult ? engine.structural.validateMicroLocalEcologyResult(result) : [];
  if (resultIssues.length) throw new Error(`Micro-local ecology result is invalid: ${JSON.stringify(resultIssues, null, 2)}`);
  const out = path.resolve(outputDirectory);
  await mkdir(out, { recursive: false });
  const files = {
    result: path.join(out, "micro_local_ecology_result.json"),
    report: path.join(out, "MICRO_LOCAL_ECOLOGY_REPORT.md"),
  };
  await Promise.all([
    writeFile(files.result, `${JSON.stringify(result, null, 2)}\n`),
    writeFile(files.report, markdown(result)),
  ]);
  return { result, output_dir: out, files };
}
