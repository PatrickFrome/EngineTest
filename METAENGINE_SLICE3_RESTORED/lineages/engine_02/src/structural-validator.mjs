let Ajv2020;
let AJV_BACKEND = "PACKAGE_AJV_8_17_1";
try {
  ({ default: Ajv2020 } = await import("ajv/dist/2020.js"));
} catch {
  ({ default: Ajv2020 } = await import("../vendor/ajv-compat/2020.mjs"));
  AJV_BACKEND = "BUNDLED_AJV_COMPAT_FALLBACK";
}
import { projectPath, readJson } from "./paths.mjs";
import { issue } from "./issues.mjs";

function ajvIssues(errors, code, prefix = "") {
  return (errors ?? []).map((error) => issue(
    "ERROR",
    code,
    `${prefix}${error.instancePath || "/"}`,
    error.message ?? "JSON Schema validation failure",
    { keyword: error.keyword, params: error.params, schemaPath: error.schemaPath },
  ));
}

export async function createStructuralValidator() {
  const ajv = new Ajv2020({ allErrors: true, strict: false, validateFormats: false });
  const extensionRegistry = await readJson(projectPath("config", "extension_registry.json"));
  const coreSchema = await readJson(projectPath("vendor", "core4", "trc_0_3.schema.json"));
  const runSchema = await readJson(projectPath("schemas", "audit_run.schema.json"));
  const run4dSchema = await readJson(projectPath("schemas", "audit_run_4d.schema.json"));
  const protocolRunSchema = await readJson(projectPath("schemas", "protocol_run.schema.json"));
  const researchPlanSchema = await readJson(projectPath("schemas", "research_plan.schema.json"));
  const researchPlanLockSchema = await readJson(projectPath("schemas", "research_plan_lock.schema.json"));
  const annotationSetSchema = await readJson(projectPath("schemas", "annotation_set.schema.json"));
  const argumentBundleSchema = await readJson(projectPath("schemas", "argument_bundle.schema.json"));
  const sourceManifestSchema = await readJson(projectPath("schemas", "source_manifest.schema.json"));
  const docxJobSchema = await readJson(projectPath("schemas", "docx_job.schema.json"));
  const segmentationManifestSchema = await readJson(projectPath("schemas", "segmentation_manifest.schema.json"));
  const sourceMapSchema = await readJson(projectPath("schemas", "source_map.schema.json"));
  const claimLedgerEntrySchema = await readJson(projectPath("schemas", "claim_ledger_entry.schema.json"));
  const hypothesisBankSchema = await readJson(projectPath("schemas", "hypothesis_bank.schema.json"));
  const archiveMapSchema = await readJson(projectPath("schemas", "archive_map.schema.json"));
  const formulaRegistrySchema = await readJson(projectPath("schemas", "formula_registry.schema.json"));
  const expertProfileSchema = await readJson(projectPath("schemas", "expert_profile.schema.json"));
  const modelExpertAssessmentSchema = await readJson(projectPath("schemas", "model_expert_assessment.schema.json"));
  const expertCycleSchema = await readJson(projectPath("schemas", "expert_cycle.schema.json"));
  const benchmarkManifestSchema = await readJson(projectPath("schemas", "benchmark_manifest.schema.json"));
  const benchmarkPredictionsSchema = await readJson(projectPath("schemas", "benchmark_predictions.schema.json"));
  const benchmarkPacketSchema = await readJson(projectPath("schemas", "benchmark_packet.schema.json"));
  const benchmarkAnnotationSchema = await readJson(projectPath("schemas", "benchmark_annotation.schema.json"));
  const benchmarkGoldSchema = await readJson(projectPath("schemas", "benchmark_gold.schema.json"));
  const benchmarkResultSchema = await readJson(projectPath("schemas", "benchmark_result.schema.json"));
  const livingAnalysisSchema = await readJson(projectPath("schemas", "living_analysis.schema.json"));
  const etymologyPassSchema = await readJson(projectPath("schemas", "etymology_pass.schema.json"));
  const portableProjectSchema = await readJson(projectPath("schemas", "portable_project.schema.json"));
  const operatorRegressionManifestSchema = await readJson(projectPath("schemas", "operator_regression_manifest.schema.json"));
  const operatorRegressionResultSchema = await readJson(projectPath("schemas", "operator_regression_result.schema.json"));
  const operatorCompetitionManifestSchema = await readJson(projectPath("schemas", "operator_competition_manifest.schema.json"));
  const operatorCompetitionResultSchema = await readJson(projectPath("schemas", "operator_competition_result.schema.json"));
  const microLocalEcologyResultSchema = await readJson(projectPath("schemas", "micro_local_ecology_result.schema.json"));
  const validateCoreSchema = ajv.compile(coreSchema);
  const validateRunSchema = ajv.compile(runSchema);
  const validateRun4dSchema = ajv.compile(run4dSchema);
  const validateProtocolRunSchema = ajv.compile(protocolRunSchema);
  const validateResearchPlanSchema = ajv.compile(researchPlanSchema);
  const validateResearchPlanLockSchema = ajv.compile(researchPlanLockSchema);
  const validateAnnotationSetSchema = ajv.compile(annotationSetSchema);
  const validateArgumentBundleSchema = ajv.compile(argumentBundleSchema);
  const validateSourceManifestSchema = ajv.compile(sourceManifestSchema);
  const validateDocxJobSchema = ajv.compile(docxJobSchema);
  const validateSegmentationManifestSchema = ajv.compile(segmentationManifestSchema);
  const validateSourceMapSchema = ajv.compile(sourceMapSchema);
  const validateClaimLedgerEntrySchema = ajv.compile(claimLedgerEntrySchema);
  const validateHypothesisBankSchema = ajv.compile(hypothesisBankSchema);
  const validateArchiveMapSchema = ajv.compile(archiveMapSchema);
  const validateFormulaRegistrySchema = ajv.compile(formulaRegistrySchema);
  const validateExpertProfileSchema = ajv.compile(expertProfileSchema);
  const validateModelExpertAssessmentSchema = ajv.compile(modelExpertAssessmentSchema);
  const validateExpertCycleSchema = ajv.compile(expertCycleSchema);
  const validateBenchmarkManifestSchema = ajv.compile(benchmarkManifestSchema);
  const validateBenchmarkPredictionsSchema = ajv.compile(benchmarkPredictionsSchema);
  const validateBenchmarkPacketSchema = ajv.compile(benchmarkPacketSchema);
  const validateBenchmarkAnnotationSchema = ajv.compile(benchmarkAnnotationSchema);
  const validateBenchmarkGoldSchema = ajv.compile(benchmarkGoldSchema);
  const validateBenchmarkResultSchema = ajv.compile(benchmarkResultSchema);
  const validateLivingAnalysisSchema = ajv.compile(livingAnalysisSchema);
  const validateEtymologyPassSchema = ajv.compile(etymologyPassSchema);
  const validatePortableProjectSchema = ajv.compile(portableProjectSchema);
  const validateOperatorRegressionManifestSchema = ajv.compile(operatorRegressionManifestSchema);
  const validateOperatorRegressionResultSchema = ajv.compile(operatorRegressionResultSchema);
  const validateOperatorCompetitionManifestSchema = ajv.compile(operatorCompetitionManifestSchema);
  const validateOperatorCompetitionResultSchema = ajv.compile(operatorCompetitionResultSchema);
  const validateMicroLocalEcologyResultSchema = ajv.compile(microLocalEcologyResultSchema);
  const extensionValidators = new Map();

  for (const [key, entry] of Object.entries(extensionRegistry.extensions)) {
    extensionValidators.set(key, ajv.compile(await readJson(projectPath(entry.schema))));
  }

  return {
    extensionRegistry,
    validatorBackend: AJV_BACKEND,

    validateRecord(record) {
      const issues = [];
      if (!validateCoreSchema(record)) {
        issues.push(...ajvIssues(validateCoreSchema.errors, "CORE_SCHEMA"));
        return issues;
      }

      for (const [key, value] of Object.entries(record.extensions ?? {})) {
        const validator = extensionValidators.get(key);
        if (!validator) continue;
        if (!validator(value)) issues.push(...ajvIssues(validator.errors, "EXTENSION_SCHEMA", `/extensions/${key}`));
      }
      return issues;
    },

    validateRun(run) {
      return validateRunSchema(run) ? [] : ajvIssues(validateRunSchema.errors, "RUN_SCHEMA");
    },

    validateRun4d(run) {
      return validateRun4dSchema(run) ? [] : ajvIssues(validateRun4dSchema.errors, "RUN_4D_SCHEMA");
    },

    validateProtocolRun(run) {
      return validateProtocolRunSchema(run) ? [] : ajvIssues(validateProtocolRunSchema.errors, "PROTOCOL_RUN_SCHEMA");
    },

    validateResearchPlan(plan) {
      return validateResearchPlanSchema(plan) ? [] : ajvIssues(validateResearchPlanSchema.errors, "RESEARCH_PLAN_SCHEMA");
    },

    validateResearchPlanLock(lock) {
      return validateResearchPlanLockSchema(lock) ? [] : ajvIssues(validateResearchPlanLockSchema.errors, "RESEARCH_LOCK_SCHEMA");
    },

    validateAnnotationSet(payload) {
      return validateAnnotationSetSchema(payload) ? [] : ajvIssues(validateAnnotationSetSchema.errors, "ANNOTATION_SET_SCHEMA");
    },

    validateArgumentBundle(bundle) {
      return validateArgumentBundleSchema(bundle) ? [] : ajvIssues(validateArgumentBundleSchema.errors, "ARGUMENT_BUNDLE_SCHEMA");
    },

    validateSourceManifest(manifest) {
      return validateSourceManifestSchema(manifest) ? [] : ajvIssues(validateSourceManifestSchema.errors, "SOURCE_MANIFEST_SCHEMA");
    },

    validateDocxJob(job) {
      return validateDocxJobSchema(job) ? [] : ajvIssues(validateDocxJobSchema.errors, "DOCX_JOB_SCHEMA");
    },

    validateSegmentationManifest(manifest) {
      return validateSegmentationManifestSchema(manifest) ? [] : ajvIssues(validateSegmentationManifestSchema.errors, "SEGMENTATION_MANIFEST_SCHEMA");
    },

    validateSourceMap(sourceMap) {
      return validateSourceMapSchema(sourceMap) ? [] : ajvIssues(validateSourceMapSchema.errors, "SOURCE_MAP_SCHEMA");
    },

    validateClaimLedgerEntry(entry) {
      return validateClaimLedgerEntrySchema(entry) ? [] : ajvIssues(validateClaimLedgerEntrySchema.errors, "CLAIM_LEDGER_ENTRY_SCHEMA");
    },

    validateHypothesisBank(bank) {
      return validateHypothesisBankSchema(bank) ? [] : ajvIssues(validateHypothesisBankSchema.errors, "HYPOTHESIS_BANK_SCHEMA");
    },

    validateArchiveMap(archiveMap) {
      return validateArchiveMapSchema(archiveMap) ? [] : ajvIssues(validateArchiveMapSchema.errors, "ARCHIVE_MAP_SCHEMA");
    },

    validateFormulaRegistry(registry) {
      return validateFormulaRegistrySchema(registry) ? [] : ajvIssues(validateFormulaRegistrySchema.errors, "FORMULA_REGISTRY_SCHEMA");
    },

    validateExpertProfile(profile) {
      return validateExpertProfileSchema(profile) ? [] : ajvIssues(validateExpertProfileSchema.errors, "EXPERT_PROFILE_SCHEMA");
    },

    validateModelExpertAssessment(assessment) {
      return validateModelExpertAssessmentSchema(assessment) ? [] : ajvIssues(validateModelExpertAssessmentSchema.errors, "MODEL_EXPERT_ASSESSMENT_SCHEMA");
    },

    validateExpertCycle(cycle) {
      return validateExpertCycleSchema(cycle) ? [] : ajvIssues(validateExpertCycleSchema.errors, "EXPERT_CYCLE_SCHEMA");
    },

    validateBenchmarkManifest(manifest) {
      return validateBenchmarkManifestSchema(manifest) ? [] : ajvIssues(validateBenchmarkManifestSchema.errors, "BENCHMARK_MANIFEST_SCHEMA");
    },

    validateBenchmarkPredictions(predictions) {
      return validateBenchmarkPredictionsSchema(predictions) ? [] : ajvIssues(validateBenchmarkPredictionsSchema.errors, "BENCHMARK_PREDICTIONS_SCHEMA");
    },

    validateBenchmarkPacket(packet) {
      return validateBenchmarkPacketSchema(packet) ? [] : ajvIssues(validateBenchmarkPacketSchema.errors, "BENCHMARK_PACKET_SCHEMA");
    },

    validateBenchmarkAnnotation(annotation) {
      return validateBenchmarkAnnotationSchema(annotation) ? [] : ajvIssues(validateBenchmarkAnnotationSchema.errors, "BENCHMARK_ANNOTATION_SCHEMA");
    },

    validateBenchmarkGold(gold) {
      return validateBenchmarkGoldSchema(gold) ? [] : ajvIssues(validateBenchmarkGoldSchema.errors, "BENCHMARK_GOLD_SCHEMA");
    },

    validateBenchmarkResult(result) {
      return validateBenchmarkResultSchema(result) ? [] : ajvIssues(validateBenchmarkResultSchema.errors, "BENCHMARK_RESULT_SCHEMA");
    },

    validateLivingAnalysis(analysis) {
      return validateLivingAnalysisSchema(analysis) ? [] : ajvIssues(validateLivingAnalysisSchema.errors, "LIVING_ANALYSIS_SCHEMA");
    },

    validateEtymologyPass(pass) {
      return validateEtymologyPassSchema(pass) ? [] : ajvIssues(validateEtymologyPassSchema.errors, "ETYMOLOGY_PASS_SCHEMA");
    },

    validatePortableProject(project) {
      return validatePortableProjectSchema(project) ? [] : ajvIssues(validatePortableProjectSchema.errors, "PORTABLE_PROJECT_SCHEMA");
    },

    validateOperatorRegressionManifest(payload) {
      return validateOperatorRegressionManifestSchema(payload) ? [] : ajvIssues(validateOperatorRegressionManifestSchema.errors, "OPERATOR_REGRESSION_MANIFEST_SCHEMA");
    },

    validateOperatorRegressionResult(payload) {
      return validateOperatorRegressionResultSchema(payload) ? [] : ajvIssues(validateOperatorRegressionResultSchema.errors, "OPERATOR_REGRESSION_RESULT_SCHEMA");
    },

    validateOperatorCompetitionManifest(payload) {
      return validateOperatorCompetitionManifestSchema(payload) ? [] : ajvIssues(validateOperatorCompetitionManifestSchema.errors, "OPERATOR_COMPETITION_MANIFEST_SCHEMA");
    },

    validateOperatorCompetitionResult(payload) {
      return validateOperatorCompetitionResultSchema(payload) ? [] : ajvIssues(validateOperatorCompetitionResultSchema.errors, "OPERATOR_COMPETITION_RESULT_SCHEMA");
    },

    validateMicroLocalEcologyResult(payload) {
      return validateMicroLocalEcologyResultSchema(payload) ? [] : ajvIssues(validateMicroLocalEcologyResultSchema.errors, "MICRO_LOCAL_ECOLOGY_RESULT_SCHEMA");
    },
  };
}
