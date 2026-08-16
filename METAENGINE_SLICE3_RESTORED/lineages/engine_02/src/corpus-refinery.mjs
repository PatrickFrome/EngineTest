import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { detectRelationCandidates, languageHints } from "./analyzer.mjs";
import { analyzeDocx } from "./docx-intake.mjs";
import { projectPath, readJson } from "./paths.mjs";
import { detectSourceResistance } from "./source-resistance.mjs";

const execFileAsync = promisify(execFile);

const LAYERS = ["SOURCE", "RECONSTRUCTION", "PROJECT_CLAIM", "RIVAL_OBJECTION", "PROTOCOL_TOOL_LOG", "UNRESOLVED"];
const SCORED_LAYERS = LAYERS.filter((layer) => layer !== "UNRESOLVED");
const MAX_SELECTORS = 200;

const DISCOURSE_RULES = [
  ["QUESTION", /\?/u],
  ["CONCLUSION", /(?<![\p{L}\p{N}_])(?:следовательно|итак|отсюда|вывод|therefore|thus|hence|somit|mithin|folglich)(?![\p{L}\p{N}_])/iu],
  ["CONTRAST", /(?<![\p{L}\p{N}_])(?:но|однако|впрочем|напротив|but|however|yet|aber|jedoch|hingegen)(?![\p{L}\p{N}_])/iu],
  ["ATTRIBUTION", /(?<![\p{L}\p{N}_])(?:пишет|утверждает|считает|по мнению|according to|writes?|argues?|schreibt|behauptet|nach ihm)(?![\p{L}\p{N}_])/iu],
  ["PROGRAM", /(?<![\p{L}\p{N}_])(?:задача|цель|этап|далее|проверим|question|task|aim|next|Aufgabe|Ziel)(?![\p{L}\p{N}_])/iu],
  ["OBJECTION", /(?<![\p{L}\p{N}_])(?:возражени\p{L}*|контраргумент\p{L}*|опровержени\p{L}*|objection|counterargument|Einwand|Gegenargument)(?![\p{L}\p{N}_])/iu],
  ["LIMIT", /(?<![\p{L}\p{N}_])(?:только|пока|не установлено|не доказано|only|not established|not proven|nur|nicht erwiesen)(?![\p{L}\p{N}_])/iu],
];

const LAYER_SIGNALS = [
  { code: "INTERACTION_NEXT_STAGE", layer: "PROTOCOL_TOOL_LOG", weight: 8, regex: /перейд[её]м к следующему этапу/iu },
  { code: "SEARCH_COMPLETED_NOTICE", layer: "PROTOCOL_TOOL_LOG", weight: 8, regex: /поиск выполнен/iu },
  { code: "GUIDE_READ_NOTICE", layer: "PROTOCOL_TOOL_LOG", weight: 8, regex: /изучено руководство/iu },
  { code: "TOOL_STATUS_TOKEN", layer: "PROTOCOL_TOOL_LOG", weight: 3, regex: /(?<![\p{L}\p{N}_])(?:PASS|FAIL|SUSPEND|REVIEW|ERROR)(?![\p{L}\p{N}_])/u },
  { code: "PROTOCOL_LEXEME", layer: "PROTOCOL_TOOL_LOG", weight: 3, regex: /(?<![\p{L}\p{N}_])(?:протокол\p{L}*|protocol\p{L}*|gate|шлюз\p{L}*)(?![\p{L}\p{N}_])/iu },
  { code: "STEP_OR_COMMAND", layer: "PROTOCOL_TOOL_LOG", weight: 2, regex: /^(?:шаг|этап|команда|запуск|результат запуска|step|stage|command|run)\b/iu },
  { code: "JSON_OR_CODE_SHAPE", layer: "PROTOCOL_TOOL_LOG", weight: 4, regex: /^\s*(?:\{|\[\]|```|"[A-Za-z0-9_.-]+"\s*:)/u },
  { code: "QUOTE_STYLE", layer: "SOURCE", weight: 4, styleRegex: /(?:Quote|Citation|BlockText|Цитат)/iu },
  { code: "DIRECT_QUOTE_MARKS", layer: "SOURCE", weight: 1.5, regex: /(?:«[^»]{20,}»|„[^“]{20,}“|"[^"]{20,}")/u },
  { code: "EDITION_LOCATOR", layer: "SOURCE", weight: 2, regex: /(?<![\p{L}\p{N}_])(?:GA\s*\d{1,3}|S\.?\s*\d{1,4}|p{1,2}\.?\s*\d{1,4}|стр\.?\s*\d{1,4})(?![\p{L}\p{N}_])/iu },
  { code: "CITATION_MARKER", layer: "SOURCE", weight: 2, regex: /\[[^\]\n]{2,180}\]/u },
  { code: "BIBLIOGRAPHIC_SHAPE", layer: "SOURCE", weight: 2, regex: /(?:doi:\s*10\.|https?:\/\/|\b(?:19|20)\d{2}\b[^\n]{0,80}\b(?:pp?\.|S\.|стр\.)\s*\d+)/iu },
  { code: "SOURCE_AUTHOR_NAME", layer: "SOURCE", weight: 1, regex: /(?<![\p{L}\p{N}_])(?:Heidegger|Хайдеггер|Husserl|Гуссерль|Kant|Кант|Külpe|Кюльпе|Lotze|Лотце|Rickert|Риккерт)(?![\p{L}\p{N}_])/iu },
  { code: "ATTRIBUTION_FORM", layer: "RECONSTRUCTION", weight: 3, regex: /(?<![\p{L}\p{N}_])(?:пишет|утверждает|полагает|считает|по мнению|у Хайдеггера|в тексте|автор|writes?|argues?|according to|schreibt|behauptet|der Text)(?![\p{L}\p{N}_])/iu },
  { code: "RECONSTRUCTION_LEXEME", layer: "RECONSTRUCTION", weight: 3, regex: /(?<![\p{L}\p{N}_])(?:реконструкц\p{L}*|реконструир\p{L}*|посылк\p{L}*|ход аргумент\p{L}*|reconstruct\p{L}*|Prämisse\p{L}*)(?![\p{L}\p{N}_])/iu },
  { code: "INTERPRETIVE_FORM", layer: "RECONSTRUCTION", weight: 1.5, regex: /(?<![\p{L}\p{N}_])(?:это означает|можно понять|следует читать|интерпретир\p{L}*|this means|can be read|ist zu verstehen)(?![\p{L}\p{N}_])/iu },
  { code: "PROJECT_SELF_REFERENCE", layer: "PROJECT_CLAIM", weight: 4, regex: /(?<![\p{L}\p{N}_])(?:наш проект|в проекте|движок|DAE|Destruktion|наша модель|наш метод)(?![\p{L}\p{N}_])/iu },
  { code: "FIRST_PERSON_PLURAL", layer: "PROJECT_CLAIM", weight: 1.5, regex: /(?<![\p{L}\p{N}_])(?:мы|предлагаем|введ[её]м|зафиксируем|различим|we|we propose|wir)(?![\p{L}\p{N}_])/iu },
  { code: "PROJECT_DECISION", layer: "PROJECT_CLAIM", weight: 2.5, regex: /(?<![\p{L}\p{N}_])(?:принимаем|сохраняем|исключаем|маркируем|будем считать|решение проекта|adopt|retain|exclude)(?![\p{L}\p{N}_])/iu },
  { code: "STRONG_CONCLUSION", layer: "PROJECT_CLAIM", weight: 1, regex: /(?<![\p{L}\p{N}_])(?:следовательно|итак|вывод|тем самым|therefore|thus|somit|folglich)(?![\p{L}\p{N}_])/iu },
  { code: "OBJECTION_LEXEME", layer: "RIVAL_OBJECTION", weight: 5, regex: /(?<![\p{L}\p{N}_])(?:возражени\p{L}*|контраргумент\p{L}*|оппонент\p{L}*|объекци\p{L}*|objection|counterargument|Einwand|Gegenargument)(?![\p{L}\p{N}_])/iu },
  { code: "RIVAL_LEXEME", layer: "RIVAL_OBJECTION", weight: 4, regex: /(?<![\p{L}\p{N}_])(?:rival|альтернатив\p{L}*|конкурирующ\p{L}*|соперничающ\p{L}*|Alternative|Gegenposition)(?![\p{L}\p{N}_])/iu },
  { code: "CRITIQUE_LEXEME", layer: "RIVAL_OBJECTION", weight: 2.5, regex: /(?<![\p{L}\p{N}_])(?:критик\p{L}*|ошибк\p{L}*|слабое место|не выдерживает|problematic|fails?|Kritik|Fehler)(?![\p{L}\p{N}_])/iu },
  { code: "CONTRAST_FORM", layer: "RIVAL_OBJECTION", weight: 1, regex: /(?<![\p{L}\p{N}_])(?:однако|напротив|но|however|but|hingegen|jedoch)(?![\p{L}\p{N}_])/iu },
];

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function normalizedText(value) {
  return value.normalize("NFKC").toLocaleLowerCase("ru").replace(/\s+/gu, " ").trim();
}

function decodeXml(value) {
  return value
    .replace(/&#x([0-9a-f]+);/giu, (_, hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
    .replace(/&#([0-9]+);/gu, (_, decimal) => String.fromCodePoint(Number(decimal)))
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", "\"")
    .replaceAll("&apos;", "'")
    .replaceAll("&amp;", "&");
}

function countMatches(text, regex) {
  return [...text.matchAll(regex)].length;
}

function tokenList(text) {
  return [...text.matchAll(/[\p{L}\p{N}][\p{L}\p{N}\p{M}'’‐‑-]*/gu)].map((match) => match[0].toLocaleLowerCase("ru"));
}

function discourseFeatures(text) {
  return DISCOURSE_RULES.filter(([, regex]) => regex.test(text)).map(([code]) => code);
}

function tableIntervals(documentXml) {
  const intervals = [];
  const stack = [];
  for (const match of documentXml.matchAll(/<\/?w:tbl(?:\s[^>]*)?>/gu)) {
    if (match[0].startsWith("</")) {
      const start = stack.pop();
      if (start !== undefined) intervals.push([start, match.index + match[0].length]);
    } else {
      stack.push(match.index);
    }
  }
  return intervals.sort((left, right) => left[0] - right[0]);
}

function headingLevel(style) {
  if (!style) return null;
  const match = style.match(/(?:Heading|Заголовок)[ _-]?([1-6])/iu);
  if (match) return Number(match[1]);
  if (/^(?:Title|Заглавие)$/iu.test(style)) return 1;
  return null;
}

function languageProfile(text) {
  const cyrillic = countMatches(text, /\p{Script=Cyrillic}/gu);
  const latin = countMatches(text, /\p{Script=Latin}/gu);
  const markers = Object.fromEntries(languageHints(text).map((item) => [item.language, item.marker_count]));
  const de = markers.DE ?? 0;
  const ru = markers.RU ?? 0;
  const en = markers.EN ?? 0;
  let dominant = "UNRESOLVED";
  const ranked = [["DE", de], ["RU", ru], ["EN", en]].sort((a, b) => b[1] - a[1]);
  if (ranked[0][1] >= 2 && ranked[0][1] >= Math.max(1, ranked[1][1] * 1.5)) dominant = ranked[0][0];
  else if (cyrillic > latin * 2 && cyrillic >= 8) dominant = "RU";
  else if (latin > cyrillic * 2 && latin >= 8 && ranked[0][1]) dominant = ranked[0][0];
  else if (cyrillic + latin > 0) dominant = "MIXED";
  return { dominant, cyrillic_letters: cyrillic, latin_letters: latin, de_markers: de, ru_markers: ru, en_markers: en };
}

export function routeCorpusLayer(text, metadata = {}) {
  const scores = Object.fromEntries(SCORED_LAYERS.map((layer) => [layer, 0]));
  const signals = [];
  for (const signal of LAYER_SIGNALS) {
    const matched = signal.regex?.test(text) || signal.styleRegex?.test(metadata.style ?? "");
    if (!matched) continue;
    scores[signal.layer] += signal.weight;
    signals.push(signal.code);
  }
  if (metadata.language_profile?.dominant === "DE" && metadata.document_language?.startsWith("ru")) {
    scores.SOURCE += 2;
    signals.push("FOREIGN_LANGUAGE_PASSAGE");
  }
  if (metadata.zone === "HEADING") {
    if (/возраж|контраргумент|rival|objection|Einwand/iu.test(text)) {
      scores.RIVAL_OBJECTION += 3;
      signals.push("RIVAL_HEADING");
    }
    if (/реконструк|interpretation|Rekonstruktion/iu.test(text)) {
      scores.RECONSTRUCTION += 3;
      signals.push("RECONSTRUCTION_HEADING");
    }
    if (/протокол|этап|шаг|protocol|stage/iu.test(text)) {
      scores.PROTOCOL_TOOL_LOG += 3;
      signals.push("PROTOCOL_HEADING");
    }
  }
  if (!text.trim()) {
    return { label: "UNRESOLVED", status: "EMPTY", routing_confidence: 0, score_margin: 0, scores, signals: [], review_required: false };
  }
  const ranked = Object.entries(scores).sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
  const [topLayer, topScore] = ranked[0];
  const secondScore = ranked[1][1];
  const margin = Number((topScore - secondScore).toFixed(3));
  const confidence = topScore ? Number((topScore / (topScore + secondScore + 2)).toFixed(6)) : 0;
  let status = "AMBIGUOUS";
  let label = "UNRESOLVED";
  if (topScore >= 3 && margin >= 2) {
    status = "ROUTED";
    label = topLayer;
  } else if (topScore >= 2 && margin >= 1) {
    status = "TENTATIVE";
    label = topLayer;
  }
  return {
    label,
    status,
    routing_confidence: confidence,
    score_margin: Math.max(0, margin),
    scores: Object.fromEntries(SCORED_LAYERS.map((layer) => [layer, Number(scores[layer].toFixed(3))])),
    signals: [...new Set(signals)].sort(),
    review_required: label !== "PROTOCOL_TOOL_LOG",
  };
}

function formulaBlocks(paragraphBody) {
  const blocks = [];
  const occupied = [];
  for (const match of paragraphBody.matchAll(/<m:oMathPara(?:\s[^>]*)?>([\s\S]*?)<\/m:oMathPara>/gu)) {
    blocks.push({ xml: match[0], index: match.index });
    occupied.push([match.index, match.index + match[0].length]);
  }
  for (const match of paragraphBody.matchAll(/<m:oMath(?:\s[^>]*)?>([\s\S]*?)<\/m:oMath>/gu)) {
    if (occupied.some(([start, end]) => match.index >= start && match.index < end)) continue;
    blocks.push({ xml: match[0], index: match.index });
  }
  return blocks.sort((left, right) => left.index - right.index);
}

function formulaFacts(xml) {
  const text = [...xml.matchAll(/<m:t(?:\s[^>]*)?>([\s\S]*?)<\/m:t>/gu)].map((match) => decodeXml(match[1])).join("").normalize("NFC");
  const normalized = normalizedText(text);
  return {
    omml_sha256: sha256(xml),
    normalized_text_sha256: sha256(normalized),
    character_length: text.length,
    math_text_runs: countMatches(xml, /<m:t(?:\s|>)/gu),
    structure_counts: {
      fraction: countMatches(xml, /<m:f(?:\s|>)/gu),
      superscript: countMatches(xml, /<m:sSup(?:\s|>)/gu),
      subscript: countMatches(xml, /<m:sSub(?:\s|>)/gu),
      radical: countMatches(xml, /<m:rad(?:\s|>)/gu),
      nary: countMatches(xml, /<m:nary(?:\s|>)/gu),
      matrix: countMatches(xml, /<m:m(?:\s|>)/gu),
    },
  };
}

export function parseOoxmlParagraphs(documentXml, options = {}) {
  const intervals = tableIntervals(documentXml);
  const raw = [];
  let intervalIndex = 0;
  for (const match of documentXml.matchAll(/<w:p(?:\s[^>]*)?>([\s\S]*?)<\/w:p>/gu)) {
    while (intervalIndex < intervals.length && intervals[intervalIndex][1] < match.index) intervalIndex += 1;
    const body = match[1];
    const pieces = [...body.matchAll(/<(?:w|m):t(?:\s[^>]*)?>([\s\S]*?)<\/(?:w|m):t>/gu)].map((item) => decodeXml(item[1]));
    const text = pieces.join("").normalize("NFC");
    const normalized = normalizedText(text);
    const style = body.match(/<w:pStyle\b[^>]*w:val="([^"]+)"/u)?.[1] ?? null;
    const level = headingLevel(style);
    const inTable = intervalIndex < intervals.length && match.index >= intervals[intervalIndex][0] && match.index < intervals[intervalIndex][1];
    const formulas = formulaBlocks(body).map((formula) => ({ ...formulaFacts(formula.xml), _xml: formula.xml }));
    let zone = "BODY";
    if (!normalized) zone = formulas.length ? "FORMULA_ONLY" : "EMPTY";
    else if (level) zone = "HEADING";
    else if (inTable) zone = "TABLE";
    const ordinal = raw.length + 1;
    const hash = sha256(normalized);
    const segmentId = `OX-P${String(ordinal).padStart(6, "0")}-${hash.slice(0, 10).toUpperCase()}`;
    const language = languageProfile(text);
    const relationCandidates = detectRelationCandidates(text).map((candidate) => ({ rt_id: candidate.rt_id, signal_class: candidate.signal_class }));
    raw.push({
      segment_id: segmentId,
      ordinal,
      selector: {
        type: "OoxmlParagraphSelector",
        part: "word/document.xml",
        paragraph_ordinal: ordinal,
        normalized_sha256: hash,
      },
      normalized_sha256: hash,
      char_length: text.length,
      token_count: tokenList(text).length,
      style,
      zone,
      heading_level: level,
      language_profile: language,
      discourse_features: discourseFeatures(text),
      relation_candidates: relationCandidates,
      hyperlink_count: countMatches(body, /<w:hyperlink(?:\s|>)/gu),
      layer_routing: routeCorpusLayer(text, { style, zone, language_profile: language, document_language: options.documentLanguage ?? "und" }),
      _text: text,
      _normalized: normalized,
      _formulas: formulas,
    });
  }
  const headingStack = [];
  const formulas = [];
  for (const segment of raw) {
    if (segment.heading_level) {
      headingStack.length = segment.heading_level - 1;
      headingStack[segment.heading_level - 1] = segment.segment_id;
      segment.heading_path = headingStack.filter(Boolean);
    } else {
      segment.heading_path = headingStack.filter(Boolean);
    }
    segment.formula_ids = segment._formulas.map((formula, index) => {
      const formulaId = `OMML-F${String(segment.ordinal).padStart(6, "0")}-${String(index + 1).padStart(3, "0")}-${formula.omml_sha256.slice(0, 10).toUpperCase()}`;
      formulas.push({
        formula_id: formulaId,
        paragraph_segment_id: segment.segment_id,
        ordinal_in_paragraph: index + 1,
        omml_sha256: formula.omml_sha256,
        normalized_text_sha256: formula.normalized_text_sha256,
        character_length: formula.character_length,
        math_text_runs: formula.math_text_runs,
        structure_counts: formula.structure_counts,
      });
      return formulaId;
    });
    segment.duplicate_cluster_id = null;
    segment.near_duplicate_cluster_id = null;
    segment.archive_state = "ACTIVE";
  }
  return { segments: raw, formulas };
}

function fnv1a32(value, seed = 2166136261) {
  let hash = seed >>> 0;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash >>> 0;
}

function shingles(text) {
  const tokens = tokenList(text).filter((token) => token.length > 1).slice(0, 320);
  if (tokens.length < 4) return new Set();
  const size = tokens.length >= 8 ? 3 : 2;
  const output = new Set();
  for (let index = 0; index <= tokens.length - size; index += 1) output.add(tokens.slice(index, index + size).join("\u241f"));
  return output;
}

function minhashSignature(features) {
  const seeds = [2166136261, 2747636419, 2654435761, 2246822519, 3266489917, 668265263, 374761393, 1274126177];
  const signature = seeds.map(() => 0xffffffff);
  for (const feature of features) {
    for (let index = 0; index < seeds.length; index += 1) signature[index] = Math.min(signature[index], fnv1a32(feature, seeds[index]));
  }
  return signature;
}

function jaccard(left, right) {
  let intersection = 0;
  for (const item of left) if (right.has(item)) intersection += 1;
  return intersection / (left.size + right.size - intersection);
}

class UnionFind {
  constructor(size) {
    this.parent = Array.from({ length: size }, (_, index) => index);
  }
  find(value) {
    if (this.parent[value] !== value) this.parent[value] = this.find(this.parent[value]);
    return this.parent[value];
  }
  union(left, right) {
    const a = this.find(left);
    const b = this.find(right);
    if (a !== b) this.parent[Math.max(a, b)] = Math.min(a, b);
  }
}

export function findDuplicateClusters(segments, options = {}) {
  const nearThreshold = options.nearThreshold ?? 0.72;
  const exactMap = new Map();
  for (const segment of segments) {
    if (segment.char_length < 20 || !segment._normalized) continue;
    if (!exactMap.has(segment.normalized_sha256)) exactMap.set(segment.normalized_sha256, []);
    exactMap.get(segment.normalized_sha256).push(segment);
  }
  const exact = [];
  const canonical = [];
  const exactNonRepresentatives = new Set();
  for (const [hash, members] of exactMap) {
    members.sort((left, right) => left.ordinal - right.ordinal);
    canonical.push(members[0]);
    if (members.length < 2) continue;
    const clusterId = `EXD-${hash.slice(0, 12).toUpperCase()}`;
    for (const member of members) member.duplicate_cluster_id = clusterId;
    for (const member of members.slice(1)) {
      member.archive_state = "ARCHIVED_EXACT_DUPLICATE";
      exactNonRepresentatives.add(member.segment_id);
    }
    exact.push({
      cluster_id: clusterId,
      representative_segment_id: members[0].segment_id,
      member_segment_ids: members.map((member) => member.segment_id),
      member_count: members.length,
      basis: "EXACT_NORMALIZED_SHA256",
      minimum_pair_similarity: 1,
      human_review_required: false,
    });
  }
  const eligible = canonical.filter((segment) => segment.char_length >= 60 && segment.token_count >= 8 && segment.archive_state === "ACTIVE");
  const featureSets = eligible.map((segment) => shingles(segment._normalized));
  const signatures = featureSets.map(minhashSignature);
  const buckets = new Map();
  for (let index = 0; index < eligible.length; index += 1) {
    for (let band = 0; band < 4; band += 1) {
      const key = `${band}:${signatures[index][band * 2]}:${signatures[index][band * 2 + 1]}`;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(index);
    }
  }
  const pairKeys = new Set();
  for (const bucket of buckets.values()) {
    if (bucket.length < 2 || bucket.length > 200) continue;
    for (let left = 0; left < bucket.length; left += 1) {
      for (let right = left + 1; right < bucket.length; right += 1) {
        const a = Math.min(bucket[left], bucket[right]);
        const b = Math.max(bucket[left], bucket[right]);
        pairKeys.add(`${a}:${b}`);
      }
    }
  }
  const union = new UnionFind(eligible.length);
  const accepted = [];
  for (const key of pairKeys) {
    const [left, right] = key.split(":").map(Number);
    const lengthRatio = Math.min(eligible[left].char_length, eligible[right].char_length) / Math.max(eligible[left].char_length, eligible[right].char_length);
    if (lengthRatio < 0.65) continue;
    const similarity = jaccard(featureSets[left], featureSets[right]);
    if (similarity < nearThreshold) continue;
    union.union(left, right);
    accepted.push({ left, right, similarity });
  }
  const components = new Map();
  for (let index = 0; index < eligible.length; index += 1) {
    const root = union.find(index);
    if (!components.has(root)) components.set(root, []);
    components.get(root).push(index);
  }
  const near = [];
  for (const indices of components.values()) {
    if (indices.length < 2) continue;
    const members = indices.map((index) => eligible[index]).sort((left, right) => left.ordinal - right.ordinal);
    const clusterId = `NEARD-${sha256(members.map((member) => member.segment_id).join("|")).slice(0, 12).toUpperCase()}`;
    for (const member of members) member.near_duplicate_cluster_id = clusterId;
    const indexSet = new Set(indices);
    const similarities = accepted.filter((edge) => indexSet.has(edge.left) && indexSet.has(edge.right)).map((edge) => edge.similarity);
    near.push({
      cluster_id: clusterId,
      representative_segment_id: members[0].segment_id,
      member_segment_ids: members.map((member) => member.segment_id),
      member_count: members.length,
      basis: "MINHASH_SHINGLE_JACCARD_CANDIDATE",
      minimum_pair_similarity: Number(Math.min(...similarities).toFixed(6)),
      human_review_required: true,
    });
  }
  return { exact, near, exactNonRepresentatives };
}

function scaleCandidate(text) {
  if (/(?<![\p{L}\p{N}_])(?:всегда|всё|все|любой|универсаль\p{L}*|без исключения|all|every|always|universal|jeder|immer|überhaupt)(?![\p{L}\p{N}_])/iu.test(text)) return "UNIVERSAL";
  if (/(?<![\p{L}\p{N}_])(?:эпох\p{L}*|эпохаль\p{L}*|Neuzeit|abendländisch|Geschichte des Seins|epochal)(?![\p{L}\p{N}_])/iu.test(text)) return "EPOCHAL";
  if (/(?<![\p{L}\p{N}_])(?:ранн\p{L}*|поздн\p{L}*|диахрон\p{L}*|развити\p{L}*|переход\p{L}*|Frühwerk|Spätwerk|diachronic)(?![\p{L}\p{N}_])/iu.test(text) && /(?:Heidegger|Хайдеггер|GA\s*\d)/iu.test(text)) return "DIACHRONIC";
  if (/(?<![\p{L}\p{N}_])(?:GA\s*\d{1,3}|работ\p{L}*|текст\p{L}*|сочинени\p{L}*|work|text|Werk)(?![\p{L}\p{N}_])/iu.test(text)) return "WORK";
  return text.trim() ? "LOCAL" : "UNRESOLVED";
}

function claimTypeFor(group, features) {
  if (group.dominant_layer === "PROTOCOL_TOOL_LOG") return "PROTOCOL_ACTIVITY";
  if (group.dominant_layer === "RIVAL_OBJECTION" || features.includes("OBJECTION")) return "OBJECTION";
  if (features.includes("QUESTION")) return "QUESTION";
  if (features.includes("CONCLUSION")) return "CONCLUSION";
  if (group.dominant_layer === "SOURCE") return "SOURCE_PASSAGE";
  if (group.dominant_layer === "RECONSTRUCTION") return "RECONSTRUCTION";
  if (group.dominant_layer === "PROJECT_CLAIM") return "PROJECT_ASSERTION";
  if (group.relation_candidates.length || features.some((feature) => ["ATTRIBUTION", "PROGRAM", "LIMIT"].includes(feature)) || group.char_length >= 240) return "UNRESOLVED_ASSERTION";
  return "CONTEXT";
}

export function buildArgumentSegments(segments) {
  const output = [];
  let current = [];
  function flush() {
    if (!current.length) return;
    const text = current.map((segment) => segment._text).join(" ").replace(/\s+/gu, " ").trim();
    if (!text) {
      current = [];
      return;
    }
    const layerCounts = new Map();
    for (const segment of current) layerCounts.set(segment.layer_routing.label, (layerCounts.get(segment.layer_routing.label) ?? 0) + 1);
    const dominantLayer = [...layerCounts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))[0][0];
    const statuses = current.map((segment) => segment.layer_routing.status).filter((status) => status !== "EMPTY");
    const routingStatus = statuses.includes("AMBIGUOUS") ? "AMBIGUOUS" : statuses.includes("TENTATIVE") ? "TENTATIVE" : "ROUTED";
    const features = [...new Set(current.flatMap((segment) => segment.discourse_features))].sort();
    const relationCandidates = [...new Set(current.flatMap((segment) => segment.relation_candidates.map((candidate) => candidate.rt_id)))].sort();
    const normalized = normalizedText(text);
    const hash = sha256(normalized);
    const index = output.length + 1;
    const archiveState = current.every((segment) => segment.archive_state === "ARCHIVED_TOOL_LOG")
      ? "ARCHIVED_TOOL_LOG"
      : current.every((segment) => segment.archive_state === "ARCHIVED_EXACT_DUPLICATE")
        ? "ARCHIVED_EXACT_DUPLICATE"
        : "ACTIVE";
    const group = {
      argument_segment_id: `AR-U${String(index).padStart(6, "0")}-${hash.slice(0, 10).toUpperCase()}`,
      member_segment_ids: current.map((segment) => segment.segment_id),
      heading_path: current[0].heading_path,
      normalized_sha256: hash,
      char_length: text.length,
      dominant_layer: dominantLayer,
      routing_status: routingStatus,
      claim_type: null,
      scale_candidate: scaleCandidate(text),
      discourse_features: features,
      relation_candidates: relationCandidates,
      archive_state: archiveState,
      _routing_confidence: Number((current.reduce((sum, segment) => sum + segment.layer_routing.routing_confidence, 0) / current.length).toFixed(6)),
      _basis_signals: [...new Set(current.flatMap((segment) => segment.layer_routing.signals))].sort(),
    };
    group.claim_type = claimTypeFor(group, features);
    output.push(group);
    current = [];
  }
  for (const segment of segments) {
    if (segment.zone === "EMPTY" || segment.zone === "HEADING") {
      flush();
      continue;
    }
    if (segment.layer_routing.label === "PROTOCOL_TOOL_LOG" && segment.layer_routing.status !== "AMBIGUOUS" && segment.archive_state === "ACTIVE") {
      segment.archive_state = "ARCHIVED_TOOL_LOG";
    }
    const boundaryFeature = segment.discourse_features.some((feature) => ["QUESTION", "CONCLUSION", "OBJECTION"].includes(feature));
    const first = current[0];
    const compatible = !first || (
      JSON.stringify(first.heading_path) === JSON.stringify(segment.heading_path)
      && first.layer_routing.label === segment.layer_routing.label
      && first.archive_state === segment.archive_state
      && current.length < 6
      && current.reduce((sum, item) => sum + item.char_length, 0) + segment.char_length <= 2000
      && !boundaryFeature
      && !current.some((item) => item.discourse_features.some((feature) => ["QUESTION", "CONCLUSION", "OBJECTION"].includes(feature)))
    );
    if (!compatible) flush();
    current.push(segment);
    if (boundaryFeature || segment.layer_routing.label === "PROTOCOL_TOOL_LOG") flush();
  }
  flush();
  return output;
}

function buildClaimLedger(argumentSegments, artifactHash, generatedAt) {
  return argumentSegments
    .filter((segment) => segment.claim_type !== "CONTEXT")
    .map((segment) => ({
      claim_id: `CLM-${artifactHash.slice(0, 8).toUpperCase()}-${segment.argument_segment_id}`,
      selector: {
        argument_segment_id: segment.argument_segment_id,
        member_segment_ids: segment.member_segment_ids,
        normalized_sha256: segment.normalized_sha256,
      },
      origin: {
        candidate_layer: segment.dominant_layer,
        routing_status: segment.routing_status,
        routing_confidence: segment._routing_confidence,
        human_attested: false,
      },
      claim_type: segment.claim_type,
      scale: segment.scale_candidate,
      apb: { A: null, P: null, B: null, status: "NOT_RECONSTRUCTED" },
      rt_candidates: segment.relation_candidates,
      operative_relation_status: "UNADJUDICATED",
      strongest_rival: null,
      revision_condition: "Open the authorized source at every member selector; identify origin, reconstruct A/P/B, distinguish an operative relation from a mentioned relation, and test the strongest live rival.",
      status: segment.archive_state === "ARCHIVED_TOOL_LOG" ? "ARCHIVED_TOOL_LOG" : segment.archive_state === "ARCHIVED_EXACT_DUPLICATE" ? "ARCHIVED_DUPLICATE" : "UNADJUDICATED",
      replaces: [],
      supersedes: [],
      depends_on: [],
      decision_history: [{ event: "MACHINE_ROUTED_FOR_REVIEW", timestamp: generatedAt, agent: "dae-corpus-refinery", basis: segment._basis_signals }],
      claim_ceiling: "CLAIM_CANDIDATE_WITHOUT_APB_RECONSTRUCTION_OR_SEMANTIC_PROMOTION",
    }));
}

function compilePatterns(patterns) {
  return patterns.map((source) => new RegExp(source, "iu"));
}

export function buildHypothesisBankFromSegments(segments, topicRegistry, metadata) {
  const hypotheses = [];
  for (const topic of topicRegistry.topics) {
    const groups = [];
    const allSelectors = new Set();
    for (const group of topic.groups) {
      const patterns = compilePatterns(group.patterns);
      const selectors = segments.filter((segment) => segment._text && patterns.some((pattern) => pattern.test(segment._text))).map((segment) => segment.segment_id);
      if (!selectors.length) continue;
      groups.push(group.group_id);
      for (const selector of selectors) allSelectors.add(selector);
    }
    if (groups.length < topic.minimum_distinct_groups || !allSelectors.size) continue;
    const selectors = [...allSelectors];
    hypotheses.push({
      hypothesis_id: `HYP-${topic.topic_id}`,
      topic_id: topic.topic_id,
      label: topic.label,
      research_question: topic.research_question,
      origin: "DETERMINISTIC_LEXICAL_TOPIC_CLUSTER",
      status: "ELIGIBLE_FOR_HUMAN_REVIEW",
      matched_groups: groups,
      evidence_segment_ids: selectors.slice(0, MAX_SELECTORS),
      evidence_count: selectors.length,
      selectors_truncated: selectors.length > MAX_SELECTORS,
      revision_condition: "Resolve source origin and edition locators, remove protocol/tool residue and exact duplicates, then test the question against independently coded evidence and a strongest rival.",
    });
  }
  const sourceResistance = detectSourceResistance(segments, hypotheses);
  for (const emergent of sourceResistance.hypotheses) {
    if (!hypotheses.some((entry) => entry.hypothesis_id === emergent.hypothesis_id)) hypotheses.push(emergent);
  }
  const matrix = topicRegistry.case_matrix;
  const cases = [];
  for (const entry of matrix.cases) {
    const patterns = compilePatterns(entry.patterns);
    const selectors = segments.filter((segment) => segment._text && patterns.some((pattern) => pattern.test(segment._text))).map((segment) => segment.segment_id);
    if (!selectors.length) continue;
    cases.push({
      case_id: entry.case_id,
      label: entry.label,
      evidence_count: selectors.length,
      evidence_segment_ids: selectors.slice(0, MAX_SELECTORS),
      status: "UNADJUDICATED_CASE_CANDIDATE",
    });
  }
  const caseMatrices = cases.length >= matrix.minimum_cases ? [{
    matrix_id: matrix.matrix_id,
    label: matrix.label,
    status: "ELIGIBLE_FOR_HETEROGENEOUS_STRESS_TEST",
    matched_case_count: cases.length,
    required_case_count: matrix.minimum_cases,
    cases,
    revision_condition: "Treat every case as a separate domain with its own source, identity, access and corrective constraints; do not infer one universal ontology from lexical co-occurrence.",
  }] : [];
  return {
    bank_version: "DAE-HYPOTHESIS-BANK-1.2",
    engine_version: metadata.engineVersion,
    generated_at: metadata.generatedAt,
    source_id: metadata.sourceId,
    registry_version: topicRegistry.registry_version,
    hypotheses,
    case_matrices: caseMatrices,
    source_resistance: sourceResistance.report,
    claim_ceiling: "HYPOTHESIS_DISCOVERY_ONLY_NOT_CORROBORATION_OR_VALIDATION",
  };
}

function buildSourceMap(segments, documentXml, aliasRegistry, sourceCatalog, metadata) {
  const catalogTargets = [];
  const catalogSelectorSet = new Set();
  for (const entry of aliasRegistry.sources) {
    const patterns = compilePatterns(entry.patterns);
    const selectors = [];
    const evidenceBasis = new Set();
    for (const segment of segments) {
      if (!segment._text) continue;
      for (let index = 0; index < patterns.length; index += 1) {
        if (!patterns[index].test(segment._text)) continue;
        selectors.push(segment.segment_id);
        catalogSelectorSet.add(segment.segment_id);
        evidenceBasis.add(`ALIAS_PATTERN_${index + 1}`);
        break;
      }
    }
    if (!selectors.length) continue;
    const catalogEntry = sourceCatalog.sources[entry.source_id];
    if (!catalogEntry) throw new Error(`REFINERY_ALIAS_CATALOG_ERROR: ${entry.source_id} is absent from source_catalog.json.`);
    catalogTargets.push({
      catalog_source_id: entry.source_id,
      catalog_kind: catalogEntry.kind,
      resolution_status: "LEXICAL_ALIAS_CANDIDATE",
      evidence_basis: [...evidenceBasis].sort(),
      mention_count: selectors.length,
      selectors: [...new Set(selectors)].slice(0, MAX_SELECTORS),
      selectors_truncated: new Set(selectors).size > MAX_SELECTORS,
      human_review_required: true,
    });
  }
  const volumes = new Map();
  let segmentsWithGa = 0;
  for (const segment of segments) {
    const seen = new Set();
    for (const match of segment._text.matchAll(/(?<![\p{L}\p{N}_])GA\s*0*([1-9][0-9]{0,2})(?![\p{L}\p{N}_])/giu)) {
      const volume = Number(match[1]);
      if (volume < 1 || volume > 105) continue;
      if (!volumes.has(volume)) volumes.set(volume, []);
      volumes.get(volume).push(segment.segment_id);
      seen.add(volume);
    }
    if (seen.size) segmentsWithGa += 1;
  }
  const markerMap = new Map();
  let pseudoCitationOccurrences = 0;
  for (const segment of segments) {
    for (const match of segment._text.matchAll(/\[[^\]\n]{0,180}(?:\+\d+|Beyng|PhilPapers|philosophisches-jahrbuch|GA\s*\d+|doi)[^\]\n]{0,180}\]/giu)) {
      const markerHash = sha256(normalizedText(match[0]));
      if (!markerMap.has(markerHash)) markerMap.set(markerHash, []);
      markerMap.get(markerHash).push(segment.segment_id);
      pseudoCitationOccurrences += 1;
    }
  }
  return {
    source_map_version: "DAE-SOURCE-MAP-1.0",
    engine_version: metadata.engineVersion,
    generated_at: metadata.generatedAt,
    document_source_id: metadata.sourceId,
    document_artifact: { sha256: metadata.artifactHash, role: "COMPOSITE_CONTAINER", admission: metadata.sourceAdmission },
    catalog_targets: catalogTargets.sort((left, right) => left.catalog_source_id.localeCompare(right.catalog_source_id)),
    ga_volume_candidates: [...volumes.entries()].sort((left, right) => left[0] - right[0]).map(([volume, selectors]) => ({
      volume,
      mention_count: selectors.length,
      selectors: [...new Set(selectors)].slice(0, MAX_SELECTORS),
      resolution_status: "VOLUME_LOCATOR_ONLY",
    })),
    unresolved_marker_clusters: [...markerMap.entries()].map(([markerHash, selectors]) => ({
      marker_sha256: markerHash,
      occurrence_count: selectors.length,
      selectors: [...new Set(selectors)].slice(0, MAX_SELECTORS),
      resolution_status: "UNRESOLVED_PSEUDO_CITATION",
    })).sort((left, right) => right.occurrence_count - left.occurrence_count || left.marker_sha256.localeCompare(right.marker_sha256)),
    coverage: {
      segments_scanned: segments.length,
      segments_with_catalog_alias: catalogSelectorSet.size,
      segments_with_ga_locator: segmentsWithGa,
      pseudo_citation_occurrences: pseudoCitationOccurrences,
      hyperlink_occurrences: countMatches(documentXml, /<w:hyperlink(?:\s|>)/gu),
      resolved_claim_level_citations: 0,
    },
    claim_ceiling: "SOURCE_TARGET_AND_CITATION_MARKER_CANDIDATES_ONLY_NOT_CLAIM_LEVEL_SOURCE_RESOLUTION",
  };
}

function formulaRegistry(formulas, metadata) {
  const groups = new Map();
  for (const formula of formulas) {
    if (!groups.has(formula.omml_sha256)) groups.set(formula.omml_sha256, []);
    groups.get(formula.omml_sha256).push(formula.formula_id);
  }
  return {
    registry_version: "DAE-OMML-FORMULAS-1.0",
    engine_version: metadata.engineVersion,
    generated_at: metadata.generatedAt,
    source_id: metadata.sourceId,
    formula_count: formulas.length,
    raw_formula_text_included: false,
    formulas,
    exact_formula_groups: [...groups.entries()].filter(([, ids]) => ids.length > 1).map(([hash, ids]) => ({ omml_sha256: hash, formula_ids: ids, occurrence_count: ids.length })),
    claim_ceiling: "FORMULA_STRUCTURE_AND_FIXITY_ONLY_NOT_MATHEMATICAL_INTERPRETATION",
  };
}

function safeOoxmlSegment(segment) {
  const {
    heading_level: _headingLevel,
    hyperlink_count: _hyperlinkCount,
    _text,
    _normalized,
    _formulas,
    ...safe
  } = segment;
  return safe;
}

function safeArgumentSegment(segment) {
  const { _routing_confidence, _basis_signals, ...safe } = segment;
  return safe;
}

function rendererSegments(bundle) {
  return bundle.units.map((unit) => ({
    unit_id: unit.unit_id,
    page_label: unit.page_label,
    zone: unit.zone,
    normalized_sha256: unit.normalized_sha256,
    char_length: unit.char_length,
    selector: unit.selector,
    discourse_features: unit.discourse_features,
    relation_candidates: [...new Set(unit.relation_candidates.map((candidate) => candidate.rt_id))].sort(),
    record_id: unit.record_id ?? null,
  }));
}

function countBy(items, getter) {
  const counts = {};
  for (const item of items) {
    const key = getter(item);
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return Object.fromEntries(Object.entries(counts).sort(([left], [right]) => left.localeCompare(right)));
}

function issueSummary(issues) {
  return issues.map((issue) => `${issue.code} ${issue.at}: ${issue.message}`).join("; ");
}

async function requireNewDirectory(directory) {
  try {
    await stat(directory);
    throw new Error(`Output directory already exists: ${directory}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

async function unzipPart(docx, part) {
  try {
    const result = await execFileAsync("unzip", ["-p", docx, part], { encoding: "utf8", maxBuffer: 128 * 1024 * 1024 });
    return result.stdout;
  } catch (error) {
    throw new Error(`DOCX_PART_FAILED ${part}: ${error.stderr ?? error.message}`);
  }
}

async function loadPageRun(engine, pageRun) {
  const root = path.resolve(pageRun);
  const [intake, manifest, bundle] = await Promise.all([
    readJson(path.join(root, "docx_intake.json")),
    readJson(path.join(root, "source_manifest.json")),
    readJson(path.join(root, "generated", "analysis_bundle.json")),
  ]);
  const manifestIssues = engine.structural.validateSourceManifest(manifest);
  if (manifestIssues.length) throw new Error(`Existing page run has an invalid source manifest: ${issueSummary(manifestIssues)}`);
  if (bundle.raw_text_included !== false || bundle.expressive_context_included !== false) throw new Error("REFINERY_PAGE_RUN_POLICY: renderer bundle contains expressive source text.");
  if (bundle.source.source_id !== manifest.source_id) throw new Error("REFINERY_PAGE_RUN_SOURCE_MISMATCH: bundle and manifest source IDs differ.");
  if (!Array.isArray(bundle.units) || bundle.units.length !== bundle.unit_count) throw new Error("REFINERY_PAGE_RUN_UNIT_MISMATCH: renderer bundle unit count is inconsistent.");
  return { root, intake, manifest, bundle, mode: "EXISTING_FIXITY_VERIFIED_PAGE_RUN" };
}

function canonicalArgumentMarkdown(report, sourceMap, hypothesisBank, ledgerSummary) {
  const layerRows = Object.entries(report.counts.layers).map(([layer, count]) => `| ${layer} | ${count} |`).join("\n");
  const claimRows = Object.entries(ledgerSummary.by_claim_type).map(([type, count]) => `| ${type} | ${count} |`).join("\n");
  const hypotheses = hypothesisBank.hypotheses.length
    ? hypothesisBank.hypotheses.map((entry) => `- ${entry.hypothesis_id}: ${entry.research_question} (${entry.evidence_count} selector candidates)`).join("\n")
    : "- No topic cluster met its minimum lexical coverage threshold.";
  return `# Canonical argument scaffold — Corpus Refinery 0.3.0

## Status

**SUSPENDED_PENDING_SOURCE_RESOLUTION_AND_HUMAN_ADJUDICATION**

The refinery did not synthesize a canonical philosophical argument automatically. The input is a composite dossier, renderer pages are technical locators, and claim-level citations are unresolved. This scaffold records a safe adjudication queue without copying source wording.

## Non-expressive corpus map

| Candidate layer | OOXML segments |
|---|---:|
${layerRows}

| Claim type | Ledger entries |
|---|---:|
${claimRows}

- OOXML-native segments: ${report.counts.ooxml_segments}
- Renderer-native units: ${report.counts.renderer_segments}
- Argument-native units: ${report.counts.argument_segments}
- OMML formulas: ${report.counts.formulas}
- Catalog source targets: ${sourceMap.catalog_targets.length}; resolved claim-level citations: 0
- Exact duplicate groups: ${report.counts.exact_duplicate_groups}; no segment was deleted

## Hypothesis queue

${hypotheses}

## Required adjudication order

1. Exclude archived protocol/tool traces from philosophical evidence while retaining their selectors and hashes.
2. Resolve each source candidate to an edition/work locator and distinguish quotation from paraphrase or attribution.
3. Reconstruct A, P and B for each retained claim candidate; the generated ledger deliberately leaves all three null.
4. Test the proposed RT against an operative/mentioned distinction and the strongest live rival.
5. Merge only human-attested duplicates; preserve replaced, superseded and dependency links in the ledger.
6. Promote no diachronic, epochal, universal or ontological claim before its dedicated source and domain gates pass.

## Claim ceiling

This artifact is a review scaffold. It establishes segmentation, fixity-linked selectors, deterministic routing and non-destructive consolidation only; it does not establish authorship, source identity, interpretation, ontology or truth.
`;
}

function reportMarkdown(report) {
  return `# Corpus Refinery run — DAE 0.3.0

Source: \`${report.source_id}\`  
Artifact SHA-256: \`${report.artifact_sha256}\`

## Result

The run completed with ${report.validation.total_errors} schema errors. It produced three competing segmentations and retained every OOXML paragraph. Layer labels are review routing candidates, not assertions about authorship or philosophical status.

| Measure | Count |
|---|---:|
| OOXML paragraphs | ${report.counts.ooxml_segments} |
| Renderer units | ${report.counts.renderer_segments} |
| Argument units | ${report.counts.argument_segments} |
| Claim-ledger entries | ${report.counts.claim_ledger_entries} |
| Formula records | ${report.counts.formulas} |
| Exact duplicate groups | ${report.counts.exact_duplicate_groups} |
| Near-duplicate candidate groups | ${report.counts.near_duplicate_groups} |
| Archived tool/log paragraphs | ${report.counts.archived_tool_logs} |
| Deleted paragraphs | 0 |

## Gates

- Source/claim resolution: **SUSPEND** — alias and pseudo-citation matches are not claim-level citations.
- Canonical argument: **SUSPEND** — A/P/B and strongest rivals remain unadjudicated.
- Hypothesis use: **REVIEW** — lexical clusters are eligible for testing, not corroborated.
- Corpus preservation: **PASS** — all paragraph selectors and hashes remain recoverable; no source text is released.

## Claim ceiling

\`${report.claim_ceiling}\`
`;
}

export async function refineDocx(engine, inputFile, jobFile, outputDir, options = {}) {
  const input = path.resolve(inputFile);
  const jobPath = path.resolve(jobFile);
  const out = path.resolve(outputDir);
  await requireNewDirectory(out);
  if (path.extname(input).toLowerCase() !== ".docx") throw new Error("refine-docx requires a .docx input file.");
  const job = await readJson(jobPath);
  const jobIssues = engine.structural.validateDocxJob(job);
  if (jobIssues.length) throw new Error(`Invalid DOCX job: ${issueSummary(jobIssues)}`);
  const artifactBytes = await readFile(input);
  const artifactHash = sha256(artifactBytes);
  const generatedAt = options.generatedAt ?? new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
  const temp = await mkdtemp(path.join(os.tmpdir(), "dae-refinery-"));
  try {
    let pageRun;
    if (options.pageRun) {
      pageRun = await loadPageRun(engine, options.pageRun);
    } else {
      const generatedPageRun = path.join(temp, "page-run");
      await analyzeDocx(engine, input, jobPath, generatedPageRun, { generatedAt });
      pageRun = await loadPageRun(engine, generatedPageRun);
      pageRun.mode = "TRANSIENT_FRESH_PAGE_RUN";
    }
    if (pageRun.intake.input.sha256 !== artifactHash) throw new Error(`REFINERY_ARTIFACT_MISMATCH: page run=${pageRun.intake.input.sha256}, input=${artifactHash}.`);
    if (pageRun.manifest.artifact.sha256 !== artifactHash || pageRun.manifest.artifact.byte_length !== artifactBytes.length) {
      throw new Error(`REFINERY_ARTIFACT_MISMATCH: source manifest does not describe the supplied DOCX bytes.`);
    }
    if (pageRun.manifest.source_id !== pageRun.intake.source_id) throw new Error("REFINERY_SOURCE_MISMATCH: intake and source manifest differ.");
    if (job.source_admission === "CATALOGUED") {
      if (!engine.context.sourceCatalog.sources[job.source_id]) throw new Error(`SOURCE_ADMISSION_BLOCK: '${job.source_id}' is not present in config/source_catalog.json.`);
      if (pageRun.manifest.source_id !== job.source_id) throw new Error(`REFINERY_SOURCE_MISMATCH: job=${job.source_id}, page run=${pageRun.manifest.source_id}.`);
    } else if (!/^LOCAL-SHA256-[A-F0-9]{64}$/u.test(pageRun.manifest.source_id)) {
      throw new Error("REFINERY_SOURCE_MISMATCH: LOCAL_HASH job requires a content-bound LOCAL-SHA256 source ID.");
    }
    const documentXml = await unzipPart(input, "word/document.xml");
    const [{ segments, formulas }, aliasRegistry, topicRegistry] = await Promise.all([
      Promise.resolve(parseOoxmlParagraphs(documentXml, { documentLanguage: job.bibliographic.language })),
      readJson(projectPath("config", "refinery_source_aliases.json")),
      readJson(projectPath("config", "refinery_topic_registry.json")),
    ]);
    const duplicates = findDuplicateClusters(segments);
    const argumentSegments = buildArgumentSegments(segments);
    const claimLedger = buildClaimLedger(argumentSegments, artifactHash, generatedAt);
    const metadata = {
      engineVersion: engine.context.engineVersion,
      generatedAt,
      sourceId: pageRun.manifest.source_id,
      sourceAdmission: job.source_admission,
      artifactHash,
    };
    const sourceMap = buildSourceMap(segments, documentXml, aliasRegistry, engine.context.sourceCatalog, metadata);
    const hypothesisBank = buildHypothesisBankFromSegments(segments, topicRegistry, metadata);
    const formulasArtifact = formulaRegistry(formulas, metadata);
    const renderer = rendererSegments(pageRun.bundle);
    const safeOoxml = segments.map(safeOoxmlSegment);
    const safeArguments = argumentSegments.map(safeArgumentSegment);
    const segmentationManifest = {
      manifest_version: "DAE-CORPUS-SEGMENTATION-1.0",
      engine_version: engine.context.engineVersion,
      generated_at: generatedAt,
      source: {
        source_id: pageRun.manifest.source_id,
        artifact_sha256: artifactHash,
        artifact_byte_length: artifactBytes.length,
        access_class: job.access_policy.analysis_class,
        raw_text_included: false,
        expressive_context_included: false,
      },
      layer_ontology: LAYERS,
      methods: {
        ooxml_native: "WORDPROCESSINGML_PARAGRAPH_ORDER_PLUS_STYLE_HEADING_PATH_AND_HASH_SELECTORS_1.0",
        renderer_native: `${pageRun.mode}; ${pageRun.bundle.method_version}; ${pageRun.manifest.pagination.authority ?? "UNSTATED_AUTHORITY"}`,
        argument_native: "CONTIGUOUS_SAME_HEADING_AND_ROUTED_LAYER_WINDOWS_CAPPED_AT_6_PARAGRAPHS_OR_2000_CHARACTERS_1.0",
        layer_routing: "WEIGHTED_EXPLICIT_SIGNALS_WITH_MARGIN_AND_UNRESOLVED_FALLBACK_1.0",
        duplicate_detection: "EXACT_NORMALIZED_SHA256_PLUS_8_VALUE_MINHASH_3_TOKEN_SHINGLES_JACCARD_GE_0.72_1.0",
      },
      counts: {
        ooxml_total: safeOoxml.length,
        ooxml_nonempty: safeOoxml.filter((segment) => segment.zone !== "EMPTY").length,
        headings: safeOoxml.filter((segment) => segment.zone === "HEADING").length,
        renderer_units: renderer.length,
        argument_units: safeArguments.length,
        layer_routes: countBy(safeOoxml, (segment) => segment.layer_routing.label),
        routing_statuses: countBy(safeOoxml, (segment) => segment.layer_routing.status),
      },
      ooxml_segments: safeOoxml,
      renderer_segments: renderer,
      argument_segments: safeArguments,
      claim_ceiling: "SEGMENTATION_AND_REVIEW_ROUTING_ONLY_NOT_AUTHORSHIP_SOURCE_IDENTITY_OR_SEMANTIC_TRUTH",
    };
    const archiveEntries = [];
    for (const group of duplicates.exact) {
      for (const member of group.member_segment_ids.slice(1)) archiveEntries.push({ segment_id: member, reason: "EXACT_DUPLICATE_OCCURRENCE", representative_segment_id: group.representative_segment_id, recoverability: "FULL_SELECTOR_AND_HASH_RETAINED_IN_SEGMENTATION_MANIFEST" });
    }
    for (const segment of safeOoxml.filter((item) => item.archive_state === "ARCHIVED_TOOL_LOG")) {
      archiveEntries.push({ segment_id: segment.segment_id, reason: "PROTOCOL_OR_TOOL_LOG", representative_segment_id: null, recoverability: "FULL_SELECTOR_AND_HASH_RETAINED_IN_SEGMENTATION_MANIFEST" });
    }
    const archiveMap = {
      archive_map_version: "DAE-ARCHIVE-MAP-1.0",
      engine_version: engine.context.engineVersion,
      generated_at: generatedAt,
      source_id: pageRun.manifest.source_id,
      policy: {
        deletion: "FORBIDDEN",
        canonicalization: "FIRST_OCCURRENCE_AS_REPRESENTATIVE_WITH_ALL_OCCURRENCES_PRESERVED",
        near_duplicate_action: "LINK_ONLY_REVIEW_REQUIRED",
        tool_log_action: "ARCHIVE_LAYER_WITHOUT_ERASURE",
      },
      counts: {
        segments_total: safeOoxml.length,
        deleted_segments: 0,
        exact_duplicate_groups: duplicates.exact.length,
        exact_duplicate_occurrences_archived: duplicates.exact.reduce((sum, group) => sum + group.member_count - 1, 0),
        near_duplicate_groups: duplicates.near.length,
        tool_log_segments_archived: safeOoxml.filter((segment) => segment.archive_state === "ARCHIVED_TOOL_LOG").length,
      },
      exact_duplicate_groups: duplicates.exact,
      near_duplicate_groups: duplicates.near,
      archive_entries: archiveEntries,
      claim_ceiling: "NON_DESTRUCTIVE_CONSOLIDATION_MAP_ONLY_NOT_TEXTUAL_OR_SEMANTIC_EQUIVALENCE",
    };
    const ledgerSummary = {
      ledger_version: "DAE-CLAIM-LEDGER-SUMMARY-1.0",
      source_id: pageRun.manifest.source_id,
      entry_count: claimLedger.length,
      by_origin_layer: countBy(claimLedger, (entry) => entry.origin.candidate_layer),
      by_claim_type: countBy(claimLedger, (entry) => entry.claim_type),
      by_scale: countBy(claimLedger, (entry) => entry.scale),
      by_status: countBy(claimLedger, (entry) => entry.status),
      apb_reconstructed: 0,
      strongest_rival_attested: 0,
      claim_ceiling: "QUEUE_STATISTICS_ONLY_NOT_ARGUMENT_OR_TRUTH_COUNTS",
    };
    const validations = {
      segmentation_manifest: engine.structural.validateSegmentationManifest(segmentationManifest),
      source_map: engine.structural.validateSourceMap(sourceMap),
      hypothesis_bank: engine.structural.validateHypothesisBank(hypothesisBank),
      archive_map: engine.structural.validateArchiveMap(archiveMap),
      formula_registry: engine.structural.validateFormulaRegistry(formulasArtifact),
      claim_ledger: claimLedger.flatMap((entry, index) => engine.structural.validateClaimLedgerEntry(entry).map((issue) => ({ ...issue, at: `/line/${index + 1}${issue.at}` }))),
    };
    const totalErrors = Object.values(validations).reduce((sum, issues) => sum + issues.length, 0);
    if (totalErrors) throw new Error(`CORPUS_REFINERY_SCHEMA_FAILED: ${Object.entries(validations).filter(([, issues]) => issues.length).map(([name, issues]) => `${name}=${issues.length}: ${issueSummary(issues.slice(0, 3))}`).join(" | ")}`);
    const report = {
      report_version: "DAE-CORPUS-REFINERY-0.1",
      engine_version: engine.context.engineVersion,
      generated_at: generatedAt,
      source_id: pageRun.manifest.source_id,
      artifact_sha256: artifactHash,
      page_run_mode: pageRun.mode,
      counts: {
        ooxml_segments: safeOoxml.length,
        renderer_segments: renderer.length,
        argument_segments: safeArguments.length,
        claim_ledger_entries: claimLedger.length,
        formulas: formulas.length,
        exact_duplicate_groups: duplicates.exact.length,
        near_duplicate_groups: duplicates.near.length,
        archived_tool_logs: archiveMap.counts.tool_log_segments_archived,
        layers: segmentationManifest.counts.layer_routes,
        hypotheses: hypothesisBank.hypotheses.length,
        case_matrices: hypothesisBank.case_matrices.length,
      },
      validation: { total_errors: 0, schemas_checked: 5, claim_ledger_lines_checked: claimLedger.length },
      gates: {
        corpus_preservation: "PASS",
        source_resolution: "SUSPEND",
        canonical_argument: "SUSPEND",
        hypothesis_use: "REVIEW",
      },
      output_contract: {
        source_text_included: false,
        docx_copied: false,
        rendered_pdf_included: false,
        extracted_text_included: false,
        deleted_segments: 0,
      },
      claim_ceiling: "CORPUS_NORMALIZATION_AND_REVIEW_ROUTING_ONLY_EXTERNAL_SEMANTIC_VALIDATION_PENDING",
    };
    await mkdir(out, { recursive: true });
    await Promise.all([
      writeFile(path.join(out, "segmentation_manifest.json"), `${JSON.stringify(segmentationManifest, null, 2)}\n`, "utf8"),
      writeFile(path.join(out, "source_map.json"), `${JSON.stringify(sourceMap, null, 2)}\n`, "utf8"),
      writeFile(path.join(out, "claim_ledger.jsonl"), `${claimLedger.map((entry) => JSON.stringify(entry)).join("\n")}\n`, "utf8"),
      writeFile(path.join(out, "claim_ledger_summary.json"), `${JSON.stringify(ledgerSummary, null, 2)}\n`, "utf8"),
      writeFile(path.join(out, "hypothesis_bank.json"), `${JSON.stringify(hypothesisBank, null, 2)}\n`, "utf8"),
      writeFile(path.join(out, "archive_map.json"), `${JSON.stringify(archiveMap, null, 2)}\n`, "utf8"),
      writeFile(path.join(out, "formula_registry.json"), `${JSON.stringify(formulasArtifact, null, 2)}\n`, "utf8"),
      writeFile(path.join(out, "canonical_argument.md"), canonicalArgumentMarkdown(report, sourceMap, hypothesisBank, ledgerSummary), "utf8"),
      writeFile(path.join(out, "REFINERY_REPORT.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8"),
      writeFile(path.join(out, "REFINERY_REPORT.md"), reportMarkdown(report), "utf8"),
    ]);
    return { output_dir: out, report, segmentation_manifest: segmentationManifest, source_map: sourceMap, claim_ledger_summary: ledgerSummary, hypothesis_bank: hypothesisBank, archive_map: archiveMap, formula_registry: formulasArtifact };
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
}
