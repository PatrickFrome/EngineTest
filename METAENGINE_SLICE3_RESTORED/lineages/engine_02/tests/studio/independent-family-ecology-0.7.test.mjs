import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createEngine } from "../../src/engine.mjs";
import { profileInterrogativeTexts } from "../../studio/independent-family/family-signal-runtime.mjs";
import { runIndependentFamilyEcology } from "../../studio/independent-family/independent-family-ecology.mjs";
import { runEcologyDownstream } from "../../studio/independent-family/ecology-downstream.mjs";
import { runIndependentFamilyProbe } from "../../studio/independent-family/family-probe.mjs";

const HERE=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(HERE,"../..");
const EXP=path.join(ROOT,"experiments/independent-family-ecology-0.10");

test("Unicode lexical boundaries prevent call from firing inside locally", () => {
  const profile=profileInterrogativeTexts(["The operator is only locally useful and should remain provisional."]);
  assert.equal(profile.signal_counts.ADDRESS_RESPONSE,0);
  assert.equal(profile.processual_profile_hints.includes("RESPONSIVE_ENACTMENT"),false);
});

test("processual-hermeneutic family is independent of relation-genesis cues", () => {
  const temporal=profileInterrogativeTexts([
    "Expectation changes present conduct: waiting is enacted through repeated practice.",
    "Temporal orientation is lived through anticipation and enactment in the present.",
  ]);
  assert.equal(temporal.operator_family,"PROCESSUAL_HERMENEUTIC_PROFILE");
  assert.ok(temporal.profile_hints.includes("TEMPORAL_ENACTMENT"));
  assert.ok(temporal.profile_hints.includes("PRACTICE_MEDIATION"));
  assert.equal(temporal.profile_hints.includes("CO_CONSTITUTIVE_OR_RECIPROCAL"),false);

  const relation=profileInterrogativeTexts([
    "The gathering keeps the four mutually belonging while nearness preserves distance.",
    "Reciprocal gathering preserves distance among differentiated terms.",
  ]);
  assert.equal(relation.operator_family,"RELATION_GENESIS_PROFILE");
  assert.ok(relation.profile_hints.includes("CO_CONSTITUTIVE_OR_RECIPROCAL"));
  assert.ok(relation.profile_hints.includes("DIFFERENCE_PRESERVING_PROXIMITY"));
  assert.equal(relation.profile_hints.includes("TEMPORAL_ENACTMENT"),false);
});

test("independent-family ecology reproduces the supplied six-window regression oracle", async () => {
  const parent=await mkdtemp(path.join(tmpdir(),"destruktion-independent-family-"));
  const out=path.join(parent,"run");
  try {
    const engine=await createEngine();
    const manifest=path.join(EXP,"micro_local_ecology_manifest.json");
    const {result}=await runIndependentFamilyEcology(engine,manifest,out);
    assert.equal(result.outcome,"PASSES_MICRO_LOCAL_ECOLOGY_REGRESSION");
    assert.equal(result.summary.source_births_confirmed,4);
    assert.equal(result.summary.candidates,4);
    assert.equal(result.summary.expectations_passed,6);
    assert.equal(result.summary.expected_windows,6);
    assert.equal(result.synthesis.decision,"PRESERVE_POLYPHONIC_LOCALITY");

    const decisions=Object.fromEntries(result.windows.map((w)=>[w.heading,[w.decision,w.selected_candidates]]));
    assert.deepEqual(decisions["W1 — Temporal enactment"],["SELECT_LOCAL_WINNER",["TEMPORAL_ENACTMENT_SOURCE_BORN"]]);
    assert.deepEqual(decisions["W2 — Practice and material mediation"],["SELECT_LOCAL_WINNER",["PRACTICE_MEDIATION_SOURCE_BORN"]]);
    assert.deepEqual(decisions["W3 — Absence and trace"],["SELECT_LOCAL_WINNER",["ABSENCE_DISCLOSURE_SOURCE_BORN"]]);
    assert.deepEqual(decisions["W4 — Geviert-style relation control"],["SELECT_LOCAL_WINNER",["GEVIERT_CO_CONSTITUTIVE_GATHERING"]]);
    assert.deepEqual(decisions["W5 — Cross-family composition"],["LOCAL_COMPOSITION",["GEVIERT_CO_CONSTITUTIVE_GATHERING","TEMPORAL_ENACTMENT_SOURCE_BORN"]]);
    assert.deepEqual(decisions["W6 — Descriptive negative control"],["ABSTAIN_UNRESOLVED",[]]);

    assert.deepEqual(result.boundaries.map((b)=>b.boundary_type),[
      "OPERATOR_REGIME_SHIFT","OPERATOR_REGIME_SHIFT","OPERATOR_REGIME_SHIFT","PARTIAL_OPERATOR_OVERLAP","OPEN_BOUNDARY",
    ]);
  } finally {
    await rm(parent,{recursive:true,force:true});
  }
});

test("downstream adapter preserves boundaries and refuses a global thesis", async () => {
  const parent=await mkdtemp(path.join(tmpdir(),"destruktion-ecology-downstream-"));
  const run=path.join(parent,"run");
  const down=path.join(parent,"downstream");
  try {
    const engine=await createEngine();
    const manifest=path.join(EXP,"micro_local_ecology_manifest.json");
    const ecology=await runIndependentFamilyEcology(engine,manifest,run);
    const downstream=await runEcologyDownstream(ecology.files.result,down);
    const result=downstream.result;
    assert.equal(result.outcome,"PRESERVES_MICRO_LOCAL_ECOLOGY_DOWNSTREAM");
    assert.equal(result.summary.windows,6);
    assert.equal(result.summary.local_residual_nodes,1);
    assert.equal(result.summary.open_boundaries,1);
    assert.equal(result.summary.distinct_operator_families_observed,2);
    assert.equal(result.summary.global_thesis_allowed,false);
    assert.equal(result.expert_layer.global_adjudication.epistemic_status,"POLYPHONIC_GLOBAL_ABSTENTION");
    assert.equal(result.expert_layer.global_adjudication.thesis_allowed,false);
    assert.equal(result.living_graph.nodes.filter((n)=>n.node_type==="HERMENEUTIC_BOUNDARY").length,5);
  } finally {
    await rm(parent,{recursive:true,force:true});
  }
});

test("family probe stays non-promoting even when processual pressure is detected", async () => {
  const parent=await mkdtemp(path.join(tmpdir(),"destruktion-family-probe-"));
  const out=path.join(parent,"probe");
  try {
    const source=path.join(EXP,"origins/temporal_enactment_origin.docx");
    const {result}=await runIndependentFamilyProbe(source,out,{documentLanguage:"en"});
    assert.equal(result.family_candidate.candidate,"PROCESSUAL_HERMENEUTIC_FAMILY_CANDIDATE");
    assert.equal(result.family_candidate.status,"EXPERIMENTAL_PROBE_NOT_SOURCE_BIRTH");
    assert.equal(result.family_candidate.epistemic_firewall.source_birth_confirmed,false);
    assert.equal(result.family_candidate.epistemic_firewall.promotion_forbidden,true);
  } finally {
    await rm(parent,{recursive:true,force:true});
  }
});
