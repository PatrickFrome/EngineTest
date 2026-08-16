import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { classificationMetrics, evaluateExpertBenchmark, initExpertBenchmark } from "../src/benchmark.mjs";
import { createEngine } from "../src/engine.mjs";
import { projectPath, readJson } from "../src/paths.mjs";

const engine = await createEngine();
const generatedAt = "2026-08-11T12:00:00Z";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function jsonBytes(value) {
  return Buffer.from(`${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function syntheticCycle(file, count = 80) {
  const original = await readJson(projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "expert-cycle", "expert_cycle.json"));
  const cycle = clone(original);
  cycle.engine_version = engine.context.engineVersion;
  cycle.generated_at = generatedAt;
  cycle.run_id = "EXPERT-SYNTHETIC-BENCHMARK-ABCDEF123456";
  const prototypes = Object.fromEntries(original.thesis_results.map((entry) => [entry.status, entry]));
  cycle.thesis_results = Array.from({ length: count }, (_, index) => {
    const status = ["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"][index % 4];
    const result = clone(prototypes[status]);
    result.thesis_id = `SYNTHETIC_${String(index + 1).padStart(3, "0")}`;
    result.title = `Synthetic benchmark thesis ${index + 1}`;
    result.statement = `Synthetic independently adjudicable thesis number ${index + 1}.`;
    result.status = status;
    result.confidence = 0.9;
    return result;
  });
  const ids = (status) => cycle.thesis_results.filter((entry) => entry.status === status).map((entry) => entry.thesis_id);
  cycle.global_analytics.supported_theses = ids("SUPPORTED");
  cycle.global_analytics.qualified_theses = ids("QUALIFIED");
  cycle.global_analytics.rejected_theses = ids("REJECTED");
  cycle.global_analytics.insufficient_theses = ids("INSUFFICIENT");
  assert.equal(engine.structural.validateExpertCycle(cycle).length, 0);
  await writeFile(file, jsonBytes(cycle));
}

async function perfectExternalLabels(benchmarkDirectory, annotationDirectory, goldFile) {
  const manifest = await readJson(path.join(benchmarkDirectory, "benchmark_manifest.json"));
  const predictions = await readJson(path.join(benchmarkDirectory, "sealed_predictions.json"));
  const lock = await readJson(path.join(benchmarkDirectory, "benchmark_lock.json"));
  const primary = new Map(predictions.systems.find((system) => system.system_id === "DAE_PRIMARY").predictions.map((entry) => [entry.unit_id, entry.status]));
  const packetHashes = Object.values(lock.blind_packet_sha256);
  await mkdir(annotationDirectory, { recursive: true });
  const annotationPayload = (coder, packetHash, completedAt) => ({
    annotation_version: "DAE-EXPERT-ANNOTATION-1.0",
    benchmark_id: manifest.benchmark_id,
    manifest_sha256: lock.manifest_sha256,
    packet_sha256: packetHash,
    coder: {
      id: coder,
      role: "INDEPENDENT_DOMAIN_ANNOTATOR",
      independent_of_system_development: true,
      blinded_to_predictions: true,
      source_access_attested: true,
      conflicts_disclosed: [],
    },
    completed_at: completedAt,
    units: manifest.units.map((unit) => ({
      unit_id: unit.unit_id,
      status: primary.get(unit.unit_id),
      confidence: 3,
      evidence_refs: [`SYNTHETIC-SOURCE#${unit.unit_id}`],
      rationale: "Independent synthetic fixture rationale with sufficient length.",
    })),
    claim_ceiling: "INDEPENDENT_CODER_JUDGMENT_NOT_ADJUDICATED_GOLD",
  });
  const bytesA = jsonBytes(annotationPayload("external-coder-a", packetHashes[0], "2026-08-11T12:10:00Z"));
  const bytesB = jsonBytes(annotationPayload("external-coder-b", packetHashes[1], "2026-08-11T12:11:00Z"));
  await Promise.all([
    writeFile(path.join(annotationDirectory, "coder-a.json"), bytesA),
    writeFile(path.join(annotationDirectory, "coder-b.json"), bytesB),
  ]);
  const gold = {
    gold_version: "DAE-ADJUDICATED-GOLD-1.0",
    benchmark_id: manifest.benchmark_id,
    manifest_sha256: lock.manifest_sha256,
    adjudication: {
      curator_id: "external-curator",
      independent_of_system_development: true,
      predictions_hidden_until_gold_frozen: true,
      source_annotation_sha256: [sha256(bytesA), sha256(bytesB)],
    },
    frozen_at: "2026-08-11T12:20:00Z",
    units: manifest.units.map((unit) => ({
      unit_id: unit.unit_id,
      gold_status: primary.get(unit.unit_id),
      adjudication_method: "UNANIMOUS_AUTO_MERGE",
      evidence_refs: [`SYNTHETIC-SOURCE#${unit.unit_id}`],
      rationale: "Both independent synthetic coders agreed before predictions were unsealed.",
    })),
    claim_ceiling: "FROZEN_ADJUDICATED_BENCHMARK_GOLD_FOR_THIS_SAMPLE",
  };
  await writeFile(goldFile, jsonBytes(gold));
}

test("benchmark-init seals predictions and blind packets omit decision fields", async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), "dae-benchmark-init-"));
  try {
    const cycle = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "expert-cycle", "expert_cycle.json");
    const output = path.join(temp, "benchmark");
    const result = await initExpertBenchmark(engine, [cycle], output, { generatedAt });
    assert.equal(result.unit_count, 9);
    assert.equal(result.status, "BLOCKED_PENDING_INDEPENDENT_LABELS");
    const packet = await readJson(path.join(output, "blind_packets", "coder-a.json"));
    assert.equal(packet.units.every((unit) => !("status" in unit) && !("confidence" in unit) && !("analysis" in unit)), true);
    assert.equal(engine.structural.validateBenchmarkPacket(packet).length, 0);
    const predictions = await readJson(path.join(output, "sealed_predictions.json"));
    assert.equal(predictions.systems.find((system) => system.system_id === "DAE_PRIMARY").predictions.length, 9);
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("benchmark evaluation blocks without independent annotations and adjudicated gold", async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), "dae-benchmark-blocked-"));
  try {
    const cycle = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "expert-cycle", "expert_cycle.json");
    const benchmark = path.join(temp, "benchmark");
    await initExpertBenchmark(engine, [cycle], benchmark, { generatedAt });
    const evaluated = await evaluateExpertBenchmark(engine, benchmark, path.join(temp, "evaluation"), { generatedAt });
    assert.equal(evaluated.result.outcome, "BLOCKED_PENDING_INDEPENDENT_LABELS");
    assert.equal(evaluated.result.systems, null, "metrics must not be computed against system-generated pseudo-gold");
    assert(evaluated.result.issues.some((entry) => entry.code === "INDEPENDENT_LABELS_REQUIRED"));
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("sealed prediction mutation invalidates the benchmark before evaluation", async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), "dae-benchmark-fixity-"));
  try {
    const cycle = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "expert-cycle", "expert_cycle.json");
    const benchmark = path.join(temp, "benchmark");
    await initExpertBenchmark(engine, [cycle], benchmark, { generatedAt });
    const file = path.join(benchmark, "sealed_predictions.json");
    const predictions = await readJson(file);
    predictions.systems[0].predictions[0].status = "INSUFFICIENT";
    await writeFile(file, jsonBytes(predictions));
    const evaluated = await evaluateExpertBenchmark(engine, benchmark, path.join(temp, "evaluation"), { generatedAt });
    assert.equal(evaluated.result.outcome, "INVALID_BENCHMARK");
    assert(evaluated.result.issues.some((entry) => entry.code === "BENCHMARK_FILE_FIXITY_FAILED"));
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("expert-cycle snapshot mutation invalidates prediction provenance", async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), "dae-benchmark-source-fixity-"));
  try {
    const cycle = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "expert-cycle", "expert_cycle.json");
    const benchmark = path.join(temp, "benchmark");
    await initExpertBenchmark(engine, [cycle], benchmark, { generatedAt });
    const manifest = await readJson(path.join(benchmark, "benchmark_manifest.json"));
    const snapshot = path.join(benchmark, manifest.source_cycles[0].snapshot_file);
    const payload = await readJson(snapshot);
    payload.thesis_results[0].confidence = 0.01;
    await writeFile(snapshot, jsonBytes(payload));
    const evaluated = await evaluateExpertBenchmark(engine, benchmark, path.join(temp, "evaluation"), { generatedAt });
    assert.equal(evaluated.result.outcome, "INVALID_BENCHMARK");
    assert(evaluated.result.issues.some((entry) => entry.code === "EXPERT_CYCLE_SNAPSHOT_FIXITY_FAILED"));
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("classification metrics expose dangerous overpromotion and abstention", () => {
  const metrics = classificationMetrics(
    ["SUPPORTED", "QUALIFIED", "INSUFFICIENT", "REJECTED"],
    ["REJECTED", "INSUFFICIENT", "SUPPORTED", "REJECTED"],
    [0.9, 0.8, 0.7, 0.95],
  );
  assert.equal(metrics.dangerous_overpromotion.count, 2);
  assert.equal(metrics.abstention.count, 1);
  assert.equal(metrics.accuracy, 0.25);
  assert(metrics.calibration.decision_brier > 0);
});

test("80-unit balanced independent benchmark can pass every frozen promotion gate", async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), "dae-benchmark-pass-"));
  try {
    const cycleFile = path.join(temp, "expert_cycle.json");
    const benchmark = path.join(temp, "benchmark");
    const annotations = path.join(temp, "annotations");
    const gold = path.join(temp, "gold.json");
    await syntheticCycle(cycleFile, 80);
    await initExpertBenchmark(engine, [cycleFile], benchmark, { generatedAt, bootstrapIterations: 500 });
    await perfectExternalLabels(benchmark, annotations, gold);
    const evaluated = await evaluateExpertBenchmark(engine, benchmark, path.join(temp, "evaluation"), {
      annotationsDirectory: annotations,
      goldFile: gold,
      generatedAt: "2026-08-11T12:30:00Z",
    });
    assert.equal(evaluated.result.outcome, "PASS_PROMOTION_GATE", JSON.stringify(evaluated.result.issues, null, 2));
    assert.equal(evaluated.result.promotion_gate.passed, true);
    assert.equal(evaluated.result.systems.DAE_PRIMARY.macro_f1, 1);
    assert.equal(evaluated.result.agreement.metrics.nominal.alpha, 1);
    assert(evaluated.result.comparison.macro_f1_improvement >= 0.05);
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});
