import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { parseOoxmlParagraphs } from "../../src/corpus-refinery.mjs";

const execFileAsync = promisify(execFile);

function count(text, regex) {
  return [...String(text ?? "").matchAll(regex)].length;
}

function mergeCounts(...records) {
  const out = {};
  for (const record of records) {
    for (const [key, value] of Object.entries(record)) out[key] = (out[key] ?? 0) + value;
  }
  return out;
}

const RELATION_SIGNALS = [
  ["DIFFERENTIAL", /(?<![\p{L}\p{N}_])(?:difference|différence|differen[cz]\p{L}*|unterschied\p{L}*|различ\p{L}*|opposition\p{L}*|gegenüber|контраст\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["REFERENCE_RELATIVE", /(?<![\p{L}\p{N}_])(?:relation\p{L}*|relative|relatif|rapport\p{L}*|reference|référence|bezug|verhältnis|отнош\p{L}*|соотнош\p{L}*|связ\p{L}*|comparison|comparaison|vergleich)(?![\p{L}\p{N}_])/giu],
  ["SYSTEM_FIELD", /(?<![\p{L}\p{N}_])(?:system\p{L}*|système|struktur\p{L}*|structure|ensemble|whole|field|totality|систем\p{L}*|структур\p{L}*|целост\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["ASYMMETRIC_DEPENDENCE", /(?<![\p{L}\p{N}_])(?:depend\p{L}*|conceived\s+through|in\s+another|present\s+in\s+a\s+subject|predicat\p{L}*|dépend\p{L}*|abhäng\p{L}*|завис\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["RECIPROCITY_GATHERING", /(?<![\p{L}\p{N}_])(?:recipro\p{L}*|mutual\p{L}*|co[- ]?constit\p{L}*|gather\p{L}*|versamm\p{L}*|belong\p{L}*|zusammengehör\p{L}*|zueinander|взаим\p{L}*|соопредел\p{L}*|собира\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["DISTANCE_DIFFERENTIATION", /(?<![\p{L}\p{N}_])(?:near(?:ness)?|proximity|distance|far(?:ness)?|nähe|näher\p{L}*|ferne|fern\p{L}*|proche|proximité|loin|близ\p{L}*|даль\p{L}*|дистанц\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["PRIORITY", /(?<![\p{L}\p{N}_])(?:priority|prior\s+to|primary|first|vorrang|ursprüng\p{L}*|первич\p{L}*|приоритет\p{L}*)(?![\p{L}\p{N}_])/giu],
];

const PROCESSUAL_SIGNALS = [
  ["TEMPORALITY", /(?<![\p{L}\p{N}_])(?:temporal\p{L}*|temporality|chronolog\p{L}*|present|future|past|before|after|now|later|sequence|kairolog\p{L}*|zeit\p{L}*|gegenwart|zukunft|vergangen\p{L}*|врем\p{L}*|настоящ\p{L}*|будущ\p{L}*|прошл\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["EXPECTATION", /(?<![\p{L}\p{N}_])(?:expect\p{L}*|wait\p{L}*|await\p{L}*|anticipat\p{L}*|arrival|deferral|defer\p{L}*|hope|erwart\p{L}*|warten\p{L}*|ankunft|aufschub|ожидан\p{L}*|ждат\p{L}*|предвосхищ\p{L}*|надежд\p{L}*|отсроч\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["ENACTMENT_PRACTICE", /(?<![\p{L}\p{N}_])(?:enact\p{L}*|practice|practical|conduct|doing|perform\p{L}*|ritual|gesture\p{L}*|praxis|vollzug\p{L}*|verhalten|handlung\p{L}*|практик\p{L}*|действ\p{L}*|исполн\p{L}*|поведен\p{L}*|ритуал\p{L}*|жест\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["REPETITION_RHYTHM", /(?<![\p{L}\p{N}_])(?:repeat\p{L}*|repetition|habit\p{L}*|rhythm\p{L}*|recurr\p{L}*|wiederhol\p{L}*|rhythmus|gewohn\p{L}*|повтор\p{L}*|ритм\p{L}*|привыч\p{L}*|возвращ\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["MATERIAL_MEDIATION", /(?<![\p{L}\p{N}_])(?:material\p{L}*|bod\p{L}*|corporeal|spatial|place|artifact\p{L}*|object\p{L}*|medium|media|mediat\p{L}*|vermittel\p{L}*|körper\p{L}*|leib\p{L}*|raum\p{L}*|ort\p{L}*|материал\p{L}*|телес\p{L}*|простран\p{L}*|мест\p{L}*|артефакт\p{L}*|объект\p{L}*|посред\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["ABSENCE_WITHDRAWAL", /(?<![\p{L}\p{N}_])(?:absence|absent|withdraw\p{L}*|disappear\p{L}*|missing|non[- ]?availability|hiddenness|conceal\p{L}*|abwesen\p{L}*|entzug\p{L}*|verborgen\p{L}*|отсутств\p{L}*|ускольз\p{L}*|сокры\p{L}*|исчез\p{L}*|недоступ\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["TRACE_DISCLOSURE", /(?<![\p{L}\p{N}_])(?:trace\p{L}*|hint\p{L}*|indicat\p{L}*|disclos\p{L}*|show\p{L}*|manifest\p{L}*|spur\p{L}*|anzeig\p{L}*|zeig\p{L}*|offenbar\p{L}*|след\p{L}*|нам[её]к\p{L}*|указ\p{L}*|раскрыв\p{L}*|показыв\p{L}*|прояв\p{L}*)(?![\p{L}\p{N}_])/giu],
  ["ADDRESS_RESPONSE", /(?<![\p{L}\p{N}_])(?:address\p{L}*|call|calling|response|respond\p{L}*|answer\p{L}*|being[- ]called|anspruch\p{L}*|ruf\p{L}*|antwort\p{L}*|обращ\p{L}*|зов\p{L}*|призыв\p{L}*|ответ\p{L}*)(?![\p{L}\p{N}_])/giu],
];

function signalCounts(text, registry) {
  return Object.fromEntries(registry.map(([name, regex]) => [name, count(text, regex)]));
}

export function profileInterrogativeTexts(texts) {
  const joined = (texts ?? []).join("\n");
  const relation = signalCounts(joined, RELATION_SIGNALS);
  const processual = signalCounts(joined, PROCESSUAL_SIGNALS);
  const signal_counts = mergeCounts(relation, processual);
  const active_signal_families = Object.entries(signal_counts).filter(([, n]) => n > 0).map(([k]) => k);

  const relationHints = [];
  if (relation.DIFFERENTIAL > 0 && relation.SYSTEM_FIELD > 0) relationHints.push("DIFFERENTIAL_CONSTITUTION");
  if (relation.ASYMMETRIC_DEPENDENCE > 0 && relation.PRIORITY > 0) relationHints.push("ASYMMETRIC_DEPENDENCE");
  if (relation.RECIPROCITY_GATHERING > 0) relationHints.push("CO_CONSTITUTIVE_OR_RECIPROCAL");
  if (relation.DISTANCE_DIFFERENTIATION > 0) relationHints.push("DIFFERENCE_PRESERVING_PROXIMITY");
  if (relation.REFERENCE_RELATIVE > 0 && relation.ASYMMETRIC_DEPENDENCE > 0) relationHints.push("LOCAL_MODE_VARIATION");

  const processualHints = [];
  if (processual.TEMPORALITY > 0 && (processual.EXPECTATION > 0 || processual.ENACTMENT_PRACTICE > 0)) processualHints.push("TEMPORAL_ENACTMENT");
  if (processual.ENACTMENT_PRACTICE > 0 && (processual.REPETITION_RHYTHM > 0 || processual.MATERIAL_MEDIATION > 0)) processualHints.push("PRACTICE_MEDIATION");
  if (processual.ABSENCE_WITHDRAWAL > 0 && processual.TRACE_DISCLOSURE > 0) processualHints.push("ABSENCE_DISCLOSURE");
  if (processual.ADDRESS_RESPONSE > 0 && processual.ENACTMENT_PRACTICE > 0) processualHints.push("RESPONSIVE_ENACTMENT");

  let operator_family = "GENERIC_SOURCE_FORCED_REVISION";
  let source_operator_candidate = "SOURCE_FORCED_TOPIC_AND_OPERATOR_CANDIDATE";
  if (relationHints.length && processualHints.length) {
    operator_family = "MULTI_FAMILY_LOCAL_PROFILE";
    source_operator_candidate = "MULTI_FAMILY_LOCAL_OPERATOR_ECOLOGY";
  } else if (processualHints.length) {
    operator_family = "PROCESSUAL_HERMENEUTIC_PROFILE";
    source_operator_candidate = "PROCESSUAL_HERMENEUTIC_FAMILY_CANDIDATE";
  } else if (relationHints.length) {
    operator_family = "RELATION_GENESIS_PROFILE";
    source_operator_candidate = "RELATION_GENESIS_PROFILE_WITH_CO_EMERGENT_RELATA_CANDIDATE";
  }

  return {
    source_operator_candidate,
    operator_family,
    active_signal_families,
    signal_counts,
    profile_hints: [...new Set([...relationHints, ...processualHints])],
    relation_profile_hints: relationHints,
    processual_profile_hints: processualHints,
    claim_ceiling: processualHints.length
      ? "REPRESENTATION_TEST_CANDIDATE_NOT_PROCESS_ONTOLOGY"
      : "REPRESENTATION_TEST_CANDIDATE_NOT_SOURCE_ONTOLOGY",
  };
}

export async function readDocxSegments(docxFile, options = {}) {
  const { stdout } = await execFileAsync("unzip", ["-p", docxFile, "word/document.xml"], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  return parseOoxmlParagraphs(stdout, { documentLanguage: options.documentLanguage ?? "und" }).segments;
}

export function headingBoundedWindows(segments, config = {}) {
  const includeLayers = new Set(config.include_layers ?? ["SOURCE"]);
  const headingLevel = Number(config.heading_level ?? 1);
  const minimumTextChars = Number(config.minimum_text_chars ?? 30);
  const maxParagraphs = Number(config.maximum_window_paragraphs ?? 8);
  const windows = [];
  let current = null;

  for (const segment of segments) {
    if (segment.zone === "HEADING" && Number(segment.heading_level ?? 0) === headingLevel) {
      if (current) windows.push(current);
      current = {
        heading: segment._text,
        heading_segment_id: segment.segment_id,
        paragraphs: [],
      };
      continue;
    }
    if (!current) continue;
    if (current.paragraphs.length >= maxParagraphs) continue;
    if (segment.archive_state !== "ACTIVE") continue;
    if (!includeLayers.has(segment.layer_routing?.label)) continue;
    if (String(segment._text ?? "").trim().length < minimumTextChars) continue;
    current.paragraphs.push(segment);
  }
  if (current) windows.push(current);

  return windows
    .filter((window) => window.paragraphs.length)
    .map((window, index) => {
      const profile = profileInterrogativeTexts(window.paragraphs.map((p) => p._text));
      const layerCounts = {};
      for (const p of window.paragraphs) layerCounts[p.layer_routing.label] = (layerCounts[p.layer_routing.label] ?? 0) + 1;
      return {
        window_id: `MW-${String(index + 1).padStart(3, "0")}`,
        heading: window.heading,
        heading_segment_id: window.heading_segment_id,
        ordinal_start: window.paragraphs[0].ordinal,
        ordinal_end: window.paragraphs.at(-1).ordinal,
        paragraph_segment_ids: window.paragraphs.map((p) => p.segment_id),
        paragraph_hashes: window.paragraphs.map((p) => p.normalized_sha256),
        layer_counts: layerCounts,
        ...profile,
        unserved_signal_families: [],
      };
    });
}

export { RELATION_SIGNALS, PROCESSUAL_SIGNALS };
