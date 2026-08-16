import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createEngine } from "../src/engine.mjs";
import { runEtymologyProtocol, validateEtymologyPass } from "../src/etymology.mjs";
import { runLivingAnalysis } from "../src/living-analysis.mjs";
import { projectPath } from "../src/paths.mjs";

const engine = await createEngine();
const refinery = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "refinery");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

async function workspace(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), "dae-ety-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  return root;
}

test("ETY-0.2 covers every central concept while refusing automatic significance", async (t) => {
  const root = await workspace(t);
  const result = await runEtymologyProtocol(engine, refinery, path.join(root, "run"), { generatedAt: "2026-08-11T12:00:00Z" });
  assert.equal(result.validation.conformant, true, JSON.stringify(result.validation.issues, null, 2));
  assert.equal(result.pass.coverage.coverage_complete, true);
  assert.equal(result.pass.coverage.cards_emitted, result.pass.coverage.central_concepts);
  assert.equal(result.pass.coverage.ety_full_executed, result.pass.coverage.ety_full_required);
  assert(result.pass.cards.some((card) => card.concept_id === "WIRKLICHKEIT" && card.level === "ETY-FULL"));
  assert(result.pass.cards.every((card) => card.ety_min.local_sense.resolution === "UNRESOLVED"));
  assert(result.pass.cards.every((card) => card.bridge.semantic_promotion_allowed === false));
  assert.equal(result.pass.output_contract.mandatory_execution, true);
  assert.equal(result.pass.output_contract.mandatory_significance, false);
  assert.equal(result.pass.output_contract.null_result_is_valid, true);
});

test("ETY-FULL cannot omit counter-etymology, phenomenological and bridge contours", async (t) => {
  const root = await workspace(t);
  const result = await runEtymologyProtocol(engine, refinery, path.join(root, "run"), { generatedAt: "2026-08-11T12:00:00Z" });
  const invalid = clone(result.pass);
  const full = invalid.cards.find((card) => card.level === "ETY-FULL");
  delete full.ety_full.COUNTER_ETYMOLOGY;
  const validation = validateEtymologyPass(engine, invalid);
  assert.equal(validation.conformant, false);
  assert(validation.issues.some((entry) => entry.code === "ETYMOLOGY_PASS_SCHEMA"));
});

test("living analysis cryptographically binds mandatory etymology and every constellation references cards", async (t) => {
  const root = await workspace(t);
  const result = await runLivingAnalysis(engine, refinery, path.join(root, "run"), { seed: "ety-bound", generatedAt: "2026-08-11T12:00:00Z" });
  const bytes = await readFile(result.files.etymology);
  const hash = createHash("sha256").update(bytes).digest("hex");
  assert.equal(result.analysis.etymology.pass_sha256, hash);
  assert.equal(result.analysis.output_contract.mandatory_etymology_executed, true);
  assert(result.analysis.constellations.every((entry) => entry.etymology_card_ids.length > 0));
  assert.equal(result.etymology.pass.output_contract.semantic_promotion_performed, false);
});


test("explicit ETY stress terms remain mandatory even when no topic hypothesis selects them", async (t) => {
  const root = await workspace(t);
  const synthetic = path.join(root, "refinery");
  await mkdir(synthetic);
  const report = JSON.parse(await readFile(path.join(refinery, "REFINERY_REPORT.json"), "utf8"));
  const bank = JSON.parse(await readFile(path.join(refinery, "hypothesis_bank.json"), "utf8"));
  bank.bank_version = "DAE-HYPOTHESIS-BANK-1.1";
  bank.source_resistance = {
    status: "NO_STRONG_REGISTRY_RESISTANCE_DETECTED",
    central_terms: [],
    covered_terms: [],
    uncovered_terms: [],
    coverage_ratio: 1,
    explicit_stress_terms: ["Vierung", "Spiegel-Spiel", "Schonen"],
    emergent_hypotheses: [],
    principle: "SOURCE_CENTRALITY_CAN_FORCE_TOPIC_AND_OPERATOR_REVISION_BUT_CANNOT_BY_ITSELF_VALIDATE_A_PHILOSOPHICAL_CLAIM",
  };
  await Promise.all([
    writeFile(path.join(synthetic, "REFINERY_REPORT.json"), `${JSON.stringify(report, null, 2)}\n`),
    writeFile(path.join(synthetic, "hypothesis_bank.json"), `${JSON.stringify(bank, null, 2)}\n`),
  ]);
  const result = await runEtymologyProtocol(engine, synthetic, path.join(root, "run"), { generatedAt: "2026-08-11T12:00:00Z" });
  for (const conceptId of ["VIERUNG", "SPIEGEL_SPIEL", "SCHONEN"]) {
    const card = result.pass.cards.find((entry) => entry.concept_id === conceptId);
    assert(card, `${conceptId} must receive mandatory ETY coverage`);
    assert.equal(card.level, "ETY-FULL");
    assert(card.escalation_reasons.includes("EXPLICIT_ETY_STRESS_REQUEST_REQUIRES_FULL_CONTEXT_AUDIT"));
  }
});
