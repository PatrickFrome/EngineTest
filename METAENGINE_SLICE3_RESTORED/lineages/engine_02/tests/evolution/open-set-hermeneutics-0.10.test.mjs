import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { detectSourceResistance } from "../../src/source-resistance.mjs";
import { evaluateMicroLocalEcology } from "../../src/micro-local-ecology.mjs";
import { evaluateOperatorDelta } from "../../mutation/operator-mutation-engine.mjs";

const readJson = file => readFile(new URL(file, import.meta.url), "utf8").then(JSON.parse);
const [registry, policy, delta] = await Promise.all([
  readJson("../../config/living_operator_registry.json"),
  readJson("../../config/operator_mutation_policy.json"),
  readJson("../../fixtures/mutation/open-set-add-family.pass.json"),
]);

function segment(id, text, ordinal) {
  return { segment_id: id, ordinal, archive_state: "ACTIVE", layer_routing: { label: "SOURCE" }, _text: text };
}

const source = [
  segment("OX-P000001", "Geviert and Vierung gather Erde, Himmel, Göttliche and Sterbliche without reducing them to four isolated objects.", 1),
  segment("OX-P000002", "The Ding gathers Geviert; Nähe is not simple abolition of Ferne, and Wohnen remains bound to Ort.", 2),
  segment("OX-P000003", "Geviert returns with Ding and Wohnen; Nähe and Ferne remain locally articulated rather than globally resolved.", 3),
  segment("OX-P000004", "Ort and Raum shift the local field while Ding and Wohnen recur; Geviert remains source-central.", 4),
];
const legacy = [{ topic_id: "TECHNOLOGY", label: "Technology", research_question: "How is ordering technical?", matched_groups: ["TECHNOLOGY"] }];

test("0.10 emits an UNKNOWN_OPERATOR_FAMILY alongside known profiling instead of collapsing source resistance into it", () => {
  const result = detectSourceResistance(source, legacy);
  assert.equal(result.report.status, "REGISTRY_BLIND_SPOT");
  assert.equal(result.report.open_set_status, "OPEN_SET_RIVAL_REQUIRED");
  assert.equal(result.report.open_set_candidate.family, "UNKNOWN_OPERATOR_FAMILY");
  assert.match(result.report.open_set_candidate.candidate, /^F-OPEN-/u);
  assert(result.report.micro_local_windows.length >= 2);
  const forced = result.hypotheses.find(item => item.origin === "SOURCE_FORCED_REGISTRY_RESISTANCE");
  assert.equal(forced.open_set_candidate.family, "UNKNOWN_OPERATOR_FAMILY");
  assert(forced.micro_local_window_ids.length >= 2);
});

test("micro-local ecology keeps known and open-set routes as rivals per argument window", () => {
  const resistance = detectSourceResistance(source, legacy);
  const bank = { source_id: "CONTROLLED-OPENSET-GEVIERT", source_resistance: resistance.report };
  const ecology = evaluateMicroLocalEcology(bank);
  assert.equal(ecology.outcome, "MICRO_LOCAL_ROUTING_AVAILABLE");
  assert(ecology.counts.windows >= 2);
  assert(ecology.routes.some(route => ["KEEP_KNOWN_AND_OPEN_SET_RIVALS", "OPEN_SET_LOCAL_CANDIDATE"].includes(route.decision)));
  assert(ecology.routes.every(route => route.segment_ids.length >= 1));
});

test("ADD_OPERATOR births an executable conditional family without mutating the baseline registry", async () => {
  const baseline = JSON.stringify(registry);
  const result = await evaluateOperatorDelta({ delta, registry, policy });
  assert.equal(result.receipt.runtime_reachability, "FULL", JSON.stringify(result.receipt.issues, null, 2));
  assert.equal(result.receipt.decision.decision, "ACCEPTED_CANDIDATE", JSON.stringify(result.receipt.issues, null, 2));
  assert.equal(JSON.stringify(registry), baseline);
  const added = result.candidateRegistry.conditional_families.find(item => item.family_id === "F-OPEN-SILENCE-WITHDRAWAL-001");
  assert(added);
  assert.equal(result.receipt.executable_probe.before.active, false);
  assert.equal(result.receipt.executable_probe.after[0].active, true);
});
