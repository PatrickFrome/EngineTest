import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { evaluateOperatorDelta } from "../../mutation/operator-mutation-engine.mjs";
import { evaluateGestureActivation, emitGestureProgram, validateDeclarativeGestures } from "../../src/generative-gesture-runtime.mjs";
const readJson = file => readFile(new URL(file, import.meta.url), "utf8").then(JSON.parse);
const [registry, policy, delta] = await Promise.all([
  readJson("../../config/living_operator_registry.json"), readJson("../../config/operator_mutation_policy.json"), readJson("../../fixtures/mutation/gx1-declarative-split.pass.json")
]);
test("0.9 baseline registry is executable declarative ecology including GX7", () => {
  assert.deepEqual(validateDeclarativeGestures(registry), []);
  assert(registry.generative_gestures.some(g => g.gesture_id === "GX7" && g.activation && g.emission_program));
});
test("source-bound GX1 split becomes a reversible executable candidate registry", async () => {
  const before = JSON.stringify(registry);
  const result = await evaluateOperatorDelta({ delta, registry, policy });
  assert.equal(result.receipt.runtime_reachability, "FULL", JSON.stringify(result.receipt.issues, null, 2));
  assert.equal(result.receipt.decision.decision, "ACCEPTED_CANDIDATE", JSON.stringify(result.receipt.issues, null, 2));
  assert.equal(JSON.stringify(registry), before);
  assert(!result.candidateRegistry.generative_gestures.some(g => g.gesture_id === "GX1"));
  assert(result.candidateRegistry.generative_gestures.some(g => g.gesture_id === "GX1A-EXCLUSION"));
  assert(result.candidateRegistry.generative_gestures.some(g => g.gesture_id === "GX1B-SUCCESS-COST"));
  assert.deepEqual(validateDeclarativeGestures(result.candidateRegistry), []);
});
test("GX7 declarative activation is source-forced", () => {
  const gx7 = registry.generative_gestures.find(g => g.gesture_id === "GX7");
  const base = { lens:{self_critique:"risk",mutation:"mut",operator_delta:"delta"}, families:[], resolution:"RESOLVED", questionNode:{node_id:"Q"}, derived:{source_resistance_text:"resist",operator_delta_text:"delta"} };
  assert.equal(evaluateGestureActivation(gx7,{...base,hypothesis:{origin:"EXPLICIT_PROJECT_THESIS_CANDIDATE"}}).active,false);
  assert.equal(evaluateGestureActivation(gx7,{...base,hypothesis:{origin:"SOURCE_FORCED_REGISTRY_RESISTANCE",source_resistance_trigger:"resist"}}).active,true);
});
