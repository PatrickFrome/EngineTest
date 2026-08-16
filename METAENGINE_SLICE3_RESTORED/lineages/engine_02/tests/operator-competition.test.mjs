import test from "node:test";
import assert from "node:assert/strict";
import { decideCompetitionTarget, evaluateCandidateOnTarget } from "../src/operator-competition.mjs";

const birth = { source_birth_confirmed: true };

function candidate(id, required, optional = [], incompatible = []) {
  return {
    candidate_id: id,
    label: id,
    origin_corpus_id: `ORIGIN_${id}`,
    source_operator: "RELATION_GENESIS_PROFILE_WITH_CO_EMERGENT_RELATA_CANDIDATE",
    required_profile_hints: required,
    optional_profile_hints: optional,
    incompatible_profile_hints: incompatible,
  };
}

test("candidate scoring rewards local distinction gain and penalizes missing required hints", () => {
  const good = evaluateCandidateOnTarget(candidate("A", ["ASYMMETRIC_DEPENDENCE"]), ["ASYMMETRIC_DEPENDENCE"], birth);
  const bad = evaluateCandidateOnTarget(candidate("B", ["CO_CONSTITUTIVE_OR_RECIPROCAL"]), ["ASYMMETRIC_DEPENDENCE"], birth);
  assert.equal(good.viable, true);
  assert.equal(good.score, 4);
  assert.equal(bad.viable, false);
  assert.ok(bad.score < 0);
});

test("competition selects one local winner when it covers the target profile", () => {
  const hints = ["CO_CONSTITUTIVE_OR_RECIPROCAL", "DIFFERENCE_PRESERVING_PROXIMITY"];
  const evaluations = [
    evaluateCandidateOnTarget(candidate("GEVIERT", ["CO_CONSTITUTIVE_OR_RECIPROCAL"], ["DIFFERENCE_PRESERVING_PROXIMITY"]), hints, birth),
    evaluateCandidateOnTarget(candidate("ASYM", ["ASYMMETRIC_DEPENDENCE"]), hints, birth),
  ];
  const decision = decideCompetitionTarget(hints, evaluations, { dominance_margin: 2, composition_gain_threshold: 1 });
  assert.equal(decision.decision, "SELECT_LOCAL_WINNER");
  assert.deepEqual(decision.selected_candidates, ["GEVIERT"]);
  assert.deepEqual(decision.residual_hints, []);
});

test("competition composes locally when two source-born candidates add non-redundant distinctions", () => {
  const hints = ["ASYMMETRIC_DEPENDENCE", "LOCAL_MODE_VARIATION"];
  const evaluations = [
    evaluateCandidateOnTarget(candidate("ASYM", ["ASYMMETRIC_DEPENDENCE"]), hints, birth),
    evaluateCandidateOnTarget(candidate("LOCAL", ["LOCAL_MODE_VARIATION"]), hints, birth),
    evaluateCandidateOnTarget(candidate("DIFF", ["DIFFERENTIAL_CONSTITUTION"]), hints, birth),
  ];
  const decision = decideCompetitionTarget(hints, evaluations, { dominance_margin: 2, composition_gain_threshold: 1 });
  assert.equal(decision.decision, "LOCAL_COMPOSITION");
  assert.deepEqual(new Set(decision.selected_candidates), new Set(["ASYM", "LOCAL"]));
  assert.deepEqual(decision.residual_hints, []);
});

test("competition abstains when source resistance yields no operator profile", () => {
  const evaluations = [evaluateCandidateOnTarget(candidate("A", ["ASYMMETRIC_DEPENDENCE"]), [], birth)];
  const decision = decideCompetitionTarget([], evaluations, {});
  assert.equal(decision.decision, "ABSTAIN_UNRESOLVED");
  assert.deepEqual(decision.selected_candidates, []);
});

test("unconfirmed source birth prevents candidate routing even when target hints match", () => {
  const c = candidate("A", ["ASYMMETRIC_DEPENDENCE"]);
  const evaluation = evaluateCandidateOnTarget(c, ["ASYMMETRIC_DEPENDENCE"], { source_birth_confirmed: false });
  assert.equal(evaluation.viable, false);
  const decision = decideCompetitionTarget(["ASYMMETRIC_DEPENDENCE"], [evaluation], {});
  assert.equal(decision.decision, "ABSTAIN_UNRESOLVED");
});
