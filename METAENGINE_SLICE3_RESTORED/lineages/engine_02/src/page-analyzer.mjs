import { createHash } from "node:crypto";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { detectRelationCandidates, languageHints } from "./analyzer.mjs";
import { readJson } from "./paths.mjs";

const DISCOURSE_RULES = [
  ["QUESTION", /\?/u],
  ["CONCLUSION", /(?<![\p{L}\p{N}_])(?:therefore|thus|hence|следовательно|отсюда|somit|mithin|daher|folglich|dem vorstehenden zufolge|erhellt|ersichtlich)(?![\p{L}\p{N}_])/iu],
  ["CONTRAST", /(?<![\p{L}\p{N}_])(?:but|however|yet|но|однако|aber|jedoch|allein|demgegenüber|hingegen)(?![\p{L}\p{N}_])/iu],
  ["CONCESSION", /(?<![\p{L}\p{N}_])(?:although|admittedly|хотя|правда|zwar|freilich|desungeachtet|mögen)(?![\p{L}\p{N}_])/iu],
  ["EVIDENCE", /(?<![\p{L}\p{N}_])(?:evidence|fact|experience|shows?|данн\p{L}*|факт\p{L}*|опыт\p{L}*|показыва\p{L}*|tatsache\p{L}*|erfahrung\p{L}*|zeigt|zeigen|offenbar(?:t|en))(?![\p{L}\p{N}_])/iu],
  ["LIMIT", /(?<![\p{L}\p{N}_])(?:only|not yet|incomplete|только|ещ[её] не|неполн\p{L}*|nur|noch nichts|ideal(?:es|e|er)? ziel|nicht ohne weiteres)(?![\p{L}\p{N}_])/iu],
  ["PROGRAM", /(?<![\p{L}\p{N}_])(?:problem|question|task|aim|проблем\p{L}*|вопрос\p{L}*|задач\p{L}*|цель\p{L}*|problem\p{L}*|frage\p{L}*|aufgabe\p{L}*|ziel\p{L}*)(?![\p{L}\p{N}_])/iu],
  ["ATTRIBUTION", /(?<![\p{L}\p{N}_])(?:writes?|argues?|according to|пишет|утверждает|по мнению|schreibt|behauptet|nach ihm|nach Külpe)(?![\p{L}\p{N}_])/iu],
];

const TERM_RULES = [
  ["REALITY", /(?<![\p{L}\p{N}_])(?:Realität(?:en)?|Realen|Reale|Reales)(?![\p{L}\p{N}_])/gu],
  ["REALISM", /(?<![\p{L}\p{N}_])(?:Realismus|realistisch(?:e[rmns]?)?)(?![\p{L}\p{N}_])/giu],
  ["POSITING", /(?<![\p{L}\p{N}_])(?:Setzung|setzen|gesetzt(?:e[rmns]?)?)(?![\p{L}\p{N}_])/giu],
  ["DETERMINATION", /(?<![\p{L}\p{N}_])(?:Bestimmung|bestimmen|bestimmt(?:e[rmns]?)?)(?![\p{L}\p{N}_])/giu],
  ["CONSCIOUSNESS", /(?<![\p{L}\p{N}_])Bewusst\p{L}*(?![\p{L}\p{N}_])/giu],
  ["EXPERIENCE", /(?<![\p{L}\p{N}_])Erfahrung\p{L}*(?![\p{L}\p{N}_])/giu],
  ["THINKING", /(?<![\p{L}\p{N}_])(?:Denken|Denk\p{L}*|gedacht)(?![\p{L}\p{N}_])/giu],
  ["SCIENCE", /(?<![\p{L}\p{N}_])(?:Wissenschaft\p{L}*|Naturwissenschaft\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["CONSCIENTIALISM", /(?<![\p{L}\p{N}_])Konszientialismus(?![\p{L}\p{N}_])/giu],
  ["PHENOMENALISM", /(?<![\p{L}\p{N}_])Phänomenalismus(?![\p{L}\p{N}_])/giu],
  ["BEING_NOUN", /(?<![\p{L}\p{N}_])Sein(?:s)?(?![\p{L}\p{N}_])/gu],
  ["DASEIN", /(?<![\p{L}\p{N}_])Dasein(?![\p{L}\p{N}_])/gu],
  ["TEMPORALITY", /(?<![\p{L}\p{N}_])Zeitlichkeit(?![\p{L}\p{N}_])/gu],
];

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function compactId(value) {
  return value.normalize("NFKD").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toUpperCase().slice(0, 48) || "SOURCE";
}

function issueSummary(issues) {
  return issues.map((item) => `${item.code} ${item.at}: ${item.message}`).join("; ");
}

async function requireNewDirectory(outputDir) {
  try {
    await stat(outputDir);
    throw new Error(`Output directory already exists: ${outputDir}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

function compileDropPatterns(manifest) {
  return (manifest.structure?.drop_line_patterns ?? []).map((source) => new RegExp(source, "iu"));
}

function joinHyphenated(lines) {
  let output = "";
  for (const original of lines) {
    const line = original.trim().replace(/\u00ad/gu, "");
    if (!line) continue;
    if (!output) {
      output = line;
      continue;
    }
    if (/[-‐‑]$/u.test(output) && /^\p{Ll}/u.test(line)) output = `${output.slice(0, -1)}${line}`;
    else output += ` ${line}`;
  }
  return output.normalize("NFC").replace(/\s+/gu, " ").trim();
}

function blockZone(text, firstLine) {
  if (/^(?:[IVX]+\.|\d+\.)$/u.test(text) || (text.length < 120 && /(?:PHILOSOPHIE|REALITÄTSPROBLEM)$/u.test(text))) return "HEADING";
  if (/^(?:\*+\)|\d+\)|\d+\s*\)|[¹²³⁴⁵⁶⁷⁸⁹⁰])/u.test(firstLine.trim())) return "NOTE";
  return "BODY";
}

function pageBlocks(pageText, dropPatterns) {
  const lines = pageText.replace(/\r\n?/gu, "\n").split("\n");
  const blocks = [];
  let current = [];
  let startLine = 1;

  function flush(endLine) {
    if (!current.length) return;
    const text = joinHyphenated(current.map((item) => item.text));
    if (text) blocks.push({ line_start: startLine, line_end: endLine, text, zone: blockZone(text, current[0].text) });
    current = [];
  }

  for (let index = 0; index < lines.length; index += 1) {
    const lineNumber = index + 1;
    const line = lines[index];
    if (dropPatterns.some((pattern) => pattern.test(line))) {
      flush(lineNumber - 1);
      continue;
    }
    const startsNote = /^(?:\s*)(?:\*+\)|\d+\)|\d+\s*\))/u.test(line);
    if (startsNote && current.length) flush(lineNumber - 1);
    if (!line.trim()) {
      flush(lineNumber - 1);
      continue;
    }
    if (!current.length) startLine = lineNumber;
    current.push({ text: line });
  }
  flush(lines.length);
  return blocks;
}

function sentenceUnits(block, locale, baseOffset) {
  if (block.zone === "HEADING") return [{ text: block.text, start: baseOffset, end: baseOffset + block.text.length }];
  const segmenter = new Intl.Segmenter(locale, { granularity: "sentence" });
  return [...segmenter.segment(block.text)]
    .map((entry) => ({ text: entry.segment.trim(), start: baseOffset + entry.index, end: baseOffset + entry.index + entry.segment.length }))
    .filter((entry) => entry.text.length > 1);
}

function detectDiscourseFeatures(text) {
  return DISCOURSE_RULES.filter(([, regex]) => regex.test(text)).map(([id]) => id);
}

function countTerms(text) {
  return Object.fromEntries(TERM_RULES.map(([id, regex]) => [id, [...text.matchAll(regex)].length]));
}

function makeSafeRecord({ baseId, index, unit, sourceId, sourceHash, timestamp }) {
  const candidates = unit.relation_candidates;
  const pivot = candidates[0];
  const ambiguous = candidates.length > 1;
  const rtId = ambiguous ? "RT00" : pivot.rt_id;
  const activated = ["O0", "O1", "O4", "O9", ...(ambiguous ? ["O6"] : [])];
  const relationList = candidates.map((candidate) => `${candidate.rt_id} ('${candidate.signal}')`).join(", ");
  const locator = `${sourceId}#page=${unit.page_label}&start=${unit.selector.start}&end=${unit.selector.end}`;
  const spanDescription = `Source-side span at ${locator}; source wording is omitted under the derivative-only output policy.`;
  return {
    record_id: `${baseId}-PAGED-AUTO-${String(index + 1).padStart(3, "0")}`,
    api_version: "TRC-0.3",
    profile: "ANALYTIC",
    provenance: {
      source_refs: [locator],
      method_version: "CORE 4.0.0-alpha.1 + DAE-PAGED-LEXICAL-CANDIDATE-0.4",
      agent: "dae-page-aware-lexical-candidate-generator",
      activity_id: `${baseId}-PAGED-INTAKE`,
      timestamp,
      artifact_hash: `sha256:${sourceHash}`
    },
    from_node: {
      node_id: "A",
      kind: "CLAIM",
      description: spanDescription,
      claim_facets: { basis: ["TXT"], force: "HYPOTHETICAL", normativity: "UNRESOLVED" },
      support_refs: [locator]
    },
    to_node: {
      node_id: "B",
      kind: "CLAIM",
      description: `Unresolved target-side span following the candidate signal at ${locator}.`,
      claim_facets: { basis: ["TXT"], force: "HYPOTHETICAL", normativity: "UNRESOLVED" },
      support_refs: [locator]
    },
    transition: {
      inference_mode: rtId === "RT06" ? "CAUSAL" : "UNRESOLVED",
      relation: { rt_id: rtId },
      bridge: {
        status: "UNRESOLVED",
        statement: `Lexical candidate ${relationList} at ${locator}; expressive source context is intentionally not copied into the output.`,
        support_refs: [locator],
        discriminator: "Inspect the authorized source locally; test the frozen relation definition, direction, modality and strongest live rival."
      }
    },
    scale_check: { applicable: false },
    audit: {
      native_domain: "HISTORY_OF_PHILOSOPHY_AND_TEXTUAL_SCHOLARSHIP",
      native_method: "Page-resolved source criticism plus lexical candidate generation",
      activated_operators: activated,
      trv: ambiguous ? ["OPACITY", "UNDERDETERMINATION"] : ["OPACITY"],
      ncv: [],
      rtr: "HIGH",
      cost_note: "Derivative-only automatic candidate; source inspection and philosophical adjudication remain mandatory."
    },
    ...(ambiguous ? {
      rivals: candidates.map((candidate) => ({
        description: `Lexical candidate ${candidate.rt_id} triggered by '${candidate.signal}'.`,
        relation_rt_id: candidate.rt_id,
        bridge: "Not yet established.",
        discriminator: "Adjudicate modality and relation function in the authorized local source span."
      }))
    } : {}),
    extensions: {
      audit_semantics: {
        schema_version: "0.1",
        transition_role: "INFERENCE_AUDIT",
        relation_applies_to: "TRANSITION",
        relation_rationale: `Page-aware automatic candidates: ${relationList}. The text itself is not redistributed and no candidate is semantic gold.`,
        semantic_review_status: "STRUCTURAL_ONLY",
        human_review_required: true,
        review_notes: [
          "Open the authorized source at the printed-page selector and reconstruct A, P and B.",
          "Separate a mentioned modal or normative word from the operative relation.",
          "Do not promote journal pagination or an edition crosswalk into philosophical evidence."
        ]
      }
    },
    outcome: "DEFER",
    open_questions: [
      "Are the page-bounded relata correct?",
      "Which relation, if any, survives source, bridge, modality and rival review?"
    ]
  };
}

export async function analyzePagedText(engine, inputFile, manifestFile, outputDir, options = {}) {
  const input = path.resolve(inputFile);
  const manifestPath = path.resolve(manifestFile);
  const out = path.resolve(outputDir);
  await requireNewDirectory(out);

  const manifest = await readJson(manifestPath);
  const manifestIssues = engine.structural.validateSourceManifest(manifest);
  if (manifestIssues.length) throw new Error(`Invalid source manifest: ${issueSummary(manifestIssues)}`);
  const contentBoundLocalSource = /^LOCAL-SHA256-[A-F0-9]{64}$/u.test(manifest.source_id);
  if (!engine.context.sourceCatalog.sources[manifest.source_id] && !contentBoundLocalSource) {
    throw new Error(`Source '${manifest.source_id}' is absent from config/source_catalog.json and is not a content-bound LOCAL-SHA256 source.`);
  }
  if (manifest.access_policy.analysis_class === "REFERENCE_ONLY" || !manifest.access_policy.allow_derived_outputs) {
    throw new Error(`SOURCE_POLICY_BLOCK: ${manifest.source_id} permits reference use only; page analysis was not executed.`);
  }
  if (manifest.access_policy.analysis_class === "DERIVATIVE_ONLY" && manifest.access_policy.raw_text_retention !== "TRANSIENT") {
    throw new Error("SOURCE_POLICY_BLOCK: DERIVATIVE_ONLY input must use TRANSIENT raw-text retention.");
  }

  const bytes = await readFile(input);
  const inputHash = sha256(bytes);
  if (bytes.length !== manifest.extracted_text.byte_length) throw new Error(`SOURCE_FIXITY_MISMATCH: expected ${manifest.extracted_text.byte_length} bytes, received ${bytes.length}.`);
  if (inputHash !== manifest.extracted_text.sha256) throw new Error(`SOURCE_FIXITY_MISMATCH: expected sha256:${manifest.extracted_text.sha256}, received sha256:${inputHash}.`);

  const rawText = bytes.toString("utf8");
  const pages = rawText.split("\f");
  if (!pages.at(-1)?.trim()) pages.pop();
  if (pages.length !== manifest.pagination.labels.length) {
    throw new Error(`PAGE_COUNT_MISMATCH: manifest has ${manifest.pagination.labels.length} labels, extraction has ${pages.length} pages.`);
  }

  const dropPatterns = compileDropPatterns(manifest);
  const analyzeNotes = manifest.structure?.analyze_notes ?? false;
  const locale = manifest.bibliographic.language;
  const baseId = compactId(manifest.source_id);
  const timestamp = options.generatedAt ?? new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
  const allUnits = [];
  const pageSummaries = [];

  for (let pageIndex = 0; pageIndex < pages.length; pageIndex += 1) {
    const pageLabel = manifest.pagination.labels[pageIndex];
    const blocks = pageBlocks(pages[pageIndex], dropPatterns);
    let pageOffset = 0;
    let unitOrdinal = 0;
    const zoneCounts = { BODY: 0, NOTE: 0, HEADING: 0 };
    for (const [blockIndex, block] of blocks.entries()) {
      zoneCounts[block.zone] += 1;
      const units = sentenceUnits(block, locale, pageOffset);
      for (const sentence of units) {
        unitOrdinal += 1;
        const candidates = block.zone === "NOTE" && !analyzeNotes ? [] : detectRelationCandidates(sentence.text);
        allUnits.push({
          unit_id: `${baseId}-P${pageLabel}-U${String(unitOrdinal).padStart(3, "0")}`,
          page_label: pageLabel,
          page_index: pageIndex,
          block_index: blockIndex,
          line_start: block.line_start,
          line_end: block.line_end,
          zone: block.zone,
          selector: {
            type: "TextPositionSelector",
            start: sentence.start,
            end: sentence.end,
            coordinate_space: "NORMALIZED_PAGE_TEXT"
          },
          char_length: sentence.text.length,
          normalized_sha256: sha256(sentence.text),
          discourse_features: detectDiscourseFeatures(sentence.text),
          relation_candidates: candidates
        });
      }
      pageOffset += block.text.length + 2;
    }
    pageSummaries.push({
      page_label: pageLabel,
      source_page_sha256: sha256(pages[pageIndex]),
      block_count: blocks.length,
      unit_count: allUnits.filter((unit) => unit.page_index === pageIndex).length,
      zone_counts: zoneCounts
    });
  }

  const candidateUnits = allUnits.filter((unit) => unit.relation_candidates.length);
  await mkdir(path.join(out, "records"), { recursive: true });
  const recordFiles = [];
  const selectedRelationCounts = {};
  for (const [index, unit] of candidateUnits.entries()) {
    const record = makeSafeRecord({ baseId, index, unit, sourceId: manifest.source_id, sourceHash: inputHash, timestamp });
    selectedRelationCounts[record.transition.relation.rt_id] = (selectedRelationCounts[record.transition.relation.rt_id] ?? 0) + 1;
    const file = path.join(out, "records", `${record.record_id}.json`);
    await writeFile(file, `${JSON.stringify(record, null, 2)}\n`, "utf8");
    recordFiles.push(file);
    unit.record_id = record.record_id;
  }
  const validation = await engine.validateInputs(recordFiles.length ? [path.join(out, "records")] : []);
  const relationCounts = {};
  const discourseCounts = {};
  for (const unit of candidateUnits) {
    for (const candidate of unit.relation_candidates) relationCounts[candidate.rt_id] = (relationCounts[candidate.rt_id] ?? 0) + 1;
  }
  for (const unit of allUnits) {
    for (const feature of unit.discourse_features) discourseCounts[feature] = (discourseCounts[feature] ?? 0) + 1;
  }
  const pageTermCounts = Object.fromEntries(pages.map((pageText, pageIndex) => [manifest.pagination.labels[pageIndex], countTerms(pageText)]));
  const totalTermCounts = Object.fromEntries(TERM_RULES.map(([id]) => [id, Object.values(pageTermCounts).reduce((sum, page) => sum + page[id], 0)]));

  const unitsWithoutText = allUnits.map(({ ...unit }) => unit);
  const bundle = {
    bundle_version: "DAE-PAGED-INTAKE-0.2",
    generated_at: timestamp,
    source: {
      source_id: manifest.source_id,
      manifest_path: path.basename(manifestPath),
      input_path_scope: "BASENAME_ONLY",
      input_basename: path.basename(input),
      extracted_text_byte_length: bytes.length,
      extracted_text_sha256: inputHash,
      original_artifact: manifest.artifact,
      bibliographic: manifest.bibliographic,
      crosswalk: manifest.crosswalk,
      pagination: manifest.pagination
    },
    access_policy: manifest.access_policy,
    method: "TEI_PAGE_BREAK_AND_W3C_WEB_ANNOTATION_INSPIRED_POSITION_SELECTORS_PLUS_DE_RU_EN_LEXICAL_CANDIDATES",
    method_version: "DAE-PAGED-LEXICAL-CANDIDATE-0.4",
    language_hints: languageHints(rawText),
    raw_text_included: false,
    expressive_context_included: false,
    claim_ceiling: "PAGE_RESOLVED_DERIVATIVE_CANDIDATES_ONLY_NOT_SOURCE_TEXT_OR_INTERPRETATION",
    page_count: pages.length,
    unit_count: allUnits.length,
    candidate_unit_count: candidateUnits.length,
    candidate_record_count: recordFiles.length,
    ambiguous_unit_count: candidateUnits.filter((unit) => unit.relation_candidates.length > 1).length,
    relation_candidate_counts: Object.fromEntries(Object.entries(relationCounts).sort(([left], [right]) => left.localeCompare(right))),
    selected_record_relation_counts: Object.fromEntries(Object.entries(selectedRelationCounts).sort(([left], [right]) => left.localeCompare(right))),
    discourse_feature_counts: Object.fromEntries(Object.entries(discourseCounts).sort(([left], [right]) => left.localeCompare(right))),
    term_index: {
      claim_ceiling: "LEXICAL_DISTRIBUTION_ONLY_NOT_CONCEPTUAL_OR_ONTOLOGICAL_STATUS",
      lexicon_scope: "GERMAN_FORMS_ONLY_IN_0.4",
      totals: totalTermCounts,
      by_page: pageTermCounts
    },
    pages: pageSummaries,
    units: unitsWithoutText,
    validation: validation.counts
  };
  await writeFile(path.join(out, "analysis_bundle.json"), `${JSON.stringify(bundle, null, 2)}\n`, "utf8");
  return { output_dir: out, bundle, validation };
}
