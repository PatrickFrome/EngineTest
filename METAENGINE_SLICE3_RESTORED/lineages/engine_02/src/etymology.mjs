import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { countIssues, issue, sortIssues } from "./issues.mjs";
import { projectPath } from "./paths.mjs";

const PASS_VERSION = "DAE-ETYMOLOGY-PASS-1.0";
const PROTOCOL_VERSION = "ETY-0.2";
const CLAIM_CEILING = "MANDATORY_ETYMOLOGICAL_SEMANTIC_COVERAGE_NOT_CONCEPTUAL_OR_ONTOLOGICAL_PROOF";
const PROJECT_REFS = ["config/etymology_registry.json", "vendor/protocol2x/etymology-0.2.md"];

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function slug(value, fallback = "CONCEPT") {
  const output = String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/gu, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/gu, "_")
    .replace(/^_+|_+$/gu, "")
    .slice(0, 72);
  return output || fallback;
}

function field(resolution, value, sourceRefs = []) {
  return {
    resolution,
    value: String(value),
    source_refs: [...new Set(sourceRefs)].sort(),
  };
}

function configuredField(value, fallback, sourceRefs = PROJECT_REFS) {
  return value
    ? field("PROVISIONAL_RECONSTRUCTION", value, sourceRefs)
    : field("UNRESOLVED", fallback, []);
}

function metadataField(value, fallback) {
  return value
    ? field("FIXED_PROJECT_METADATA", value, ["config/etymology_registry.json"])
    : field("UNRESOLVED", fallback, []);
}

function conceptIdsForHypothesis(registry, hypothesis) {
  const configured = registry.topic_concepts[hypothesis.topic_id] ?? [];
  const emergent = (hypothesis.emergent_terms ?? []).map((entry) => slug(entry)).filter(Boolean);
  if (configured.length || emergent.length) return [...new Set([...configured, ...emergent])];
  const groups = (hypothesis.matched_groups ?? []).map((entry) => slug(entry)).filter(Boolean);
  return groups.length ? groups.slice(0, 5) : [slug(hypothesis.label)];
}

function sourceFormForConcept(conceptId, hypotheses) {
  for (const hypothesis of hypotheses) {
    for (const term of hypothesis.emergent_terms ?? []) {
      if (slug(term) === slug(conceptId)) return term;
    }
  }
  return null;
}

function escalationReasons(registry, entry, hypotheses) {
  const reasons = [];
  if (entry?.full_required) reasons.push("REGISTRY_HIGH_CONCEPTUAL_LOAD");
  if (hypotheses.some((hypothesis) => ["SOURCE_FORCED_REGISTRY_RESISTANCE", "EXPLICIT_PROJECT_THESIS_CANDIDATE"].includes(hypothesis.origin))) reasons.push("SOURCE_FORCED_TERM_REQUIRES_FULL_CONTEXT_AUDIT");
  if (hypotheses.some((hypothesis) => hypothesis.ety_stress_request === true)) reasons.push("EXPLICIT_ETY_STRESS_REQUEST_REQUIRES_FULL_CONTEXT_AUDIT");
  if (hypotheses.some((hypothesis) => registry.full_topics.includes(hypothesis.topic_id))) reasons.push("TOPIC_REQUIRES_DIACHRONIC_TRANSLATION_OR_TECHNICAL_AUDIT");
  const text = hypotheses.map((hypothesis) => `${hypothesis.label} ${hypothesis.research_question}`).join(" ");
  if (/translation|перевод|diachron|диахрон|genealog|генеалог|ontolog|онтолог|technical|техник/iu.test(text)) reasons.push("QUESTION_ESCALATION_TRIGGER");
  return [...new Set(reasons)].sort();
}

function sourceBasis(hypotheses) {
  const selectors = [...new Set(hypotheses.flatMap((entry) => entry.evidence_segment_ids ?? []))];
  const selectorCount = hypotheses.reduce((sum, entry) => sum + (entry.evidence_count ?? entry.evidence_segment_ids?.length ?? 0), 0);
  return {
    hypothesis_ids: hypotheses.map((entry) => entry.hypothesis_id).sort(),
    selector_count: selectorCount,
    selectors: selectors.slice(0, 12),
    selectors_truncated: hypotheses.some((entry) => entry.selectors_truncated) || selectorCount > Math.min(12, selectors.length),
  };
}

function fullContours(entry, selectors) {
  const sourceRefs = [...PROJECT_REFS, ...selectors.slice(0, 3)];
  return {
    G_FORM: configuredField(
      [entry?.morphology, entry?.derivation].filter(Boolean).join(" "),
      "Form history, morphological changes, borrowings and earliest relevant attestations require an independent lexicographic source.",
      sourceRefs,
    ),
    G_SENSE: configuredField(
      [entry?.sense_range, entry?.semantic_drift].filter(Boolean).join(" Semantic-drift candidate: "),
      "Parallel historical sense branches have not been reconstructed.",
      sourceRefs,
    ),
    G_FUNCTION: configuredField(
      entry?.function,
      "The word's philosophical function across dated passages remains unresolved.",
      sourceRefs,
    ),
    G_CONTRAST: configuredField(
      entry?.contrasts ? `${entry.contrasts}. Semantic neighbours: ${entry.neighbors ?? "not resolved"}.` : null,
      "The active contrast field and semantic neighbours remain unresolved.",
      sourceRefs,
    ),
    G_TRANSLATION: configuredField(
      entry?.translations ? `${entry.translations}. Residual: ${entry.translation_residual ?? "must be tested locally"}.` : null,
      "Translation history, alternatives and residuals remain unresolved.",
      sourceRefs,
    ),
    ETY_AUTH: field(
      "UNRESOLVED",
      "Authorial etymologization and historically supported etymology have not yet been independently separated for the cited source spans.",
      selectors.slice(0, 3),
    ),
    COUNTER_ETYMOLOGY: configuredField(
      entry?.counter_line ?? "Test the same form with a different function and the same function under a different form.",
      "No counter-etymology has been articulated.",
      sourceRefs,
    ),
    PHENOMENOLOGICAL_CHECK: field(
      "UNRESOLVED",
      "No lexical distinction is promoted until the analysed phenomenon independently discriminates it.",
      selectors.slice(0, 3),
    ),
    BRIDGE_CHECK: field(
      "UNRESOLVED",
      "No etymology-to-concept or etymology-to-ontology bridge has been independently established.",
      selectors.slice(0, 3),
    ),
  };
}

function cardFor(conceptId, registry, hypotheses) {
  const entry = registry.concepts[conceptId] ?? null;
  const dynamicSourceForm = sourceFormForConcept(conceptId, hypotheses);
  const escalation = escalationReasons(registry, entry, hypotheses);
  const basis = sourceBasis(hypotheses);
  const sourceRefs = [...PROJECT_REFS, ...basis.selectors.slice(0, 3)];
  const gains = [];
  if (entry?.lost_distinction) gains.push("GG1_NEW_DISTINCTION");
  if (entry?.new_question) gains.push("GG2_NEW_QUESTION");
  if (entry?.counter_line) gains.push("GG3_NEW_RIVAL");
  return {
    card_id: `ETY-CARD-${slug(conceptId)}`,
    concept_id: slug(conceptId),
    topic_ids: [...new Set(hypotheses.map((entryHypothesis) => entryHypothesis.topic_id))].sort(),
    level: escalation.length ? "ETY-FULL" : "ETY-MIN",
    escalation_reasons: escalation,
    source_basis: basis,
    ety_min: {
      source_form: entry?.source_form
        ? metadataField(entry.source_form, "Source form unresolved.")
        : dynamicSourceForm
          ? field("PROVISIONAL_RECONSTRUCTION", dynamicSourceForm, basis.selectors.slice(0, 4))
          : metadataField(conceptId, "Source form unresolved."),
      language: metadataField(entry?.language, "Source language unresolved."),
      lemma: metadataField(entry?.lemma, "Lemma unresolved."),
      morphological_structure: configuredField(entry?.morphology, "Morphological segmentation has not been established.", sourceRefs),
      historical_derivation: configuredField(entry?.derivation, "Historical derivation and earliest relevant attestation require an independent lexicographic source.", sourceRefs),
      semantic_range: configuredField(entry?.sense_range, "Historical and synchronic sense range remains unresolved.", sourceRefs),
      local_sense: field("UNRESOLVED", "Local syntax and sense require direct inspection of the cited source spans; topic detection is insufficient.", basis.selectors.slice(0, 4)),
      philosophical_function: configuredField(entry?.function, "The local philosophical function remains unresolved.", sourceRefs),
      translations: configuredField(entry?.translations, "Standard, alternative and working translations remain unresolved.", sourceRefs),
      translation_residual: configuredField(entry?.translation_residual, "Translation loss has not yet been discriminated in the source context.", sourceRefs),
      etymological_risk: field("PROVISIONAL_RECONSTRUCTION", "Root fallacy, semantic anachronism, false cognate, translation collapse, selective etymology, authorial-etymology smuggling and etymology→ontology promotion remain active risks.", ["vendor/protocol2x/etymology-0.2.md"]),
    },
    ety_full: escalation.length ? fullContours(entry, basis.selectors) : null,
    anti_etymological_firewall: {
      origin_is_not_current_sense: true,
      earliest_is_not_truest: true,
      lexical_identity_is_not_conceptual_identity: true,
      authorial_wordplay_is_not_historical_linguistics: true,
      language_is_not_ontology: true,
    },
    generative_result: {
      lost_distinction: configuredField(entry?.lost_distinction, "No discriminating lost distinction has yet been established.", sourceRefs),
      semantic_drift: configuredField(entry?.semantic_drift, "No source-resolved semantic drift has yet been established.", sourceRefs),
      new_question: configuredField(entry?.new_question, "No etymologically generated philosophical question has yet been established.", sourceRefs),
      qualitative_gains: gains,
    },
    bridge: {
      candidate: null,
      independent_support: "NOT_ASSESSED",
      semantic_promotion_allowed: false,
    },
    revision_trigger: "Reopen the card when a dated primary occurrence, authoritative historical dictionary entry, translation witness or phenomenological contrast changes form, sense, function or the proposed bridge.",
  };
}

function countUnresolved(value) {
  if (Array.isArray(value)) return value.reduce((sum, entry) => sum + countUnresolved(entry), 0);
  if (!value || typeof value !== "object") return 0;
  return (value.resolution === "UNRESOLVED" ? 1 : 0) + Object.values(value).reduce((sum, entry) => sum + countUnresolved(entry), 0);
}

export function validateEtymologyPass(engine, pass, file = "<memory>") {
  const issues = [...engine.structural.validateEtymologyPass(pass)];
  const cards = pass?.cards ?? [];
  const ids = new Set();
  for (const card of cards) {
    if (ids.has(card.card_id)) issues.push(issue("ERROR", "ETY_DUPLICATE_CARD", "/cards", `Duplicate card ${card.card_id}.`));
    ids.add(card.card_id);
    if (card.level === "ETY-FULL" && !card.ety_full) issues.push(issue("ERROR", "ETY_FULL_CONTOURS_REQUIRED", "/cards", `${card.card_id} requires all nine ETY-FULL contours.`));
    if (card.level === "ETY-MIN" && card.ety_full !== null) issues.push(issue("ERROR", "ETY_MIN_CANNOT_IMPLY_FULL", "/cards", `${card.card_id} claims ETY-MIN but contains ETY-FULL.`));
    if (card.bridge?.semantic_promotion_allowed) issues.push(issue("ERROR", "ETY_SEMANTIC_PROMOTION_FORBIDDEN", "/cards", `${card.card_id} cannot promote etymology into a conceptual or ontological conclusion.`));
  }
  if (pass?.coverage?.cards_emitted !== cards.length || pass?.coverage?.central_concepts !== cards.length) issues.push(issue("ERROR", "ETY_COVERAGE_COUNT_MISMATCH", "/coverage", "Central concept and emitted card counts must match."));
  if (pass?.coverage?.ety_full_required !== cards.filter((card) => card.level === "ETY-FULL").length || pass?.coverage?.ety_full_executed !== cards.filter((card) => card.ety_full).length) issues.push(issue("ERROR", "ETY_FULL_COUNT_MISMATCH", "/coverage", "ETY-FULL required/executed counts do not match cards."));
  const sorted = sortIssues(issues);
  const counts = countIssues(sorted);
  return { file, conformant: counts.ERROR === 0, counts, issues: sorted };
}

export async function buildEtymologyPass(engine, refineryDirectory, options = {}) {
  const refineryRoot = path.resolve(refineryDirectory);
  const registryFile = projectPath("config", "etymology_registry.json");
  const reportFile = path.join(refineryRoot, "REFINERY_REPORT.json");
  const hypothesisFile = path.join(refineryRoot, "hypothesis_bank.json");
  const [registryBytes, reportBytes, hypothesisBytes] = await Promise.all([
    readFile(registryFile), readFile(reportFile), readFile(hypothesisFile),
  ]);
  const registry = JSON.parse(registryBytes.toString("utf8"));
  const report = JSON.parse(reportBytes.toString("utf8"));
  const hypothesisBank = JSON.parse(hypothesisBytes.toString("utf8"));
  const bankIssues = engine.structural.validateHypothesisBank(hypothesisBank);
  if (bankIssues.length) throw new Error(`ETY_HYPOTHESIS_BANK_INVALID: ${JSON.stringify(bankIssues, null, 2)}`);
  const associations = new Map();
  for (const hypothesis of hypothesisBank.hypotheses) {
    for (const conceptId of conceptIdsForHypothesis(registry, hypothesis)) {
      const normalized = slug(conceptId);
      if (!associations.has(normalized)) associations.set(normalized, []);
      associations.get(normalized).push(hypothesis);
    }
  }
  for (const term of hypothesisBank.source_resistance?.explicit_stress_terms ?? []) {
    const normalized = slug(term);
    if (!normalized) continue;
    const pseudoHypothesis = {
      hypothesis_id: `HYP-ETY-STRESS-${normalized}`,
      topic_id: "ETY_STRESS_REQUEST",
      label: `Mandatory ETY stress term: ${term}`,
      research_question: `What local, historical and translational distinctions are lost if ${term} is treated as semantically transparent?`,
      matched_groups: ["ETY_STRESS_REQUEST"],
      evidence_segment_ids: [],
      evidence_count: 0,
      selectors_truncated: false,
      emergent_terms: [term],
      ety_stress_request: true,
    };
    if (!associations.has(normalized)) associations.set(normalized, []);
    associations.get(normalized).push(pseudoHypothesis);
  }
  if (!associations.size && Array.isArray(options.conceptHints)) {
    for (const hint of options.conceptHints) {
      const topicId = hint.topic_id ?? hint.thesis_id ?? "EXPERT_PROFILE_CONCEPT";
      const pseudoHypothesis = {
        hypothesis_id: `HYP-ETY-PROFILE-${slug(hint.thesis_id ?? topicId)}`,
        topic_id: topicId,
        label: hint.title ?? hint.statement ?? topicId,
        research_question: hint.statement ?? hint.title ?? topicId,
        matched_groups: [hint.title ?? topicId],
        evidence_segment_ids: [],
        evidence_count: 0,
        selectors_truncated: false,
      };
      for (const conceptId of conceptIdsForHypothesis(registry, pseudoHypothesis)) {
        const normalized = slug(conceptId);
        if (!associations.has(normalized)) associations.set(normalized, []);
        associations.get(normalized).push(pseudoHypothesis);
      }
    }
  }
  if (!associations.size) throw new Error("ETY_REQUIRES_AT_LEAST_ONE_CENTRAL_CONCEPT");
  const cards = [...associations.entries()].map(([conceptId, hypotheses]) => cardFor(conceptId, registry, hypotheses)).sort((left, right) => left.card_id.localeCompare(right.card_id));
  const unresolvedFields = countUnresolved(cards);
  const generatedAt = String(options.generatedAt ?? new Date().toISOString());
  const runDigest = sha256([report.source_id, report.artifact_sha256, sha256(hypothesisBytes), sha256(registryBytes)].join("|"));
  const pass = {
    pass_version: PASS_VERSION,
    protocol_version: PROTOCOL_VERSION,
    engine_version: engine.context.engineVersion,
    generated_at: generatedAt,
    run_id: `ETY-${slug(report.source_id, "SOURCE")}-${runDigest.slice(0, 12).toUpperCase()}`,
    source: {
      source_id: report.source_id,
      artifact_sha256: report.artifact_sha256,
      hypothesis_bank_sha256: sha256(hypothesisBytes),
      raw_source_included: false,
    },
    registry: {
      registry_version: registry.registry_version,
      sha256: sha256(registryBytes),
      source_note: registry.source_note,
    },
    cards,
    coverage: {
      central_concepts: cards.length,
      cards_emitted: cards.length,
      ety_min_executed: cards.length,
      ety_full_required: cards.filter((card) => card.level === "ETY-FULL").length,
      ety_full_executed: cards.filter((card) => card.ety_full).length,
      coverage_complete: true,
      unresolved_fields: unresolvedFields,
      knowledge_resolution: unresolvedFields ? "PARTIAL" : "LEXICOGRAPHICALLY_SOURCED",
      interpretation: "Coverage is complete because every central concept received ETY-MIN and every escalated concept received all ETY-FULL contours. This does not mean that unresolved historical, local or phenomenological fields have been answered.",
    },
    output_contract: {
      mandatory_execution: true,
      mandatory_significance: false,
      local_context_precedes_origin: true,
      authorial_etymology_separated: true,
      counter_etymology_required_for_full: true,
      phenomenological_check_required_for_full: true,
      bridge_required_for_semantic_promotion: true,
      semantic_promotion_performed: false,
      null_result_is_valid: true,
      raw_source_included: false,
    },
    claim_ceiling: CLAIM_CEILING,
  };
  const validation = validateEtymologyPass(engine, pass);
  if (!validation.conformant) throw new Error(`ETYMOLOGY_PASS_INVALID: ${JSON.stringify(validation.issues, null, 2)}`);
  const bytes = Buffer.from(`${JSON.stringify(pass, null, 2)}\n`, "utf8");
  return { pass, validation, bytes, sha256: sha256(bytes), markdown: renderEtymologyMarkdown(pass) };
}

export function renderEtymologyMarkdown(pass) {
  const lines = [
    "# Обязательный этимолого-семантический проход ETY-0.2",
    "",
    "> Проверка обязательна; философская значимость не обязательна. Происхождение слова не является его актуальным смыслом, а язык не является онтологическим доказательством.",
    "",
    `Центральных понятий: **${pass.coverage.central_concepts}**; ETY-FULL: **${pass.coverage.ety_full_executed}**; неразрешённых полей: **${pass.coverage.unresolved_fields}**. Knowledge resolution: **${pass.coverage.knowledge_resolution}**.`,
    "",
  ];
  for (const card of pass.cards) {
    lines.push(`## ${card.ety_min.source_form.value} — ${card.level}`, "", `Темы: ${card.topic_ids.map((topic) => `\`${topic}\``).join(", ")}.`, "");
    lines.push(`- Лемма / язык: ${card.ety_min.lemma.value} / ${card.ety_min.language.value}.`);
    lines.push(`- Историческая деривация: ${card.ety_min.historical_derivation.value}`);
    lines.push(`- Семантический диапазон: ${card.ety_min.semantic_range.value}`);
    lines.push(`- Локальное значение: ${card.ety_min.local_sense.value}`);
    lines.push(`- Философская функция: ${card.ety_min.philosophical_function.value}`);
    lines.push(`- Перевод / residual: ${card.ety_min.translations.value} ${card.ety_min.translation_residual.value}`);
    lines.push(`- Lost distinction: ${card.generative_result.lost_distinction.value}`);
    lines.push(`- Semantic drift: ${card.generative_result.semantic_drift.value}`);
    lines.push(`- New question: ${card.generative_result.new_question.value}`);
    lines.push(`- Предел: ${card.ety_min.etymological_risk.value}`, "");
  }
  lines.push("## Итоговый firewall", "", "Ни одна карточка не разрешает etymology→concept или etymology→ontology promotion. Для этого необходим независимый bridge, локальный контекст и феноменологический/исторический контроль.", "", `Claim ceiling: \`${pass.claim_ceiling}\`.`, "");
  return `${lines.join("\n")}\n`;
}

export async function runEtymologyProtocol(engine, refineryDirectory, outputDirectory, options = {}) {
  const outputDir = path.resolve(outputDirectory);
  const result = await buildEtymologyPass(engine, refineryDirectory, options);
  await mkdir(outputDir, { recursive: false });
  const files = {
    pass: path.join(outputDir, "etymology_pass.json"),
    analytics: path.join(outputDir, "ETYMOLOGICAL_ANALYSIS.md"),
  };
  await Promise.all([
    writeFile(files.pass, result.bytes),
    writeFile(files.analytics, result.markdown, "utf8"),
  ]);
  return { output_dir: outputDir, ...result, files };
}

export async function validateEtymologyPassFile(engine, filePath) {
  const resolved = path.resolve(filePath);
  return validateEtymologyPass(engine, JSON.parse(await readFile(resolved, "utf8")), resolved);
}
