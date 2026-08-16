import { createEngine } from "./engine.mjs";
import { analyzeText } from "./analyzer.mjs";
import { analyzePagedText } from "./page-analyzer.mjs";
import { analyzeDocx } from "./docx-intake.mjs";
import { refineDocx } from "./corpus-refinery.mjs";
import { runExpertCycle, runExpertDocx } from "./expert-cycle.mjs";
import { runLivingAnalysis, validateLivingAnalysisFile } from "./living-analysis.mjs";
import { runOperatorRegression } from "./operator-regression.mjs";
import { runOperatorCompetition } from "./operator-competition.mjs";
import { runMicroLocalEcology } from "./micro-local-ecology.mjs";
import { gateOperatorDelta } from "../mutation/operator-mutation-engine.mjs";
import { runEtymologyProtocol, validateEtymologyPassFile } from "./etymology.mjs";
import { evaluateAgreement } from "./agreement.mjs";
import { evaluateExpertBenchmark, initExpertBenchmark } from "./benchmark.mjs";
import { validateArgumentBundle } from "./argument-graph.mjs";
import { initProtocolRun, validateProtocolRun } from "./protocol-runner.mjs";
import { freezeResearchPlan, verifyResearchPlan } from "./research-plan.mjs";
import { writeRoCrate } from "./ro-crate.mjs";
import { portableProjectCard, readPortableProjectManifest, validatePortableProject } from "./portable-project.mjs";
import { validateRun, validateRun4d } from "./run-validator.mjs";
import { formatProtocolReport, formatRunReport, formatValidationReport } from "./report.mjs";

const HELP = `Destruktion Automation Engine 0.10.0-alpha.1

Usage:
  destruktion validate <record.json|directory>... [--json] [--fail-on-review]
  destruktion validate-run <run.json> [--json] [--fail-on-review]
  destruktion validate-run-4d <run.json> [--json] [--fail-on-review]
  destruktion analyze <source.txt|source.md> --out <new-directory> [--json]
  destruktion analyze-pages <source.txt> --manifest <source-manifest.json> --out <new-directory> [--json]
  destruktion analyze-docx <source.docx> --job <docx-job.json> --out <new-directory> [--json]
  destruktion refine-docx <source.docx> --job <docx-job.json> --out <new-directory> [--page-run <analyze-docx-output>] [--json]
  destruktion etymology-cycle <refinery-directory> --out <new-directory> [--json]
  destruktion etymology-validate <etymology_pass.json> [--json]
  destruktion living-cycle <refinery-directory> --out <new-directory> [--registry <living-operator-registry.json>] [--seed <text>] [--max-families <n>] [--max-operators <n>] [--json]
  destruktion living-validate <living_analysis.json> [--json]
  destruktion operator-mutation <operator_delta.json> --registry <registry.json> --policy <policy.json> --out <new-directory> [--json]
  destruktion operator-regression <manifest.json> --out <new-directory> [--json]
  destruktion operator-competition <manifest.json> --out <new-directory> [--json]
  destruktion micro-local-ecology <hypothesis_bank.json> --out <new-directory> [--json]
  destruktion portable-check [project-directory] [--json]
  destruktion portable-card [project-directory] [--json]
  destruktion expert-cycle <refinery-directory> --out <new-directory> [--profile <expert-profile.json>] [--provider deterministic|openai] [--docx <source.docx>] [--model <model>] [--allow-external-source-transfer] [--json]
  destruktion expert-docx <source.docx> --job <docx-job.json> --out <new-directory> [--page-run <analyze-docx-output>] [--profile <expert-profile.json>] [--provider deterministic|openai] [--model <model>] [--allow-external-source-transfer] [--json]
  destruktion benchmark-init <expert_cycle.json>... --out <new-directory> [--min-units <n>=80] [--seed <text>] [--json]
  destruktion benchmark-evaluate <benchmark-directory> --out <new-directory> [--annotations <directory>] [--gold <gold.json>] [--json]
  destruktion protocols [--json]
  destruktion protocol-show <protocol-id> [--json]
  destruktion protocol-init <protocol-id> --out <new-file.json>
  destruktion protocol-run <run.json> [--json] [--fail-on-review]
  destruktion freeze-plan <plan.json> --out <new-lock.json> [--json]
  destruktion verify-plan <plan.json> <lock.json> [--json]
  destruktion agreement <annotations.json> [--json]
  destruktion validate-argument <argument-bundle.json> [--json] [--fail-on-review]
  destruktion export-crate <directory> --out <directory/ro-crate-metadata.json> [--json]
  destruktion explain <RT00..RT28> [--json]
  destruktion rules [--json]
  destruktion version

Exit codes: 0 conformant, 1 conformance/review policy failure, 2 usage/runtime error.
`;

function options(args) {
  return {
    json: args.includes("--json"),
    failOnReview: args.includes("--fail-on-review"),
    positional: args.filter((arg) => !arg.startsWith("--")),
  };
}

export async function main(argv) {
  const [command, ...rest] = argv;
  if (!command || ["help", "--help", "-h"].includes(command)) {
    console.log(HELP);
    return 0;
  }
  if (command === "version" || command === "--version") {
    console.log("0.10.0-alpha.1");
    return 0;
  }

  const engine = await createEngine();
  const opt = options(rest);
  if (command === "portable-check") {
    if (opt.positional.length > 1) throw new Error("portable-check accepts at most one project directory");
    const result = await validatePortableProject(engine, opt.positional[0]);
    if (opt.json) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `PORTABLE PROJECT  conformant=${result.conformant}`,
      `version=${result.manifest?.portable_project_version ?? "UNRESOLVED"} assets=${result.manifest?.required_assets?.length ?? 0}`,
      `errors=${result.counts.ERROR} review=${result.counts.REVIEW} warnings=${result.counts.WARNING}`,
      `entrypoint=${result.manifest?.entrypoint ?? "UNRESOLVED"}`,
      ...result.issues.map((item) => `  ${item.severity.padEnd(7)} ${item.code} ${item.at} — ${item.message}`),
    ].join("\n"));
    return result.conformant ? 0 : 1;
  }
  if (command === "portable-card") {
    if (opt.positional.length > 1) throw new Error("portable-card accepts at most one project directory");
    const projectRoot = opt.positional[0];
    const validation = await validatePortableProject(engine, projectRoot);
    if (!validation.conformant) {
      console.log(opt.json ? JSON.stringify(validation, null, 2) : [
        "PORTABLE PROJECT INVALID",
        ...validation.issues.map((item) => `  ${item.severity.padEnd(7)} ${item.code} ${item.at} — ${item.message}`),
      ].join("\n"));
      return 1;
    }
    const card = portableProjectCard(await readPortableProjectManifest(projectRoot));
    console.log(opt.json ? JSON.stringify(card, null, 2) : [
      `${card.title}`,
      `portable=${card.portable_project_version} engine=${card.engine_version} entrypoint=${card.entrypoint}`,
      `profiles=${Object.entries(card.execution_profiles).map(([key, value]) => `${key}:${value}`).join(", ")}`,
      `inputs=${card.supported_inputs.join(", ")}`,
      `mandatory_etymology=${card.mandatory_etymology} outputs=${card.primary_outputs.join(", ")}`,
      `Claim ceiling: ${card.claim_ceiling}.`,
    ].join("\n"));
    return 0;
  }
  if (command === "validate") {
    if (!opt.positional.length) throw new Error("validate requires at least one JSON file or directory");
    const report = await engine.validateInputs(opt.positional);
    console.log(opt.json ? JSON.stringify(report, null, 2) : formatValidationReport(report));
    return report.counts.ERROR > 0 || (opt.failOnReview && report.counts.REVIEW > 0) ? 1 : 0;
  }
  if (command === "validate-run") {
    if (opt.positional.length !== 1) throw new Error("validate-run requires exactly one run manifest");
    const result = await validateRun(engine, opt.positional[0]);
    console.log(opt.json ? JSON.stringify(result, null, 2) : formatRunReport(result));
    return !result.conformant || (opt.failOnReview && result.review_required) ? 1 : 0;
  }
  if (command === "validate-run-4d") {
    if (opt.positional.length !== 1) throw new Error("validate-run-4d requires exactly one run manifest");
    const result = await validateRun4d(engine, opt.positional[0]);
    console.log(opt.json ? JSON.stringify(result, null, 2) : formatRunReport(result));
    return !result.conformant || (opt.failOnReview && result.review_required) ? 1 : 0;
  }
  if (command === "analyze") {
    const outIndex = rest.indexOf("--out");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("analyze requires --out <new-directory>");
    const inputArgs = rest.filter((arg, index) => index !== outIndex && index !== outIndex + 1 && !arg.startsWith("--"));
    if (inputArgs.length !== 1) throw new Error("analyze requires exactly one UTF-8 text or Markdown source");
    const result = await analyzeText(engine, inputArgs[0], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `ANALYSIS CANDIDATES  source=${result.bundle.source.source_id}`,
      `units=${result.bundle.unit_count} records=${result.bundle.candidate_record_count}`,
      `conformant=${result.validation.counts.conformant} errors=${result.validation.counts.ERROR} review_required=${result.validation.counts.review_required}`,
      `output=${result.output_dir}`,
      "Claim ceiling: candidate generation only; human/domain review is mandatory."
    ].join("\n"));
    return result.validation.counts.ERROR > 0 ? 1 : 0;
  }
  if (command === "analyze-pages") {
    const outIndex = rest.indexOf("--out");
    const manifestIndex = rest.indexOf("--manifest");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("analyze-pages requires --out <new-directory>");
    if (manifestIndex < 0 || !rest[manifestIndex + 1]) throw new Error("analyze-pages requires --manifest <source-manifest.json>");
    const excluded = new Set([outIndex, outIndex + 1, manifestIndex, manifestIndex + 1]);
    const inputArgs = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (inputArgs.length !== 1) throw new Error("analyze-pages requires exactly one form-feed-delimited UTF-8 source");
    const result = await analyzePagedText(engine, inputArgs[0], rest[manifestIndex + 1], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `PAGED ANALYSIS  source=${result.bundle.source.source_id}`,
      `pages=${result.bundle.page_count} units=${result.bundle.unit_count} records=${result.bundle.candidate_record_count}`,
      `conformant=${result.validation.counts.conformant} errors=${result.validation.counts.ERROR} review_required=${result.validation.counts.review_required}`,
      `raw_text_included=${result.bundle.raw_text_included} output=${result.output_dir}`,
      "Claim ceiling: page-resolved derivative candidates only; source and semantic review remain mandatory."
    ].join("\n"));
    return result.validation.counts.ERROR > 0 ? 1 : 0;
  }
  if (command === "analyze-docx") {
    const outIndex = rest.indexOf("--out");
    const jobIndex = rest.indexOf("--job");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("analyze-docx requires --out <new-directory>");
    if (jobIndex < 0 || !rest[jobIndex + 1]) throw new Error("analyze-docx requires --job <docx-job.json>");
    const excluded = new Set([outIndex, outIndex + 1, jobIndex, jobIndex + 1]);
    const inputArgs = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (inputArgs.length !== 1) throw new Error("analyze-docx requires exactly one DOCX source");
    const result = await analyzeDocx(engine, inputArgs[0], rest[jobIndex + 1], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify({ output_dir: result.output_dir, intake: result.intake, bundle: result.bundle, validation: result.validation }, null, 2));
    else console.log([
      `DOCX ANALYSIS  source=${result.bundle.source.source_id}`,
      `rendered_pages=${result.intake.rendering.page_count} units=${result.bundle.unit_count} records=${result.bundle.candidate_record_count}`,
      `conformant=${result.validation.counts.conformant} errors=${result.validation.counts.ERROR} review_required=${result.validation.counts.review_required}`,
      `raw_text_retained=${result.intake.retention.extracted_text_retained} output=${result.output_dir}`,
      "Claim ceiling: renderer-resolved derivative candidates and document-structure audit only; human source and semantic review remain mandatory."
    ].join("\n"));
    return result.validation.counts.ERROR > 0 ? 1 : 0;
  }
  if (command === "refine-docx") {
    const outIndex = rest.indexOf("--out");
    const jobIndex = rest.indexOf("--job");
    const pageRunIndex = rest.indexOf("--page-run");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("refine-docx requires --out <new-directory>");
    if (jobIndex < 0 || !rest[jobIndex + 1]) throw new Error("refine-docx requires --job <docx-job.json>");
    if (pageRunIndex >= 0 && !rest[pageRunIndex + 1]) throw new Error("refine-docx --page-run requires an analyze-docx output directory");
    const excluded = new Set([outIndex, outIndex + 1, jobIndex, jobIndex + 1]);
    if (pageRunIndex >= 0) {
      excluded.add(pageRunIndex);
      excluded.add(pageRunIndex + 1);
    }
    const inputArgs = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (inputArgs.length !== 1) throw new Error("refine-docx requires exactly one DOCX source");
    const result = await refineDocx(engine, inputArgs[0], rest[jobIndex + 1], rest[outIndex + 1], {
      ...(pageRunIndex >= 0 ? { pageRun: rest[pageRunIndex + 1] } : {}),
    });
    if (rest.includes("--json")) console.log(JSON.stringify({ output_dir: result.output_dir, report: result.report, claim_ledger_summary: result.claim_ledger_summary }, null, 2));
    else console.log([
      `CORPUS REFINERY  source=${result.report.source_id}`,
      `ooxml=${result.report.counts.ooxml_segments} renderer=${result.report.counts.renderer_segments} arguments=${result.report.counts.argument_segments}`,
      `claims=${result.report.counts.claim_ledger_entries} formulas=${result.report.counts.formulas} exact_duplicate_groups=${result.report.counts.exact_duplicate_groups}`,
      `schema_errors=${result.report.validation.total_errors} deleted_segments=${result.report.output_contract.deleted_segments} output=${result.output_dir}`,
      "Claim ceiling: segmentation, source routing and hypothesis discovery only; A/P/B, rivals and semantic promotion require human review."
    ].join("\n"));
    return result.report.validation.total_errors > 0 ? 1 : 0;
  }
  if (command === "living-cycle") {
    const outIndex = rest.indexOf("--out");
    const seedIndex = rest.indexOf("--seed");
    const familiesIndex = rest.indexOf("--max-families");
    const operatorsIndex = rest.indexOf("--max-operators");
    const registryIndex = rest.indexOf("--registry");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("living-cycle requires --out <new-directory>");
    for (const [index, flag] of [[seedIndex, "--seed"], [familiesIndex, "--max-families"], [operatorsIndex, "--max-operators"], [registryIndex, "--registry"]]) {
      if (index >= 0 && !rest[index + 1]) throw new Error(`living-cycle ${flag} requires a value`);
    }
    const excluded = new Set([outIndex, outIndex + 1]);
    for (const index of [seedIndex, familiesIndex, operatorsIndex, registryIndex]) {
      if (index >= 0) {
        excluded.add(index);
        excluded.add(index + 1);
      }
    }
    const roots = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (roots.length !== 1) throw new Error("living-cycle requires exactly one Corpus Refinery directory");
    const maximumFamilies = familiesIndex >= 0 ? Number(rest[familiesIndex + 1]) : undefined;
    const maximumOperators = operatorsIndex >= 0 ? Number(rest[operatorsIndex + 1]) : undefined;
    if (maximumFamilies !== undefined && !Number.isInteger(maximumFamilies)) throw new Error("living-cycle --max-families must be an integer");
    if (maximumOperators !== undefined && !Number.isInteger(maximumOperators)) throw new Error("living-cycle --max-operators must be an integer");
    const result = await runLivingAnalysis(engine, roots[0], rest[outIndex + 1], {
      ...(seedIndex >= 0 ? { seed: rest[seedIndex + 1] } : {}),
      ...(maximumFamilies !== undefined ? { maximumFamilies } : {}),
      ...(maximumOperators !== undefined ? { maximumOperators } : {}),
      ...(registryIndex >= 0 ? { registryFile: rest[registryIndex + 1] } : {}),
    });
    if (rest.includes("--json")) console.log(JSON.stringify({ output_dir: result.output_dir, run_id: result.analysis.run_id, validation: result.validation, sufficient_openness: result.analysis.sufficient_openness }, null, 2));
    else console.log([
      `LIVING EXPLORATORY CYCLE  run=${result.analysis.run_id}`,
      `constellations=${result.analysis.constellations.length} nodes=${result.analysis.graph.nodes.length} edges=${result.analysis.graph.edges.length}`,
      `active_moves=${result.trace.constellations.reduce((sum, entry) => sum + entry.steps.length, 0)} all_moves_add_gain=${result.analysis.output_contract.each_active_step_adds_traceable_gain}`,
      `sufficient_openness=${result.analysis.sufficient_openness.satisfied} output=${result.output_dir}`,
      `living_analytics=${result.files.analytics}`,
      `philosophical_field_note=${result.files.field_note}`,
      "Claim ceiling: traceable generative reconstruction only; discovery is not justification and no terminal verdict is emitted.",
    ].join("\n"));
    return result.validation.conformant ? 0 : 1;
  }
  if (command === "etymology-cycle") {
    const outIndex = rest.indexOf("--out");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("etymology-cycle requires --out <new-directory>");
    const excluded = new Set([outIndex, outIndex + 1]);
    const roots = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (roots.length !== 1) throw new Error("etymology-cycle requires exactly one Corpus Refinery directory");
    const result = await runEtymologyProtocol(engine, roots[0], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify({ output_dir: result.output_dir, run_id: result.pass.run_id, coverage: result.pass.coverage, validation: result.validation }, null, 2));
    else console.log([
      `MANDATORY ETYMOLOGY  run=${result.pass.run_id}`,
      `concepts=${result.pass.coverage.central_concepts} ety_full=${result.pass.coverage.ety_full_executed} unresolved_fields=${result.pass.coverage.unresolved_fields}`,
      `coverage_complete=${result.pass.coverage.coverage_complete} knowledge_resolution=${result.pass.coverage.knowledge_resolution}`,
      `output=${result.output_dir}`,
      "Claim ceiling: mandatory etymological-semantic coverage, not conceptual or ontological proof.",
    ].join("\n"));
    return result.validation.conformant ? 0 : 1;
  }
  if (command === "etymology-validate") {
    const inputs = rest.filter((arg) => !arg.startsWith("--"));
    if (inputs.length !== 1) throw new Error("etymology-validate requires exactly one etymology_pass.json");
    const result = await validateEtymologyPassFile(engine, inputs[0]);
    if (rest.includes("--json")) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `ETYMOLOGY VALIDATION  conformant=${result.conformant}`,
      `errors=${result.counts.ERROR} review=${result.counts.REVIEW} warnings=${result.counts.WARNING}`,
      `file=${result.file}`,
    ].join("\n"));
    return result.conformant ? 0 : 1;
  }
  if (command === "living-validate") {
    const inputs = rest.filter((arg) => !arg.startsWith("--"));
    if (inputs.length !== 1) throw new Error("living-validate requires exactly one living_analysis.json");
    const result = await validateLivingAnalysisFile(engine, inputs[0]);
    if (rest.includes("--json")) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `LIVING ANALYSIS VALIDATION  conformant=${result.conformant}`,
      `errors=${result.counts.ERROR} review=${result.counts.REVIEW} warnings=${result.counts.WARNING}`,
      `file=${result.file}`,
    ].join("\n"));
    return result.conformant ? 0 : 1;
  }
  if (command === "operator-mutation") {
    const outIndex = rest.indexOf("--out");
    const registryIndex = rest.indexOf("--registry");
    const policyIndex = rest.indexOf("--policy");
    for (const [index, flag] of [[outIndex, "--out"], [registryIndex, "--registry"], [policyIndex, "--policy"]]) if (index < 0 || !rest[index + 1]) throw new Error(`operator-mutation requires ${flag} <path>`);
    const excluded = new Set([outIndex, outIndex + 1, registryIndex, registryIndex + 1, policyIndex, policyIndex + 1]);
    const inputs = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (inputs.length !== 1) throw new Error("operator-mutation requires exactly one operator_delta.json");
    const result = await gateOperatorDelta(inputs[0], rest[registryIndex + 1], rest[policyIndex + 1], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify(result.receipt, null, 2));
    else console.log([
      `OPERATOR MUTATION  delta=${result.receipt.delta_id}`,
      `decision=${result.receipt.decision.decision} promotion_ready=${result.receipt.decision.promotion_ready} reachability=${result.receipt.runtime_reachability}`,
      `candidate_registry=${result.files.candidate ?? "NONE"}`,
      `rollback=${result.files.rollback}`,
      `report=${result.files.report}`,
      "Candidate generation is reversible and does not silently replace the baseline registry.",
    ].join("\n"));
    return result.receipt.decision.promotion_ready ? 0 : 1;
  }
  if (command === "operator-regression") {
    const outIndex = rest.indexOf("--out");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("operator-regression requires --out <new-directory>");
    const inputs = rest.filter((arg, index) => index !== outIndex && index !== outIndex + 1 && !arg.startsWith("--"));
    if (inputs.length !== 1) throw new Error("operator-regression requires exactly one regression manifest");
    const result = await runOperatorRegression(engine, inputs[0], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify(result.result, null, 2));
    else console.log([
      `OPERATOR REGRESSION  candidate=${result.result.candidate_operator}`,
      `outcome=${result.result.outcome} corpora=${result.result.summary.corpora} expectations=${result.result.summary.expectations_passed}/${result.result.summary.corpora}`,
      `promotion=${result.result.promotion_status} output=${result.output_dir}`,
      `report=${result.files.report}`,
      `Claim ceiling: ${result.result.claim_ceiling}.`,
    ].join("\n"));
    return result.result.outcome === "SURVIVES_CROSS_CORPUS_REGRESSION" ? 0 : 1;
  }
  if (command === "operator-competition") {
    const outIndex = rest.indexOf("--out");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("operator-competition requires --out <new-directory>");
    const inputs = rest.filter((arg, index) => index !== outIndex && index !== outIndex + 1 && !arg.startsWith("--"));
    if (inputs.length !== 1) throw new Error("operator-competition requires exactly one competition manifest");
    const result = await runOperatorCompetition(engine, inputs[0], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify(result.result, null, 2));
    else console.log([
      `OPERATOR COMPETITION  outcome=${result.result.outcome}`,
      `candidates=${result.result.summary.candidates} births=${result.result.summary.source_births_confirmed}/${result.result.summary.candidates}`,
      `targets=${result.result.summary.targets} expectations=${result.result.summary.expectations_passed}/${result.result.summary.targets}`,
      `winners=${result.result.summary.local_winners} compositions=${result.result.summary.local_compositions} unresolved=${result.result.summary.unresolved_rivals} abstentions=${result.result.summary.abstentions}`,
      `promotion=${result.result.promotion_status} output=${result.output_dir}`,
      `report=${result.files.report}`,
      `Claim ceiling: ${result.result.claim_ceiling}.`,
    ].join("\n"));
    return result.result.outcome === "PASSES_LOCAL_OPERATOR_ECOLOGY_REGRESSION" ? 0 : 1;
  }
  if (command === "micro-local-ecology") {
    const outIndex = rest.indexOf("--out");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("micro-local-ecology requires --out <new-directory>");
    const inputs = rest.filter((arg, index) => index !== outIndex && index !== outIndex + 1 && !arg.startsWith("--"));
    if (inputs.length !== 1) throw new Error("micro-local-ecology requires exactly one hypothesis bank");
    const result = await runMicroLocalEcology(engine, inputs[0], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify(result.result, null, 2));
    else console.log([
      `MICRO-LOCAL ECOLOGY  outcome=${result.result.outcome}`,
      `windows=${result.result.counts.windows} known=${result.result.counts.known_only} open_set=${result.result.counts.open_set_only} rivals=${result.result.counts.rival_routes} abstentions=${result.result.counts.abstentions}`,
      `transitions=${result.result.counts.route_transitions} output=${result.output_dir}`,
      `report=${result.files.report}`,
      `Claim ceiling: ${result.result.claim_ceiling}.`,
    ].join("\n"));
    return result.result.outcome === "MICRO_LOCAL_ROUTING_AVAILABLE" ? 0 : 1;
  }
  if (command === "expert-cycle") {
    const outIndex = rest.indexOf("--out");
    const profileIndex = rest.indexOf("--profile");
    const providerIndex = rest.indexOf("--provider");
    const docxIndex = rest.indexOf("--docx");
    const modelIndex = rest.indexOf("--model");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("expert-cycle requires --out <new-directory>");
    for (const [index, flag] of [[profileIndex, "--profile"], [providerIndex, "--provider"], [docxIndex, "--docx"], [modelIndex, "--model"]]) {
      if (index >= 0 && !rest[index + 1]) throw new Error(`expert-cycle ${flag} requires a value`);
    }
    const excluded = new Set([outIndex, outIndex + 1]);
    for (const index of [profileIndex, providerIndex, docxIndex, modelIndex]) {
      if (index >= 0) {
        excluded.add(index);
        excluded.add(index + 1);
      }
    }
    const roots = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (roots.length !== 1) throw new Error("expert-cycle requires exactly one Corpus Refinery directory");
    const result = await runExpertCycle(engine, roots[0], rest[outIndex + 1], {
      ...(profileIndex >= 0 ? { profile: rest[profileIndex + 1] } : {}),
      provider: providerIndex >= 0 ? rest[providerIndex + 1] : "deterministic",
      ...(docxIndex >= 0 ? { docx: rest[docxIndex + 1] } : {}),
      ...(modelIndex >= 0 ? { model: rest[modelIndex + 1] } : {}),
      allowExternalSourceTransfer: rest.includes("--allow-external-source-transfer"),
    });
    if (rest.includes("--json")) console.log(JSON.stringify({ output_dir: result.output_dir, cycle: result.cycle }, null, 2));
    else console.log([
      `AUTONOMOUS EXPERT CYCLE  run=${result.cycle.run_id}`,
      `theses=${result.cycle.thesis_results.length} supported=${result.cycle.global_analytics.supported_theses.length} qualified=${result.cycle.global_analytics.qualified_theses.length} rejected=${result.cycle.global_analytics.rejected_theses.length} insufficient=${result.cycle.global_analytics.insufficient_theses.length}`,
      `backend=${result.cycle.backend.kind} all_terminal=${result.cycle.output_contract.all_theses_terminal} output=${result.output_dir}`,
      `final_analytics=${result.final_analytics}`,
      "Claim ceiling: final expert adjudication for this run; not infallibility or external validation.",
    ].join("\n"));
    return 0;
  }
  if (command === "expert-docx") {
    const outIndex = rest.indexOf("--out");
    const jobIndex = rest.indexOf("--job");
    const pageRunIndex = rest.indexOf("--page-run");
    const profileIndex = rest.indexOf("--profile");
    const providerIndex = rest.indexOf("--provider");
    const modelIndex = rest.indexOf("--model");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("expert-docx requires --out <new-directory>");
    if (jobIndex < 0 || !rest[jobIndex + 1]) throw new Error("expert-docx requires --job <docx-job.json>");
    for (const [index, flag] of [[pageRunIndex, "--page-run"], [profileIndex, "--profile"], [providerIndex, "--provider"], [modelIndex, "--model"]]) {
      if (index >= 0 && !rest[index + 1]) throw new Error(`expert-docx ${flag} requires a value`);
    }
    const excluded = new Set([outIndex, outIndex + 1, jobIndex, jobIndex + 1]);
    for (const index of [pageRunIndex, profileIndex, providerIndex, modelIndex]) {
      if (index >= 0) {
        excluded.add(index);
        excluded.add(index + 1);
      }
    }
    const inputs = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (inputs.length !== 1) throw new Error("expert-docx requires exactly one DOCX source");
    const result = await runExpertDocx(engine, inputs[0], rest[jobIndex + 1], rest[outIndex + 1], {
      ...(pageRunIndex >= 0 ? { pageRun: rest[pageRunIndex + 1] } : {}),
      ...(profileIndex >= 0 ? { profile: rest[profileIndex + 1] } : {}),
      provider: providerIndex >= 0 ? rest[providerIndex + 1] : "deterministic",
      ...(modelIndex >= 0 ? { model: rest[modelIndex + 1] } : {}),
      allowExternalSourceTransfer: rest.includes("--allow-external-source-transfer"),
    });
    if (rest.includes("--json")) console.log(JSON.stringify({ output_dir: result.output_dir, pipeline: result.pipeline, cycle: result.expert.cycle }, null, 2));
    else console.log([
      `EXPERT DOCX PIPELINE  run=${result.pipeline.run_id}`,
      `refinery=COMPLETE expert_cycle=COMPLETE final_analytics=COMPLETE`,
      `theses=${result.expert.cycle.thesis_results.length} output=${result.output_dir}`,
      `final_analytics=${result.output_dir}/FINAL_ANALYTICS.md`,
      "Claim ceiling: final expert adjudication for this run; not infallibility or external validation.",
    ].join("\n"));
    return 0;
  }
  if (command === "benchmark-init") {
    const outIndex = rest.indexOf("--out");
    const minimumIndex = rest.indexOf("--min-units");
    const seedIndex = rest.indexOf("--seed");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("benchmark-init requires --out <new-directory>");
    for (const [index, flag] of [[minimumIndex, "--min-units"], [seedIndex, "--seed"]]) {
      if (index >= 0 && !rest[index + 1]) throw new Error(`benchmark-init ${flag} requires a value`);
    }
    const excluded = new Set([outIndex, outIndex + 1]);
    for (const index of [minimumIndex, seedIndex]) {
      if (index >= 0) {
        excluded.add(index);
        excluded.add(index + 1);
      }
    }
    const cycles = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (!cycles.length) throw new Error("benchmark-init requires at least one expert_cycle.json");
    const minimumUnits = minimumIndex >= 0 ? Number(rest[minimumIndex + 1]) : 80;
    if (!Number.isInteger(minimumUnits) || minimumUnits < 80) throw new Error("benchmark-init --min-units must be an integer >= 80");
    const result = await initExpertBenchmark(engine, cycles, rest[outIndex + 1], {
      minimumUnits,
      ...(seedIndex >= 0 ? { seed: rest[seedIndex + 1] } : {}),
    });
    if (rest.includes("--json")) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `FROZEN BLIND BENCHMARK  id=${result.benchmark_id}`,
      `units=${result.unit_count} minimum=${result.minimum_units} power=${result.unit_count >= result.minimum_units ? "READY" : "UNDERPOWERED"}`,
      `status=${result.status} manifest_sha256=${result.manifest_sha256}`,
      `output=${result.output_dir}`,
      "Predictions are sealed; share only blind_packets with independent coders.",
    ].join("\n"));
    return 0;
  }
  if (command === "benchmark-evaluate") {
    const outIndex = rest.indexOf("--out");
    const annotationsIndex = rest.indexOf("--annotations");
    const goldIndex = rest.indexOf("--gold");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("benchmark-evaluate requires --out <new-directory>");
    for (const [index, flag] of [[annotationsIndex, "--annotations"], [goldIndex, "--gold"]]) {
      if (index >= 0 && !rest[index + 1]) throw new Error(`benchmark-evaluate ${flag} requires a value`);
    }
    const excluded = new Set([outIndex, outIndex + 1]);
    for (const index of [annotationsIndex, goldIndex]) {
      if (index >= 0) {
        excluded.add(index);
        excluded.add(index + 1);
      }
    }
    const roots = rest.filter((arg, index) => !excluded.has(index) && !arg.startsWith("--"));
    if (roots.length !== 1) throw new Error("benchmark-evaluate requires exactly one benchmark directory");
    const result = await evaluateExpertBenchmark(engine, roots[0], rest[outIndex + 1], {
      ...(annotationsIndex >= 0 ? { annotationsDirectory: rest[annotationsIndex + 1] } : {}),
      ...(goldIndex >= 0 ? { goldFile: rest[goldIndex + 1] } : {}),
    });
    if (rest.includes("--json")) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `EMPIRICAL BENCHMARK  id=${result.result.benchmark_id ?? "INVALID"}`,
      `outcome=${result.result.outcome} units=${result.result.unit_count}`,
      `promotion=${result.result.promotion_gate.passed ? "PASS" : "NOT_PASSED"} output=${result.output_dir}`,
      `report=${result.output_dir}/FINAL_BENCHMARK_REPORT.md`,
      `Claim ceiling: ${result.result.claim_ceiling}.`,
    ].join("\n"));
    return result.result.outcome === "PASS_PROMOTION_GATE" ? 0 : 1;
  }
  if (command === "protocols") {
    const payload = engine.context.protocolRegistry.protocols.map(({ id, title_ru, group, status, automation, activation, value }) => ({ id, title_ru, group, status, automation, activation, value }));
    if (rest.includes("--json")) console.log(JSON.stringify({ registry_version: engine.context.protocolRegistry.registry_version, count: payload.length, protocols: payload }, null, 2));
    else console.log(payload.map((item) => `${item.id.padEnd(30)} ${item.status.padEnd(30)} ${item.automation.padEnd(12)} ${item.title_ru}`).join("\n"));
    return 0;
  }
  if (command === "protocol-show") {
    if (opt.positional.length !== 1) throw new Error("protocol-show requires one protocol identifier");
    const protocol = engine.context.protocolRegistry.protocols.find((item) => item.id === opt.positional[0].toUpperCase());
    if (!protocol) throw new Error(`Unknown protocol '${opt.positional[0]}'.`);
    if (rest.includes("--json")) console.log(JSON.stringify(protocol, null, 2));
    else console.log([
      `${protocol.id} — ${protocol.title_ru}`,
      `Status: ${protocol.status}; automation: ${protocol.automation}; activation: ${protocol.activation}`,
      `Value: ${protocol.value}`,
      ...protocol.checks.map((check) => `  ${check.id}: ${check.prompt}`),
    ].join("\n"));
    return 0;
  }
  if (command === "protocol-init") {
    const outIndex = rest.indexOf("--out");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("protocol-init requires --out <new-file.json>");
    const ids = rest.filter((arg, index) => index !== outIndex && index !== outIndex + 1 && !arg.startsWith("--"));
    if (ids.length !== 1) throw new Error("protocol-init requires exactly one protocol identifier");
    const result = await initProtocolRun(engine, ids[0].toUpperCase(), rest[outIndex + 1]);
    console.log(`Created ${result.protocol.id} run template: ${result.output_file}`);
    return 0;
  }
  if (command === "protocol-run") {
    if (opt.positional.length !== 1) throw new Error("protocol-run requires exactly one run JSON file");
    const result = await validateProtocolRun(engine, opt.positional[0]);
    console.log(opt.json ? JSON.stringify(result, null, 2) : formatProtocolReport(result));
    return !result.conformant || result.outcome === "SUSPEND" || (opt.failOnReview && result.review_required) ? 1 : 0;
  }
  if (command === "freeze-plan") {
    const outIndex = rest.indexOf("--out");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("freeze-plan requires --out <new-lock.json>");
    const plans = rest.filter((arg, index) => index !== outIndex && index !== outIndex + 1 && !arg.startsWith("--"));
    if (plans.length !== 1) throw new Error("freeze-plan requires exactly one research plan");
    const result = await freezeResearchPlan(engine, plans[0], rest[outIndex + 1]);
    if (rest.includes("--json")) console.log(JSON.stringify(result, null, 2));
    else console.log(result.written ? [
      `${result.execution_status}  plan=${result.preregistration_id}`,
      `sha256=${result.canonical_sha256}`,
      `lock=${result.lock_file}`,
      `Claim ceiling: ${result.claim_ceiling}.`,
    ].join("\n") : formatValidationReport({ results: [{ file: result.plan_file, record_id: null, conformant: false, review_required: false, counts: result.counts, issues: result.issues }], counts: { files: 1, conformant: 0, review_required: 0, ...result.counts } }));
    return result.written ? 0 : 1;
  }
  if (command === "verify-plan") {
    if (opt.positional.length !== 2) throw new Error("verify-plan requires a plan and its lock");
    const result = await verifyResearchPlan(engine, opt.positional[0], opt.positional[1]);
    if (opt.json) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `${result.unchanged ? "UNCHANGED" : "DEVIATED"}  plan=${result.preregistration_id}`,
      `frozen=${result.frozen_sha256}`,
      `current=${result.current_sha256}`,
      `deviations=${result.deviations.length}`,
      ...result.issues.map((item) => `  ${item.severity.padEnd(7)} ${item.code} ${item.at} — ${item.message}`),
      `Claim ceiling: ${result.claim_ceiling}.`,
    ].join("\n"));
    return result.unchanged ? 0 : 1;
  }
  if (command === "agreement") {
    if (opt.positional.length !== 1) throw new Error("agreement requires exactly one annotation set");
    const result = await evaluateAgreement(engine, opt.positional[0]);
    if (opt.json) console.log(JSON.stringify(result, null, 2));
    else {
      const alpha = result.metrics?.nominal?.alpha;
      const ci = result.metrics?.bootstrap?.alpha_ci95 ?? [null, null];
      console.log([
        `${result.outcome}  dataset=${result.dataset_id} codebook=${result.codebook_id}`,
        `alpha=${alpha ?? "NA"} ci95=[${ci[0] ?? "NA"}, ${ci[1] ?? "NA"}]`,
        `multilabel_match=${result.metrics?.multilabel?.exact_match ?? "NA"} multilabel_f1=${result.metrics?.multilabel?.pairwise_f1 ?? "NA"}`,
        ...result.issues.map((item) => `  ${item.severity.padEnd(7)} ${item.code} ${item.at} — ${item.message}`),
        `Claim ceiling: ${result.claim_ceiling}.`,
      ].join("\n"));
    }
    return result.threshold_passed ? 0 : 1;
  }
  if (command === "validate-argument") {
    if (opt.positional.length !== 1) throw new Error("validate-argument requires exactly one argument bundle");
    const result = await validateArgumentBundle(engine, opt.positional[0]);
    if (opt.json) console.log(JSON.stringify(result, null, 2));
    else console.log([
      `${result.conformant ? result.review_required ? "PASS + HUMAN REVIEW" : "PASS" : "FAIL"}  argument-bundle=${result.bundle_id}`,
      ...result.issue_results.map((item) => `  ISSUE ${item.claim_id} ${item.proof_standard} => ${item.status} pro=[${item.applicable_pro.join(",")}] con=[${item.applicable_con.join(",")}]`),
      ...result.issues.map((item) => `  ${item.severity.padEnd(7)} ${item.code} ${item.at} — ${item.message}`),
      `Claim ceiling: ${result.claim_ceiling}.`,
    ].join("\n"));
    return !result.conformant || (opt.failOnReview && result.review_required) ? 1 : 0;
  }
  if (command === "export-crate") {
    const outIndex = rest.indexOf("--out");
    if (outIndex < 0 || !rest[outIndex + 1]) throw new Error("export-crate requires --out <directory/ro-crate-metadata.json>");
    const roots = rest.filter((arg, index) => index !== outIndex && index !== outIndex + 1 && !arg.startsWith("--"));
    if (roots.length !== 1) throw new Error("export-crate requires exactly one directory");
    const result = await writeRoCrate(roots[0], rest[outIndex + 1], { engineVersion: engine.context.engineVersion });
    console.log(rest.includes("--json") ? JSON.stringify(result, null, 2) : `RO-Crate 1.3 metadata: ${result.output_file}\npayload_files=${result.payload_files} entities=${result.entities}`);
    return 0;
  }
  if (command === "explain") {
    if (opt.positional.length !== 1) throw new Error("explain requires one RT identifier");
    const entry = engine.context.registry.entries.find((item) => item.rt_id === opt.positional[0].toUpperCase());
    if (!entry) throw new Error(`${opt.positional[0]} is not present in RT00–RT28`);
    console.log(opt.json ? JSON.stringify(entry, null, 2) : [
      `${entry.rt_id} — ${entry.label}`,
      `Assertion: ${entry.assertion}`,
      `Minimum bridge: ${entry.minimum_bridge_evidence}`,
      `Forbidden promotion: ${entry.forbidden_promotion}`,
    ].join("\n"));
    return 0;
  }
  if (command === "rules") {
    const payload = {
      policy: engine.context.policy,
      aag_invariants: engine.context.aag.invariants,
      registered_extensions: Object.keys(engine.context.extensionRegistry.extensions),
      registered_relations: [...engine.context.relationIds],
    };
    console.log(opt.json ? JSON.stringify(payload, null, 2) : [
      `Policy: ${payload.policy.policy_version}`,
      `AAG invariants: ${payload.aag_invariants.join(", ")}`,
      `Extensions: ${payload.registered_extensions.join(", ")}`,
      `Relations: ${payload.registered_relations[0]}–${payload.registered_relations.at(-1)} (${payload.registered_relations.length})`,
    ].join("\n"));
    return 0;
  }

  console.error(HELP);
  throw new Error(`unknown command '${command}'`);
}
