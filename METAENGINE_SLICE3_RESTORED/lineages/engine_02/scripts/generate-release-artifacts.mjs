import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { evaluateAgreement } from "../src/agreement.mjs";
import { validateArgumentBundle } from "../src/argument-graph.mjs";
import { canonicalBenchmarkSha256 } from "../src/benchmark.mjs";
import { createEngine } from "../src/engine.mjs";
import { validateEtymologyPassFile } from "../src/etymology.mjs";
import { validateLivingAnalysisFile } from "../src/living-analysis.mjs";
import { readPortableProjectManifest, validatePortableProject } from "../src/portable-project.mjs";
import { validateProtocolRun } from "../src/protocol-runner.mjs";
import { writeRoCrate } from "../src/ro-crate.mjs";
import { validateRun, validateRun4d } from "../src/run-validator.mjs";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const engine = await createEngine();
const generatedAt = new Date().toISOString();
const portableProject = await readPortableProjectManifest(root);
const portableValidation = await validatePortableProject(engine, root);
if (!portableValidation.conformant) throw new Error(`AI-chat portable project is invalid: ${JSON.stringify(portableValidation.issues, null, 2)}`);

function relativeFiles(payload) {
  return JSON.parse(JSON.stringify(payload), (key, value) => {
    if ((key === "file" || key.endsWith("_file")) && typeof value === "string" && path.isAbsolute(value)) {
      return path.relative(root, value).replaceAll(path.sep, "/");
    }
    return value;
  });
}

async function readJson(relative) {
  return JSON.parse(await readFile(path.join(root, relative), "utf8"));
}

const original4a = relativeFiles(await engine.validateInputs([path.join(root, "vendor", "module4a", "fixtures_original")]));
const repaired4a = relativeFiles(await engine.validateInputs([path.join(root, "fixtures", "4a_repaired")]));
const candidates4d = relativeFiles(await engine.validateInputs([path.join(root, "fixtures", "4d_candidates")]));
const upstream4d = await readJson("vendor/module4d_upstream/UPSTREAM_PROVENANCE.json");
if (upstream4d.integrity_check !== "PASS" || upstream4d.verified_entries !== 19) throw new Error("Verified upstream MODULE-MIGRATION-4D-0.1 provenance is incomplete.");

const runs4a = {};
for (const name of ["stable-valid.json", "unstable-valid.json", "unstable-invalid.json"]) {
  runs4a[name] = relativeFiles(await validateRun(engine, path.join(root, "fixtures", "runs", name)));
}
const runs4d = {};
for (const name of ["epochal-valid.json", "epochal-invalid.json"]) {
  runs4d[name] = relativeFiles(await validateRun4d(engine, path.join(root, "fixtures", "runs4d", name)));
}

const protocolRuns = {};
for (const name of ["claim-discipline-pass.json", "data-gate-suspend.json"]) {
  protocolRuns[name] = relativeFiles(await validateProtocolRun(engine, path.join(root, "fixtures", "protocols", name)));
}
const agreement = relativeFiles(await evaluateAgreement(engine, path.join(root, "fixtures", "research", "annotations-perfect.json")));
const argument = relativeFiles(await validateArgumentBundle(engine, path.join(root, "fixtures", "arguments", "bridge-supported.json")));

const researchPlan = await readJson("fixtures/research/ro03-mini-plan.json");
const researchPlanIssues = engine.structural.validateResearchPlan(researchPlan);
const researchPlanStatus = {
  preregistration_id: researchPlan.preregistration_id,
  structural_conformant: researchPlanIssues.length === 0,
  blocked_gates: Object.entries(researchPlan.gates).filter(([, gate]) => gate.status !== "PASS").map(([name]) => name),
  execution_status: Object.values(researchPlan.gates).every((gate) => gate.status === "PASS") ? "READY_TO_FREEZE_AND_EXECUTE" : "FREEZABLE_BUT_EXECUTION_BLOCKED",
  claim_ceiling: "LOCAL_CONTENT_INTEGRITY_NOT_PUBLIC_PREREGISTRATION",
};

const sourceManifest = await readJson("vendor/v38/manifest.json");
const protocolRegistry = await readJson("config/protocol_registry.json");
const protocolInventory = {
  ...sourceManifest.protocol_audit,
  registry_families: protocolRegistry.protocols.length,
  by_status: Object.fromEntries([...new Set(protocolRegistry.protocols.map((item) => item.status))].sort().map((status) => [status, protocolRegistry.protocols.filter((item) => item.status === status).length])),
  by_automation: Object.fromEntries([...new Set(protocolRegistry.protocols.map((item) => item.automation))].sort().map((mode) => [mode, protocolRegistry.protocols.filter((item) => item.automation === mode).length])),
};
const gaPilot = await readJson("experiments/heidegger-ga/RESULTS.json");
const gaProtocolRuns = {};
for (const name of ["ga01-local-claim-pass.json", "catalog-source-audit-review.json", "development-claim-suspend.json", "reale-translation-suspend.json"]) {
  gaProtocolRuns[name] = relativeFiles(await validateProtocolRun(engine, path.join(root, "experiments", "heidegger-ga", "protocols", name)));
}
const gaWorkRoot = path.join(root, "experiments", "heidegger-ga", "full-work-1912");
const gaWork = await readJson("experiments/heidegger-ga/full-work-1912/RESULTS.json");
const gaWorkManifest = await readJson("experiments/heidegger-ga/full-work-1912/source_manifest.json");
const gaWorkManifestIssues = engine.structural.validateSourceManifest(gaWorkManifest);
if (gaWorkManifestIssues.length) throw new Error(`GA 1 work source manifest is invalid: ${JSON.stringify(gaWorkManifestIssues, null, 2)}`);
const gaWorkBundle = await readJson("experiments/heidegger-ga/full-work-1912/generated/analysis_bundle.json");
const gaWorkArgument = relativeFiles(await validateArgumentBundle(engine, path.join(gaWorkRoot, "argument_graph.json")));
const gaWorkProtocolRuns = {};
for (const name of ["full-work-source-audit-review.json", "moderate-reconstruction-pass.json", "strong-ontology-suspend.json", "single-work-data-gate-suspend.json", "ablation-suspend.json"]) {
  gaWorkProtocolRuns[name] = relativeFiles(await validateProtocolRun(engine, path.join(gaWorkRoot, "protocols", name)));
}
const dossierRoot = path.join(root, "experiments", "heidegger-ga", "user-dossier-ga1-1-2026");
const dossier = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/RESULTS.json");
const dossierManifest = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/run/source_manifest.json");
const dossierManifestIssues = engine.structural.validateSourceManifest(dossierManifest);
if (dossierManifestIssues.length) throw new Error(`User DOCX dossier source manifest is invalid: ${JSON.stringify(dossierManifestIssues, null, 2)}`);
const dossierIntake = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/run/docx_intake.json");
const dossierBundle = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/run/generated/analysis_bundle.json");
const dossierAblation = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/ABLATION_RESULTS.json");
const dossierRefineryRoot = path.join(dossierRoot, "refinery");
const dossierRefineryAssessment = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/CORPUS_REFINERY_ASSESSMENT.json");
const dossierSegmentation = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/refinery/segmentation_manifest.json");
const dossierSourceMap = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/refinery/source_map.json");
const dossierHypothesisBank = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/refinery/hypothesis_bank.json");
const dossierArchiveMap = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/refinery/archive_map.json");
const dossierFormulaRegistry = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/refinery/formula_registry.json");
const dossierClaimLedger = (await readFile(path.join(dossierRefineryRoot, "claim_ledger.jsonl"), "utf8")).trim().split("\n").filter(Boolean).map(JSON.parse);
const dossierRefineryIssues = {
  segmentation_manifest: engine.structural.validateSegmentationManifest(dossierSegmentation),
  source_map: engine.structural.validateSourceMap(dossierSourceMap),
  hypothesis_bank: engine.structural.validateHypothesisBank(dossierHypothesisBank),
  archive_map: engine.structural.validateArchiveMap(dossierArchiveMap),
  formula_registry: engine.structural.validateFormulaRegistry(dossierFormulaRegistry),
  claim_ledger: dossierClaimLedger.flatMap((entry) => engine.structural.validateClaimLedgerEntry(entry)),
};
const dossierRefineryErrorCount = Object.values(dossierRefineryIssues).reduce((sum, issues) => sum + issues.length, 0);
if (dossierRefineryErrorCount) throw new Error(`User DOCX dossier Corpus Refinery artifacts are invalid: ${JSON.stringify(dossierRefineryIssues, null, 2)}`);
const dossierProtocolRuns = {};
for (const name of ["source-audit-fail.json", "d28-core-fail.json", "anti-self-circulation-fail.json", "ontology-gate-suspend.json", "meta-destruction-suspend.json"]) {
  dossierProtocolRuns[name] = relativeFiles(await validateProtocolRun(engine, path.join(dossierRoot, "protocols", name)));
}
const dossierExpertRoot = path.join(dossierRoot, "expert-cycle-0.5");
const dossierExpertCycle = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/expert-cycle-0.5/expert_cycle.json");
const dossierExpertTrace = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/expert-cycle-0.5/expert_trace.json");
const dossierExpertIssues = engine.structural.validateExpertCycle(dossierExpertCycle);
if (dossierExpertIssues.length) throw new Error(`User DOCX autonomous expert cycle is invalid: ${JSON.stringify(dossierExpertIssues, null, 2)}`);
const dossierExpertProfileBytes = await readFile(path.join(root, "config", "expert_profiles", "heidegger_ga_dossier_1.0.json"));
const dossierSegmentationBytes = await readFile(path.join(dossierRefineryRoot, "segmentation_manifest.json"));
const expectedExpertProfileHash = createHash("sha256").update(dossierExpertProfileBytes).digest("hex");
const expectedRefineryManifestHash = createHash("sha256").update(dossierSegmentationBytes).digest("hex");
if (dossierExpertCycle.profile.profile_sha256 !== expectedExpertProfileHash) throw new Error("User DOCX expert profile hash is stale.");
if (dossierExpertCycle.source.refinery_manifest_sha256 !== expectedRefineryManifestHash) throw new Error("User DOCX expert cycle refinery hash is stale.");
if (!dossierExpertCycle.thesis_results.every((entry) => ["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"].includes(entry.status))) {
  throw new Error("User DOCX expert cycle contains a non-terminal thesis.");
}
const dossierExpertEtymologyFile = path.join(dossierExpertRoot, "etymology_pass.json");
const dossierExpertEtymology = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/expert-cycle-0.5/etymology_pass.json");
const dossierExpertEtymologyValidation = await validateEtymologyPassFile(engine, dossierExpertEtymologyFile);
if (!dossierExpertEtymologyValidation.conformant) throw new Error(`User DOCX expert-cycle ETY pass is invalid: ${JSON.stringify(dossierExpertEtymologyValidation.issues, null, 2)}`);
const dossierExpertEtymologyBytes = await readFile(dossierExpertEtymologyFile);
if (dossierExpertCycle.etymology?.pass_sha256 !== createHash("sha256").update(dossierExpertEtymologyBytes).digest("hex")) {
  throw new Error("User DOCX expert-cycle ETY pass hash is stale.");
}
const dossierLivingRoot = path.join(dossierRoot, "living-analysis-0.5");
const dossierLivingFile = path.join(dossierLivingRoot, "living_analysis.json");
const dossierLivingEtymologyFile = path.join(dossierLivingRoot, "etymology_pass.json");
const dossierLiving = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/living-analysis-0.5/living_analysis.json");
const dossierLivingEtymology = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/living-analysis-0.5/etymology_pass.json");
const dossierLivingValidation = await validateLivingAnalysisFile(engine, dossierLivingFile);
const dossierLivingEtymologyValidation = await validateEtymologyPassFile(engine, dossierLivingEtymologyFile);
if (!dossierLivingValidation.conformant) throw new Error(`User DOCX living analysis is invalid: ${JSON.stringify(dossierLivingValidation.issues, null, 2)}`);
if (!dossierLivingEtymologyValidation.conformant) throw new Error(`User DOCX living-analysis ETY pass is invalid: ${JSON.stringify(dossierLivingEtymologyValidation.issues, null, 2)}`);
const dossierLivingEtymologyBytes = await readFile(dossierLivingEtymologyFile);
if (dossierLiving.etymology?.pass_sha256 !== createHash("sha256").update(dossierLivingEtymologyBytes).digest("hex")) {
  throw new Error("User DOCX living-analysis ETY pass hash is stale.");
}
const dossierLivingCrossEdges = dossierLiving.graph.edges.filter((edge) => edge.relation === "CROSSES_CONSTELLATION").length;
const dossierLivingForbiddenTerminalFields = dossierLivingValidation.issues.filter((entry) => entry.code === "LIVING_TERMINAL_FIELD_FORBIDDEN").length;
const geviertRoot = path.join(root, "experiments", "heidegger-geviert-0.6");
const geviertLivingFile = path.join(geviertRoot, "living_analysis.json");
const geviertEtymologyFile = path.join(geviertRoot, "etymology_pass.json");
const geviertLiving = await readJson("experiments/heidegger-geviert-0.6/living_analysis.json");
const geviertEtymology = await readJson("experiments/heidegger-geviert-0.6/etymology_pass.json");
const geviertExpert = await readJson("experiments/heidegger-geviert-0.6/expert_cycle.json");
const geviertHypothesis = await readJson("experiments/heidegger-geviert-0.6/hypothesis_bank.json");
const geviertLivingValidation = await validateLivingAnalysisFile(engine, geviertLivingFile);
const geviertEtymologyValidation = await validateEtymologyPassFile(engine, geviertEtymologyFile);
if (!geviertLivingValidation.conformant || !geviertEtymologyValidation.conformant) throw new Error("Geviert 0.6 regression is not conformant.");
const geviertCrossEdges = geviertLiving.graph.edges.filter((edge) => edge.relation === "CROSSES_CONSTELLATION").length;
const geviertStatuses = Object.fromEntries(["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"].map((status) => [status, geviertExpert.thesis_results.filter((entry) => entry.status === status).length]));
const crossCorpusOperatorRegression = await readJson("experiments/cross-corpus-operator-regression-0.7/operator_regression_result.json");
const crossCorpusOperatorRegressionIssues = engine.structural.validateOperatorRegressionResult(crossCorpusOperatorRegression);
if (crossCorpusOperatorRegressionIssues.length) throw new Error(`Cross-corpus operator regression is invalid: ${JSON.stringify(crossCorpusOperatorRegressionIssues, null, 2)}`);
if (!crossCorpusOperatorRegression.engine_version) throw new Error("Cross-corpus operator regression engine version is missing.");
const operatorCompetition = await readJson("experiments/operator-competition-0.8/run/operator_competition_result.json");
const operatorCompetitionIssues = engine.structural.validateOperatorCompetitionResult(operatorCompetition);
if (operatorCompetitionIssues.length) throw new Error(`Operator competition 0.8 is invalid: ${JSON.stringify(operatorCompetitionIssues, null, 2)}`);
if (!operatorCompetition.engine_version) throw new Error("Operator competition 0.8 engine version is missing.");
const dossierBenchmarkRoot = path.join(dossierRoot, "benchmark-0.4");
const dossierBenchmarkManifest = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/benchmark-0.4/benchmark_manifest.json");
const dossierBenchmarkPredictions = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/benchmark-0.4/sealed_predictions.json");
const dossierBenchmarkPacketA = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/benchmark-0.4/blind_packets/coder-a.json");
const dossierBenchmarkPacketB = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/benchmark-0.4/blind_packets/coder-b.json");
const dossierBenchmarkLock = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/benchmark-0.4/benchmark_lock.json");
const dossierBenchmarkResult = await readJson("experiments/heidegger-ga/user-dossier-ga1-1-2026/benchmark-0.4/blocked-evaluation/BENCHMARK_RESULT.json");
const dossierBenchmarkIssues = [
  ...engine.structural.validateBenchmarkManifest(dossierBenchmarkManifest),
  ...engine.structural.validateBenchmarkPredictions(dossierBenchmarkPredictions),
  ...engine.structural.validateBenchmarkPacket(dossierBenchmarkPacketA),
  ...engine.structural.validateBenchmarkPacket(dossierBenchmarkPacketB),
  ...engine.structural.validateBenchmarkResult(dossierBenchmarkResult),
];
if (dossierBenchmarkIssues.length) throw new Error(`User DOCX empirical benchmark artifacts are invalid: ${JSON.stringify(dossierBenchmarkIssues, null, 2)}`);
const dossierBenchmarkManifestHash = canonicalBenchmarkSha256(dossierBenchmarkManifest);
if (dossierBenchmarkLock.manifest_sha256 !== dossierBenchmarkManifestHash || dossierBenchmarkPredictions.manifest_sha256 !== dossierBenchmarkManifestHash) {
  throw new Error("User DOCX empirical benchmark manifest fixity is stale.");
}
const [dossierBenchmarkManifestBytes, dossierBenchmarkPredictionBytes, dossierBenchmarkPacketABytes, dossierBenchmarkPacketBBytes] = await Promise.all([
  readFile(path.join(dossierBenchmarkRoot, "benchmark_manifest.json")),
  readFile(path.join(dossierBenchmarkRoot, "sealed_predictions.json")),
  readFile(path.join(dossierBenchmarkRoot, "blind_packets", "coder-a.json")),
  readFile(path.join(dossierBenchmarkRoot, "blind_packets", "coder-b.json")),
]);
const fileHash = (bytes) => createHash("sha256").update(bytes).digest("hex");
if (dossierBenchmarkLock.manifest_file_sha256 !== fileHash(dossierBenchmarkManifestBytes) || dossierBenchmarkLock.sealed_predictions_sha256 !== fileHash(dossierBenchmarkPredictionBytes)) {
  throw new Error("User DOCX empirical benchmark file lock is stale.");
}
for (const [packet, bytes] of [[dossierBenchmarkPacketA, dossierBenchmarkPacketABytes], [dossierBenchmarkPacketB, dossierBenchmarkPacketBBytes]]) {
  if (dossierBenchmarkLock.blind_packet_sha256[packet.packet_id] !== fileHash(bytes)) throw new Error(`Blind packet ${packet.packet_id} fixity is stale.`);
}
for (const sourceCycle of dossierBenchmarkManifest.source_cycles) {
  const bytes = await readFile(path.join(dossierBenchmarkRoot, sourceCycle.snapshot_file));
  if (fileHash(bytes) !== sourceCycle.expert_cycle_sha256) throw new Error(`Expert-cycle snapshot ${sourceCycle.snapshot_file} fixity is stale.`);
}
if (dossierBenchmarkResult.outcome !== "BLOCKED_PENDING_INDEPENDENT_LABELS" || dossierBenchmarkResult.systems !== null) {
  throw new Error("User DOCX empirical benchmark must remain blocked without independent labels and must not emit pseudo-performance metrics.");
}

const tap = execFileSync(process.execPath, ["--test", "--test-reporter=tap"], { cwd: root, encoding: "utf8" });
const tests = Number(tap.match(/# tests (\d+)/)?.[1] ?? 0);
const passed = Number(tap.match(/# pass (\d+)/)?.[1] ?? 0);
const failed = Number(tap.match(/# fail (\d+)/)?.[1] ?? 0);
if (!tests || failed) throw new Error(`Test suite did not pass:\n${tap}`);

const validationReport = {
  report_version: `DAE-VALIDATION-${engine.context.engineVersion}`,
  generated_at: generatedAt,
  claim_ceiling: "DETERMINISTIC_CONFORMANCE_RUN_BOUND_EXPERT_ADJUDICATION_AND_TRACEABLE_GENERATIVE_RECONSTRUCTION_NOT_PHILOSOPHICAL_TRUTH_OR_EXTERNAL_SEMANTIC_VALIDATION",
  source_v38: {
    artifact_id: sourceManifest.artifact_id,
    document_sha256: sourceManifest.document.sha256,
    extract_sha256: sourceManifest.canonical_extract.sha256,
    word_count: sourceManifest.canonical_extract.word_count,
    line_count: sourceManifest.canonical_extract.line_count,
    protocol_inventory: protocolInventory,
  },
  portable_project: {
    portable_project_version: portableProject.portable_project_version,
    entrypoint: portableProject.entrypoint,
    schema_errors: portableValidation.counts.ERROR,
    required_assets: portableProject.required_assets.length,
    execution_profiles: Object.fromEntries(Object.entries(portableProject.execution_profiles).map(([key, value]) => [key, value.provenance_label])),
    supported_inputs: portableProject.supported_inputs,
    mandatory_etymology: portableProject.invariants.mandatory_etymology,
    document_only_may_claim_code_execution: portableProject.invariants.document_only_may_claim_code_execution,
    primary_outputs: [portableProject.output_contract.primary_living_output, portableProject.output_contract.final_expert_output],
    claim_ceiling: portableProject.claim_ceiling,
  },
  trc_and_modules: {
    original_4a_baseline: original4a,
    repaired_4a_0_2: repaired4a,
    verified_4d_upstream: upstream4d,
    engine_compatibility_4d_candidates: candidates4d,
  },
  workflows: {
    branch_4a: runs4a,
    branch_4d: runs4d,
    geviert_source_resistance_0_6: {
      source_resistance_status: geviertHypothesis.source_resistance?.status,
      source_central_terms: geviertHypothesis.source_resistance?.central_terms?.length ?? 0,
      registry_coverage_ratio: geviertHypothesis.source_resistance?.coverage_ratio ?? null,
      hypotheses: geviertHypothesis.hypotheses.length,
      etymology_cards: geviertEtymology.coverage.cards_emitted,
      expert_statuses: geviertStatuses,
      living_layer: geviertLiving.layer.layer_id,
      constellations: geviertLiving.constellations.length,
      nodes: geviertLiving.graph.nodes.length,
      edges: geviertLiving.graph.edges.length,
      cross_constellation_edges: geviertCrossEdges,
      method_mutations: geviertLiving.method_mutations?.length ?? 0,
      sufficient_openness: geviertLiving.sufficient_openness.satisfied,
      claim_ceiling: geviertLiving.claim_ceiling,
    },
    cross_corpus_operator_regression_0_7: {
      candidate_operator: crossCorpusOperatorRegression.candidate_operator,
      outcome: crossCorpusOperatorRegression.outcome,
      operator_state: crossCorpusOperatorRegression.operator_state,
      recommended_action: crossCorpusOperatorRegression.recommended_action,
      corpora: crossCorpusOperatorRegression.summary.corpora,
      expectations_passed: crossCorpusOperatorRegression.summary.expectations_passed,
      overgeneralization_detected: crossCorpusOperatorRegression.summary.overgeneralization_detected,
      promotion_status: crossCorpusOperatorRegression.promotion_status,
      claim_ceiling: crossCorpusOperatorRegression.claim_ceiling,
    },
    operator_competition_0_8: {
      outcome: operatorCompetition.outcome,
      routing_policy: operatorCompetition.routing_policy,
      candidates: operatorCompetition.summary.candidates,
      source_births_confirmed: operatorCompetition.summary.source_births_confirmed,
      targets: operatorCompetition.summary.targets,
      expectations_passed: operatorCompetition.summary.expectations_passed,
      local_winners: operatorCompetition.summary.local_winners,
      local_compositions: operatorCompetition.summary.local_compositions,
      unresolved_rivals: operatorCompetition.summary.unresolved_rivals,
      abstentions: operatorCompetition.summary.abstentions,
      promotion_status: operatorCompetition.promotion_status,
      claim_ceiling: operatorCompetition.claim_ceiling,
    },
  },
  protocol_runs: protocolRuns,
  research_controls: {
    preregistration_fixture: researchPlanStatus,
    agreement_fixture: agreement,
    argument_fixture: argument,
  },
  heidegger_ga_pilot: {
    catalog: gaPilot.catalog,
    actual_source_probe: gaPilot.actual_source_probe,
    protocol_runs: gaProtocolRuns,
    research_plan: gaPilot.research_plan,
    verdict: gaPilot.verdict,
    full_first_work: {
      source_manifest_conformant: gaWorkManifestIssues.length === 0,
      page_aware_bundle: {
        pages: gaWorkBundle.page_count,
        units: gaWorkBundle.unit_count,
        candidate_records: gaWorkBundle.candidate_record_count,
        ambiguous_units: gaWorkBundle.ambiguous_unit_count,
        raw_text_included: gaWorkBundle.raw_text_included,
        selected_relations: gaWorkBundle.selected_record_relation_counts,
        validation: gaWorkBundle.validation,
      },
      argument_graph: gaWorkArgument,
      protocol_runs: gaWorkProtocolRuns,
      verdict: gaWork.verdict,
    },
    user_docx_dossier: {
      source_manifest_conformant: dossierManifestIssues.length === 0,
      artifact_sha256: dossier.source_docx_sha256,
      pagination_authority: dossier.pagination_authority,
      document_audit: {
        renderer_pages: dossierIntake.rendering.page_count,
        ooxml_paragraphs: dossierIntake.ooxml_audit.paragraphs_total,
        source_recorded_page_breaks: dossierIntake.ooxml_audit.explicit_page_breaks + dossierIntake.ooxml_audit.last_rendered_page_breaks,
        hyperlinks: dossierIntake.ooxml_audit.hyperlinks,
        pseudo_citation_markers: dossierIntake.ooxml_audit.interaction_residue.pseudo_citation_markers,
        risk_flags: dossierIntake.risk_flags,
      },
      page_aware_bundle: {
        pages: dossierBundle.page_count,
        units: dossierBundle.unit_count,
        candidate_records: dossierBundle.candidate_record_count,
        ambiguous_units: dossierBundle.ambiguous_unit_count,
        raw_text_included: dossierBundle.raw_text_included,
        selected_relations: dossierBundle.selected_record_relation_counts,
        validation: dossierBundle.validation,
      },
      unicode_ablation: dossierAblation,
      corpus_refinery: {
        schema_errors: dossierRefineryErrorCount,
        competing_segmentations: {
          ooxml: dossierSegmentation.counts.ooxml_total,
          renderer: dossierSegmentation.counts.renderer_units,
          argument: dossierSegmentation.counts.argument_units,
        },
        layer_routes: dossierSegmentation.counts.layer_routes,
        claim_ledger_entries: dossierClaimLedger.length,
        apb_reconstructed: 0,
        exact_duplicate_groups: dossierArchiveMap.counts.exact_duplicate_groups,
        near_duplicate_groups: dossierArchiveMap.counts.near_duplicate_groups,
        deleted_segments: dossierArchiveMap.counts.deleted_segments,
        formula_containers: dossierFormulaRegistry.formula_count,
        hypothesis_topics: dossierHypothesisBank.hypotheses.length,
        case_matrices: dossierHypothesisBank.case_matrices.length,
        source_resolution: dossierRefineryAssessment.source_resolution.gate,
        privacy_audit: dossierRefineryAssessment.privacy_audit,
        claim_ceiling: dossierSegmentation.claim_ceiling,
      },
      autonomous_expert_cycle: {
        schema_errors: dossierExpertIssues.length,
        run_id: dossierExpertCycle.run_id,
        backend: dossierExpertCycle.backend,
        mandatory_prepasses: dossierExpertCycle.prepasses,
        passes: dossierExpertCycle.passes,
        thesis_count: dossierExpertCycle.thesis_results.length,
        supported: dossierExpertCycle.global_analytics.supported_theses.length,
        qualified: dossierExpertCycle.global_analytics.qualified_theses.length,
        rejected: dossierExpertCycle.global_analytics.rejected_theses.length,
        insufficient: dossierExpertCycle.global_analytics.insufficient_theses.length,
        all_terminal: dossierExpertCycle.output_contract.all_theses_terminal,
        source_text_included: dossierExpertCycle.output_contract.source_text_included,
        model_fallback_count: dossierExpertTrace.model_fallback_count,
        etymology: {
          schema_errors: dossierExpertEtymologyValidation.counts.ERROR,
          protocol_version: dossierExpertEtymology.protocol_version,
          cards: dossierExpertEtymology.coverage.cards_emitted,
          ety_full: dossierExpertEtymology.coverage.ety_full_executed,
          unresolved_fields: dossierExpertEtymology.coverage.unresolved_fields,
          knowledge_resolution: dossierExpertEtymology.coverage.knowledge_resolution,
          coverage_complete: dossierExpertEtymology.coverage.coverage_complete,
          mandatory_execution: dossierExpertEtymology.output_contract.mandatory_execution,
          mandatory_significance: dossierExpertEtymology.output_contract.mandatory_significance,
          semantic_promotion_performed: dossierExpertEtymology.output_contract.semantic_promotion_performed,
        },
        final_verdict: dossierExpertCycle.global_analytics.final_verdict,
        claim_ceiling: dossierExpertCycle.claim_ceiling,
      },
      living_analysis: {
        schema_errors: dossierLivingValidation.counts.ERROR,
        run_id: dossierLiving.run_id,
        layer: dossierLiving.layer,
        constellations: dossierLiving.constellations.length,
        nodes: dossierLiving.graph.nodes.length,
        edges: dossierLiving.graph.edges.length,
        cross_constellation_edges: dossierLivingCrossEdges,
        retired_operators: dossierLiving.graph.retired_operators.length,
        sufficient_openness: dossierLiving.sufficient_openness.satisfied,
        forbidden_terminal_fields: dossierLivingForbiddenTerminalFields,
        active_steps_require_gain: dossierLiving.output_contract.each_active_step_adds_traceable_gain,
        discovery_is_not_justification: dossierLiving.output_contract.discovery_is_not_justification,
        etymology: {
          schema_errors: dossierLivingEtymologyValidation.counts.ERROR,
          protocol_version: dossierLivingEtymology.protocol_version,
          cards: dossierLivingEtymology.coverage.cards_emitted,
          ety_full: dossierLivingEtymology.coverage.ety_full_executed,
          unresolved_fields: dossierLivingEtymology.coverage.unresolved_fields,
          knowledge_resolution: dossierLivingEtymology.coverage.knowledge_resolution,
          coverage_complete: dossierLivingEtymology.coverage.coverage_complete,
          mandatory_execution: dossierLivingEtymology.output_contract.mandatory_execution,
          mandatory_significance: dossierLivingEtymology.output_contract.mandatory_significance,
          semantic_promotion_performed: dossierLivingEtymology.output_contract.semantic_promotion_performed,
        },
        outputs: ["PHILOSOPHICAL_FIELD_NOTE.md", "LIVING_ANALYTICS.md", "CONSTELLATION.md", "living_analysis.json", "operator_trace.json", "ETYMOLOGICAL_ANALYSIS.md", "etymology_pass.json"],
        claim_ceiling: dossierLiving.claim_ceiling,
      },
      empirical_benchmark: {
        benchmark_id: dossierBenchmarkManifest.benchmark_id,
        manifest_sha256: dossierBenchmarkManifestHash,
        units: dossierBenchmarkManifest.units.length,
        frozen_minimum_units: dossierBenchmarkManifest.evaluation_plan.minimum_units,
        blind_packets: 2,
        outcome: dossierBenchmarkResult.outcome,
        performance_metrics_emitted: dossierBenchmarkResult.systems !== null,
        synthetic_positive_role: "REGRESSION_TEST_ONLY_NOT_EMPIRICAL_EVIDENCE",
        claim_ceiling: dossierBenchmarkResult.claim_ceiling,
      },
      protocol_runs: dossierProtocolRuns,
      verdict: dossier.verdict,
    },
  },
  reproducibility: {
    ro_crate: "GENERATED_AFTER_THIS_REPORT",
    release_hash_manifest: "GENERATED_AFTER_RO_CRATE",
  },
  automated_tests: { tests, passed, failed, command: "node --test" },
};
await writeFile(path.join(root, "VALIDATION_REPORT.json"), `${JSON.stringify(validationReport, null, 2)}\n`, "utf8");

const md = `# Validation Report — DAE ${engine.context.engineVersion}

Generated: 2026-08-11

## Claim ceiling

The release establishes deterministic conformance, explicit review routing, registered reliability metrics, terminal run-bound expert adjudication, mandatory ETY-0.2 execution and a traceable non-linear exploratory graph. It does not establish philosophical truth, infallibility, construct validity, external reproducibility or superiority over domain-native methods.

## Integrated source audit

The canonical v3.8 source contains ${sourceManifest.canonical_extract.word_count.toLocaleString("en-US")} words and ${sourceManifest.canonical_extract.line_count.toLocaleString("en-US")} extracted lines. The heading-level audit found ${protocolInventory.explicit_control_heading_occurrences} explicit protocol/control occurrences (${protocolInventory.current_occurrences} current, ${protocolInventory.archival_occurrences} archival and ${protocolInventory.superseded_or_retrospective_occurrences} superseded/retrospective), canonicalized into ${protocolInventory.registry_families} executable protocol families.

## Results

| Suite | Items | Conformant/pass | Errors | Review flags | Expected result |
|---|---:|---:|---:|---:|---|
| AI-chat portable project | ${portableProject.required_assets.length} bound assets | ${portableValidation.conformant ? portableProject.required_assets.length : 0} | ${portableValidation.counts.ERROR} | ${portableValidation.counts.REVIEW} | Dual runtime; no pseudo-execution in document-only mode |
| Original 4A-0.1 fixtures | ${original4a.counts.files} | ${original4a.counts.conformant} | ${original4a.counts.ERROR} | ${original4a.counts.REVIEW} | Strict failure |
| Repaired 4A-0.2 fixtures | ${repaired4a.counts.files} | ${repaired4a.counts.conformant} | ${repaired4a.counts.ERROR} | ${repaired4a.counts.REVIEW} | Conformant + expert review |
| Verified upstream 4D package | ${upstream4d.verified_entries} | ${upstream4d.verified_entries} | 0 | — | Byte-preserving extraction; archive SHA fixed |
| 4D engine compatibility candidates | ${candidates4d.counts.files} | ${candidates4d.counts.conformant} | ${candidates4d.counts.ERROR} | ${candidates4d.counts.REVIEW} | Conformant + expert review; not represented as upstream data |
| 4A stable workflow | 1 | ${runs4a["stable-valid.json"].conformant ? 1 : 0} | ${runs4a["stable-valid.json"].counts.ERROR} | ${runs4a["stable-valid.json"].counts.REVIEW} | Pass |
| 4A unstable workflow with IND4 | 1 | ${runs4a["unstable-valid.json"].conformant ? 1 : 0} | ${runs4a["unstable-valid.json"].counts.ERROR} | ${runs4a["unstable-valid.json"].counts.REVIEW} | Pass |
| 4A identity-before-relata negative | 1 | ${runs4a["unstable-invalid.json"].conformant ? 1 : 0} | ${runs4a["unstable-invalid.json"].counts.ERROR} | ${runs4a["unstable-invalid.json"].counts.REVIEW} | Fail |
| 4D epochal workflow | 1 | ${runs4d["epochal-valid.json"].conformant ? 1 : 0} | ${runs4d["epochal-valid.json"].counts.ERROR} | ${runs4d["epochal-valid.json"].counts.REVIEW} | Pass + totalization review |
| 4D premature totalization negative | 1 | ${runs4d["epochal-invalid.json"].conformant ? 1 : 0} | ${runs4d["epochal-invalid.json"].counts.ERROR} | ${runs4d["epochal-invalid.json"].counts.REVIEW} | Fail |
| Deterministic protocol fixture | 1 | ${protocolRuns["claim-discipline-pass.json"].outcome === "PASS" ? 1 : 0} | ${protocolRuns["claim-discipline-pass.json"].counts.ERROR} | ${protocolRuns["claim-discipline-pass.json"].counts.REVIEW} | PASS |
| Blocked research-gate fixture | 1 | ${protocolRuns["data-gate-suspend.json"].outcome === "SUSPEND" ? 1 : 0} | ${protocolRuns["data-gate-suspend.json"].counts.ERROR} | ${protocolRuns["data-gate-suspend.json"].counts.REVIEW} | SUSPEND |
| Agreement metric fixture | 1 | ${agreement.threshold_passed ? 1 : 0} | ${agreement.counts.ERROR} | ${agreement.counts.REVIEW} | Threshold pass; rare-code warning remains |
| Argument graph fixture | 1 | ${argument.conformant ? 1 : 0} | ${argument.counts.ERROR} | ${argument.counts.REVIEW} | Graph-internal support only |
| Heidegger GA catalog snapshot | ${gaPilot.catalog.official_entries} | ${gaPilot.catalog.official_entries} | 0 | — | Bibliographic metadata only |
| GA 1 local textual claim | 1 | ${gaProtocolRuns["ga01-local-claim-pass.json"].outcome === "PASS" ? 1 : 0} | ${gaProtocolRuns["ga01-local-claim-pass.json"].counts.ERROR} | ${gaProtocolRuns["ga01-local-claim-pass.json"].counts.REVIEW} | PASS at one-page scale |
| GA 1 → GA 2 strong development claim | 1 | ${gaProtocolRuns["development-claim-suspend.json"].outcome === "SUSPEND" ? 1 : 0} | ${gaProtocolRuns["development-claim-suspend.json"].counts.ERROR} | ${gaProtocolRuns["development-claim-suspend.json"].counts.REVIEW} | SUSPEND |
| German lexical adapter on GA 1, p. 1 | 1 | ${gaPilot.actual_source_probe.after_german_adapter.validation.conformant} | ${gaPilot.actual_source_probe.after_german_adapter.validation.ERROR} | ${gaPilot.actual_source_probe.after_german_adapter.validation.REVIEW} | RT04 candidate + review |
| GA 1 first work paged intake | ${gaWorkBundle.candidate_record_count} | ${gaWorkBundle.validation.conformant} | ${gaWorkBundle.validation.ERROR} | ${gaWorkBundle.validation.REVIEW} | Derivative-only; every record remains review |
| GA 1 first work argument graph | 1 | ${gaWorkArgument.conformant ? 1 : 0} | ${gaWorkArgument.counts.ERROR} | ${gaWorkArgument.review_required ? 1 : 0} | CONTESTED pro/con reconstruction |
| GA 1 moderate reconstruction | 1 | ${gaWorkProtocolRuns["moderate-reconstruction-pass.json"].outcome === "PASS" ? 1 : 0} | ${gaWorkProtocolRuns["moderate-reconstruction-pass.json"].counts.ERROR} | ${gaWorkProtocolRuns["moderate-reconstruction-pass.json"].counts.REVIEW} | PASS at single-work scale |
| GA 1 fundamental-ontology promotion | 1 | ${gaWorkProtocolRuns["strong-ontology-suspend.json"].outcome === "SUSPEND" ? 1 : 0} | ${gaWorkProtocolRuns["strong-ontology-suspend.json"].counts.ERROR} | ${gaWorkProtocolRuns["strong-ontology-suspend.json"].counts.REVIEW} | SUSPEND |
| User DOCX dossier paged intake | ${dossierBundle.candidate_record_count} | ${dossierBundle.validation.conformant} | ${dossierBundle.validation.ERROR} | ${dossierBundle.validation.REVIEW} | Derivative-only review queue |
| User DOCX Corpus Refinery ledger | ${dossierClaimLedger.length} | ${dossierClaimLedger.length} | ${dossierRefineryErrorCount} | ${dossierClaimLedger.length} | Schema-valid review queue; A/P/B remain null |
| User DOCX autonomous expert cycle | ${dossierExpertCycle.thesis_results.length} | ${dossierExpertCycle.thesis_results.length} | ${dossierExpertIssues.length} | — | All theses terminal; final analytics emitted |
| Mandatory ETY-0.2 pre-pass | ${dossierLivingEtymology.coverage.cards_emitted} concepts | ${dossierLivingEtymology.coverage.ety_min_executed} ETY-MIN / ${dossierLivingEtymology.coverage.ety_full_executed} ETY-FULL | ${dossierLivingEtymologyValidation.counts.ERROR} | ${dossierLivingEtymology.coverage.unresolved_fields} unresolved fields | Complete execution; partial knowledge; no automatic semantic promotion |
| D3 living constellations | ${dossierLiving.constellations.length} | ${dossierLiving.graph.nodes.length} nodes / ${dossierLiving.graph.edges.length} edges | ${dossierLivingValidation.counts.ERROR} | ${dossierLivingCrossEdges} cross-constellation edges | Sufficient openness=${dossierLiving.sufficient_openness.satisfied}; no terminal verdict fields |
| Geviert source-resistance regression 0.6 | ${geviertLiving.constellations.length} constellations | ${geviertLiving.graph.nodes.length} nodes / ${geviertLiving.graph.edges.length} edges | ${geviertLivingValidation.counts.ERROR} | ${geviertHypothesis.source_resistance?.central_terms?.length ?? 0} source-central terms; ${geviertLiving.method_mutations?.length ?? 0} experimental mutation | Registry blind spot handled; relation-first not promoted to ontology |
| Cross-corpus operator regression 0.7 | ${crossCorpusOperatorRegression.summary.corpora} corpora | ${crossCorpusOperatorRegression.summary.expectations_passed}/${crossCorpusOperatorRegression.summary.corpora} preregistered expectations | 0 | — | ${crossCorpusOperatorRegression.outcome}; state ${crossCorpusOperatorRegression.operator_state}; no CORE promotion |
| Operator competition 0.8 | ${operatorCompetition.summary.targets} targets | ${operatorCompetition.summary.expectations_passed}/${operatorCompetition.summary.targets} preregistered expectations | 0 | ${operatorCompetition.summary.local_compositions} local composition; ${operatorCompetition.summary.abstentions} abstention | ${operatorCompetition.outcome}; local routing only; no CORE promotion |
| User DOCX frozen blind benchmark | ${dossierBenchmarkManifest.units.length} | 0 | ${dossierBenchmarkIssues.length} | 3 | BLOCKED pending independent labels; below ${dossierBenchmarkManifest.evaluation_plan.minimum_units}-unit minimum |
| User DOCX dossier source admission | 1 | ${dossierProtocolRuns["source-audit-fail.json"].outcome === "FAIL" ? 1 : 0} | ${dossierProtocolRuns["source-audit-fail.json"].counts.ERROR} | ${dossierProtocolRuns["source-audit-fail.json"].counts.REVIEW} | Expected FAIL as primary/independent evidence |
| User DOCX dossier ontology model | 1 | ${dossierProtocolRuns["ontology-gate-suspend.json"].outcome === "SUSPEND" ? 1 : 0} | ${dossierProtocolRuns["ontology-gate-suspend.json"].counts.ERROR} | ${dossierProtocolRuns["ontology-gate-suspend.json"].counts.REVIEW} | Expected SUSPEND pending independent review |
| Automated tests | ${tests} | ${passed} | ${failed} | — | All pass |

## Interpretation

The engine now encodes valuable v3.8 controls as versioned, evidence-bearing protocol runs. Archival derivatives remain isolated and require an explicit archival-review mode. Blocked data, authorization, licence or coder gates suspend execution instead of fabricating an empirical result. The 4D branch blocks epochal Gestell finalization until MA4 reconstruction and concrete TO4/BS4 discrimination exist, while still requiring human review of any totalizing conclusion.

The DAE-AI-CHAT-1.0 envelope makes the release relocatable across AI-chat environments. Its ${portableProject.required_assets.length} required assets are path-safe and SHA-256 bound. A capable agent runs portable-check and the real CLI; a read-only chat applies the self-contained protocol with provenance label DOCUMENT_ONLY_LANGUAGE_MODEL_EXECUTION. The latter is forbidden from claiming code execution, schema conformance, generated hashes or unseen source locators.

The original 4A fixtures remain available as a regression baseline: they pass the frozen upstream JSON Schema but fail strict release policy. Repaired records remove deterministic errors without receiving an automatic semantic promotion.

The Heidegger GA pilot records a reproduced language-coverage failure and its repair: before the German adapter GA 1, p. 1 produced zero candidates; after the adapter it produced one local RT04 candidate with no deterministic error and mandatory review. The full first work is now processed as 11 printed pages and 280 non-expressive units; 17 bare modal cues remain RT00 rather than being promoted to normative RT21. Catalog metadata remains explicitly unable to support a corpus-level philosophical claim, and the full-work graph remains CONTESTED.

The user-supplied DOCX dossier exposed a second language-coverage failure: ASCII word boundaries suppressed Cyrillic routing and produced only ${dossierAblation.comparison.before_unicode_boundary_fix.candidate_records} candidates. Unicode letter/number boundaries restored ${dossierAblation.comparison.after_unicode_boundary_fix.candidate_records} review candidates across ${dossierBundle.unit_count} units, with ${dossierBundle.ambiguous_unit_count} unresolved units and no semantic promotion. Its ${dossierIntake.rendering.page_count} A4 pages are renderer-derived, not GA pagination. Source, D2.8 and anti-self-circulation negative controls prevent the composite dossier from becoming primary or independent evidence.

Corpus Refinery adds three competing unitizations (${dossierSegmentation.counts.ooxml_total.toLocaleString("en-US")} OOXML paragraphs, ${dossierSegmentation.counts.renderer_units.toLocaleString("en-US")} renderer units and ${dossierSegmentation.counts.argument_units.toLocaleString("en-US")} argument windows) without privileging one as the philosophical segmentation. It routes ${dossierSegmentation.counts.layer_routes.UNRESOLVED.toLocaleString("en-US")} paragraphs to UNRESOLVED, emits ${dossierClaimLedger.length.toLocaleString("en-US")} claim candidates with no automatic A/P/B reconstruction, records ${dossierFormulaRegistry.formula_count.toLocaleString("en-US")} non-expressive OMML containers and deletes zero segments. The seven-case matrix is present only as a hypothesis bank; source resolution and canonical synthesis remain suspended.

The autonomous expert cycle consumes that preserved evidence layer without changing it. ETYMOLOGICAL_PASS now runs before RECONSTRUCTOR, CRITIC and ADJUDICATOR; every central concept therefore receives ETY-MIN, while load triggers escalate selected concepts to the nine-contour ETY-FULL check. The current dossier emits ${dossierExpertEtymology.coverage.cards_emitted} cards, including ${dossierExpertEtymology.coverage.ety_full_executed} ETY-FULL cards, and retains ${dossierExpertEtymology.coverage.unresolved_fields} unresolved fields instead of inventing historical or local evidence. The subsequent adjudication assigns all ${dossierExpertCycle.thesis_results.length} theses a terminal run-bound status and yields ${dossierExpertCycle.global_analytics.supported_theses.length} SUPPORTED, ${dossierExpertCycle.global_analytics.qualified_theses.length} QUALIFIED, ${dossierExpertCycle.global_analytics.rejected_theses.length} REJECTED and ${dossierExpertCycle.global_analytics.insufficient_theses.length} INSUFFICIENT decisions. INSUFFICIENT is final for that audit run, while the exploratory layer remains deliberately non-terminal.

The D3 living layer traverses ${dossierLiving.constellations.length} topic constellations as a revisable directed multigraph of ${dossierLiving.graph.nodes.length} nodes and ${dossierLiving.graph.edges.length} edges, including ${dossierLivingCrossEdges} cross-constellation links. GX1–GX7 gestures are triggered by the question rather than executed as a fixed questionnaire; every active non-question move records a GG1–GG7 gain, and G0–G4 marks generative kind rather than truth or confidence. The run stops only at sufficient openness: transformed problem, live rival, reverse pressure, formal indication, typed remainder and a reopening condition. Its field note is the primary philosophical output; the larger graph report remains an audit substrate.

The 0.6 Geviert adversarial regression adds a source-resistance gate before registry closure. It detects ${geviertHypothesis.source_resistance?.central_terms?.length ?? 0} source-backed central terms outside the legacy topic space, preserves explicit project claims for separate adjudication, emits ${geviertEtymology.coverage.cards_emitted} ETY cards and creates ${geviertLiving.method_mutations?.length ?? 0} source-forced experimental operator mutation. 'RELATION_FIRST' remains only one rival representation alongside relata-first, reciprocal, co-constitutive and unresolved-ontology modes. The mutation remains reversible and requires rival-unitization plus cross-corpus regression.

The 0.7 cross-corpus operator regression turns the 0.6 retirement requirement into an executable lifecycle gate. The Geviert-derived candidate is tested against Saussure transfer, Spinoza and Aristotle mixed controls, and a Descartes negative control. ${crossCorpusOperatorRegression.summary.expectations_passed}/${crossCorpusOperatorRegression.summary.corpora} preregistered expectations pass; the candidate is therefore only ${crossCorpusOperatorRegression.operator_state} with action ${crossCorpusOperatorRegression.recommended_action}. Negative-control activation would quarantine it, and absence of positive transfer would retire it. No regression outcome promotes the candidate into frozen CORE or establishes philosophical truth.

The 0.8 operator-competition layer prevents a transferable operator family from becoming a new default ontology. Four source-born profiles are birth-audited against their origin refinery/living traces and then compete locally across five targets. ${operatorCompetition.summary.expectations_passed}/${operatorCompetition.summary.targets} preregistered target expectations pass: ${operatorCompetition.summary.local_winners} local winners, ${operatorCompetition.summary.local_compositions} local composition and ${operatorCompetition.summary.abstentions} full abstention. The Aristotle case composes asymmetric dependence with local mode variation; the Descartes control forces abstention rather than a least-bad operator. These are routing results only, not philosophical truth or CORE promotion.

The 0.4 benchmark freezes those ${dossierBenchmarkManifest.units.length} thesis decisions separately from two blind coder packets. Because no independent raw annotations or adjudicated gold exist, evaluation correctly returns ${dossierBenchmarkResult.outcome}, emits no confusion/F1/calibration metrics and records that the sample is below the preregistered ${dossierBenchmarkManifest.evaluation_plan.minimum_units}-unit minimum. A balanced 80-unit synthetic fixture passes the computational gate only as a regression test; it is not empirical evidence.
`;
await writeFile(path.join(root, "VALIDATION_REPORT.md"), md, "utf8");

await writeRoCrate(root, path.join(root, "ro-crate-metadata.json"), {
  overwrite: true,
  engineVersion: engine.context.engineVersion,
  generatedAt,
  name: `Destruktion Automation Engine ${engine.context.engineVersion} research object`,
  description: "Portable AI-chat Destruktion 4.0 project with dual execution profiles, mandatory ETY-0.2, non-linear D3 exploratory constellations, source-forced operator evolution, local operator competition/composition/abstention, autonomous expert cycle, frozen blind benchmark, fixtures, tests, reports and provenance.",
});

async function listFiles(dir) {
  const output = [];
  for (const name of (await readdir(dir)).sort()) {
    if (name === "node_modules" || name === "RELEASE_MANIFEST.json") continue;
    const full = path.join(dir, name);
    const info = await stat(full);
    if (info.isDirectory()) output.push(...await listFiles(full));
    else output.push(full);
  }
  return output;
}

const hashes = {};
for (const file of await listFiles(root)) {
  const bytes = await readFile(file);
  hashes[path.relative(root, file).replaceAll(path.sep, "/")] = createHash("sha256").update(bytes).digest("hex");
}
const coreFiles = Object.fromEntries(Object.entries(hashes).filter(([name]) => name.startsWith("vendor/core4/")));
const manifest = {
  release: `Destruktion Automation Engine ${engine.context.engineVersion}`,
  generated_at: generatedAt,
  status: "DEVELOPER-TESTED / EXTERNAL-SEMANTIC-VALIDATION-PENDING",
  frozen_core: { version: "CORE 4.0.0-alpha.1", changed: false, files: coreFiles },
  integrated_scope: {
    ai_chat_portable_project: portableProject.portable_project_version,
    ai_chat_entrypoint: portableProject.entrypoint,
    ai_chat_required_assets: portableProject.required_assets.length,
    ai_chat_execution_profiles: Object.keys(portableProject.execution_profiles),
    ai_chat_document_only_pseudo_execution: portableProject.invariants.document_only_may_claim_code_execution,
    source_v38_protocol_occurrences: protocolInventory.explicit_control_heading_occurrences,
    protocol_families: protocolInventory.registry_families,
    module_4d_upstream_integrity: upstream4d.integrity_check,
    module_4d_upstream_entries: upstream4d.verified_entries,
    module_4d_upstream_archive_sha256: upstream4d.archive_sha256,
    module_4d_engine_compatibility_candidates: candidates4d.counts.files,
    heidegger_ga_catalog_entries: gaPilot.catalog.official_entries,
    heidegger_ga_pilot: gaPilot.verdict,
    heidegger_ga_first_work_pages: gaWorkBundle.page_count,
    heidegger_ga_first_work_units: gaWorkBundle.unit_count,
    heidegger_ga_first_work_candidates: gaWorkBundle.candidate_record_count,
    user_docx_intake: "IMPLEMENTED",
    user_docx_renderer_pages: dossierBundle.page_count,
    user_docx_units: dossierBundle.unit_count,
    user_docx_candidates: dossierBundle.candidate_record_count,
    corpus_refinery: "IMPLEMENTED",
    corpus_refinery_ooxml_segments: dossierSegmentation.counts.ooxml_total,
    corpus_refinery_argument_segments: dossierSegmentation.counts.argument_units,
    corpus_refinery_claim_candidates: dossierClaimLedger.length,
    corpus_refinery_deleted_segments: dossierArchiveMap.counts.deleted_segments,
    corpus_refinery_formula_containers: dossierFormulaRegistry.formula_count,
    autonomous_expert_cycle: "IMPLEMENTED",
    autonomous_expert_theses: dossierExpertCycle.thesis_results.length,
    autonomous_expert_all_terminal: dossierExpertCycle.output_contract.all_theses_terminal,
    final_analytics: "EMITTED_AS_MARKDOWN_AND_JSON",
    mandatory_etymology_protocol: geviertEtymology.protocol_version,
    mandatory_etymology_cards: geviertEtymology.coverage.cards_emitted,
    mandatory_etymology_full_cards: geviertEtymology.coverage.ety_full_executed,
    mandatory_etymology_unresolved_fields: geviertEtymology.coverage.unresolved_fields,
    mandatory_etymology_semantic_promotion: geviertEtymology.output_contract.semantic_promotion_performed,
    living_exploratory_layer: geviertLiving.layer.layer_id,
    living_constellations: geviertLiving.constellations.length,
    living_nodes: geviertLiving.graph.nodes.length,
    living_edges: geviertLiving.graph.edges.length,
    living_cross_constellation_edges: geviertCrossEdges,
    source_resistance_gate: geviertHypothesis.source_resistance?.status ?? "UNRESOLVED",
    source_resistance_central_terms: geviertHypothesis.source_resistance?.central_terms?.length ?? 0,
    experimental_method_mutations: geviertLiving.method_mutations?.length ?? 0,
    cross_corpus_operator_regression: crossCorpusOperatorRegression.outcome,
    cross_corpus_operator_state: crossCorpusOperatorRegression.operator_state,
    cross_corpus_operator_action: crossCorpusOperatorRegression.recommended_action,
    cross_corpus_operator_corpora: crossCorpusOperatorRegression.summary.corpora,
    cross_corpus_operator_expectations_passed: crossCorpusOperatorRegression.summary.expectations_passed,
    operator_competition: operatorCompetition.outcome,
    operator_competition_candidates: operatorCompetition.summary.candidates,
    operator_competition_targets: operatorCompetition.summary.targets,
    operator_competition_expectations_passed: operatorCompetition.summary.expectations_passed,
    operator_competition_local_compositions: operatorCompetition.summary.local_compositions,
    operator_competition_abstentions: operatorCompetition.summary.abstentions,
    philosophical_field_note: "EMITTED",
    frozen_blind_benchmark: "IMPLEMENTED",
    benchmark_units: dossierBenchmarkManifest.units.length,
    benchmark_outcome: dossierBenchmarkResult.outcome,
    benchmark_frozen_minimum_units: dossierBenchmarkManifest.evaluation_plan.minimum_units,
    empirical_metrics: ["confusion matrix", "per-class precision/recall/F1", "macro-F1 bootstrap CI", "abstention and coverage", "dangerous overpromotion", "decision Brier/ECE", "risk-coverage"],
    unicode_word_boundaries: "IMPLEMENTED",
    page_aware_derivative_intake: "IMPLEMENTED",
    source_policy_gate: "IMPLEMENTED",
    lexical_languages: ["DE", "RU", "EN"],
    external_models: ["SHACL-inspired validation results", "PROV-O provenance roles", "AIF/Carneades argumentation", "OSF-style plan freezing", "Krippendorff alpha", "INCEpTION-style annotation/agreement/curation separation", "scikit-learn-compatible classification and calibration semantics", "RO-Crate 1.3 packaging", "W3C Web Annotation position selectors", "TEI page milestones", "IIIF Manifest/Canvas/Range structure", "OpenAI Responses structured-output adapter with explicit transfer authorization"],
  },
  conformance: {
    ai_chat_portable_project: portableValidation.conformant ? "IMPLEMENTED_AND_CONFORMANT" : "FAILED",
    repaired_4a_fixtures: repaired4a.counts,
    verified_4d_upstream: { integrity: upstream4d.integrity_check, entries: upstream4d.verified_entries },
    engine_compatibility_4d_fixtures: candidates4d.counts,
    automated_tests: { tests, passed, failed },
    protocol_execution: "IMPLEMENTED",
    autonomous_expert_cycle: "IMPLEMENTED",
    terminal_run_bound_adjudication: "IMPLEMENTED",
    mandatory_etymology_prepass: dossierLivingEtymologyValidation.conformant ? "IMPLEMENTED_AND_CONFORMANT" : "FAILED",
    etymology_semantic_firewall: dossierLivingEtymology.output_contract.semantic_promotion_performed ? "FAILED" : "IMPLEMENTED",
    living_nonlinear_graph: geviertLivingValidation.conformant ? "IMPLEMENTED_AND_CONFORMANT" : "FAILED",
    living_sufficient_openness: geviertLiving.sufficient_openness.satisfied,
    living_terminal_verdicts: geviertLiving.output_contract.terminal_verdicts_emitted,
    operator_cross_corpus_regression: crossCorpusOperatorRegression.outcome,
    operator_cross_corpus_promotion_status: crossCorpusOperatorRegression.promotion_status,
    operator_competition: operatorCompetition.outcome,
    operator_competition_promotion_status: operatorCompetition.promotion_status,
    operator_competition_routing_policy: operatorCompetition.routing_policy,
    frozen_blind_benchmark: "IMPLEMENTED",
    benchmark_fixity_and_gold_lineage: "IMPLEMENTED",
    empirical_promotion_gate: dossierBenchmarkResult.outcome,
    local_plan_integrity: "IMPLEMENTED",
    agreement_calculation: "IMPLEMENTED",
    external_interrater: "NOT ESTABLISHED",
    external_domain_validation: "NOT ESTABLISHED",
  },
  file_count: Object.keys(hashes).length,
  sha256: hashes,
};
await writeFile(path.join(root, "RELEASE_MANIFEST.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`Release artifacts generated: ${Object.keys(hashes).length} hashed files, ${passed}/${tests} tests passed, ${protocolInventory.registry_families} protocol families integrated.`);
