import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { countIssues, issue, sortIssues } from "./issues.mjs";
import { buildEtymologyPass } from "./etymology.mjs";
import { projectPath, readJson } from "./paths.mjs";
import { evaluateGestureActivation, emitGestureProgram, validateDeclarativeGestures } from "./generative-gesture-runtime.mjs";

const ANALYSIS_VERSION = "DAE-LIVING-ANALYSIS-1.3";
const LAYER_ID = "D3-EXPLORATORY-0.2";
const CLAIM_CEILING = "GENERATIVE_RECONSTRUCTION_WITH_TRACEABLE_SOURCE_POINTERS_NOT_TRUTH_OR_EXTERNAL_VALIDATION";

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function slug(value, fallback = "NODE") {
  const normalized = String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/gu, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/gu, "_")
    .replace(/^_+|_+$/gu, "")
    .slice(0, 72);
  return normalized || fallback;
}

function stableScore(seed, ...parts) {
  return Number.parseInt(sha256([seed, ...parts].join("\u241f")).slice(0, 12), 16) / 0xffffffffffff;
}

function stableId(prefix, ...parts) {
  return `${prefix}-${parts.map((part) => slug(part)).join("-")}`;
}

function normalizeText(value) {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase("und");
}

function triggerMatches(haystack, trigger) {
  const needle = normalizeText(trigger).trim();
  if (!needle) return false;
  if (/\s|-/u.test(needle)) return haystack.includes(needle);
  const tokens = haystack.match(/[\p{L}\p{N}]+/gu) ?? [];
  if (tokens.includes(needle)) return true;
  const nonAsciiStem = /[^\x00-\x7F]/u.test(needle) && [...needle].length >= 5;
  return nonAsciiStem && tokens.some((token) => token.startsWith(needle));
}

function sourceResolution(report) {
  if (report?.gates?.source_resolution === "PASS") return "RESOLVED";
  if (report?.gates?.source_resolution === "REVIEW") return "PARTIAL";
  return "UNRESOLVED";
}

function scopeForTopic(topicId) {
  if (topicId === "META_CRITIQUE" || topicId.startsWith("EMERGENT_SOURCE_")) return "METHOD";
  if (topicId.startsWith("EMERGENT_CLAIM_")) return "WORK";
  if (["DIACHRONIC_HEIDEGGER", "TERM_GENEALOGY"].includes(topicId)) return "DIACHRONIC";
  if (topicId === "ACT_CONTENT_OBJECT") return "WORK";
  return "REGIONAL";
}

function sourceBasis(hypothesis, resolution) {
  const selectors = (hypothesis.evidence_segment_ids ?? []).slice(0, 8);
  const count = hypothesis.evidence_count ?? hypothesis.evidence_segment_ids?.length ?? 0;
  return {
    hypothesis_id: hypothesis.hypothesis_id,
    selector_count: count,
    selectors,
    selectors_truncated: Boolean(hypothesis.selectors_truncated || count > selectors.length),
    source_resolution: resolution,
  };
}

function epistemicRegisters(role) {
  const map = {
    QUESTION: ["STRUCTURAL_SIGNAL", "OPEN_QUESTION"],
    PROBLEM_GENESIS: ["IMMANENT_INFERENCE", "RECONSTRUCTIVE_PROPOSAL"],
    LEXICAL_GENEALOGY: ["TEXTUAL_POINTER", "HISTORICAL_LEAD"],
    CONCEPTUAL_GENEALOGY: ["HISTORICAL_LEAD", "RECONSTRUCTIVE_PROPOSAL"],
    PROBLEM_GENEALOGY: ["HISTORICAL_LEAD", "RECONSTRUCTIVE_PROPOSAL"],
    COUNTER_GENEALOGY: ["HISTORICAL_LEAD", "RECONSTRUCTIVE_PROPOSAL"],
    COUNTERGENETIC_FORK: ["RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
    DECONFLATION: ["IMMANENT_INFERENCE", "RECONSTRUCTIVE_PROPOSAL"],
    SPECIALIZED_PROBE: ["RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
    RESIDUAL_CANDIDATE: ["PHENOMENOLOGICAL_HYPOTHESIS", "OPEN_QUESTION"],
    REVERSE_TEST: ["IMMANENT_INFERENCE", "OPEN_QUESTION"],
    RIVAL_RECONSTRUCTION: ["RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
    POLYPHONIC_FIELD: ["RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
    POSITIVE_KERNEL: ["PHENOMENOLOGICAL_HYPOTHESIS", "RECONSTRUCTIVE_PROPOSAL"],
    FORMAL_INDICATION: ["RECONSTRUCTIVE_PROPOSAL"],
    SURPRISE: ["RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
    EXPLANATORY_BALANCE: ["IMMANENT_INFERENCE", "RECONSTRUCTIVE_PROPOSAL"],
    SELF_CRITIQUE: ["IMMANENT_INFERENCE", "OPEN_QUESTION"],
    MUTATION: ["RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
    DESTROYED: ["IMMANENT_INFERENCE"],
    PRESERVED: ["PHENOMENOLOGICAL_HYPOTHESIS", "RECONSTRUCTIVE_PROPOSAL"],
    OPEN_RESIDUAL: ["OPEN_QUESTION"],
    RESEARCH_BRANCH: ["RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
    REVISION_TRIGGER: ["OPEN_QUESTION"],
    SOURCE_RESISTANCE: ["STRUCTURAL_SIGNAL", "TEXTUAL_POINTER", "OPEN_QUESTION"],
    REPRESENTATION_FAILURE: ["IMMANENT_INFERENCE", "RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
    OPERATOR_DELTA: ["RECONSTRUCTIVE_PROPOSAL", "OPEN_QUESTION"],
  };
  return map[role] ?? ["RECONSTRUCTIVE_PROPOSAL"];
}

function generativeMetadata(role) {
  const map = {
    QUESTION: ["G0", []],
    PROBLEM_GENESIS: ["G2", ["GG2_NEW_QUESTION"]],
    LEXICAL_GENEALOGY: ["G1", ["GG1_NEW_DISTINCTION"]],
    CONCEPTUAL_GENEALOGY: ["G1", ["GG1_NEW_DISTINCTION"]],
    PROBLEM_GENEALOGY: ["G2", ["GG2_NEW_QUESTION"]],
    COUNTER_GENEALOGY: ["G2", ["GG2_NEW_QUESTION", "GG3_NEW_RIVAL"]],
    COUNTERGENETIC_FORK: ["G2", ["GG2_NEW_QUESTION", "GG3_NEW_RIVAL"]],
    DECONFLATION: ["G1", ["GG1_NEW_DISTINCTION"]],
    SPECIALIZED_PROBE: ["G1", ["GG1_NEW_DISTINCTION"]],
    RESIDUAL_CANDIDATE: ["G2", ["GG5_NEW_PHENOMENON"]],
    REVERSE_TEST: ["G3", ["GG4_REVERSAL"]],
    RIVAL_RECONSTRUCTION: ["G2", ["GG3_NEW_RIVAL"]],
    POLYPHONIC_FIELD: ["G3", ["GG3_NEW_RIVAL", "GG5_NEW_PHENOMENON"]],
    POSITIVE_KERNEL: ["G3", ["GG1_NEW_DISTINCTION"]],
    FORMAL_INDICATION: ["G3", ["GG1_NEW_DISTINCTION"]],
    SURPRISE: ["G3", ["GG1_NEW_DISTINCTION", "GG2_NEW_QUESTION", "GG5_NEW_PHENOMENON"]],
    EXPLANATORY_BALANCE: ["G1", ["GG1_NEW_DISTINCTION"]],
    SELF_CRITIQUE: ["G2", ["GG5_NEW_PHENOMENON"]],
    MUTATION: ["G3", ["GG4_REVERSAL", "GG1_NEW_DISTINCTION"]],
    DESTROYED: ["G1", ["GG1_NEW_DISTINCTION"]],
    PRESERVED: ["G1", ["GG1_NEW_DISTINCTION"]],
    OPEN_RESIDUAL: ["G2", ["GG5_NEW_PHENOMENON"]],
    RESEARCH_BRANCH: ["G4", ["GG2_NEW_QUESTION", "GG6_BRANCH_PRODUCTIVITY"]],
    REVISION_TRIGGER: ["G4", ["GG6_BRANCH_PRODUCTIVITY"]],
    SOURCE_RESISTANCE: ["G3", ["GG5_NEW_PHENOMENON", "GG7_OPERATOR_EVOLUTION"]],
    REPRESENTATION_FAILURE: ["G3", ["GG1_NEW_DISTINCTION", "GG7_OPERATOR_EVOLUTION"]],
    OPERATOR_DELTA: ["G4", ["GG4_REVERSAL", "GG7_OPERATOR_EVOLUTION"]],
  };
  const [generativeRegister, generativeGains] = map[role] ?? ["G1", []];
  return { generative_register: generativeRegister, generative_gains: generativeGains };
}

const GESTURE_REFS = {
  GX1: ["2.0 §8.3", "2.17.M", "D3-EXPLORATORY §3"],
  GX2: ["2.0 §§5.2–5.6", "D3-EXPLORATORY §4"],
  GX3: ["2.0 §7.1", "D3-EXPLORATORY §5"],
  GX4: ["2.0 §7.2", "2.6", "D3-EXPLORATORY §6"],
  GX5: ["2.0 §§7.3–7.5", "2.0 §13", "D3-EXPLORATORY §§7–8"],
  GX6: ["2.0 §§8.3, 15, 18", "D3-EXPLORATORY §§9–11"],
  GX7: ["SOURCE-RESISTANCE / OPERATOR-MUTATION 0.1", "D3-EXPLORATORY-0.2"],
};

const PREFERRED_FAMILIES = {
  REALITY_AND_REALISM: ["F-REALITY-PROFILES", "F-UNDERDETERMINATION", "F-BEING-ROLES"],
  ACT_CONTENT_OBJECT: ["F-GIVENNESS-REFLECTION", "F-CONSTITUTION", "F-VERIFICATION"],
  REGIONAL_REALIZATION_PROFILE: ["F-REALITY-PROFILES", "F-INDIVIDUATION", "F-ENABLEMENT", "F-UNDERDETERMINATION"],
  DIACHRONIC_HEIDEGGER: ["F-EPOCH-HISTORY", "F-LANGUAGE-TRANSLATION", "F-LATE-OPERATORS", "F-HISTORICITY", "F-MEDIATION-COMPRESSION"],
  TERM_GENEALOGY: ["F-LANGUAGE-TRANSLATION", "F-REALITY-PROFILES", "F-BEING-ROLES", "F-MEDIATION-COMPRESSION"],
  META_CRITIQUE: ["F-UNDERDETERMINATION", "F-VERIFICATION", "F-MEDIATION-COMPRESSION"],
  TECHNOLOGY_AND_ORDERING: ["F-TECHNOLOGY", "F-CYBERNETICS", "F-TECHNICAL-LANGUAGE", "F-UNDERDETERMINATION"],
  IDENTITY_AND_INDIVIDUATION: ["F-IDENTITY", "F-INDIVIDUATION", "F-BOUNDARY", "F-RELATION-COUPLING", "F-CONSTITUTION", "F-ENABLEMENT"],
  MEDIATION_COMPRESSION: ["F-MEDIATION-COMPRESSION", "F-VERIFICATION", "F-UNDERDETERMINATION", "F-RELATION-COUPLING"],
};

function selectFamilies(registry, hypothesis, seed, maximum) {
  const preferred = PREFERRED_FAMILIES[hypothesis.topic_id] ?? [];
  const haystack = normalizeText([
    hypothesis.topic_id,
    hypothesis.label,
    hypothesis.research_question,
    ...(hypothesis.matched_groups ?? []),
    ...(hypothesis.emergent_terms ?? []),
    hypothesis.source_resistance_trigger ?? "",
  ].join(" "));
  const scored = registry.conditional_families.map((family) => {
    const matches = family.triggers.filter((trigger) => triggerMatches(haystack, trigger));
    return {
      family,
      score: matches.length + (preferred.includes(family.family_id) ? 4 : 0),
    };
  }).sort((left, right) => right.score - left.score || left.family.family_id.localeCompare(right.family.family_id));
  const selected = scored.filter((item) => item.score > 0).slice(0, maximum).map((item) => item.family);
  const byId = new Map(registry.conditional_families.map((family) => [family.family_id, family]));
  for (const familyId of preferred) {
    if (selected.length >= maximum) break;
    const family = byId.get(familyId);
    if (family && !selected.some((item) => item.family_id === familyId)) selected.push(family);
  }
  for (const fallbackId of ["F-UNDERDETERMINATION", "F-VERIFICATION"]) {
    if (selected.length >= 2) break;
    const family = byId.get(fallbackId);
    if (family && !selected.some((item) => item.family_id === fallbackId)) selected.push(family);
  }
  return selected.slice(0, maximum);
}

function declarativeContext(hypothesis, lens, families, resolution, questionNode = null) {
  const counter = String(lens?.counter_genealogy ?? "");
  const indication = lens?.formal_indication ?? {};
  const residualKind = residualKindFor(hypothesis, resolution);
  const terms = (hypothesis.emergent_terms ?? []).slice(0, 12);
  return { hypothesis, lens, families, resolution, questionNode, derived: {
    counter_genealogy_lcfirst: counter ? `${counter.charAt(0).toLocaleLowerCase("und")}${counter.slice(1)}` : "",
    family_positive_models_top3: families.slice(0, 3).map((family) => family.positive_model).join(" / "),
    formal_indication_text: formalIndication(indication),
    residual_kind: residualKind,
    resolution_qualification: resolution === "UNRESOLVED" && ["DIACHRONIC_HEIDEGGER", "TERM_GENEALOGY"].includes(hypothesis.topic_id) ? " Source resolution remains unresolved, so the historical remainder is also typed R3-U." : "",
    source_resistance_text: `${hypothesis.source_resistance_trigger ?? "The source is not adequately represented by the current registry."} Central terms under pressure: ${terms.join(", ") || hypothesis.label}.`,
    operator_delta_text: `${lens.operator_delta ?? "SOURCE_FORCED_OPERATOR_CANDIDATE"}. ${lens.mutation} This delta is not CORE promotion and must survive rollback, regression and competition.`,
    open_set_operator_delta_text: `${hypothesis.open_set_candidate?.candidate ?? "UNKNOWN_OPERATOR_FAMILY"}. Open-set rival derived from micro-local source signatures; it must not be translated back into the known profile vocabulary before its own before/after test. ${hypothesis.open_set_candidate?.claim_ceiling ?? "OPEN_SET_OPERATOR_CANDIDATE_NOT_DISCOVERED_ONTOLOGY_OR_CORE_PROMOTION"}.`
  }};
}

function gestureActivation(gesture, hypothesis, lens, families, resolution) {
  if (gesture?.activation) return evaluateGestureActivation(gesture, declarativeContext(hypothesis, lens, families, resolution));
  const familyIds = new Set(families.map((family) => family.family_id));
  const evidenceCount = hypothesis.evidence_count ?? 0;
  if (gesture.gesture_id === "GX1") {
    const active = evidenceCount >= 10 && Boolean(lens.positive_kernel && lens.self_critique);
    return { active, reason: active ? `The topic recurs in ${evidenceCount} selector candidates and has an identifiable success/blindness tension.` : "No broad successful explanatory field with a determinate residual is yet visible." };
  }
  if (gesture.gesture_id === "GX2") {
    const sensitive = ["F-LANGUAGE-TRANSLATION", "F-EPOCH-HISTORY", "F-BEING-ROLES", "F-HISTORICITY"].some((id) => familyIds.has(id));
    const active = sensitive || (hypothesis.matched_groups ?? []).length >= 2;
    return { active, reason: active ? "The question depends on several lexical/conceptual poles or a contestable historical inheritance." : "No countergenetic trigger beyond the current problem formulation is established." };
  }
  if (gesture.gesture_id === "GX3") {
    const active = Boolean(lens.destroyed && lens.preserved);
    return { active, reason: active ? "The lens already weakens an inherited necessity while retaining a phenomenon that can answer back." : "No determinate downgrade is available for a reverse arrow." };
  }
  if (gesture.gesture_id === "GX4") {
    const active = Array.isArray(lens.rivals) && lens.rivals.length >= 2;
    return { active, reason: active ? `${lens.rivals.length} admissible reconstructions are available; premature selection would erase contrastive gain.` : "Fewer than two admissible rivals are available." };
  }
  if (gesture.gesture_id === "GX5") {
    const indication = lens.formal_indication ?? {};
    const active = Boolean(lens.positive_kernel && indication.direction && indication.enactment && indication.limit);
    return { active, reason: active ? "A constructive gain can be expressed as direction, negation, enactment test and limit without theory promotion." : "No sufficiently articulated positive appropriation is available." };
  }
  if (gesture.gesture_id === "GX6") {
    const active = Boolean(lens.open && lens.revision_trigger);
    const qualification = resolution === "UNRESOLVED" && ["DIACHRONIC_HEIDEGGER", "TERM_GENEALOGY"].includes(hypothesis.topic_id)
      ? " Source resolution remains unresolved, so the historical remainder is also typed R3-U."
      : "";
    return { active, reason: active ? `The remainder specifies a discriminating reopening condition and can become a research branch.${qualification}` : "The remainder is not yet determinate enough to create a branch." };
  }
  if (gesture.gesture_id === "GX7") {
    const active = hypothesis.origin === "SOURCE_FORCED_REGISTRY_RESISTANCE";
    return { active, reason: active
      ? (hypothesis.source_resistance_trigger ?? "Source-central evidence remains outside the curated topic ontology and therefore forces a representation audit.")
      : "GX7 is source-forced rather than thesis-forced: an explicit project claim may demand adjudication, but it cannot by itself license mutation of the method." };
  }
  return { active: false, reason: "Unknown gesture." };
}

function nodeFactory(context, role, key, title, proposition, generatedBy, parentIds = [], residualKind = null) {
  return {
    node_id: stableId("N", context.hypothesis.topic_id, generatedBy, key),
    constellation_id: context.constellationId,
    role,
    title,
    proposition,
    philosophical_function: context.functionText,
    generated_by: generatedBy,
    protocol_refs: generatedBy.startsWith("GX") ? (GESTURE_REFS[generatedBy] ?? context.protocolRefs ?? []) : context.protocolRefs,
    parent_ids: [...new Set(parentIds)].sort(),
    source_basis: context.sourceBasis,
    epistemic_registers: epistemicRegisters(role),
    ...generativeMetadata(role),
    residual_kind: residualKind,
    scope: scopeForTopic(context.hypothesis.topic_id),
    revisable_by: [context.hypothesis.revision_condition, context.lens.revision_trigger].filter(Boolean),
    evidence_ceiling: role === "QUESTION"
      ? "LEXICAL_TOPIC_CLUSTER_NOT_VALIDATED_HYPOTHESIS"
      : "EXPLORATORY_CANDIDATE_REQUIRING_ANALYTIC_AND_SOURCE_VALIDATION",
  };
}

function formalIndication(indication) {
  return [
    `${indication.name}.`,
    `Richtung: ${indication.direction}`,
    `Negationsfunktion: ${indication.negation}`,
    `Vollzugsprüfung: ${indication.enactment}`,
    `Grenze: ${indication.limit}`,
  ].join(" ");
}

function residualKindFor(hypothesis, resolution) {
  if (resolution === "UNRESOLVED" && ["DIACHRONIC_HEIDEGGER", "TERM_GENEALOGY"].includes(hypothesis.topic_id)) return "R3-U";
  if (/whether|ли\s|или/u.test(normalizeText(hypothesis.research_question))) return "R3-A";
  return "R3-R";
}

function nodesForGesture(gesture, context) {
  const { lens, hypothesis, families, questionNode, seed, resolution } = context;
  if (Array.isArray(gesture?.emission_program)) {
    const runtimeContext = declarativeContext(hypothesis, lens, families, resolution, questionNode);
    return emitGestureProgram(gesture, runtimeContext, ({ role, key, title, proposition, parents, residualKind }) => nodeFactory({
      ...context, functionText: gesture.question, protocolRefs: gesture.protocol_refs ?? GESTURE_REFS[gesture.gesture_id] ?? [],
    }, role, key, title, proposition, gesture.gesture_id, parents, residualKind));
  }
  const q = questionNode.node_id;
  const make = (role, key, title, proposition, parents = [q], residualKind = null) => nodeFactory({
    ...context,
    functionText: gesture.question,
    protocolRefs: GESTURE_REFS[gesture.gesture_id],
  }, role, key, title, proposition, gesture.gesture_id, parents, residualKind);

  if (gesture.gesture_id === "GX1") {
    const residual = make(
      "RESIDUAL_CANDIDATE",
      "SUCCESS_BLINDNESS",
      "Residual produced by explanatory success",
      `The success of “${lens.positive_kernel}” may exclude this phenomenon from view: ${lens.self_critique}`,
      [q],
      "R3-R",
    );
    const critique = make("SELF_CRITIQUE", "SUCCESS_SELF_CRITIQUE", "Self-critique from the residual", lens.self_critique, [residual.node_id], "R3-R");
    return [residual, critique];
  }

  if (gesture.gesture_id === "GX2") {
    const problem = make("PROBLEM_GENESIS", "PROBLEM_GENESIS", "How the initial question was produced", lens.problem_genesis);
    const genealogies = [
      ["LEXICAL_GENEALOGY", "LEXICAL", "Lexical line", lens.genealogies.lexical],
      ["CONCEPTUAL_GENEALOGY", "CONCEPTUAL", "Conceptual line", lens.genealogies.conceptual],
      ["PROBLEM_GENEALOGY", "PROBLEM", "Problem-scene line", lens.genealogies.problem],
    ].sort((left, right) => stableScore(seed, hypothesis.topic_id, right[1]) - stableScore(seed, hypothesis.topic_id, left[1]));
    const genealogyNodes = genealogies.map(([role, key, title, proposition]) => make(role, key, title, proposition, [problem.node_id]));
    const counter = make("COUNTER_GENEALOGY", "COUNTER", "Counter-genealogy", lens.counter_genealogy, genealogyNodes.map((node) => node.node_id));
    const fork = make(
      "COUNTERGENETIC_FORK",
      "RIVAL_QUESTION",
      "Rival question rather than rival answer",
      `If ${lens.counter_genealogy.charAt(0).toLocaleLowerCase("und")}${lens.counter_genealogy.slice(1)}, the initial question “${hypothesis.research_question}” must be reformulated before it is answered.`,
      [counter.node_id],
    );
    const deconflation = make("DECONFLATION", "DIFFERENCE", "Difference created by the fork", lens.deconflation, [problem.node_id, fork.node_id]);
    return [problem, ...genealogyNodes, counter, fork, deconflation];
  }

  if (gesture.gesture_id === "GX3") {
    const reverse = make("REVERSE_TEST", "REVERSE", "The dismantled position answers back", `The inherited position still sees something the new reconstruction could lose: ${lens.preserved}`);
    const destroyed = make("DESTROYED", "R1", "R1 — dismantled necessity", lens.destroyed, [reverse.node_id]);
    const mutation = make("MUTATION", "REVERSED_KERNEL", "Reconstruction after the reverse arrow", lens.mutation, [reverse.node_id]);
    return [reverse, destroyed, mutation];
  }

  if (gesture.gesture_id === "GX4") {
    const rivals = lens.rivals.map((rival, index) => make("RIVAL_RECONSTRUCTION", `RIVAL_${index + 1}`, `Live reconstruction ${index + 1}`, rival));
    const field = make(
      "POLYPHONIC_FIELD",
      "NON_DOMINATED",
      "Non-dominated constellation",
      `No winner is selected at discovery time. Each reconstruction must state what only it makes visible, what it prevents from being asked, and which phenomenon exists only inside its problem-space.`,
      rivals.map((node) => node.node_id),
      "R3-A",
    );
    const collision = families.slice(0, 3).map((family) => family.positive_model).join(" / ");
    const surprise = make("SURPRISE", "COLLISION", "Abductive collision", `${lens.surprise} The conjecture is traceable to a collision among ${collision}.`, [field.node_id], "R3-G");
    return [...rivals, field, surprise];
  }

  if (gesture.gesture_id === "GX5") {
    const kernel = make("POSITIVE_KERNEL", "ANEIGNUNG", "Positive appropriation", lens.positive_kernel);
    const indication = make("FORMAL_INDICATION", "FORMAL_INDICATION", "Formal indication before theory", formalIndication(lens.formal_indication), [kernel.node_id]);
    const preserved = make("PRESERVED", "R2", "R2 — philosophical gain retained", lens.preserved, [kernel.node_id]);
    const balance = make("EXPLANATORY_BALANCE", "GAIN_PRICE", "Gain, price and discriminator", `Gain: ${lens.positive_kernel} Price: ${lens.self_critique} Discriminator: ${lens.revision_trigger}`, [kernel.node_id, indication.node_id]);
    return [kernel, indication, preserved, balance];
  }

  if (gesture.gesture_id === "GX6") {
    const residualKind = residualKindFor(hypothesis, resolution);
    const residual = make("OPEN_RESIDUAL", "R3_TYPED", `${residualKind} — typed open remainder`, lens.open, [q], residualKind);
    const branch = make("RESEARCH_BRANCH", "R3_G_BRANCH", "R3-G — new research node", `New research object: ${lens.revision_trigger}`, [residual.node_id], "R3-G");
    const revision = make("REVISION_TRIGGER", "REOPEN", "Concrete reopening condition", lens.revision_trigger, [branch.node_id], "R3-G");
    return [residual, branch, revision];
  }

  if (gesture.gesture_id === "GX7") {
    const terms = (hypothesis.emergent_terms ?? []).slice(0, 12);
    const resistance = make("SOURCE_RESISTANCE", "SOURCE_RESISTANCE", "Source resistance to the current problem-space", `${hypothesis.source_resistance_trigger ?? "The source is not adequately represented by the current registry."} Central terms under pressure: ${terms.join(", ") || hypothesis.label}.`, [q], "R3-G");
    const failure = make("REPRESENTATION_FAILURE", "REPRESENTATION_FAILURE", "Representation failure as an object of inquiry", `Test whether the current unitization makes the source appear only after it has already been translated into known nodes and relations. ${lens.self_critique}`, [resistance.node_id], "R3-G");
    const delta = make("OPERATOR_DELTA", "OPERATOR_DELTA", "Experimental operator delta", `${lens.operator_delta ?? "SOURCE_FORCED_OPERATOR_CANDIDATE"}. ${lens.mutation} This delta is not CORE promotion and must survive rollback and cross-corpus regression.`, [failure.node_id], "R3-G");
    return [resistance, failure, delta];
  }

  return [];
}

function familyNode(family, context) {
  return nodeFactory({
    ...context,
    functionText: family.diagnostic,
    protocolRefs: family.protocol_refs,
  }, "SPECIALIZED_PROBE", family.family_id, family.title,
  `${family.diagnostic} Constructive move: ${family.constructive_move} Positive possibility: ${family.positive_model} Self-risk: ${family.self_risk}`,
  `FAMILY-${family.family_id}`, [context.questionNode.node_id]);
}

function relationForRole(role) {
  return {
    PROBLEM_GENESIS: "MOTIVATES",
    LEXICAL_GENEALOGY: "GENEALOGICALLY_TRANSFORMS",
    CONCEPTUAL_GENEALOGY: "GENEALOGICALLY_TRANSFORMS",
    PROBLEM_GENEALOGY: "GENEALOGICALLY_TRANSFORMS",
    COUNTER_GENEALOGY: "COUNTERS",
    COUNTERGENETIC_FORK: "COUNTERS",
    DECONFLATION: "DECONFLATES",
    SPECIALIZED_PROBE: "ENABLES",
    RESIDUAL_CANDIDATE: "OPENS",
    REVERSE_TEST: "DISPUTES",
    RIVAL_RECONSTRUCTION: "RIVALS",
    POLYPHONIC_FIELD: "PRESERVES",
    POSITIVE_KERNEL: "PRESERVES",
    FORMAL_INDICATION: "ENABLES",
    SURPRISE: "COLLIDES_WITH",
    EXPLANATORY_BALANCE: "ENABLES",
    SELF_CRITIQUE: "OPENS",
    MUTATION: "MUTATES_INTO",
    DESTROYED: "DESTROYS_NECESSITY",
    PRESERVED: "PRESERVES",
    OPEN_RESIDUAL: "OPENS",
    RESEARCH_BRANCH: "OPENS",
    REVISION_TRIGGER: "REOPENS",
    SOURCE_RESISTANCE: "OPENS",
    REPRESENTATION_FAILURE: "SELF_CRITIQUES",
    OPERATOR_DELTA: "FORCES_MUTATION",
  }[role] ?? "ENABLES";
}

function edgeId(from, to, relation) {
  return `E-${sha256(`${from}|${to}|${relation}`).slice(0, 16).toUpperCase()}`;
}

function addEdge(edges, nodesById, from, to, relation, rationale, addParent = true) {
  if (!from || !to || !nodesById.has(from) || !nodesById.has(to)) return;
  const id = edgeId(from, to, relation);
  if (!edges.some((edge) => edge.edge_id === id)) edges.push({ edge_id: id, from, to, relation, rationale });
  if (addParent) {
    const target = nodesById.get(to);
    target.parent_ids = [...new Set([...target.parent_ids, from])].sort();
  }
}

function edgesFromParents(nodes) {
  const edges = [];
  const nodesById = new Map(nodes.map((node) => [node.node_id, node]));
  for (const node of nodes) {
    for (const parent of node.parent_ids) {
      addEdge(edges, nodesById, parent, node.node_id, relationForRole(node.role), `${nodesById.get(parent)?.role ?? "A prior node"} makes ${node.role} available without imposing a fixed next step.`, false);
    }
  }
  const first = (role) => nodes.find((node) => node.role === role)?.node_id;
  const all = (role) => nodes.filter((node) => node.role === role).map((node) => node.node_id);
  const positive = first("POSITIVE_KERNEL");
  const selfCritique = first("SELF_CRITIQUE");
  const reverse = first("REVERSE_TEST");
  const mutation = first("MUTATION");
  const surprise = first("SURPRISE");
  if (selfCritique && positive) addEdge(edges, nodesById, selfCritique, positive, "SELF_CRITIQUES", "The residual attacks the positive appropriation rather than becoming an appended disclaimer.", false);
  if (positive && mutation) addEdge(edges, nodesById, positive, mutation, "MUTATES_INTO", "Positive appropriation is rewritten after reverse pressure.");
  if (selfCritique && mutation) addEdge(edges, nodesById, selfCritique, mutation, "MUTATES_INTO", "Self-critique changes the kernel's content.");
  if (reverse && mutation) addEdge(edges, nodesById, reverse, mutation, "MUTATES_INTO", "The old position's counterpressure changes the reconstruction.");
  if (surprise) {
    for (const family of all("SPECIALIZED_PROBE").slice(0, 4)) {
      addEdge(edges, nodesById, family, surprise, "COLLIDES_WITH", "Two non-neighbouring lenses generate an abductive possibility; novelty is not treated as evidence.");
    }
  }
  return edges.sort((left, right) => left.edge_id.localeCompare(right.edge_id));
}

function adaptiveLensForHypothesis(hypothesis, fallback) {
  if (!["SOURCE_FORCED_REGISTRY_RESISTANCE", "EXPLICIT_PROJECT_THESIS_CANDIDATE"].includes(hypothesis.origin) && !hypothesis.topic_id.startsWith("EMERGENT_")) return fallback;
  const terms = (hypothesis.emergent_terms ?? []).slice(0, 12);
  const termText = terms.length ? terms.join(", ") : hypothesis.label;
  const candidateFamily = hypothesis.operator_candidate?.family ?? null;
  const openSetCandidate = hypothesis.open_set_candidate?.status === "OPEN_SET_RIVAL_REQUIRED" ? hypothesis.open_set_candidate : null;
  const relationSensitive = candidateFamily === "RELATION_GENESIS_PROFILE"
    || /relation|relata|co[-_ ]?constit|co[-_ ]?emerg|geviert|vierung|versamm|gather|nähe|ferne|ort|raum|welt|world|spiegel|difference|différence|system|système|depend|relative|отнош|соопредел|собир|различ|систем|завис/iu.test(`${hypothesis.label} ${hypothesis.research_question} ${termText}`);
  const profileHints = hypothesis.operator_candidate?.profile_hints ?? [];
  const openSetRivals = (openSetCandidate?.rival_unitizations ?? []).map((unit) => `OPEN_SET_${unit.unitization_id}: ${unit.description} Consequence: ${unit.analytic_consequence}`);
  const relationRivals = [
    "RELATA_FIRST: treat the units as sufficiently individuated before the relation, then test what this representation clarifies and what source features it loses.",
    "ASYMMETRIC_DEPENDENCE: allow one term to depend for existence, intelligibility or attribution on another without inferring reciprocal co-constitution or relation-first ontology.",
    "RECIPROCAL_RELATION: treat the units as distinguishable while their actual profile changes through reciprocal interaction; distinguish interaction from constitutive dependence.",
    "CO_CONSTITUTIVE: allow the relata to remain distinguishable while some of their local determination depends on reciprocal participation; demand a discriminator against mere interaction.",
    "RELATION_FIRST: test whether a relational or differential field is explanatorily prior to the units without turning the relation into a fifth substance or a universal ontology.",
    "UNRESOLVED_ONTOLOGY: suspend the priority question if the source makes relata-first versus relation-first itself a distorting alternative.",
    "LOCAL_PROFILE_VARIATION: permit different passages or categories in one corpus to require different relation-genesis profiles instead of forcing a single ontology across the whole text.",
    ...openSetRivals
  ];
  return {
    problem_genesis: `The current problem-space may be an artifact of registry coverage: source-central terms (${termText}) were not allowed to determine the initial unit of analysis on their own terms.`,
    deconflation: relationSensitive
      ? "Separate external connection, asymmetric dependence, reciprocal interaction, co-constitution, relation-first articulation, unresolved priority and local profile variation; do not assume that one relation ontology must govern the entire corpus."
      : "Separate registry recognition, source centrality, argumentative importance and truth; an unrecognized term can force a new question without becoming a privileged answer.",
    genealogies: {
      lexical: `Track the local forms and translation residues of ${termText}; lexical recurrence is a source signal, not an ontological proof.`,
      conceptual: relationSensitive ? `Track whether the source treats units as prior to relation, asymmetrically dependent, reciprocally interacting, co-constituted, relation-first, locally heterogeneous or resistant to the priority distinction; keep rival trajectories live. Source-derived profile hints: ${profileHints.join(", ") || "UNRESOLVED"}.` : "Track functions that the omitted terms perform even when no existing topic label names them.",
      problem: "Track how the question changes when source-central residues, explicit project theses and rival unitizations are allowed to reorganize the inquiry rather than being routed into the nearest legacy topic."
    },
    counter_genealogy: relationSensitive ? "A strengthened relata-first reading may preserve literal differentiation better than a relational reconstruction and can expose co-constitution as a contemporary projection." : "The legacy registry may have omitted these terms for good reasons: recurrence can be decorative, dossier-induced or too local to warrant a new problem-space.",
    rivals: relationSensitive ? relationRivals : [
      "LEGACY_ROUTING: the nearest curated topic already explains the material and the apparent blind spot is only vocabulary variation.",
      "SOURCE_FORCED_ROUTING: the omitted terms alter what counts as a unit, relation or relevant question and therefore require an emergent constellation before adjudication.",
      ...openSetRivals
    ],
    positive_kernel: relationSensitive ? "Use a reversible relation-genesis profile instead of a fixed node-edge ontology: RELATA_FIRST / ASYMMETRIC_DEPENDENCE / RECIPROCAL_RELATION / CO_CONSTITUTIVE / RELATION_FIRST / UNRESOLVED_ONTOLOGY remain competing local representations, with LOCAL_PROFILE_VARIATION allowed when one corpus contains more than one regime." : "Source centrality may force a provisional topic without conferring truth: the method must be corrigible at the level of its own categories, not only at the level of confidence scores.",
    formal_indication: {
      name: relationSensitive ? "Reversible relation-genesis profile" : "Source-forced category revision",
      direction: relationSensitive ? "Ask whether the analytic units are fully specifiable before the relation that joins them, whether dependence is one-way or reciprocal, and whether that answer changes across local passages." : "Ask what the source repeatedly makes salient that the registry cannot name without translation into another problem.",
      negation: "Do not identify novelty, recurrence or representational failure with philosophical truth.",
      enactment: relationSensitive ? "Re-run the same selectors through rival unitizations and compare lost distinctions, explanatory gain and source fidelity." : "Compare legacy routing with an emergent source-forced routing and record which distinctions disappear under each.",
      limit: "The operator delta remains experimental, reversible and local until it survives cross-corpus regression."
    },
    surprise: relationSensitive ? "The source may not merely add another relation to the graph; it may make nodehood itself a revisable analytical achievement." : "The most informative residue may be a failure of the method's topic ontology rather than a new claim about the source.",
    self_critique: relationSensitive ? "Relation-first language can domesticate a resistant text into contemporary relational ontology, while multiplying representation modes can become unfalsifiable methodological theatre." : "A method that mutates whenever it misses something can immunize itself against failure by redescribing every error as productive novelty.",
    mutation: relationSensitive ? "Permit an experimental non-pairwise representation in which relata-status is itself typed and revisable; require rollback to pairwise graph if the new mode yields no source-linked distinction or fails regression." : "Permit a source-forced topic/operator candidate only when omitted centrality recurs across independent selectors and the candidate survives a rival routing comparison.",
    destroyed: "The assumption that a curated topic registry and pairwise unitization are neutral preconditions of philosophical analysis.",
    preserved: "Traceability, discriminating rivals, source ceilings and the right to retire a mutation when it adds no repeatable gain.",
    open: relationSensitive ? "Whether the source requires relata-first, asymmetric-dependence, reciprocal, co-constitutive, relation-first, locally plural or deliberately unresolved representation, and whether any discriminator transfers beyond this corpus." : "Whether the detected blind spot is a source-driven problem or an artifact of dossier construction and term selection.",
    revision_trigger: relationSensitive ? "Reopen or retire the operator delta after a rival-unitization regression: mutation survives only if it restores source-central distinctions without inflating unsupported ontology." : "Reopen after an independent corpus shows whether the same category failure recurs or disappears under ordinary routing.",
    operator_delta: relationSensitive ? (hypothesis.operator_candidate?.candidate ?? "RELATION_GENESIS_PROFILE_WITH_CO_EMERGENT_RELATA_CANDIDATE") : "SOURCE_FORCED_TOPIC_AND_OPERATOR_CANDIDATE"
  };
}

function buildConstellation(registry, lenses, hypothesis, seed, resolution, options) {
  const constellationId = stableId("C", hypothesis.topic_id);
  const baseLens = lenses.topics[hypothesis.topic_id] ?? lenses.default;
  const lens = adaptiveLensForHypothesis(hypothesis, baseLens);
  const families = selectFamilies(registry, hypothesis, seed, options.maximumFamilies);
  const basis = sourceBasis(hypothesis, resolution);
  const questionNode = nodeFactory({
    hypothesis,
    constellationId,
    sourceBasis: basis,
    lens,
    functionText: "Keep the inquiry open and traceable while generative gestures alter its formulation.",
    protocolRefs: ["2.0 §0.1", "D3-EXPLORATORY §18"],
  }, "QUESTION", "QUESTION", hypothesis.label, hypothesis.research_question, "HYPOTHESIS-SEED", []);
  const activations = registry.generative_gestures.map((gesture) => ({ gesture, ...gestureActivation(gesture, hypothesis, lens, families, resolution) }));
  const activeGestures = activations.filter((item) => item.active);
  const skippedGestures = activations.filter((item) => !item.active).map((item) => ({ gesture_id: item.gesture.gesture_id, reason: item.reason }));
  const tasks = [
    ...activeGestures.map((item) => ({ kind: "GESTURE", key: item.gesture.gesture_id, payload: item })),
    ...families.map((family) => ({ kind: "FAMILY", key: family.family_id, payload: family })),
  ];
  tasks.sort((left, right) => stableScore(seed, hypothesis.topic_id, right.key) - stableScore(seed, hypothesis.topic_id, left.key) || left.key.localeCompare(right.key));
  const nodes = [questionNode];
  const trace = [];
  const retired = [];
  const context = { hypothesis, constellationId, sourceBasis: basis, lens, families, questionNode, seed, resolution };
  for (const [index, task] of tasks.entries()) {
    if (index >= options.maximumOperators) {
      retired.push({ operator_id: task.key, reason: "EXPLORATORY_TRAVERSAL_BUDGET_REACHED; available for reopening." });
      continue;
    }
    const produced = task.kind === "GESTURE"
      ? nodesForGesture(task.payload.gesture, context)
      : [familyNode(task.payload, context)];
    nodes.push(...produced);
    trace.push({
      iteration: index + 1,
      selected_operator: task.key,
      task_kind: task.kind,
      trigger: task.kind === "GESTURE" ? task.payload.reason : task.payload.diagnostic,
      produced_nodes: produced.map((node) => node.node_id),
      produced_roles: produced.map((node) => node.role),
      generative_gains: [...new Set(produced.flatMap((node) => node.generative_gains))],
      gain_contract_satisfied: produced.length > 0 && produced.every((node) => node.generative_gains.length > 0),
      selection_basis: "SEEDED_CHOICE_AMONG_INDEPENDENT_TRIGGERED_GESTURES_AND_FAMILIES",
    });
  }
  for (const skipped of skippedGestures) retired.push({ operator_id: skipped.gesture_id, reason: `TRIGGER_NOT_MET: ${skipped.reason}` });
  nodes.sort((left, right) => left.node_id.localeCompare(right.node_id));
  const edges = edgesFromParents(nodes);
  const ids = (roles) => nodes.filter((node) => roles.includes(node.role)).map((node) => node.node_id);
  const constellation = {
    constellation_id: constellationId,
    topic_id: hypothesis.topic_id,
    title: hypothesis.label,
    guiding_question: hypothesis.research_question,
    claim_statement: hypothesis.claim_statement ?? null,
    emergent_terms: [...new Set(hypothesis.emergent_terms ?? [])],
    entry_node_ids: [questionNode.node_id],
    etymology_card_ids: options.etymologyCardIds,
    activated_gestures: activeGestures.map((item) => item.gesture.gesture_id),
    skipped_gestures: skippedGestures,
    activated_families: families.map((family) => family.family_id),
    genealogical_node_ids: ids(["LEXICAL_GENEALOGY", "CONCEPTUAL_GENEALOGY", "PROBLEM_GENEALOGY", "COUNTER_GENEALOGY", "COUNTERGENETIC_FORK"]),
    rival_node_ids: ids(["RIVAL_RECONSTRUCTION", "POLYPHONIC_FIELD"]),
    kernel_node_ids: ids(["POSITIVE_KERNEL", "FORMAL_INDICATION", "MUTATION"]),
    surprise_node_ids: ids(["SURPRISE"]),
    residual_node_ids: ids(["RESIDUAL_CANDIDATE", "OPEN_RESIDUAL"]),
    research_branch_node_ids: ids(["RESEARCH_BRANCH"]),
    revision_trigger_node_ids: ids(["REVISION_TRIGGER"]),
    method_mutation_node_ids: ids(["SOURCE_RESISTANCE", "REPRESENTATION_FAILURE", "OPERATOR_DELTA"]),
    cross_constellation_edges: [],
  };
  return { constellation, nodes, edges, trace, retired, families, activations };
}

function addCrossConstellationEdges(results) {
  const edges = [];
  const allNodes = new Map(results.flatMap((result) => result.nodes).map((node) => [node.node_id, node]));
  for (let leftIndex = 0; leftIndex < results.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < results.length; rightIndex += 1) {
      const left = results[leftIndex];
      const right = results[rightIndex];
      const rightFamilies = new Set(right.families.map((family) => family.family_id));
      const shared = left.families.map((family) => family.family_id).filter((familyId) => rightFamilies.has(familyId));
      if (!shared.length) continue;
      const from = left.nodes.find((node) => node.role === "RESEARCH_BRANCH") ?? left.nodes.find((node) => node.role === "SURPRISE");
      const to = right.nodes.find((node) => node.role === "QUESTION");
      if (!from || !to) continue;
      const relation = "CROSSES_CONSTELLATION";
      const edge = {
        edge_id: edgeId(from.node_id, to.node_id, relation),
        from: from.node_id,
        to: to.node_id,
        relation,
        rationale: `A branch crosses constellations through ${shared.join(", ")} without subsuming the second question.`,
      };
      edges.push(edge);
      left.constellation.cross_constellation_edges.push(edge.edge_id);
      right.constellation.cross_constellation_edges.push(edge.edge_id);
      const target = allNodes.get(to.node_id);
      target.parent_ids = [...new Set([...target.parent_ids, from.node_id])].sort();
    }
  }
  return edges;
}

function sufficientOpenness(nodes, constellations) {
  const roles = new Set(nodes.map((node) => node.role));
  const hasOrSkipped = (gestureId) => constellations.every((entry) => entry.activated_gestures.includes(gestureId) || entry.skipped_gestures.some((item) => item.gesture_id === gestureId && item.reason.length > 0));
  const criteria = {
    problem_transformed: roles.has("COUNTERGENETIC_FORK") || roles.has("DECONFLATION"),
    new_distinction: nodes.some((node) => node.generative_gains.includes("GG1_NEW_DISTINCTION")),
    live_rival_or_counterquestion: roles.has("RIVAL_RECONSTRUCTION") || roles.has("COUNTERGENETIC_FORK"),
    reverse_pressure_or_explicit_skip: hasOrSkipped("GX3"),
    constructive_indication_or_explicit_skip: hasOrSkipped("GX5"),
    typed_residual: nodes.some((node) => node.residual_kind !== null),
    reopening_condition: roles.has("REVISION_TRIGGER") || constellations.every((entry) => entry.skipped_gestures.some((item) => item.gesture_id === "GX6")),
    source_resistance_handled_or_explicitly_absent: hasOrSkipped("GX7"),
    discovery_justification_firewall: true,
  };
  const missing = Object.entries(criteria).filter(([, value]) => !value).map(([key]) => key);
  return {
    principle: "SUFFICIENT_OPENNESS_NOT_CLOSURE",
    satisfied: missing.length === 0,
    criteria,
    missing,
    interpretation: missing.length
      ? `The exploratory graph remains underdeveloped in: ${missing.join(", ")}. This calls for reopening, not a negative verdict.`
      : "The run stops provisionally because the problem has changed under constraints, live alternatives remain, the constructive move is revisable and the remainder is typed. No truth verdict or CORE promotion follows.",
  };
}

function collectMethodMutations(nodes) {
  return nodes.filter((node) => node.role === "OPERATOR_DELTA").map((node) => ({
    mutation_id: stableId("MUT", node.constellation_id, node.node_id),
    trigger_node_id: node.parent_ids[0] ?? node.node_id,
    operator_node_id: node.node_id,
    candidate: node.proposition.split(". ")[0],
    mutation_state: "EXPERIMENTAL_CANDIDATE_NOT_CORE",
    regression_requirements: [
      "RIVAL_UNITIZATION_COMPARISON",
      "SOURCE_LINKED_DISTINCTION_GAIN",
      "ROLLBACK_PATH_PRESERVED",
      "CROSS_CORPUS_REGRESSION"
    ],
    retirement_condition: "Retire the mutation if it adds no repeatable source-linked distinction, merely renames an existing operator, or increases ontological commitment without discriminating evidence."
  }));
}

function globalFinding(topicIds) {
  const findings = [];
  const hasSourceForced = [...topicIds].some((id) => id.startsWith("EMERGENT_SOURCE_"));
  const hasExplicitClaims = [...topicIds].some((id) => id.startsWith("EMERGENT_CLAIM_"));
  if (hasSourceForced) findings.push("Сопротивляющийся источник получил право изменить не только ответ, но и исходную единицу анализа: topic recognition, nodehood и relation-type стали ревизуемыми объектами.");
  if (hasExplicitClaims) findings.push("Явные тезисы досье больше не исчезают только потому, что для них нет заранее подготовленной тематической линзы: они сохраняются как отдельные adjudicable constellations.");
  if (topicIds.has("REALITY_AND_REALISM") && topicIds.has("REGIONAL_REALIZATION_PROFILE")) findings.push("Проблема реальности мутирует из спора «независимо или сконструировано» в экологию разнородных источников коррекции и зависимости.");
  if (topicIds.has("IDENTITY_AND_INDIVIDUATION")) findings.push("Онтологический счёт предшествует тождеству: нельзя судить о сохранении X, пока не оправдано, почему именно это считается одним X, а соперничающее членение — нет.");
  if (topicIds.has("DIACHRONIC_HEIDEGGER") && topicIds.has("TERM_GENEALOGY")) findings.push("Развитие Хайдеггера лучше представлять косой из траекторий слова, функции и проблемы, чем одной линией от раннего к позднему.");
  if (topicIds.has("TECHNOLOGY_AND_ORDERING")) findings.push("Gestell сильнее всего работает как различающая сигнатура упорядочивания; непрозрачность при этом совместима с вычислимостью, а не противоположна ей.");
  if (topicIds.has("META_CRITIQUE")) findings.push("Метод рекурсивен только тогда, когда сопротивляющийся материал способен снять или мутировать оператор, а не просто добавить очередное предупреждение.");
  if (topicIds.has("MEDIATION_COMPRESSION")) findings.push("Обзор может быть точным и всё же недостаточным: допустимость компрессии зависит от её эпистемической роли и обратимого пути к потерянному контексту.");
  return findings.length ? findings.join(" ") : "Единый вердикт уступает преобразованиям вопроса, недоминируемым альтернативам и типизированным исследовательским ветвям.";
}

function emergentJunctions(topicIds) {
  const junctions = [];
  if (topicIds.has("REALITY_AND_REALISM") && topicIds.has("IDENTITY_AND_INDIVIDUATION")) junctions.push("Если разные виды сущего исправляют наши описания по-разному, то individuation перестаёт быть подготовительной технической процедурой: способ быть одним может зависеть от способа сопротивляться ошибочному описанию. Но обратная стрелка сразу кусает эту гипотезу — мы рискуем определять сущее через наш тест коррекции.");
  if (topicIds.has("META_CRITIQUE") && topicIds.has("TECHNOLOGY_AND_ORDERING")) junctions.push("Сам DAE начинает походить на региональный Gestell: он делает понятия доступными, сравнимыми и вызываемыми по запросу. Отличие от тотального постава будет реальным лишь там, где запись сохраняет dissent, rival unitization, отзыв собственного оператора и маршрут назад к источнику.");
  if (topicIds.has("DIACHRONIC_HEIDEGGER") && topicIds.has("TERM_GENEALOGY")) junctions.push("Поздняя самоинтерпретация может быть не только свидетельством пути, но и редакторским монтажом раннего. ETY-0.2 поэтому ищет не корень, обещающий истину, а расхождение формы, функции и problem-scene, способное сорвать ретроспективный телос.");
  if (topicIds.has("ACT_CONTENT_OBJECT") && topicIds.has("META_CRITIQUE")) junctions.push("Если рефлексия изменяет акт, который должна лишь обнаружить, то аналитическая машина изменяет корпус, который должна лишь представить: unitization, отбор и порядок создают новый предмет. Traceback нужен не только для provenance, но и для демонтажа собственного Gegenstand машины.");
  if (topicIds.has("IDENTITY_AND_INDIVIDUATION") && topicIds.has("TECHNOLOGY_AND_ORDERING")) junctions.push("Bestand и individuation встречаются в неожиданной точке: система может считать человека заменимым ресурсным token именно потому, что заранее выбрала удобный principle of individuation. Критика resourceization поэтому должна атаковать не только обращение с готовыми единицами, но и производство самих единиц счёта.");
  if ([...topicIds].some((id) => id.startsWith("EMERGENT_SOURCE_"))) junctions.push("Source resistance делает unitization философским вопросом: если источник теряет различие только после разбиения на готовые узлы, то граф больше не является невинной формой записи. Но отсюда ещё не следует relation-first ontology; необходимо сравнение rival unitizations и право отката.");
  return junctions;
}

function routeCollision(source, target, edge) {
  const leftFamilies = new Set(source?.activated_families ?? []);
  const shared = (target?.activated_families ?? []).filter((family) => leftFamilies.has(family));
  const claim = target?.claim_statement ?? target?.guiding_question ?? target?.title ?? "целевой тезис";
  const probes = [];
  if (shared.includes("F-RELATION-GENESIS")) probes.push("сменить порядок конституирования: считать ли relata готовыми до связи, локально соопределяемыми, relation-first или оставить сам приоритет неразрешённым");
  if (shared.includes("F-REPRESENTATION-RESISTANCE")) probes.push("повторить тезис на rival unitization и проверить, сохраняется ли различие, ради которого тезис был введён");
  if (shared.includes("F-LANGUAGE-TRANSLATION")) probes.push("развести source-term, перевод и метаязык реконструкции, чтобы переводческая удобность не стала скрытым онтологическим bridge");
  if (shared.includes("F-WORLD-ACCESS")) probes.push("проверить, описывает ли тезис готовый объект или изменение самого способа доступности/раскрытия мира");
  if (shared.includes("F-PLACE-SPATIALITY")) probes.push("сравнить container-space unitization с place-producing unitization, не объявляя ни одну исходно привилегированной");
  if (shared.includes("F-MORTALITY")) probes.push("отделить биологический класс от source-specific способа отношения к смертности");
  const experiment = probes.length ? probes.join("; затем ") : "поменять unitization и проверить, сохраняется ли тезис без помощи исходной схемы представления";
  return {
    claim,
    shared,
    experiment,
    discriminator: `Тезис «${claim}» получает дополнительный вес только если различающий эффект переживает этот эксперимент; если эффект исчезает или меняет знак, route возвращается как counterpressure, а не как подтверждение.`,
    rationale: edge.rationale,
  };
}

function renderPhilosophicalFieldNote(analysis, etymologyPass) {
  const topicIds = new Set(analysis.constellations.map((entry) => entry.topic_id));
  const nodes = new Map(analysis.graph.nodes.map((node) => [node.node_id, node]));
  const constellations = new Map(analysis.constellations.map((entry) => [entry.constellation_id, entry]));
  const routePriority = (edge) => {
    const fromTopic = constellations.get(nodes.get(edge.from)?.constellation_id)?.topic_id ?? "";
    const toTopic = constellations.get(nodes.get(edge.to)?.constellation_id)?.topic_id ?? "";
    const sourceForced = [fromTopic, toTopic].some((id) => id.startsWith("EMERGENT_SOURCE_")) ? 2 : 0;
    const explicitClaim = [fromTopic, toTopic].some((id) => id.startsWith("EMERGENT_CLAIM_")) ? 1 : 0;
    return sourceForced + explicitClaim;
  };
  const routes = analysis.graph.edges
    .filter((edge) => edge.relation === "CROSSES_CONSTELLATION")
    .sort((left, right) => routePriority(right) - routePriority(left) || stableScore(analysis.seed, right.edge_id) - stableScore(analysis.seed, left.edge_id))
    .slice(0, 5);
  const lines = [
    "# Полевая философская запись",
    "",
    "> Это первичный живой вывод D3-EXPLORATORY. Он не раскладывает корпус по заранее обязательной последовательности, а собирает маршруты из конфликтов unitization, source-resistance, rivals и обратных стрелок. `LIVING_ANALYTICS.md` сохраняет повторяемый граф для аудита; полевая запись имеет право менять композицию, но не evidence ceiling.",
    "",
    "## Что произошло с исходным вопросом",
    "",
    globalFinding(topicIds),
    "",
    "## Узлы, которых не было в отдельной теме",
    "",
  ];
  const junctions = emergentJunctions(topicIds);
  for (const [index, junction] of junctions.entries()) lines.push(`${index + 1}. ${junction}`, "");
  if (!junctions.length) lines.push("Ни одно заранее артикулированное межтематическое столкновение не сработало; этот null result сохраняется вместо универсальной синтетической фразы.", "");
  if (analysis.method_mutations?.length) {
    lines.push("## Методический перелом", "", "Источник не только породил новый тезис, но и атаковал форму, в которой метод разрешает тезису появиться. Поэтому здесь сохраняются конкурирующие представления, а не выбирается новая онтология:", "");
    lines.push("- **RELATA_FIRST** — единицы считаются определёнными до связи; проверяется, какие различия это сохраняет и какие стирает.");
    lines.push("- **RECIPROCAL_RELATION** — relata считаются различимыми, но взаимно модифицируют условия проявления друг друга; этот режим нужен как rival к более сильной co-constitution.");
    lines.push("- **CO_CONSTITUTIVE** — различимые relata локально соопределяются без слияния; требуется отличие от простой взаимной причинности.");
    lines.push("- **RELATION_FIRST** — проверяется объяснительный приоритет отношения/события без превращения его в пятую субстанцию.");
    lines.push("- **UNRESOLVED_ONTOLOGY** — сам вопрос о приоритете снимается, если оппозиция relata-first/relation-first уже искажает источник.", "");
    for (const mutation of analysis.method_mutations) lines.push(`**Кандидат мутации:** ${mutation.candidate}. Состояние: ${mutation.mutation_state}. Условие снятия: ${mutation.retirement_condition}`, "");
  }
  lines.push("## Маршруты столкновения", "");
  if (!routes.length) lines.push("Межконстелляционных переходов в этом прогоне нет. Это не дефицит, который следует заполнить синтетической фразой: при одном source-forced узле нелинейность удерживается внутри rival unitizations и operator mutation.", "");
  for (const [index, edge] of routes.entries()) {
    const from = nodes.get(edge.from);
    const to = nodes.get(edge.to);
    const source = constellations.get(from?.constellation_id);
    const target = constellations.get(to?.constellation_id);
    const collision = routeCollision(source, target, edge);
    const counterpressure = analysis.graph.nodes.find((node) => node.constellation_id === target?.constellation_id && ["SELF_CRITIQUE", "REVERSE_TEST"].includes(node.role));
    const targetTerms = (target?.emergent_terms ?? []).slice(0, 5);
    lines.push(`### Маршрут ${index + 1}: ${source?.title ?? from?.title} ↝ ${target?.title ?? to?.title}`, "");
    lines.push(`**Ставка целевого узла.** ${collision.claim}`, "");
    if (targetTerms.length) lines.push(`**Локальные носители различия.** ${targetTerms.join(", ")}.`, "");
    lines.push(`**Герменевтическое столкновение.** Вместо переноса готового вывода маршрут требует: ${collision.experiment}.`, "");
    lines.push(`**Почему переход не является выводом.** ${collision.rationale}`, "");
    lines.push(`**Ответное давление.** ${counterpressure?.proposition ?? "Встречная констелляция пока не создала отдельного контрдавления; это отсутствие сохраняется как null result, а не заполняется модельной риторикой."}`, "");
    lines.push(`**Discriminator.** ${collision.discriminator}`, "");
  }
  const etyCards = etymologyPass.cards
    .filter((card) => card.generative_result.qualitative_gains.length || card.topic_ids.includes("ETY_STRESS_REQUEST") || card.topic_ids.some((id) => id.startsWith("EMERGENT_SOURCE_")))
    .sort((left, right) => {
      const leftSource = left.topic_ids.some((id) => id.startsWith("EMERGENT_SOURCE_")) ? 1 : 0;
      const rightSource = right.topic_ids.some((id) => id.startsWith("EMERGENT_SOURCE_")) ? 1 : 0;
      return rightSource - leftSource || stableScore(analysis.seed, right.card_id) - stableScore(analysis.seed, left.card_id);
    })
    .slice(0, 8);
  lines.push("## Этимологические возмущения", "", "Здесь этимология допускается только как генератор различия или вопроса; local sense всех карточек текущего досье остаётся неразрешённым до прямой проверки span. Source-forced ETY null result сохраняется как результат, а не заполняется красивой этимологией.", "");
  for (const card of etyCards) {
    if (card.generative_result.qualitative_gains.length) lines.push(`- **${card.ety_min.source_form.value}:** ${card.generative_result.lost_distinction.value} ${card.generative_result.new_question.value}`);
    else lines.push(`- **${card.ety_min.source_form.value}:** ETY-null — локальный смысл, историческая деривация и переводческий residual пока не разрешены; термин остаётся обязательным объектом проверки без etymology→ontology promotion.`);
  }
  lines.push("", "## Самодеструкция этой записи", "", "Эта полевая запись сама производит Laienbrevier Effect: выбранные маршруты могут выглядеть как естественная архитектура корпуса, хотя они выбраны из более широкого графа seeded traversal. Поэтому каждый маршрут обратим к узлам, селекторам и ETY-карточкам; другой seed изменит путь чтения, но не множество кандидатов. Если краткая запись начнёт заменять граф и источник, её собственный успех станет основанием для снятия.", "");
  lines.push("## Остаток", "", "Неожиданность текущего прогона состоит не в одном новом тезисе о Хайдеггере. Она состоит в самоприменении: машина анализа обнаруживает себя одновременно как инструмент различения и как возможный режим поставления понятий. Следующий сильный тест должен быть уже не повторением этого успеха, а cross-corpus испытанием: способен ли другой resistant source породить иной operator delta, а текущий relation-genesis operator — быть отвергнутым там, где он не добавляет воспроизводимого различия. Отдельно нужно проверить, может ли сопротивление источника менять не только граф, но и форму итогового письма.", "", `Claim ceiling: \`${analysis.claim_ceiling}\`.`, "");
  return `${lines.join("\n")}\n`;
}

function renderLivingMarkdown(analysis) {
  const topicIds = new Set(analysis.constellations.map((entry) => entry.topic_id));
  const lines = [
    "# Живая аналитика Destruktion 0.6",
    "",
    "> Режим: D3-EXPLORATORY-0.2. Это генерация философских кандидатов, а не доказательство, терминальный вердикт или изменение замороженного CORE.",
    "",
    "## Сквозной философский результат",
    "",
    globalFinding(topicIds),
    "",
    `Достаточная открытость: **${analysis.sufficient_openness.satisfied ? "достигнута" : "не достигнута"}**. ${analysis.sufficient_openness.interpretation}`,
    "",
    `Обязательный ETY-0.2: **${analysis.etymology.cards}** карточек, из них ETY-FULL — **${analysis.etymology.full_cards}**; неразрешённых полей — **${analysis.etymology.unresolved_fields}**. Полнота проверки не означает полноту знания.`,
    "",
  ];
  for (const constellation of analysis.constellations) {
    const nodes = analysis.graph.nodes.filter((node) => node.constellation_id === constellation.constellation_id);
    const byRole = (role) => nodes.filter((node) => node.role === role);
    const first = (role) => byRole(role)[0]?.proposition ?? null;
    lines.push(`## ${constellation.title}`, "", `**Исходный вопрос:** ${constellation.guiding_question}`, "", `GX: ${constellation.activated_gestures.map((id) => `\`${id}\``).join(", ")}.`, "");
    if (first("PROBLEM_GENESIS")) lines.push(`**Преобразование проблемы.** ${first("PROBLEM_GENESIS")}`, "");
    if (first("COUNTERGENETIC_FORK")) lines.push(`**Конкурирующий вопрос.** ${first("COUNTERGENETIC_FORK")}`, "");
    const genealogies = nodes.filter((node) => ["LEXICAL_GENEALOGY", "CONCEPTUAL_GENEALOGY", "PROBLEM_GENEALOGY", "COUNTER_GENEALOGY"].includes(node.role));
    if (genealogies.length) {
      lines.push("### Генеалогические развилки", "");
      for (const node of genealogies) lines.push(`- ${node.proposition}`);
      lines.push("");
    }
    if (byRole("SPECIALIZED_PROBE").length) {
      lines.push("### Содержательные линзы", "");
      for (const node of byRole("SPECIALIZED_PROBE")) lines.push(`- **${node.title}:** ${node.proposition}`);
      lines.push("");
    }
    if (byRole("RESIDUAL_CANDIDATE").length) lines.push(`**Трещина внутри успеха.** ${first("RESIDUAL_CANDIDATE")}`, "");
    if (byRole("RIVAL_RECONSTRUCTION").length) {
      lines.push("### Недоминированная полифония", "");
      for (const node of byRole("RIVAL_RECONSTRUCTION")) lines.push(`- ${node.proposition}`);
      if (first("POLYPHONIC_FIELD")) lines.push("", first("POLYPHONIC_FIELD"));
      lines.push("");
    }
    if (first("REVERSE_TEST")) lines.push(`**Обратная стрелка.** ${first("REVERSE_TEST")}`, "");
    if (first("SURPRISE")) lines.push(`**Неожиданный кандидат.** ${first("SURPRISE")}`, "");
    if (first("POSITIVE_KERNEL")) lines.push(`**Позитивное присвоение.** ${first("POSITIVE_KERNEL")}`, "");
    if (first("FORMAL_INDICATION")) lines.push(`**Formale Anzeige.** ${first("FORMAL_INDICATION")}`, "");
    if (first("SELF_CRITIQUE")) lines.push(`**Самодеструкция.** ${first("SELF_CRITIQUE")}`, "");
    if (first("MUTATION")) lines.push(`**Изменённая реконструкция.** ${first("MUTATION")}`, "");
    if (first("SOURCE_RESISTANCE")) lines.push(`**Сопротивление источника.** ${first("SOURCE_RESISTANCE")}`, "");
    if (first("REPRESENTATION_FAILURE")) lines.push(`**Провал репрезентации.** ${first("REPRESENTATION_FAILURE")}`, "");
    if (first("OPERATOR_DELTA")) lines.push(`**Operator delta.** ${first("OPERATOR_DELTA")}`, "");
    lines.push("### R1 / R2 / R3", "");
    if (first("DESTROYED")) lines.push(`- **R1:** ${first("DESTROYED")}`);
    if (first("PRESERVED")) lines.push(`- **R2:** ${first("PRESERVED")}`);
    for (const node of [...byRole("OPEN_RESIDUAL"), ...byRole("RESIDUAL_CANDIDATE")]) lines.push(`- **${node.residual_kind}:** ${node.proposition}`);
    if (first("RESEARCH_BRANCH")) lines.push(`- **R3-G:** ${first("RESEARCH_BRANCH")}`);
    if (first("REVISION_TRIGGER")) lines.push(`- **Reopen:** ${first("REVISION_TRIGGER")}`);
    lines.push("");
    if (constellation.skipped_gestures.length) {
      lines.push("Неактивированные жесты в этом узле:", "");
      for (const skipped of constellation.skipped_gestures) lines.push(`- \`${skipped.gesture_id}\`: ${skipped.reason}`);
      lines.push("");
    }
  }
  if (analysis.method_mutations?.length) {
    lines.push("## Экспериментальные мутации метода", "");
    for (const mutation of analysis.method_mutations) {
      lines.push(`- **${mutation.candidate}** — ${mutation.mutation_state}. Retirement: ${mutation.retirement_condition}`);
    }
    lines.push("");
  }
  lines.push("## Аудиторская оболочка", "", ...analysis.audit_envelope.warnings.map((warning) => `- ${warning}`), "", `Потолок утверждения: \`${analysis.claim_ceiling}\`.`, "");
  return `${lines.join("\n")}\n`;
}

function renderConstellationMarkdown(analysis) {
  const gestureTitles = { GX1: "Residual probe", GX2: "Countergenetic fork", GX3: "Reverse arrow", GX4: "Polyphony", GX5: "Formal indication", GX6: "R3 branching", GX7: "Source resistance / operator mutation" };
  const lines = ["# Карта генеративных констелляций", "", "GX — независимые жесты overlay, а не стадии конвейера.", ""];
  for (const [index, constellation] of analysis.constellations.entries()) {
    const prefix = `C${index + 1}`;
    lines.push(`## ${constellation.title}`, "", "```mermaid", "flowchart TD", `  ${prefix}Q[\"${constellation.title.replaceAll('"', "'")}\"]`);
    for (const gestureId of constellation.activated_gestures) lines.push(`  ${prefix}${gestureId}[\"${gestureId}: ${gestureTitles[gestureId]}\"]`, `  ${prefix}Q --> ${prefix}${gestureId}`);
    lines.push("```", "");
  }
  lines.push("## Межконстелляционные ветви", "");
  const cross = analysis.graph.edges.filter((edge) => edge.relation === "CROSSES_CONSTELLATION");
  if (!cross.length) lines.push("В этом проходе ветви не пересеклись.");
  for (const edge of cross) lines.push(`- \`${edge.from}\` → \`${edge.to}\`: ${edge.rationale}`);
  lines.push("");
  return `${lines.join("\n")}\n`;
}

function walkForbiddenTerminalFields(value, currentPath = "") {
  const paths = [];
  if (Array.isArray(value)) value.forEach((entry, index) => paths.push(...walkForbiddenTerminalFields(entry, `${currentPath}/${index}`)));
  else if (value && typeof value === "object") {
    for (const [key, entry] of Object.entries(value)) {
      const next = `${currentPath}/${key}`;
      if (["status", "confidence", "finality", "verdict"].includes(key)) paths.push(next);
      paths.push(...walkForbiddenTerminalFields(entry, next));
    }
  }
  return paths;
}

export function validateLivingAnalysis(engine, analysis, file = "<memory>") {
  const issues = [...engine.structural.validateLivingAnalysis(analysis)];
  const nodes = analysis?.graph?.nodes ?? [];
  const edges = analysis?.graph?.edges ?? [];
  const nodeIds = new Set();
  for (const node of nodes) {
    if (nodeIds.has(node.node_id)) issues.push(issue("ERROR", "LIVING_DUPLICATE_NODE", "/graph/nodes", `Duplicate node ${node.node_id}.`));
    nodeIds.add(node.node_id);
    if (node.generative_register === "G4" && node.residual_kind !== "R3-G") issues.push(issue("ERROR", "LIVING_G4_REQUIRES_GENERATIVE_RESIDUAL", "/graph/nodes", `${node.node_id} uses G4 without R3-G.`));
    if (node.role !== "QUESTION" && node.generative_gains.length === 0) issues.push(issue("ERROR", "LIVING_ACTIVE_MOVE_REQUIRES_GAIN", "/graph/nodes", `${node.node_id} is an active move without a traceable GG1–GG7 gain.`));
  }
  const etymologyCardIds = new Set(analysis?.etymology?.card_ids ?? []);
  for (const constellation of analysis?.constellations ?? []) {
    if (!constellation.etymology_card_ids?.length) issues.push(issue("ERROR", "LIVING_ETYMOLOGY_COVERAGE_REQUIRED", "/constellations", `${constellation.constellation_id} has no mandatory ETY-MIN coverage.`));
    for (const cardId of constellation.etymology_card_ids ?? []) if (!etymologyCardIds.has(cardId)) issues.push(issue("ERROR", "LIVING_UNKNOWN_ETYMOLOGY_CARD", "/constellations", `${constellation.constellation_id} references missing ${cardId}.`));
  }
  const edgeIds = new Set();
  for (const edge of edges) {
    if (edgeIds.has(edge.edge_id)) issues.push(issue("ERROR", "LIVING_DUPLICATE_EDGE", "/graph/edges", `Duplicate edge ${edge.edge_id}.`));
    edgeIds.add(edge.edge_id);
    if (!nodeIds.has(edge.from) || !nodeIds.has(edge.to)) issues.push(issue("ERROR", "LIVING_DANGLING_EDGE", "/graph/edges", `${edge.edge_id} references a missing node.`));
  }
  for (const node of nodes) {
    for (const parent of node.parent_ids) if (!nodeIds.has(parent)) issues.push(issue("ERROR", "LIVING_DANGLING_PARENT", "/graph/nodes", `${node.node_id} references missing parent ${parent}.`));
  }
  if (["DAE-LIVING-ANALYSIS-1.1", "DAE-LIVING-ANALYSIS-1.2"].includes(analysis?.analysis_version) && analysis?.sufficient_openness?.criteria?.source_resistance_handled_or_explicitly_absent !== true) issues.push(issue("ERROR", "LIVING_1_1_REQUIRES_SOURCE_RESISTANCE_OPENNESS", "/sufficient_openness/criteria", "Living analysis 1.1 must explicitly satisfy source-resistance handling or absence."));
  const deltaNodes = nodes.filter((node) => node.role === "OPERATOR_DELTA");
  const mutations = analysis?.method_mutations ?? [];
  if (mutations.length !== deltaNodes.length) issues.push(issue("ERROR", "LIVING_METHOD_MUTATION_COUNT_MISMATCH", "/method_mutations", `Method mutations (${mutations.length}) must correspond one-to-one with OPERATOR_DELTA nodes (${deltaNodes.length}).`));
  for (const mutation of mutations) {
    if (!nodeIds.has(mutation.operator_node_id) || !nodeIds.has(mutation.trigger_node_id)) issues.push(issue("ERROR", "LIVING_METHOD_MUTATION_DANGLING", "/method_mutations", `${mutation.mutation_id} references a missing node.`));
    const node = nodes.find((entry) => entry.node_id === mutation.operator_node_id);
    if (node?.role !== "OPERATOR_DELTA") issues.push(issue("ERROR", "LIVING_METHOD_MUTATION_WRONG_ROLE", "/method_mutations", `${mutation.mutation_id} must reference an OPERATOR_DELTA node.`));
    if (!node?.generative_gains?.includes("GG7_OPERATOR_EVOLUTION")) issues.push(issue("ERROR", "LIVING_METHOD_MUTATION_REQUIRES_GG7", "/method_mutations", `${mutation.mutation_id} lacks GG7_OPERATOR_EVOLUTION.`));
  }
  for (const forbidden of walkForbiddenTerminalFields(analysis)) issues.push(issue("ERROR", "LIVING_TERMINAL_FIELD_FORBIDDEN", forbidden, "Exploratory output cannot contain terminal status, confidence, finality or verdict fields."));
  const sorted = sortIssues(issues);
  const counts = countIssues(sorted);
  return { file, conformant: counts.ERROR === 0, counts, issues: sorted };
}

async function writeOutputs(outputDir, analysis, trace, etymology) {
  await mkdir(outputDir, { recursive: false });
  const files = {
    analysis: path.join(outputDir, "living_analysis.json"),
    analytics: path.join(outputDir, "LIVING_ANALYTICS.md"),
    constellation: path.join(outputDir, "CONSTELLATION.md"),
    audit: path.join(outputDir, "AUDIT_ENVELOPE.json"),
    trace: path.join(outputDir, "operator_trace.json"),
    etymology: path.join(outputDir, "etymology_pass.json"),
    etymology_analytics: path.join(outputDir, "ETYMOLOGICAL_ANALYSIS.md"),
    field_note: path.join(outputDir, "PHILOSOPHICAL_FIELD_NOTE.md"),
  };
  await Promise.all([
    writeFile(files.analysis, `${JSON.stringify(analysis, null, 2)}\n`, "utf8"),
    writeFile(files.analytics, renderLivingMarkdown(analysis), "utf8"),
    writeFile(files.constellation, renderConstellationMarkdown(analysis), "utf8"),
    writeFile(files.audit, `${JSON.stringify(analysis.audit_envelope, null, 2)}\n`, "utf8"),
    writeFile(files.trace, `${JSON.stringify(trace, null, 2)}\n`, "utf8"),
    writeFile(files.etymology, etymology.bytes),
    writeFile(files.etymology_analytics, etymology.markdown, "utf8"),
    writeFile(files.field_note, renderPhilosophicalFieldNote(analysis, etymology.pass), "utf8"),
  ]);
  return files;
}

export async function runLivingAnalysis(engine, refineryDirectory, outputDirectory, options = {}) {
  const refineryRoot = path.resolve(refineryDirectory);
  const outputDir = path.resolve(outputDirectory);
  const registryFile = options.registryFile ? path.resolve(options.registryFile) : projectPath("config", "living_operator_registry.json");
  const lensesFile = projectPath("config", "living_topic_lenses.json");
  const reportFile = path.join(refineryRoot, "REFINERY_REPORT.json");
  const hypothesisFile = path.join(refineryRoot, "hypothesis_bank.json");
  const [registryBytes, lensesBytes, reportBytes, hypothesisBytes] = await Promise.all([
    readFile(registryFile), readFile(lensesFile), readFile(reportFile), readFile(hypothesisFile),
  ]);
  const registry = JSON.parse(registryBytes.toString("utf8"));
  if (registry?.runtime_contract?.runtime?.startsWith("DAE-LIVING-DECLARATIVE")) {
    const declarativeErrors = validateDeclarativeGestures(registry);
    if (declarativeErrors.length) throw new Error(`LIVING_DECLARATIVE_REGISTRY_INVALID: ${JSON.stringify(declarativeErrors, null, 2)}`);
  }
  const lenses = JSON.parse(lensesBytes.toString("utf8"));
  const report = JSON.parse(reportBytes.toString("utf8"));
  const hypothesisBank = JSON.parse(hypothesisBytes.toString("utf8"));
  const bankIssues = engine.structural.validateHypothesisBank(hypothesisBank);
  if (bankIssues.length) throw new Error(`LIVING_HYPOTHESIS_BANK_INVALID: ${JSON.stringify(bankIssues, null, 2)}`);
  if (!Array.isArray(hypothesisBank.hypotheses) || !hypothesisBank.hypotheses.length) throw new Error("LIVING_ANALYSIS_REQUIRES_AT_LEAST_ONE_HYPOTHESIS");
  const seed = String(options.seed ?? "destruktion-living-default");
  const generatedAt = String(options.generatedAt ?? new Date().toISOString());
  const runOptions = {
    maximumFamilies: Number.isInteger(options.maximumFamilies) ? options.maximumFamilies : 6,
    maximumOperators: Number.isInteger(options.maximumOperators) ? options.maximumOperators : 24,
  };
  if (runOptions.maximumFamilies < 1 || runOptions.maximumFamilies > 12) throw new Error("maximumFamilies must be between 1 and 12");
  if (runOptions.maximumOperators < 1 || runOptions.maximumOperators > 64) throw new Error("maximumOperators must be between 1 and 64");
  const resolution = sourceResolution(report);
  const etymology = await buildEtymologyPass(engine, refineryRoot, { generatedAt });
  const results = hypothesisBank.hypotheses.map((hypothesis) => buildConstellation(registry, lenses, hypothesis, seed, resolution, {
    ...runOptions,
    etymologyCardIds: etymology.pass.cards.filter((card) => card.topic_ids.includes(hypothesis.topic_id)).map((card) => card.card_id),
  }));
  const crossEdges = addCrossConstellationEdges(results);
  const nodes = results.flatMap((result) => result.nodes).sort((left, right) => left.node_id.localeCompare(right.node_id));
  const edges = [...results.flatMap((result) => result.edges), ...crossEdges].sort((left, right) => left.edge_id.localeCompare(right.edge_id));
  const constellations = results.map((result) => result.constellation);
  const registryHash = sha256(registryBytes);
  const runHash = sha256([report.source_id, report.artifact_sha256, sha256(hypothesisBytes), registryHash, seed].join("|"));
  const runId = `LIVING-${slug(report.source_id, "SOURCE")}-${runHash.slice(0, 12).toUpperCase()}`;
  const auditEnvelope = {
    role: "EXTERNAL_NON_DOMINATING_AUDIT_LAYER",
    source_fixity_preserved: true,
    source_text_included: false,
    claim_level_source_resolution: resolution,
    external_validation: "PENDING",
    warnings: [
      `Claim-level source resolution is ${resolution}; selectors are pointers, not verified quotations or attributions.`,
      "Discovery is not justification: GX2 histories, GX4 alternatives, GX5 indications and GX6 branches are exploratory until O0–O9 and source review test them.",
      "G0–G4 records generative kind, never truth, confidence or evidential rank; a G4 branch can remain reconstructive while a G0 bibliographic fact can be textually secure.",
      "Novelty is not optimized. Every generated move must remain traceable, relevant to an aporia or residual, and explicitly revisable.",
      "Every active move must add at least one GG1–GG7 gain. A move without gain is retired instead of being emitted as ritual procedure.",
      "Provenance is not reconstructability: a locator alone does not disclose omitted context, collapsed ambiguity or rival unitizations.",
      "ETY-0.2 is mandatory coverage, not mandatory significance. Local use has priority over origin; etymology never licenses a conceptual or ontological promotion without an independent bridge.",
      "Meta-risks retained: novelty bias, infinite branching, poetic obscurity, countergenealogy inflation and permanent indecision.",
      "With an untruncated traversal budget, the seed changes only the order of independently triggered gestures; it does not alter candidate content, source hashes or selector sets.",
      "GX7 is source-forced method critique: source-central blind spots may create an experimental operator delta, but no delta is CORE promotion until rival-unitization, rollback and cross-corpus regression tests survive.",
    ],
  };
  const analysis = {
    analysis_version: ANALYSIS_VERSION,
    engine_version: engine.context.engineVersion,
    generated_at: generatedAt,
    run_id: runId,
    seed,
    layer: {
      layer_id: LAYER_ID,
      kind: "EXPERIMENTAL_GENERATIVE_OVERLAY",
      core_mutated: false,
      discovery_justification_firewall: true,
    },
    source: {
      source_id: report.source_id,
      artifact_sha256: report.artifact_sha256,
      refinery_report_sha256: sha256(reportBytes),
      hypothesis_bank_sha256: sha256(hypothesisBytes),
      hypothesis_count: hypothesisBank.hypotheses.length,
      claim_ledger_entries: report.counts?.claim_ledger_entries ?? 0,
    },
    operator_registry: {
      registry_version: registry.registry_version,
      sha256: registryHash,
      protocol_sources: registry.protocol_sources,
    },
    etymology: {
      protocol_version: etymology.pass.protocol_version,
      mandatory: true,
      pass_sha256: etymology.sha256,
      cards: etymology.pass.coverage.cards_emitted,
      full_cards: etymology.pass.coverage.ety_full_executed,
      card_ids: etymology.pass.cards.map((card) => card.card_id),
      coverage_complete: etymology.pass.coverage.coverage_complete,
      unresolved_fields: etymology.pass.coverage.unresolved_fields,
      semantic_promotion_without_independent_bridge: false,
    },
    graph: {
      topology: "REVISABLE_DIRECTED_MULTIGRAPH",
      nodes,
      edges,
      traversal_order: results.flatMap((result) => result.trace.flatMap((entry) => entry.produced_nodes)),
      retired_operators: results.flatMap((result) => result.retired),
    },
    constellations,
    method_mutations: collectMethodMutations(nodes),
    sufficient_openness: sufficientOpenness(nodes, constellations),
    audit_envelope: auditEnvelope,
    output_contract: {
      terminal_verdicts_emitted: false,
      raw_source_included: false,
      graph_and_narrative_emitted: true,
      exploratory_layer_only: true,
      polyphony_preserved_when_triggered: true,
      formal_indication_precedes_theory_promotion: true,
      typed_residuals_enabled: true,
      discovery_is_not_justification: true,
      audit_layer_is_external: true,
      each_active_step_adds_traceable_gain: true,
      compression_role_bounded_and_reversible: true,
      mandatory_etymology_executed: true,
      mandatory_etymological_significance: false,
    },
    claim_ceiling: CLAIM_CEILING,
  };
  const validation = validateLivingAnalysis(engine, analysis);
  if (!validation.conformant) throw new Error(`LIVING_ANALYSIS_INVALID: ${JSON.stringify(validation.issues, null, 2)}`);
  const trace = {
    trace_version: "DAE-LIVING-OPERATOR-TRACE-1.0",
    run_id: runId,
    seed,
    scheduling: "SEEDED_TRIGGERED_GESTURES_NOT_FIXED_PIPELINE",
    discovery_justification_firewall: true,
    etymology: {
      protocol_version: etymology.pass.protocol_version,
      run_id: etymology.pass.run_id,
      pass_sha256: etymology.sha256,
      mandatory_execution: true,
      mandatory_significance: false,
    },
    constellations: results.map((result) => ({
      constellation_id: result.constellation.constellation_id,
      activations: result.activations.map((item) => ({ gesture_id: item.gesture.gesture_id, active: item.active, reason: item.reason })),
      activated_families: result.constellation.activated_families,
      steps: result.trace,
      retired_operators: result.retired,
    })),
  };
  const files = await writeOutputs(outputDir, analysis, trace, etymology);
  return { output_dir: outputDir, analysis, validation, trace, etymology, files };
}

export async function validateLivingAnalysisFile(engine, filePath) {
  const resolved = path.resolve(filePath);
  return validateLivingAnalysis(engine, await readJson(resolved), resolved);
}
