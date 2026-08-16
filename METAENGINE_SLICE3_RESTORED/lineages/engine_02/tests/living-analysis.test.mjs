import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createEngine } from "../src/engine.mjs";
import { runLivingAnalysis, validateLivingAnalysis } from "../src/living-analysis.mjs";
import { projectPath } from "../src/paths.mjs";

const engine = await createEngine();
const refinery = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "refinery");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

async function json(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

async function workspace(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), "dae-living-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  return root;
}

test("living cycle emits a nonlinear, open and gain-bearing exploratory graph", async (t) => {
  const root = await workspace(t);
  const result = await runLivingAnalysis(engine, refinery, path.join(root, "run"), { seed: "living-primary" });
  assert.equal(result.validation.conformant, true, JSON.stringify(result.validation.issues, null, 2));
  assert.equal(result.analysis.layer.core_mutated, false);
  assert.equal(result.analysis.output_contract.terminal_verdicts_emitted, false);
  assert.equal(result.analysis.output_contract.each_active_step_adds_traceable_gain, true);
  assert.equal(result.analysis.sufficient_openness.satisfied, true);
  assert(result.analysis.graph.nodes.length > 100);
  assert(result.analysis.graph.edges.some((edge) => edge.relation === "CROSSES_CONSTELLATION"));
  assert(result.analysis.graph.nodes.some((node) => node.role === "COUNTER_GENEALOGY"));
  assert(result.analysis.graph.nodes.some((node) => node.role === "POLYPHONIC_FIELD"));
  assert(result.analysis.graph.nodes.some((node) => node.role === "RESEARCH_BRANCH" && node.residual_kind === "R3-G"));
  for (const node of result.analysis.graph.nodes.filter((entry) => entry.role !== "QUESTION")) {
    assert(node.generative_gains.length > 0, `${node.node_id} emitted no qualitative gain`);
  }
  for (const constellation of result.trace.constellations) {
    for (const step of constellation.steps) {
      assert.equal(step.gain_contract_satisfied, true, `${constellation.constellation_id}/${step.selected_operator}`);
      assert(step.generative_gains.length > 0);
    }
  }
  const fieldNote = await readFile(result.files.field_note, "utf8");
  assert.match(fieldNote, /Узлы, которых не было в отдельной теме/u);
  assert.match(fieldNote, /Самодеструкция этой записи/u);
  assert.match(fieldNote, /Laienbrevier Effect/u);
});

test("seed changes traversal without changing the generated philosophical candidates", async (t) => {
  const root = await workspace(t);
  const left = await runLivingAnalysis(engine, refinery, path.join(root, "left"), { seed: "constellation-left" });
  const right = await runLivingAnalysis(engine, refinery, path.join(root, "right"), { seed: "constellation-right" });
  assert.notDeepEqual(left.analysis.graph.traversal_order, right.analysis.graph.traversal_order);
  assert.deepEqual(left.analysis.source, right.analysis.source);
  assert.deepEqual(left.analysis.graph.nodes, right.analysis.graph.nodes);
  assert.deepEqual(left.analysis.graph.edges, right.analysis.graph.edges);
  assert.deepEqual(left.analysis.constellations, right.analysis.constellations);
});

test("divergent 2.27 and 2.28 protocol branches remain independently selectable", async (t) => {
  const root = await workspace(t);
  const syntheticRefinery = path.join(root, "refinery");
  await mkdir(syntheticRefinery);
  const report = await json(path.join(refinery, "REFINERY_REPORT.json"));
  const originalBank = await json(path.join(refinery, "hypothesis_bank.json"));
  const base = clone(originalBank.hypotheses[0]);
  const identity = {
    ...base,
    hypothesis_id: "HYP-BRANCH-227",
    topic_id: "IDENTITY_AND_INDIVIDUATION",
    label: "Individuation, boundary, relation and coupling",
    research_question: "Which boundary and coupling individuate a bearer before identity and constitution are asserted?",
    matched_groups: ["INDIVIDUATION", "BOUNDARY", "RELATION", "CONSTITUTION", "ENABLEMENT"],
    evidence_count: 24,
  };
  const political = {
    ...base,
    hypothesis_id: "HYP-BRANCH-228",
    topic_id: "POLITICAL_REPRESENTATION",
    label: "Institution, authority, state, leadership and representation",
    research_question: "When does a decision represent others without becoming truth, and how can authority remain corrigible?",
    matched_groups: ["INSTITUTION", "AUTHORITY", "STATE", "LEADERSHIP", "REPRESENTATION", "DECISION"],
    evidence_count: 24,
  };
  const bank = { ...originalBank, hypotheses: [identity, political], case_matrices: [] };
  await Promise.all([
    writeFile(path.join(syntheticRefinery, "REFINERY_REPORT.json"), `${JSON.stringify(report, null, 2)}\n`),
    writeFile(path.join(syntheticRefinery, "hypothesis_bank.json"), `${JSON.stringify(bank, null, 2)}\n`),
  ]);
  const result = await runLivingAnalysis(engine, syntheticRefinery, path.join(root, "run"), { seed: "branches", maximumFamilies: 8 });
  const families = new Set(result.analysis.constellations.flatMap((entry) => entry.activated_families));
  for (const family of [
    "F-ENABLEMENT", "F-CONSTITUTION", "F-IDENTITY", "F-INDIVIDUATION", "F-BOUNDARY", "F-RELATION-COUPLING",
    "F-INSTITUTION-AUTHORITY", "F-REPRESENTATION-DECISION",
  ]) assert(families.has(family), `missing independently selectable ${family}`);
});

test("an active ritual step without gain is rejected semantically", async (t) => {
  const root = await workspace(t);
  const result = await runLivingAnalysis(engine, refinery, path.join(root, "run"), { seed: "gain-negative" });
  const invalid = clone(result.analysis);
  const target = invalid.graph.nodes.find((node) => node.role !== "QUESTION");
  target.generative_gains = [];
  const validation = validateLivingAnalysis(engine, invalid);
  assert.equal(validation.conformant, false);
  assert(validation.issues.some((entry) => entry.code === "LIVING_ACTIVE_MOVE_REQUIRES_GAIN"));
});

test("weak material can skip generative gestures instead of fabricating surprise", async (t) => {
  const root = await workspace(t);
  const syntheticRefinery = path.join(root, "refinery");
  await mkdir(syntheticRefinery);
  const report = await json(path.join(refinery, "REFINERY_REPORT.json"));
  const originalBank = await json(path.join(refinery, "hypothesis_bank.json"));
  const weak = {
    ...clone(originalBank.hypotheses[0]),
    hypothesis_id: "HYP-WEAK-OPEN",
    topic_id: "UNFAMILIAR_LOCAL_APORIA",
    label: "A local unresolved aporia",
    research_question: "What is at issue in this single unresolved occurrence?",
    matched_groups: ["LOCAL"],
    evidence_segment_ids: [originalBank.hypotheses[0].evidence_segment_ids[0]],
    evidence_count: 1,
    selectors_truncated: false,
  };
  const bank = { ...originalBank, hypotheses: [weak], case_matrices: [] };
  await Promise.all([
    writeFile(path.join(syntheticRefinery, "REFINERY_REPORT.json"), `${JSON.stringify(report, null, 2)}\n`),
    writeFile(path.join(syntheticRefinery, "hypothesis_bank.json"), `${JSON.stringify(bank, null, 2)}\n`),
  ]);
  const result = await runLivingAnalysis(engine, syntheticRefinery, path.join(root, "run"), { seed: "weak-material" });
  const constellation = result.analysis.constellations[0];
  assert(constellation.skipped_gestures.some((entry) => entry.gesture_id === "GX1"));
  assert(constellation.skipped_gestures.some((entry) => entry.gesture_id === "GX2"));
  assert(!result.analysis.graph.nodes.some((node) => ["GX1", "GX2"].includes(node.generated_by)));
  assert.equal(result.validation.conformant, true);
});

test("source-forced Geviert hypothesis mutates the operator ecology without promoting relation-first ontology", async (t) => {
  const root = await workspace(t);
  const syntheticRefinery = path.join(root, "refinery");
  await mkdir(syntheticRefinery);
  const report = await json(path.join(refinery, "REFINERY_REPORT.json"));
  const originalBank = await json(path.join(refinery, "hypothesis_bank.json"));
  const base = clone(originalBank.hypotheses[0]);
  const emergent = {
    ...base,
    hypothesis_id: "HYP-EMERGENT_SOURCE_GEVIERT",
    topic_id: "EMERGENT_SOURCE_GEVIERT",
    label: "Source-forced constellation: Geviert / Vierung / Ding / Nähe",
    research_question: "Which distinctions among Geviert, Vierung, Ding and Nähe become invisible when the current relation graph determines relata in advance?",
    origin: "SOURCE_FORCED_REGISTRY_RESISTANCE",
    matched_groups: ["SOURCE_RESISTANCE", "TERM_GEVIERT", "TERM_VIERUNG", "TERM_DING", "TERM_NAHE"],
    evidence_segment_ids: base.evidence_segment_ids.slice(0, 4),
    evidence_count: 4,
    selectors_truncated: false,
    emergent_terms: ["Geviert", "Vierung", "Ding", "Nähe", "Ferne", "Erde", "Himmel", "Göttliche", "Sterbliche"],
    source_resistance_trigger: "Curated registry failed to represent the source-central constellation.",
    revision_condition: "Retire only after rival unitizations recover the source distinctions without loss.",
  };
  const bank = {
    ...originalBank,
    bank_version: "DAE-HYPOTHESIS-BANK-1.1",
    hypotheses: [emergent],
    case_matrices: [],
    source_resistance: {
      status: "REGISTRY_BLIND_SPOT",
      central_terms: emergent.emergent_terms,
      covered_terms: [],
      uncovered_terms: emergent.emergent_terms,
      coverage_ratio: 0,
      explicit_stress_terms: emergent.emergent_terms,
      emergent_hypotheses: [emergent.hypothesis_id],
      principle: "SOURCE_CENTRALITY_CAN_FORCE_TOPIC_AND_OPERATOR_REVISION_BUT_CANNOT_BY_ITSELF_VALIDATE_A_PHILOSOPHICAL_CLAIM",
    },
  };
  await Promise.all([
    writeFile(path.join(syntheticRefinery, "REFINERY_REPORT.json"), `${JSON.stringify(report, null, 2)}\n`),
    writeFile(path.join(syntheticRefinery, "hypothesis_bank.json"), `${JSON.stringify(bank, null, 2)}\n`),
  ]);
  const result = await runLivingAnalysis(engine, syntheticRefinery, path.join(root, "run"), { seed: "geviert-source-resistance", maximumFamilies: 10 });
  assert.equal(result.validation.conformant, true, JSON.stringify(result.validation.issues, null, 2));
  assert(result.analysis.graph.nodes.some((node) => node.role === "SOURCE_RESISTANCE"));
  assert(result.analysis.graph.nodes.some((node) => node.role === "REPRESENTATION_FAILURE"));
  assert(result.analysis.graph.nodes.some((node) => node.role === "OPERATOR_DELTA" && node.generative_gains.includes("GG7_OPERATOR_EVOLUTION")));
  assert(result.analysis.method_mutations.length >= 1);
  assert(result.analysis.constellations[0].activated_families.includes("F-RELATION-GENESIS"));
  assert(result.analysis.constellations[0].activated_families.includes("F-REPRESENTATION-RESISTANCE"));
  assert(result.etymology.pass.cards.some((card) => card.concept_id === "GEVIERT"));
  const field = await readFile(result.files.field_note, "utf8");
  assert.match(field, /RELATA_FIRST/u);
  assert.match(field, /UNRESOLVED_ONTOLOGY/u);
});
