import test from "node:test";
import assert from "node:assert/strict";
import { decideOperatorRegressionOutcome } from "../src/operator-regression.mjs";

const entries = [
  { corpus_id: "ORIGIN", control_role: "ORIGIN_POSITIVE" },
  { corpus_id: "TRANSFER", control_role: "TRANSFER_POSITIVE" },
  { corpus_id: "MIXED", control_role: "MIXED_CONTROL" },
  { corpus_id: "NEGATIVE", control_role: "NEGATIVE_CONTROL" },
];

function result(corpus_id, expectation_pass = true, candidate_mutation_found = false) {
  return { corpus_id, expectation_pass, candidate_mutation_found };
}

test("cross-corpus regression retains a transferable candidate only when origin, transfer and controls all pass", () => {
  const decision = decideOperatorRegressionOutcome(entries, [
    result("ORIGIN"),
    result("TRANSFER"),
    result("MIXED"),
    result("NEGATIVE"),
  ]);
  assert.equal(decision.outcome, "SURVIVES_CROSS_CORPUS_REGRESSION");
  assert.equal(decision.operator_state, "EXPERIMENTAL_TRANSFERABLE");
  assert.equal(decision.recommended_action, "RETAIN_EXPERIMENTAL_FOR_FURTHER_REGRESSION");
});

test("negative-control activation quarantines an overgeneralizing operator", () => {
  const decision = decideOperatorRegressionOutcome(entries, [
    result("ORIGIN"),
    result("TRANSFER"),
    result("MIXED"),
    result("NEGATIVE", false, true),
  ]);
  assert.equal(decision.outcome, "QUARANTINE_OVERGENERALIZATION");
  assert.equal(decision.operator_state, "QUARANTINED");
  assert.equal(decision.recommended_action, "QUARANTINE_FROM_DEFAULT_ROUTING");
});

test("a candidate with no positive transfer is explicitly retired rather than accumulated", () => {
  const decision = decideOperatorRegressionOutcome(entries, [
    result("ORIGIN"),
    result("TRANSFER", false),
    result("MIXED"),
    result("NEGATIVE"),
  ]);
  assert.equal(decision.outcome, "RETIRE_NO_TRANSFER");
  assert.equal(decision.operator_state, "RETIRED");
  assert.equal(decision.recommended_action, "RETIRE_CANDIDATE");
});
