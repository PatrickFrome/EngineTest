import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { evaluateAgreementPayload } from "./agreement.mjs";
import { issue, sortIssues } from "./issues.mjs";
import { readJson } from "./paths.mjs";

export const EXPERT_STATUSES = ["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"];
const STATUS_SET = new Set(EXPERT_STATUSES);
const FIXED_BASELINES = ["ALWAYS_INSUFFICIENT", "ALWAYS_QUALIFIED"];
const RESULT_CEILING = "SAMPLE_BOUND_EMPIRICAL_VALIDATION_NOT_GENERAL_SEMANTIC_INFALLIBILITY";

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  }
  return value;
}

export function canonicalBenchmarkJson(value) {
  return JSON.stringify(canonicalize(value));
}

export function canonicalBenchmarkSha256(value) {
  return sha256(canonicalBenchmarkJson(value));
}

function jsonBytes(value) {
  return Buffer.from(`${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function timestamp(value) {
  return value ?? new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
}

async function requireNewDirectory(directory) {
  try {
    await stat(directory);
    throw new Error(`Output directory already exists: ${directory}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

function schemaFailure(name, issues) {
  const summary = issues.slice(0, 12).map((item) => `${item.code} ${item.at}: ${item.message}`).join("; ");
  return new Error(`${name}_SCHEMA_FAILED: ${summary}`);
}

function sameMembers(left, right) {
  if (left.length !== right.length) return false;
  const a = [...left].sort();
  const b = [...right].sort();
  return a.every((value, index) => value === b[index]);
}

function duplicates(values) {
  const seen = new Set();
  const repeated = new Set();
  for (const value of values) {
    if (seen.has(value)) repeated.add(value);
    seen.add(value);
  }
  return [...repeated].sort();
}

function codebook() {
  return {
    codebook_id: "DAE-EXPERT-STATUS-1.0",
    labels: {
      SUPPORTED: "Доступное свидетельство достаточно поддерживает тезис именно в заявленном масштабе; решающее ограничение не обнаружено.",
      QUALIFIED: "Содержательное ядро поддержано, но тезис требует явного ограничения масштаба, модальности, происхождения или области применимости.",
      REJECTED: "Доступное свидетельство или решающее контрсоображение противоречит тезису; простого добавления данных недостаточно без его пересмотра.",
      INSUFFICIENT: "Доступного и разрешённого свидетельства недостаточно, чтобы выбрать поддержку либо отклонение; это воздержание, а не отрицание.",
    },
    decision_rule: "Сначала проверяется достаточность и происхождение свидетельства, затем масштаб тезиса и сильнейший соперник. REJECTED означает отрицательное решение, INSUFFICIENT — отсутствие достаточного решения.",
  };
}

function defaultEvaluationPlan(options = {}) {
  const minimumUnits = Math.max(80, Number(options.minimumUnits ?? 80));
  return {
    frozen_before_labels: true,
    minimum_units: minimumUnits,
    minimum_gold_per_label: 20,
    independent_coders_min: 2,
    agreement: {
      alpha_min: 0.67,
      alpha_ci_lower_min: 0.5,
    },
    promotion: {
      macro_f1_min: 0.7,
      macro_f1_ci_lower_min: 0.6,
      improvement_over_best_fixed_baseline_min: 0.05,
      dangerous_overpromotion_rate_max: 0.05,
      decision_ece_max: 0.15,
    },
    fixed_baselines: FIXED_BASELINES,
    bootstrap_iterations: Math.max(500, Math.min(10000, Number(options.bootstrapIterations ?? 1000))),
    seed: String(options.seed ?? "DAE-EMPIRICAL-0.4-FROZEN-SEED"),
  };
}

function blindPacket(manifest, manifestHash, label, seed) {
  const packetDigest = sha256(`${manifest.benchmark_id}\n${label}\n${seed}`).toUpperCase();
  return {
    packet_version: "DAE-BLIND-PACKET-1.0",
    benchmark_id: manifest.benchmark_id,
    manifest_sha256: manifestHash,
    packet_id: `PACKET-${label}-${packetDigest.slice(0, 12)}`,
    assignment_token: packetDigest.slice(12, 36),
    blinding: {
      system_status_removed: true,
      system_confidence_removed: true,
      system_reasons_removed: true,
      predictions_file_disclosed: false,
    },
    codebook: manifest.codebook,
    instructions: {
      independent_source_review: "Откройте разрешённую копию источника с указанным SHA-256 и вынесите решение независимо от DAE и других кодировщиков.",
      selector_role: "Candidate evidence selectors — только навигационные подсказки системы, а не gold-доказательство. Проверяйте контекст и при необходимости приводите собственные локаторы.",
      status_required: true,
      evidence_required: true,
    },
    units: manifest.units.map((unit) => ({
      unit_id: unit.unit_id,
      source: {
        source_id: unit.source_id,
        artifact_sha256: unit.artifact_sha256,
        source_access_required: true,
      },
      thesis: {
        thesis_id: unit.thesis_id,
        title: unit.title,
        statement: unit.statement,
        scale: unit.scale,
      },
      candidate_evidence_selectors: unit.candidate_evidence_selectors,
    })),
    claim_ceiling: "BLIND_ANNOTATION_MATERIAL_NOT_GOLD_OR_SYSTEM_OUTPUT",
  };
}

function annotationTemplate(packet, packetHash, generatedAt) {
  return {
    annotation_version: "DAE-EXPERT-ANNOTATION-1.0",
    benchmark_id: packet.benchmark_id,
    manifest_sha256: packet.manifest_sha256,
    packet_sha256: packetHash,
    coder: {
      id: "REPLACE_WITH_CODER_ID",
      role: "INDEPENDENT_DOMAIN_ANNOTATOR",
      independent_of_system_development: true,
      blinded_to_predictions: true,
      source_access_attested: true,
      conflicts_disclosed: [],
    },
    completed_at: generatedAt,
    units: packet.units.map((unit) => ({
      unit_id: unit.unit_id,
      status: null,
      confidence: null,
      evidence_refs: [],
      rationale: "",
    })),
    claim_ceiling: "INDEPENDENT_CODER_JUDGMENT_NOT_ADJUDICATED_GOLD",
  };
}

function goldTemplate(manifest, manifestHash, generatedAt) {
  return {
    gold_version: "DAE-ADJUDICATED-GOLD-1.0",
    benchmark_id: manifest.benchmark_id,
    manifest_sha256: manifestHash,
    adjudication: {
      curator_id: "REPLACE_WITH_CURATOR_ID",
      independent_of_system_development: true,
      predictions_hidden_until_gold_frozen: true,
      source_annotation_sha256: [],
    },
    frozen_at: generatedAt,
    units: manifest.units.map((unit) => ({
      unit_id: unit.unit_id,
      gold_status: null,
      adjudication_method: null,
      evidence_refs: [],
      rationale: "",
    })),
    claim_ceiling: "FROZEN_ADJUDICATED_BENCHMARK_GOLD_FOR_THIS_SAMPLE",
  };
}

function annotatorInstructions(manifest) {
  return `# Независимая разметка ${manifest.benchmark_id}

Этот пакет оценивает терминальные решения экспертного цикла. Он не подтверждает философскую истинность проекта автоматически.

## Порядок

1. Получите только один файл из \`blind_packets/\`; не открывайте \`sealed_predictions.json\` до заморозки gold-набора.
2. Проверьте SHA-256 разрешённой копии каждого источника.
3. Для каждой единицы изучите источник и контекст. Селекторы пакета — навигационные кандидаты, а не готовое доказательство.
4. Выберите ровно один статус из кодбука, укажите уверенность 1–3, собственные evidence refs и краткое обоснование.
5. Не согласовывайте решения со вторым кодировщиком. Сначала замораживаются обе raw-разметки и считается agreement; лишь затем отдельный куратор формирует gold.

## Запрет самоподтверждения

Автор системы, разработчик её профиля или участник, видевший sealed predictions, не считается независимым кодировщиком. Пустые метки, системные статусы и автоматически перенесённые rationale недопустимы.
`;
}

function benchmarkStatus(manifest, manifestHash) {
  const underpowered = manifest.units.length < manifest.evaluation_plan.minimum_units;
  return `# Benchmark ${manifest.benchmark_id}

Статус: **BLOCKED_PENDING_INDEPENDENT_LABELS**.

- Зафиксировано единиц: ${manifest.units.length}; promotion minimum: ${manifest.evaluation_plan.minimum_units}.
- Независимых кодировщиков требуется: ${manifest.evaluation_plan.independent_coders_min}.
- Минимальная gold-поддержка каждого класса: ${manifest.evaluation_plan.minimum_gold_per_label}.
- Manifest SHA-256: \`${manifestHash}\`.
- Текущая мощность: ${underpowered ? "UNDERPOWERED" : "SIZE_GATE_READY"}.

Предсказания отделены в \`sealed_predictions.json\`. До завершения независимых разметок и заморозки \`gold.json\` этот файл нельзя передавать кодировщикам или куратору. Отсутствие меток является блокировкой, а не отрицательным результатом.
`;
}

export async function initExpertBenchmark(engine, expertCycleFiles, outputDirectory, options = {}) {
  if (!Array.isArray(expertCycleFiles) || !expertCycleFiles.length) throw new Error("benchmark-init requires at least one expert_cycle.json");
  const out = path.resolve(outputDirectory);
  await requireNewDirectory(out);
  const loaded = [];
  for (const file of [...expertCycleFiles].map((entry) => path.resolve(entry)).sort()) {
    const bytes = await readFile(file);
    const cycle = JSON.parse(bytes.toString("utf8"));
    const issues = engine.structural.validateExpertCycle(cycle);
    if (issues.length) throw schemaFailure("EXPERT_CYCLE", issues);
    loaded.push({ file, bytes, cycle, hash: sha256(bytes) });
  }
  loaded.sort((left, right) => left.cycle.run_id.localeCompare(right.cycle.run_id));
  const duplicateRuns = duplicates(loaded.map((entry) => entry.cycle.run_id));
  if (duplicateRuns.length) throw new Error(`DUPLICATE_EXPERT_RUN_ID: ${duplicateRuns.join(", ")}`);

  const evaluationPlan = defaultEvaluationPlan(options);
  const benchmarkSeed = canonicalBenchmarkJson({
    codebook: codebook(),
    evaluation_plan: evaluationPlan,
    source_cycles: loaded.map((entry) => ({ run_id: entry.cycle.run_id, sha256: entry.hash })),
  });
  const benchmarkId = `BENCH-${sha256(benchmarkSeed).slice(0, 16).toUpperCase()}`;
  const generatedAt = timestamp(options.generatedAt);
  const units = loaded.flatMap(({ cycle }) => cycle.thesis_results.map((thesis) => ({
    unit_id: `BU-${sha256(`${cycle.run_id}\n${thesis.thesis_id}\n${cycle.source.artifact_sha256}`).slice(0, 16).toUpperCase()}`,
    run_id: cycle.run_id,
    source_id: cycle.source.source_id,
    artifact_sha256: cycle.source.artifact_sha256,
    thesis_id: thesis.thesis_id,
    title: thesis.title,
    statement: thesis.statement,
    scale: thesis.scale,
    source_access_required: true,
    candidate_evidence_selectors: [...new Set(thesis.evidence.selectors)].sort(),
  }))).sort((left, right) => left.unit_id.localeCompare(right.unit_id));
  const duplicateUnits = duplicates(units.map((unit) => unit.unit_id));
  if (duplicateUnits.length) throw new Error(`DUPLICATE_BENCHMARK_UNIT_ID: ${duplicateUnits.join(", ")}`);

  const manifest = {
    benchmark_version: "DAE-EXPERT-BENCHMARK-1.0",
    engine_version: engine.context.engineVersion,
    generated_at: generatedAt,
    benchmark_id: benchmarkId,
    task: "EXPERT_THESIS_STATUS",
    codebook: codebook(),
    source_cycles: loaded.map(({ cycle, hash }) => ({
      run_id: cycle.run_id,
      source_id: cycle.source.source_id,
      artifact_sha256: cycle.source.artifact_sha256,
      profile_id: cycle.profile.profile_id,
      profile_sha256: cycle.profile.profile_sha256,
      expert_cycle_sha256: hash,
      expert_cycle_version: cycle.cycle_version,
      engine_version: cycle.engine_version,
      snapshot_file: `source_cycles/${cycle.run_id}.expert_cycle.json`,
    })),
    units,
    evaluation_plan: evaluationPlan,
    blinding: {
      predictions_stored_separately: true,
      packets_exclude_status_and_confidence: true,
      source_access_required: true,
      system_developers_ineligible_as_independent_coders: true,
      gold_frozen_before_unblinding: true,
    },
    claim_ceiling: "FROZEN_BLIND_EVALUATION_PLAN_NOT_EMPIRICAL_VALIDATION",
  };
  const manifestIssues = engine.structural.validateBenchmarkManifest(manifest);
  if (manifestIssues.length) throw schemaFailure("BENCHMARK_MANIFEST", manifestIssues);
  const manifestHash = canonicalBenchmarkSha256(manifest);
  const primaryByUnit = new Map();
  for (const { cycle } of loaded) {
    for (const thesis of cycle.thesis_results) {
      const unitId = `BU-${sha256(`${cycle.run_id}\n${thesis.thesis_id}\n${cycle.source.artifact_sha256}`).slice(0, 16).toUpperCase()}`;
      primaryByUnit.set(unitId, { status: thesis.status, confidence: thesis.confidence });
    }
  }
  const systemPredictions = (status = null) => units.map((unit) => ({
    unit_id: unit.unit_id,
    status: status ?? primaryByUnit.get(unit.unit_id).status,
    confidence: status === null ? primaryByUnit.get(unit.unit_id).confidence : 1,
  }));
  const predictions = {
    predictions_version: "DAE-SEALED-PREDICTIONS-1.0",
    benchmark_id: benchmarkId,
    manifest_sha256: manifestHash,
    sealed_before_labels: true,
    systems: [
      { system_id: "DAE_PRIMARY", kind: "ENGINE", predictions: systemPredictions() },
      { system_id: "ALWAYS_INSUFFICIENT", kind: "FIXED_BASELINE", predictions: systemPredictions("INSUFFICIENT") },
      { system_id: "ALWAYS_QUALIFIED", kind: "FIXED_BASELINE", predictions: systemPredictions("QUALIFIED") },
    ],
    claim_ceiling: "SEALED_SYSTEM_OUTPUT_NOT_GOLD_LABELS",
  };
  const predictionIssues = engine.structural.validateBenchmarkPredictions(predictions);
  if (predictionIssues.length) throw schemaFailure("BENCHMARK_PREDICTIONS", predictionIssues);
  const packetA = blindPacket(manifest, manifestHash, "A", evaluationPlan.seed);
  const packetB = blindPacket(manifest, manifestHash, "B", evaluationPlan.seed);
  for (const packet of [packetA, packetB]) {
    const packetIssues = engine.structural.validateBenchmarkPacket(packet);
    if (packetIssues.length) throw schemaFailure("BENCHMARK_PACKET", packetIssues);
  }
  const manifestBytes = jsonBytes(manifest);
  const predictionBytes = jsonBytes(predictions);
  const packetABytes = jsonBytes(packetA);
  const packetBBytes = jsonBytes(packetB);
  const lock = {
    lock_version: "DAE-EXPERT-BENCHMARK-LOCK-1.0",
    benchmark_id: benchmarkId,
    locked_at: generatedAt,
    timestamp_authority: "LOCAL_SYSTEM_CLOCK_UNTRUSTED",
    manifest_sha256: manifestHash,
    manifest_file_sha256: sha256(manifestBytes),
    sealed_predictions_sha256: sha256(predictionBytes),
    blind_packet_sha256: {
      [packetA.packet_id]: sha256(packetABytes),
      [packetB.packet_id]: sha256(packetBBytes),
    },
    claim_ceiling: "LOCAL_FIXITY_LOCK_NOT_PUBLIC_PREREGISTRATION",
  };
  await Promise.all([
    mkdir(path.join(out, "blind_packets"), { recursive: true }),
    mkdir(path.join(out, "annotation_templates"), { recursive: true }),
    mkdir(path.join(out, "source_cycles"), { recursive: true }),
  ]);
  await Promise.all([
    writeFile(path.join(out, "benchmark_manifest.json"), manifestBytes, { flag: "wx" }),
    writeFile(path.join(out, "benchmark_lock.json"), jsonBytes(lock), { flag: "wx" }),
    writeFile(path.join(out, "sealed_predictions.json"), predictionBytes, { flag: "wx" }),
    writeFile(path.join(out, "blind_packets", "coder-a.json"), packetABytes, { flag: "wx" }),
    writeFile(path.join(out, "blind_packets", "coder-b.json"), packetBBytes, { flag: "wx" }),
    writeFile(path.join(out, "annotation_templates", "coder-a.annotation.template.json"), jsonBytes(annotationTemplate(packetA, sha256(packetABytes), generatedAt)), { flag: "wx" }),
    writeFile(path.join(out, "annotation_templates", "coder-b.annotation.template.json"), jsonBytes(annotationTemplate(packetB, sha256(packetBBytes), generatedAt)), { flag: "wx" }),
    writeFile(path.join(out, "gold.template.json"), jsonBytes(goldTemplate(manifest, manifestHash, generatedAt)), { flag: "wx" }),
    writeFile(path.join(out, "ANNOTATOR_INSTRUCTIONS.md"), annotatorInstructions(manifest), { encoding: "utf8", flag: "wx" }),
    writeFile(path.join(out, "BENCHMARK_STATUS.md"), benchmarkStatus(manifest, manifestHash), { encoding: "utf8", flag: "wx" }),
    ...loaded.map((entry) => writeFile(path.join(out, "source_cycles", `${entry.cycle.run_id}.expert_cycle.json`), entry.bytes, { flag: "wx" })),
  ]);
  return {
    output_dir: out,
    benchmark_id: benchmarkId,
    manifest_sha256: manifestHash,
    unit_count: units.length,
    minimum_units: evaluationPlan.minimum_units,
    status: "BLOCKED_PENDING_INDEPENDENT_LABELS",
    manifest,
    lock,
  };
}

function safeDivide(numerator, denominator) {
  return denominator ? numerator / denominator : 0;
}

function round(value, digits = 6) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}

function dangerousOverpromotion(predicted, gold) {
  return predicted === "SUPPORTED" && gold !== "SUPPORTED"
    || predicted === "QUALIFIED" && ["REJECTED", "INSUFFICIENT"].includes(gold);
}

function calibration(confidences, correct, binCount = 10) {
  const bins = Array.from({ length: binCount }, (_, index) => ({
    lower: index / binCount,
    upper: (index + 1) / binCount,
    count: 0,
    confidence_sum: 0,
    correct_sum: 0,
  }));
  let brier = 0;
  for (let index = 0; index < confidences.length; index += 1) {
    const confidence = Math.max(0, Math.min(1, Number(confidences[index])));
    const target = correct[index] ? 1 : 0;
    const bin = bins[Math.min(binCount - 1, Math.floor(confidence * binCount))];
    bin.count += 1;
    bin.confidence_sum += confidence;
    bin.correct_sum += target;
    brier += (confidence - target) ** 2;
  }
  let ece = 0;
  const outputBins = bins.map((bin) => {
    const meanConfidence = safeDivide(bin.confidence_sum, bin.count);
    const accuracy = safeDivide(bin.correct_sum, bin.count);
    const gap = Math.abs(meanConfidence - accuracy);
    ece += safeDivide(bin.count, confidences.length) * gap;
    return {
      lower: bin.lower,
      upper: bin.upper,
      count: bin.count,
      mean_confidence: round(meanConfidence),
      accuracy: round(accuracy),
      gap: round(gap),
    };
  });
  return {
    decision_brier: round(safeDivide(brier, confidences.length)),
    expected_calibration_error: round(ece),
    bins: outputBins,
    interpretation: "Binary calibration of confidence in the chosen terminal status; not a multiclass probability score.",
  };
}

function riskCoverage(predictions, gold, confidences) {
  const order = predictions.map((prediction, index) => ({ prediction, gold: gold[index], confidence: confidences[index], index }))
    .sort((left, right) => right.confidence - left.confidence || left.index - right.index);
  let errors = 0;
  let riskSum = 0;
  const all = [];
  for (let index = 0; index < order.length; index += 1) {
    if (order[index].prediction !== order[index].gold) errors += 1;
    const risk = errors / (index + 1);
    riskSum += risk;
    all.push({ coverage: (index + 1) / order.length, risk });
  }
  const checkpoints = new Set([1, order.length]);
  for (let tenth = 1; tenth <= 10; tenth += 1) checkpoints.add(Math.max(1, Math.ceil(order.length * tenth / 10)));
  return {
    aurc_discrete: round(safeDivide(riskSum, order.length)),
    points: [...checkpoints].sort((a, b) => a - b).map((count) => ({
      retained_units: count,
      coverage: round(all[count - 1].coverage),
      risk: round(all[count - 1].risk),
    })),
  };
}

export function classificationMetrics(predictions, gold, confidences = predictions.map(() => 1)) {
  if (!predictions.length || predictions.length !== gold.length || confidences.length !== gold.length) throw new Error("METRIC_INPUT_LENGTH_MISMATCH");
  if (![...predictions, ...gold].every((status) => STATUS_SET.has(status))) throw new Error("METRIC_UNKNOWN_STATUS");
  const confusion = Object.fromEntries(EXPERT_STATUSES.map((actual) => [actual, Object.fromEntries(EXPERT_STATUSES.map((predicted) => [predicted, 0]))]));
  for (let index = 0; index < gold.length; index += 1) confusion[gold[index]][predictions[index]] += 1;
  const perClass = {};
  let correctCount = 0;
  let weightedF1 = 0;
  let macroF1 = 0;
  let recallTotal = 0;
  for (const status of EXPERT_STATUSES) {
    const tp = confusion[status][status];
    const support = EXPERT_STATUSES.reduce((sum, predicted) => sum + confusion[status][predicted], 0);
    const predictedCount = EXPERT_STATUSES.reduce((sum, actual) => sum + confusion[actual][status], 0);
    const fp = predictedCount - tp;
    const fn = support - tp;
    const precision = safeDivide(tp, tp + fp);
    const recall = safeDivide(tp, tp + fn);
    const f1 = safeDivide(2 * precision * recall, precision + recall);
    perClass[status] = { precision: round(precision), recall: round(recall), f1: round(f1), support };
    correctCount += tp;
    weightedF1 += f1 * support;
    macroF1 += f1;
    recallTotal += recall;
  }
  const correct = predictions.map((prediction, index) => prediction === gold[index]);
  const dangerCount = predictions.filter((prediction, index) => dangerousOverpromotion(prediction, gold[index])).length;
  const covered = predictions.map((prediction, index) => ({ prediction, gold: gold[index] })).filter((entry) => entry.prediction !== "INSUFFICIENT");
  const distribution = (values) => Object.fromEntries(EXPERT_STATUSES.map((status) => [status, values.filter((value) => value === status).length]));
  return {
    unit_count: gold.length,
    confusion_matrix: confusion,
    per_class: perClass,
    accuracy: round(correctCount / gold.length),
    balanced_accuracy: round(recallTotal / EXPERT_STATUSES.length),
    macro_f1: round(macroF1 / EXPERT_STATUSES.length),
    weighted_f1: round(weightedF1 / gold.length),
    gold_distribution: distribution(gold),
    predicted_distribution: distribution(predictions),
    dangerous_overpromotion: {
      count: dangerCount,
      rate: round(dangerCount / gold.length),
      rule: "SUPPORTED over non-SUPPORTED gold, or QUALIFIED over REJECTED/INSUFFICIENT gold.",
    },
    abstention: {
      count: gold.length - covered.length,
      rate: round((gold.length - covered.length) / gold.length),
      coverage: round(covered.length / gold.length),
      selective_accuracy: round(safeDivide(covered.filter((entry) => entry.prediction === entry.gold).length, covered.length)),
    },
    calibration: calibration(confidences, correct),
    risk_coverage: riskCoverage(predictions, gold, confidences),
  };
}

function seededRandom(seed) {
  let state = Number.parseInt(sha256(seed).slice(0, 8), 16) || 1;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 4294967296;
  };
}

function percentile(values, probability) {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const position = (sorted.length - 1) * probability;
  const lower = Math.floor(position);
  const fraction = position - lower;
  return sorted[lower + 1] === undefined ? sorted[lower] : sorted[lower] + fraction * (sorted[lower + 1] - sorted[lower]);
}

export function bootstrapClassification(predictions, gold, confidences, iterations, seed) {
  const random = seededRandom(seed);
  const samples = { macro_f1: [], accuracy: [], dangerous_overpromotion_rate: [], decision_brier: [] };
  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const indexes = Array.from({ length: gold.length }, () => Math.floor(random() * gold.length));
    const metrics = classificationMetrics(indexes.map((index) => predictions[index]), indexes.map((index) => gold[index]), indexes.map((index) => confidences[index]));
    samples.macro_f1.push(metrics.macro_f1);
    samples.accuracy.push(metrics.accuracy);
    samples.dangerous_overpromotion_rate.push(metrics.dangerous_overpromotion.rate);
    samples.decision_brier.push(metrics.calibration.decision_brier);
  }
  return {
    iterations,
    seed,
    ci95: Object.fromEntries(Object.entries(samples).map(([name, values]) => [name, [round(percentile(values, 0.025)), round(percentile(values, 0.975))]])),
  };
}

function resultBase(engine, manifest, manifestHash, generatedAt) {
  return {
    result_version: "DAE-EMPIRICAL-BENCHMARK-RESULT-1.0",
    engine_version: engine.context.engineVersion,
    generated_at: generatedAt,
    benchmark_id: manifest?.benchmark_id ?? null,
    manifest_sha256: manifestHash ?? null,
    outcome: "INVALID_BENCHMARK",
    unit_count: manifest?.units?.length ?? 0,
    inputs: {},
    agreement: null,
    systems: null,
    comparison: null,
    promotion_gate: { passed: false, eligible: false, checks: {} },
    issues: [],
    claim_ceiling: RESULT_CEILING,
  };
}

function pendingResult(base, issues, annotationFiles = []) {
  return {
    ...base,
    outcome: "BLOCKED_PENDING_INDEPENDENT_LABELS",
    inputs: {
      annotation_files: annotationFiles,
      gold_file: null,
    },
    promotion_gate: {
      passed: false,
      eligible: false,
      checks: {
        independent_annotations: { passed: false, required: 2, observed: annotationFiles.length },
        adjudicated_gold: { passed: false },
      },
    },
    issues: sortIssues(issues),
  };
}

function reportNumber(value) {
  return value === null || value === undefined ? "NA" : typeof value === "number" ? value.toFixed(3) : String(value);
}

function benchmarkReport(result) {
  const lines = [
    `# Эмпирическая проверка ${result.benchmark_id ?? "INVALID"}`,
    "",
    `Итог: **${result.outcome}**.`,
    "",
    `Единиц: ${result.unit_count}. Claim ceiling: \`${result.claim_ceiling}\`.`,
    "",
  ];
  if (!result.systems) {
    lines.push("## Почему результат заблокирован", "");
    for (const item of result.issues) lines.push(`- ${item.severity} \`${item.code}\`: ${item.message}`);
    lines.push("", "Система не подставляет собственные решения вместо независимых меток. Нужны две завершённые слепые разметки и замороженный adjudicated gold-набор, связанный с ними по SHA-256.", "");
    return `${lines.join("\n")}\n`;
  }
  const primary = result.systems.DAE_PRIMARY;
  lines.push(
    "## Основные метрики", "",
    "| Метрика | Значение |", "|---|---:|",
    `| Accuracy | ${reportNumber(primary.accuracy)} |`,
    `| Macro-F1 | ${reportNumber(primary.macro_f1)} |`,
    `| Macro-F1 95% CI | [${reportNumber(primary.bootstrap.ci95.macro_f1[0])}, ${reportNumber(primary.bootstrap.ci95.macro_f1[1])}] |`,
    `| Dangerous overpromotion | ${reportNumber(primary.dangerous_overpromotion.rate)} |`,
    `| Decision ECE | ${reportNumber(primary.calibration.expected_calibration_error)} |`,
    `| Decision Brier | ${reportNumber(primary.calibration.decision_brier)} |`,
    `| Coverage | ${reportNumber(primary.abstention.coverage)} |`,
    `| Krippendorff α до adjudication | ${reportNumber(result.agreement?.metrics?.nominal?.alpha)} |`,
    "",
    "## Матрица ошибок", "",
    `| Gold \\ Predicted | ${EXPERT_STATUSES.join(" | ")} |`,
    `|---|${EXPERT_STATUSES.map(() => "---:").join("|")}|`,
  );
  for (const actual of EXPERT_STATUSES) lines.push(`| ${actual} | ${EXPERT_STATUSES.map((predicted) => primary.confusion_matrix[actual][predicted]).join(" | ")} |`);
  lines.push("", "## Promotion gate", "");
  for (const [name, check] of Object.entries(result.promotion_gate.checks)) {
    lines.push(`- ${check.passed ? "PASS" : "FAIL"} \`${name}\`: observed=${JSON.stringify(check.observed ?? null)}, required=${JSON.stringify(check.required ?? null)}`);
  }
  lines.push("", `Сильнейший заранее зафиксированный baseline: \`${result.comparison.best_fixed_baseline}\`; Δ macro-F1 = ${reportNumber(result.comparison.macro_f1_improvement)}.`, "");
  if (result.issues.length) {
    lines.push("## Замечания", "");
    for (const item of result.issues) lines.push(`- ${item.severity} \`${item.code}\`: ${item.message}`);
    lines.push("");
  }
  return `${lines.join("\n")}\n`;
}

async function writeBenchmarkResult(engine, out, result) {
  const schemaIssues = engine.structural.validateBenchmarkResult(result);
  if (schemaIssues.length) throw schemaFailure("BENCHMARK_RESULT", schemaIssues);
  await mkdir(out, { recursive: true });
  await Promise.all([
    writeFile(path.join(out, "BENCHMARK_RESULT.json"), jsonBytes(result), { flag: "wx" }),
    writeFile(path.join(out, "FINAL_BENCHMARK_REPORT.md"), benchmarkReport(result), { encoding: "utf8", flag: "wx" }),
  ]);
}

function exactUnitIssues(payload, expectedIds, pointer) {
  const ids = payload.units.map((unit) => unit.unit_id);
  const output = [];
  const repeated = duplicates(ids);
  if (repeated.length) output.push(issue("ERROR", "DUPLICATE_BENCHMARK_UNIT", pointer, `Duplicate units: ${repeated.join(", ")}.`));
  if (!sameMembers(ids, expectedIds)) output.push(issue("ERROR", "BENCHMARK_UNIT_SET_MISMATCH", pointer, "Submitted unit identifiers must exactly match the frozen manifest."));
  return output;
}

async function loadBenchmarkIntegrity(engine, benchmarkDirectory) {
  const root = path.resolve(benchmarkDirectory);
  const [manifestBytes, predictionBytes, lock, packetABytes, packetBBytes] = await Promise.all([
    readFile(path.join(root, "benchmark_manifest.json")),
    readFile(path.join(root, "sealed_predictions.json")),
    readJson(path.join(root, "benchmark_lock.json")),
    readFile(path.join(root, "blind_packets", "coder-a.json")),
    readFile(path.join(root, "blind_packets", "coder-b.json")),
  ]);
  const manifest = JSON.parse(manifestBytes.toString("utf8"));
  const predictions = JSON.parse(predictionBytes.toString("utf8"));
  const packets = [JSON.parse(packetABytes.toString("utf8")), JSON.parse(packetBBytes.toString("utf8"))];
  const manifestHash = canonicalBenchmarkSha256(manifest);
  const issues = [
    ...engine.structural.validateBenchmarkManifest(manifest),
    ...engine.structural.validateBenchmarkPredictions(predictions),
    ...packets.flatMap((packet) => engine.structural.validateBenchmarkPacket(packet)),
  ];
  if (lock.benchmark_id !== manifest.benchmark_id || predictions.benchmark_id !== manifest.benchmark_id || packets.some((packet) => packet.benchmark_id !== manifest.benchmark_id)) {
    issues.push(issue("ERROR", "BENCHMARK_ID_MISMATCH", "/benchmark_id", "Manifest, lock, predictions and blind packets must share one benchmark identifier."));
  }
  if (lock.manifest_sha256 !== manifestHash || predictions.manifest_sha256 !== manifestHash || packets.some((packet) => packet.manifest_sha256 !== manifestHash)) {
    issues.push(issue("ERROR", "BENCHMARK_MANIFEST_FIXITY_FAILED", "/manifest_sha256", "A benchmark component does not match the canonical frozen manifest hash."));
  }
  if (lock.manifest_file_sha256 !== sha256(manifestBytes) || lock.sealed_predictions_sha256 !== sha256(predictionBytes)) {
    issues.push(issue("ERROR", "BENCHMARK_FILE_FIXITY_FAILED", "/benchmark_lock", "Manifest or sealed prediction bytes changed after lock creation."));
  }
  for (const [index, packet] of packets.entries()) {
    const bytes = index === 0 ? packetABytes : packetBBytes;
    if (lock.blind_packet_sha256?.[packet.packet_id] !== sha256(bytes)) issues.push(issue("ERROR", "BLIND_PACKET_FIXITY_FAILED", `/blind_packets/${index}`, `${packet.packet_id} changed after lock creation.`));
  }
  const expectedIds = manifest.units.map((unit) => unit.unit_id);
  const cycleSnapshots = [];
  for (const [index, sourceCycle] of manifest.source_cycles.entries()) {
    try {
      const snapshotPath = path.resolve(root, sourceCycle.snapshot_file);
      if (!snapshotPath.startsWith(`${path.join(root, "source_cycles")}${path.sep}`)) {
        issues.push(issue("ERROR", "EXPERT_CYCLE_SNAPSHOT_PATH_INVALID", `/source_cycles/${index}/snapshot_file`, "Snapshot must remain inside source_cycles/."));
        continue;
      }
      const bytes = await readFile(snapshotPath);
      const cycle = JSON.parse(bytes.toString("utf8"));
      issues.push(...engine.structural.validateExpertCycle(cycle));
      if (sha256(bytes) !== sourceCycle.expert_cycle_sha256) issues.push(issue("ERROR", "EXPERT_CYCLE_SNAPSHOT_FIXITY_FAILED", `/source_cycles/${index}`, `${sourceCycle.snapshot_file} does not match its frozen SHA-256.`));
      if (cycle.run_id !== sourceCycle.run_id || cycle.source?.source_id !== sourceCycle.source_id || cycle.source?.artifact_sha256 !== sourceCycle.artifact_sha256 || cycle.profile?.profile_sha256 !== sourceCycle.profile_sha256) {
        issues.push(issue("ERROR", "EXPERT_CYCLE_SNAPSHOT_IDENTITY_MISMATCH", `/source_cycles/${index}`, "Snapshot identity does not match the manifest source-cycle record."));
      }
      cycleSnapshots.push(cycle);
    } catch (error) {
      issues.push(issue("ERROR", "EXPERT_CYCLE_SNAPSHOT_READ_FAILED", `/source_cycles/${index}`, error.message));
    }
  }
  const systemIds = predictions.systems.map((system) => system.system_id);
  if (!sameMembers(systemIds, ["DAE_PRIMARY", ...FIXED_BASELINES])) issues.push(issue("ERROR", "BENCHMARK_SYSTEM_SET_MISMATCH", "/systems", "Exactly DAE_PRIMARY and the two frozen baselines are required."));
  for (const [index, system] of predictions.systems.entries()) {
    const ids = system.predictions.map((prediction) => prediction.unit_id);
    if (!sameMembers(ids, expectedIds) || duplicates(ids).length) issues.push(issue("ERROR", "PREDICTION_UNIT_SET_MISMATCH", `/systems/${index}/predictions`, `${system.system_id} predictions do not exactly cover the manifest.`));
    if (system.system_id === "ALWAYS_INSUFFICIENT" && system.predictions.some((entry) => entry.status !== "INSUFFICIENT" || entry.confidence !== 1)) issues.push(issue("ERROR", "FROZEN_BASELINE_DEFINITION_MISMATCH", `/systems/${index}`, "ALWAYS_INSUFFICIENT must predict INSUFFICIENT at confidence 1 for every unit."));
    if (system.system_id === "ALWAYS_QUALIFIED" && system.predictions.some((entry) => entry.status !== "QUALIFIED" || entry.confidence !== 1)) issues.push(issue("ERROR", "FROZEN_BASELINE_DEFINITION_MISMATCH", `/systems/${index}`, "ALWAYS_QUALIFIED must predict QUALIFIED at confidence 1 for every unit."));
  }
  const primary = predictions.systems.find((system) => system.system_id === "DAE_PRIMARY");
  const primaryMap = new Map(primary?.predictions?.map((entry) => [entry.unit_id, entry]) ?? []);
  for (const cycle of cycleSnapshots) {
    for (const thesis of cycle.thesis_results) {
      const unitId = `BU-${sha256(`${cycle.run_id}\n${thesis.thesis_id}\n${cycle.source.artifact_sha256}`).slice(0, 16).toUpperCase()}`;
      const observed = primaryMap.get(unitId);
      if (!observed || observed.status !== thesis.status || observed.confidence !== thesis.confidence) issues.push(issue("ERROR", "SEALED_PREDICTION_SOURCE_MISMATCH", `/systems/DAE_PRIMARY/${unitId}`, "Sealed primary prediction differs from its frozen expert-cycle snapshot."));
    }
  }
  for (const [index, packet] of packets.entries()) {
    const packetIds = packet.units.map((unit) => unit.unit_id);
    if (!sameMembers(packetIds, expectedIds) || duplicates(packetIds).length) issues.push(issue("ERROR", "BLIND_PACKET_UNIT_SET_MISMATCH", `/blind_packets/${index}/units`, "Blind packet must exactly cover the frozen manifest units."));
    if (packet.units.some((unit) => ["status", "confidence", "analysis", "recommendation", "deterministic_gate", "reconstruction"].some((key) => Object.hasOwn(unit, key)) || Object.hasOwn(unit.thesis ?? {}, "status") || Object.hasOwn(unit.thesis ?? {}, "confidence"))) {
      issues.push(issue("ERROR", "BLIND_PACKET_DECISION_LEAK", `/blind_packets/${index}/units`, "Blind packet contains a forbidden system-decision field."));
    }
  }
  return { root, manifest, predictions, lock, packets, manifestHash, issues: sortIssues(issues) };
}

async function annotationFilesIn(directory) {
  if (!directory) return [];
  try {
    const entries = await readdir(path.resolve(directory), { withFileTypes: true });
    return entries.filter((entry) => entry.isFile() && entry.name.endsWith(".json") && !entry.name.endsWith(".template.json"))
      .map((entry) => path.join(path.resolve(directory), entry.name)).sort();
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

export async function evaluateExpertBenchmark(engine, benchmarkDirectory, outputDirectory, options = {}) {
  const out = path.resolve(outputDirectory);
  await requireNewDirectory(out);
  const generatedAt = timestamp(options.generatedAt);
  let integrity;
  try {
    integrity = await loadBenchmarkIntegrity(engine, benchmarkDirectory);
  } catch (error) {
    const base = resultBase(engine, null, null, generatedAt);
    const result = { ...base, issues: [issue("ERROR", "BENCHMARK_READ_FAILED", "/", error.message)] };
    await writeBenchmarkResult(engine, out, result);
    return { output_dir: out, result };
  }
  const { manifest, predictions, lock, manifestHash } = integrity;
  const base = resultBase(engine, manifest, manifestHash, generatedAt);
  if (integrity.issues.some((item) => item.severity === "ERROR")) {
    const result = { ...base, inputs: { benchmark_directory: path.basename(integrity.root) }, issues: integrity.issues };
    await writeBenchmarkResult(engine, out, result);
    return { output_dir: out, result };
  }
  const annotationFiles = await annotationFilesIn(options.annotationsDirectory);
  if (annotationFiles.length < manifest.evaluation_plan.independent_coders_min || !options.goldFile) {
    const missing = [];
    if (annotationFiles.length < manifest.evaluation_plan.independent_coders_min) missing.push(issue("REVIEW", "INDEPENDENT_LABELS_REQUIRED", "/annotations", `${manifest.evaluation_plan.independent_coders_min} completed independent annotation files are required; observed ${annotationFiles.length}.`));
    if (!options.goldFile) missing.push(issue("REVIEW", "ADJUDICATED_GOLD_REQUIRED", "/gold", "Gold must be frozen from the independent raw annotations before predictions are unsealed."));
    if (manifest.units.length < manifest.evaluation_plan.minimum_units) missing.push(issue("WARNING", "BENCHMARK_UNDERPOWERED", "/units", `${manifest.units.length} units are below the frozen minimum ${manifest.evaluation_plan.minimum_units}.`));
    const result = pendingResult(base, missing, annotationFiles.map((file) => path.basename(file)));
    await writeBenchmarkResult(engine, out, result);
    return { output_dir: out, result };
  }

  const issues = [];
  const annotations = [];
  for (const file of annotationFiles) {
    try {
      const bytes = await readFile(file);
      const payload = JSON.parse(bytes.toString("utf8"));
      issues.push(...engine.structural.validateBenchmarkAnnotation(payload));
      annotations.push({ file, bytes, hash: sha256(bytes), payload });
    } catch (error) {
      issues.push(issue("ERROR", "ANNOTATION_READ_FAILED", `/annotations/${path.basename(file)}`, error.message));
    }
  }
  let gold = null;
  let goldBytes = null;
  try {
    goldBytes = await readFile(path.resolve(options.goldFile));
    gold = JSON.parse(goldBytes.toString("utf8"));
    issues.push(...engine.structural.validateBenchmarkGold(gold));
  } catch (error) {
    issues.push(issue("ERROR", "GOLD_READ_FAILED", "/gold", error.message));
  }
  const expectedIds = manifest.units.map((unit) => unit.unit_id);
  const allowedPacketHashes = new Set(Object.values(lock.blind_packet_sha256));
  for (const [index, annotation] of annotations.entries()) {
    const payload = annotation.payload ?? {};
    if (payload.benchmark_id !== manifest.benchmark_id || payload.manifest_sha256 !== manifestHash) issues.push(issue("ERROR", "ANNOTATION_BENCHMARK_MISMATCH", `/annotations/${index}`, "Annotation does not belong to this frozen manifest."));
    if (!allowedPacketHashes.has(payload.packet_sha256)) issues.push(issue("ERROR", "ANNOTATION_PACKET_MISMATCH", `/annotations/${index}/packet_sha256`, "Annotation is not linked to either frozen blind packet."));
    if (Array.isArray(payload.units)) issues.push(...exactUnitIssues(payload, expectedIds, `/annotations/${index}/units`));
  }
  const coderIds = annotations.map((entry) => entry.payload?.coder?.id).filter(Boolean);
  if (duplicates(coderIds).length) issues.push(issue("ERROR", "DUPLICATE_INDEPENDENT_CODER", "/annotations", "Every raw annotation must have a distinct coder id."));
  if (gold) {
    if (gold.benchmark_id !== manifest.benchmark_id || gold.manifest_sha256 !== manifestHash) issues.push(issue("ERROR", "GOLD_BENCHMARK_MISMATCH", "/gold", "Gold does not belong to this frozen manifest."));
    if (Array.isArray(gold.units)) issues.push(...exactUnitIssues(gold, expectedIds, "/gold/units"));
    const submittedHashes = annotations.map((entry) => entry.hash);
    if (!sameMembers(gold.adjudication?.source_annotation_sha256 ?? [], submittedHashes)) issues.push(issue("ERROR", "GOLD_ANNOTATION_FIXITY_MISMATCH", "/gold/adjudication/source_annotation_sha256", "Gold must name exactly the raw annotation byte hashes evaluated in this run."));
    const latestAnnotation = Math.max(...annotations.map((entry) => Date.parse(entry.payload.completed_at)).filter(Number.isFinite));
    if (Number.isFinite(latestAnnotation) && Date.parse(gold.frozen_at) < latestAnnotation) issues.push(issue("ERROR", "GOLD_FROZEN_BEFORE_ANNOTATIONS", "/gold/frozen_at", "Gold freeze time precedes a contributing annotation completion time."));
  }
  if (issues.some((item) => item.severity === "ERROR")) {
    const result = {
      ...base,
      inputs: {
        annotation_files: annotations.map((entry) => ({ name: path.basename(entry.file), sha256: entry.hash })),
        gold_file: goldBytes ? { name: path.basename(options.goldFile), sha256: sha256(goldBytes) } : null,
      },
      issues: sortIssues(issues),
    };
    await writeBenchmarkResult(engine, out, result);
    return { output_dir: out, result };
  }

  const annotationMaps = annotations.map((entry) => new Map(entry.payload.units.map((unit) => [unit.unit_id, unit])));
  const agreementPayload = {
    agreement_version: "DAE-ANNOTATIONS-1.0",
    dataset_id: manifest.benchmark_id,
    codebook_id: manifest.codebook.codebook_id,
    coders: annotations.map((entry) => ({ id: entry.payload.coder.id, independent: true })),
    units: manifest.units.map((unit) => ({
      unit_id: unit.unit_id,
      annotations: Object.fromEntries(annotations.map((entry, index) => [entry.payload.coder.id, {
        dominant: annotationMaps[index].get(unit.unit_id).status,
        secondary: [],
        confidence: annotationMaps[index].get(unit.unit_id).confidence,
      }])),
    })),
    thresholds: {
      alpha_min: manifest.evaluation_plan.agreement.alpha_min,
      alpha_ci_lower_min: manifest.evaluation_plan.agreement.alpha_ci_lower_min,
      multilabel_match_min: 0,
      multilabel_f1_min: 0,
      bootstrap_iterations: manifest.evaluation_plan.bootstrap_iterations,
      seed: `${manifest.evaluation_plan.seed}:agreement`,
    },
  };
  const agreement = evaluateAgreementPayload(engine, agreementPayload, "<frozen-independent-annotations>");
  const goldMap = new Map(gold.units.map((unit) => [unit.unit_id, unit.gold_status]));
  const systems = {};
  for (const system of predictions.systems) {
    const predictionMap = new Map(system.predictions.map((entry) => [entry.unit_id, entry]));
    const orderedPredictions = manifest.units.map((unit) => predictionMap.get(unit.unit_id).status);
    const orderedConfidence = manifest.units.map((unit) => predictionMap.get(unit.unit_id).confidence);
    const orderedGold = manifest.units.map((unit) => goldMap.get(unit.unit_id));
    const metrics = classificationMetrics(orderedPredictions, orderedGold, orderedConfidence);
    metrics.bootstrap = bootstrapClassification(orderedPredictions, orderedGold, orderedConfidence, manifest.evaluation_plan.bootstrap_iterations, `${manifest.evaluation_plan.seed}:${system.system_id}`);
    systems[system.system_id] = metrics;
  }
  const bestBaseline = FIXED_BASELINES.map((id) => ({ id, macroF1: systems[id].macro_f1, accuracy: systems[id].accuracy }))
    .sort((left, right) => right.macroF1 - left.macroF1 || right.accuracy - left.accuracy || left.id.localeCompare(right.id))[0];
  const primary = systems.DAE_PRIMARY;
  const goldDistribution = primary.gold_distribution;
  const comparison = {
    best_fixed_baseline: bestBaseline.id,
    best_fixed_baseline_macro_f1: bestBaseline.macroF1,
    primary_macro_f1: primary.macro_f1,
    macro_f1_improvement: round(primary.macro_f1 - bestBaseline.macroF1),
    comparator_policy: "Strongest of the two baselines frozen before gold labels.",
  };
  const checks = {
    sample_size: { observed: manifest.units.length, required: manifest.evaluation_plan.minimum_units, passed: manifest.units.length >= manifest.evaluation_plan.minimum_units },
    gold_per_label: { observed: goldDistribution, required: manifest.evaluation_plan.minimum_gold_per_label, passed: EXPERT_STATUSES.every((status) => goldDistribution[status] >= manifest.evaluation_plan.minimum_gold_per_label) },
    agreement_alpha: { observed: agreement.metrics?.nominal?.alpha ?? null, required: manifest.evaluation_plan.agreement.alpha_min, passed: Number.isFinite(agreement.metrics?.nominal?.alpha) && agreement.metrics.nominal.alpha >= manifest.evaluation_plan.agreement.alpha_min },
    agreement_alpha_ci_lower: { observed: agreement.metrics?.bootstrap?.alpha_ci95?.[0] ?? null, required: manifest.evaluation_plan.agreement.alpha_ci_lower_min, passed: Number.isFinite(agreement.metrics?.bootstrap?.alpha_ci95?.[0]) && agreement.metrics.bootstrap.alpha_ci95[0] >= manifest.evaluation_plan.agreement.alpha_ci_lower_min },
    primary_macro_f1: { observed: primary.macro_f1, required: manifest.evaluation_plan.promotion.macro_f1_min, passed: primary.macro_f1 >= manifest.evaluation_plan.promotion.macro_f1_min },
    primary_macro_f1_ci_lower: { observed: primary.bootstrap.ci95.macro_f1[0], required: manifest.evaluation_plan.promotion.macro_f1_ci_lower_min, passed: primary.bootstrap.ci95.macro_f1[0] >= manifest.evaluation_plan.promotion.macro_f1_ci_lower_min },
    baseline_improvement: { observed: comparison.macro_f1_improvement, required: manifest.evaluation_plan.promotion.improvement_over_best_fixed_baseline_min, passed: comparison.macro_f1_improvement >= manifest.evaluation_plan.promotion.improvement_over_best_fixed_baseline_min },
    dangerous_overpromotion: { observed: primary.dangerous_overpromotion.rate, required: { maximum: manifest.evaluation_plan.promotion.dangerous_overpromotion_rate_max }, passed: primary.dangerous_overpromotion.rate <= manifest.evaluation_plan.promotion.dangerous_overpromotion_rate_max },
    decision_ece: { observed: primary.calibration.expected_calibration_error, required: { maximum: manifest.evaluation_plan.promotion.decision_ece_max }, passed: primary.calibration.expected_calibration_error <= manifest.evaluation_plan.promotion.decision_ece_max },
  };
  const reliable = checks.agreement_alpha.passed && checks.agreement_alpha_ci_lower.passed;
  const powered = checks.sample_size.passed && checks.gold_per_label.passed;
  const allPassed = Object.values(checks).every((check) => check.passed);
  const outcome = !reliable ? "FAIL_RELIABILITY" : !powered ? "BLOCKED_UNDERPOWERED" : allPassed ? "PASS_PROMOTION_GATE" : "FAIL_PROMOTION_GATE";
  const resultIssues = [...issues, ...agreement.issues];
  if (!powered) resultIssues.push(issue("REVIEW", "BENCHMARK_UNDERPOWERED", "/promotion_gate", "Sample size or per-label gold support is below the frozen minimum."));
  if (!reliable) resultIssues.push(issue("REVIEW", "BENCHMARK_RELIABILITY_FAILED", "/agreement", "Independent agreement failed its frozen alpha gate before adjudication."));
  if (powered && reliable && !allPassed) resultIssues.push(issue("REVIEW", "BENCHMARK_PROMOTION_FAILED", "/promotion_gate", "At least one performance, safety or calibration requirement failed."));
  const result = {
    ...base,
    outcome,
    inputs: {
      annotation_files: annotations.map((entry) => ({ name: path.basename(entry.file), sha256: entry.hash, coder_id: entry.payload.coder.id })),
      gold_file: { name: path.basename(options.goldFile), sha256: sha256(goldBytes) },
    },
    agreement,
    systems,
    comparison,
    promotion_gate: { passed: outcome === "PASS_PROMOTION_GATE", eligible: reliable && powered, checks },
    issues: sortIssues(resultIssues),
  };
  await writeBenchmarkResult(engine, out, result);
  return { output_dir: out, result };
}
