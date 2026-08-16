import test from "node:test";
import assert from "node:assert/strict";
import { detectSourceResistance } from "../src/source-resistance.mjs";
import { buildAutomaticExpertProfile } from "../src/expert-cycle.mjs";

function segment(id, layer, text, ordinal) {
  return {
    segment_id: id,
    ordinal,
    archive_state: "ACTIVE",
    layer_routing: { label: layer },
    _text: text,
  };
}

const segments = [
  segment("OX-P000001", "SOURCE", "Etymological stress terms: Geviert, Vierung, Ding, Nähe, Ferne, Erde, Himmel, Göttliche, Sterbliche, Welt, Ort, Raum, Wohnen", 1),
  segment("OX-P000002", "SOURCE", "Geviert and Vierung are named together; Erde, Himmel, Göttliche and Sterbliche are not introduced as four isolated objects.", 2),
  segment("OX-P000003", "SOURCE", "The Ding gathers: Nähe preserves Ferne while the Geviert is gathered.", 3),
  segment("OX-P000004", "SOURCE", "Ort and Raum are articulated through the Ding and Wohnen rather than through a neutral container alone.", 4),
  segment("OX-P000005", "RECONSTRUCTION", "Geviert may therefore require a rival unitization in which relation and relata are not fixed in advance.", 5),
  segment("OX-P000006", "PROJECT_CLAIM", "Наш проект предлагает проверить тезис: METHOD_MUTATION — pairwise node-edge graph Destruktion недостаточен там, где источник запрещает начинать с изолированных relata.", 6),
  segment("OX-P000007", "PROJECT_CLAIM", "Наш проект предлагает проверить тезис: UNIVERSAL_ONTOLOGY — Geviert является доказанной универсальной структурой реальности как таковой.", 7),
  segment("OX-P000008", "PROJECT_CLAIM", "Наш проект предлагает проверить тезис: CO_CONSTITUTIVE_HYPOTHESIS — более адекватной рабочей моделью является взаимная соопределённость четырёх без их слияния.", 8),
];

const legacyHypotheses = [{
  hypothesis_id: "HYP-TECH",
  topic_id: "TECHNOLOGY_AND_ORDERING",
  label: "Technology and ordering",
  research_question: "How does ordering become technical?",
  matched_groups: ["TECHNOLOGY"],
}];

test("source resistance can force an unregistered topic and preserve explicit project theses", () => {
  const result = detectSourceResistance(segments, legacyHypotheses);
  assert.equal(result.report.status, "REGISTRY_BLIND_SPOT");
  assert(result.report.central_terms.includes("Geviert"));
  assert(result.report.uncovered_terms.includes("Geviert"));
  assert(result.hypotheses.some((item) => item.origin === "SOURCE_FORCED_REGISTRY_RESISTANCE" && item.emergent_terms.includes("Geviert")));
  const mutation = result.hypotheses.find((item) => item.topic_id === "EMERGENT_CLAIM_METHOD_MUTATION");
  assert(mutation);
  assert.match(mutation.claim_statement, /pairwise node-edge graph/u);
});

test("automatic expert profile adjudicates the explicit claim rather than replacing it by a meta-thesis", () => {
  const resistance = detectSourceResistance(segments, legacyHypotheses);
  const bank = {
    hypotheses: resistance.hypotheses,
    case_matrices: [],
  };
  const manifest = {
    source: { source_id: "GEVIERT-REGRESSION" },
  };
  const sourceMap = { coverage: { resolved_claim_level_citations: 0 } };
  const profile = buildAutomaticExpertProfile(bank, manifest, sourceMap);

  const method = profile.theses.find((item) => item.topic_id === "EMERGENT_CLAIM_METHOD_MUTATION");
  assert.equal(method.statement, "pairwise node-edge graph Destruktion недостаточен там, где источник запрещает начинать с изолированных relata.");
  assert.equal(method.evaluation_mode, "META_METHOD");
  assert.equal(method.scale, "METHOD");

  const universal = profile.theses.find((item) => item.topic_id === "EMERGENT_CLAIM_UNIVERSAL_ONTOLOGY");
  assert.equal(universal.evaluation_mode, "UNIVERSALIZATION");
  assert.equal(universal.scale, "UNIVERSAL");
  assert(universal.minimum_resolved_sources >= 3);

  const bounded = profile.theses.find((item) => item.topic_id === "EMERGENT_CLAIM_CO_CONSTITUTIVE_HYPOTHESIS");
  assert.equal(bounded.evaluation_mode, "SOURCE_DEPENDENT");
  assert.equal(bounded.source_burden, "PRIMARY_TEXT");
  assert.equal(bounded.minimum_resolved_sources, 0);
});


test("multilingual source centrality finds Saussure-native differential terms without an explicit stress list", () => {
  const local = [
    segment("OX-P100001", "SOURCE", "La langue est un système de signes; la valeur dépend des différences entre les termes du système.", 101),
    segment("OX-P100002", "SOURCE", "Dans la langue il n’y a que des différences; les différences constituent les valeurs du système.", 102),
    segment("OX-P100003", "SOURCE", "La valeur d’un terme change lorsque le terme voisin change; le système articule les différences.", 103),
  ];
  const result = detectSourceResistance(local, legacyHypotheses);
  assert.equal(result.report.explicit_stress_terms.length, 0);
  assert(result.report.central_terms.includes("langue"));
  assert(result.report.central_terms.includes("système"));
  assert(result.report.central_terms.includes("valeur"));
  assert(result.report.central_terms.includes("différences"));
  assert.equal(result.report.operator_candidate.family, "RELATION_GENESIS_PROFILE");
  assert(result.report.operator_candidate.profile_hints.includes("DIFFERENTIAL_CONSTITUTION"));
});

test("relation-genesis profiling can preserve asymmetric dependence rather than forcing co-constitution", () => {
  const local = [
    segment("OX-P200001", "SOURCE", "Substance is in itself and conceived through itself; a mode is in another and conceived through another.", 201),
    segment("OX-P200002", "SOURCE", "Substance is prior to its modifications; modes depend on substance and are conceived through substance.", 202),
    segment("OX-P200003", "SOURCE", "A mode is an affection of substance; substance is primary and the mode is dependent on another.", 203),
  ];
  const result = detectSourceResistance(local, legacyHypotheses);
  assert(result.report.central_terms.some((term) => term.toLowerCase() === "substance"));
  assert(result.report.central_terms.some((term) => term.toLowerCase() === "mode"));
  assert.equal(result.report.operator_candidate.family, "RELATION_GENESIS_PROFILE");
  assert(result.report.operator_candidate.profile_hints.includes("ASYMMETRIC_DEPENDENCE"));
  assert(!result.report.operator_candidate.profile_hints.includes("CO_CONSTITUTIVE_OR_RECIPROCAL"));
});

test("a cogito-style negative control does not activate the relation-genesis operator merely because it is philosophically central", () => {
  const local = [
    segment("OX-P300001", "SOURCE", "I am, I exist is necessarily true whenever I think it.", 301),
    segment("OX-P300002", "SOURCE", "I am a thinking thing: doubting, understanding, affirming, denying, willing, imagining and sensing.", 302),
    segment("OX-P300003", "SOURCE", "Thought belongs to me and cannot be separated from me in this meditation.", 303),
  ];
  const result = detectSourceResistance(local, legacyHypotheses);
  assert.notEqual(result.report.operator_candidate.candidate, "RELATION_GENESIS_PROFILE_WITH_CO_EMERGENT_RELATA_CANDIDATE");
  assert.equal(result.report.operator_candidate.family, "GENERIC_SOURCE_FORCED_REVISION");
});
