import { discoverOpenSetOperator } from "./open-set-discovery.mjs";

const MAX_TERMS = 24;
const MAX_HYPOTHESES = 24;

function slug(value, fallback = "TERM") {
  const normalized = String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/gu, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/gu, "_")
    .replace(/^_+|_+$/gu, "")
    .slice(0, 72);
  return normalized || fallback;
}

function normalize(value) {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase("und").replace(/\s+/gu, " ").trim();
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function termSurfacePatterns(term) {
  const source = String(term ?? "").trim();
  if (!source) return [];
  const patterns = [escapeRegex(source)];
  if (!/[\s/-]/u.test(source) && /^[\p{Lu}]/u.test(source) && [...source].length >= 4) {
    if (/e$/iu.test(source)) patterns.push(`${escapeRegex(source)}(?:n|r|s|m)?`);
    else patterns.push(`${escapeRegex(source)}(?:e|en|er|es|s)?`);
  }
  if (!/[\s/-]/u.test(source) && /en$/iu.test(source) && [...source].length >= 6) {
    const base = source.slice(0, -2);
    patterns.push(`${escapeRegex(base)}(?:en|t|te|ten|end|ende|enden)`);
    const eStem = source.slice(0, -1);
    patterns.push(`${escapeRegex(eStem)}(?:n|nd|nde|nden|t)`);
  }
  return [...new Set(patterns)];
}

function mentions(text, term) {
  const patterns = termSurfacePatterns(term);
  if (!patterns.length) return false;
  return patterns.some((body) => new RegExp(`(?<![\\p{L}\\p{N}_])(?:${body})(?![\\p{L}\\p{N}_])`, "iu").test(text));
}

// The stop list is deliberately multilingual and conservative. It is not a language detector;
// it only prevents recurrent function words from masquerading as source-native concepts.
const TERM_STOP = new Set([
  "source", "primary", "project", "claim", "thesis", "terms", "term", "research", "dossier", "heidegger",
  "reading", "ontology", "interpretation", "reconstruction", "strong", "rival", "method", "machine", "destruktion",
  "author", "text", "chapter", "section", "page", "pages", "work", "works", "said", "says", "called", "means", "mean",
  "thing", "things", "something", "anything", "everything", "nothing", "another", "other", "others", "itself", "themselves",
  "and", "or", "the", "a", "an", "of", "to", "in", "is", "are", "was", "were", "be", "as", "for", "by", "on", "at", "it", "its", "he", "she", "we", "you", "they", "his", "her", "our", "your", "them", "then",
  "which", "that", "this", "these", "those", "there", "where", "when", "what", "with", "without", "from", "into", "through",
  "their", "therefore", "however", "because", "between", "being", "been", "have", "has", "having", "more", "less", "only",
  "le", "la", "les", "un", "une", "des", "de", "du", "au", "aux", "en", "et", "ou", "il", "ils", "on", "son", "sa", "ses", "leur", "leurs", "ne", "pas",
  "pour", "dans", "avec", "sans", "entre", "comme", "mais", "donc", "plus", "moins", "tout", "tous", "toute", "toutes",
  "quelque", "autre", "autres", "chose", "choses", "être", "etre", "sont", "est", "par", "que", "qui", "dont", "elle", "elles",
  "celui", "celle", "ceux", "celles", "ainsi", "lorsque", "encore", "fait", "même", "meme", "peut", "peuvent", "doit", "doivent",
  "das", "die", "der", "den", "dem", "des", "ein", "eine", "einer", "eines", "einem", "einen", "und", "oder", "doch", "nicht", "ist", "sind",
  "sein", "seine", "seiner", "ihre", "ihren", "dies", "diese", "dieser", "dieses", "etwas", "nichts", "ander", "andere", "anderen",
  "хайдеггер", "проект", "тезис", "термин", "термины", "источник", "источника", "источнике", "текст", "автор", "работа", "работы",
  "который", "которая", "которые", "которое", "этот", "эта", "это", "эти", "такой", "такая", "такие", "может", "могут", "будет",
  "source-bounded", "html", "http", "https", "www", "com", "org", "net", "beyng",
  "sich", "n’y", "seulement", "cannot", "else",
]);

function cleanTerm(value) {
  return String(value ?? "")
    .replace(/^[\s“”„«»'"`*•·–—-]+|[\s“”„«»'"`*•·–—.]+$/gu, "")
    .replace(/\s+/gu, " ")
    .trim();
}

function admissibleTerm(value) {
  const term = cleanTerm(value);
  if (!term || [...term].length < 3 || [...term].length > 64) return false;
  if (TERM_STOP.has(normalize(term))) return false;
  if (/^(?:GA\d+|GA\s*\d+|https?|www)$/iu.test(term)) return false;
  if (!/[\p{L}]/u.test(term)) return false;
  return true;
}

function explicitStressTerms(segments) {
  const ordered = [...segments].sort((a, b) => (a.ordinal ?? 0) - (b.ordinal ?? 0));
  const terms = [];
  const marker = /(?:etymolog(?:ical|isch)|этимолог\p{L}*).{0,40}(?:stress|central|key|термин\p{L}*|центральн\p{L}*|ключев\p{L}*)/iu;
  for (let index = 0; index < ordered.length; index += 1) {
    const segment = ordered[index];
    const text = String(segment._text ?? "");
    if (!marker.test(text)) continue;
    const payloads = [];
    if (text.includes(":")) payloads.push(text.slice(text.indexOf(":") + 1));
    const next = ordered[index + 1];
    if (next && (next.ordinal ?? 0) === (segment.ordinal ?? 0) + 1) payloads.push(String(next._text ?? ""));
    for (const payload of payloads) {
      const effectivePayload = payload.includes(":") ? payload.slice(payload.indexOf(":") + 1) : payload;
      for (const piece of effectivePayload.split(/[,;]\s*/u)) {
        const term = cleanTerm(piece.replace(/^(?:и|and|und|et)\s+/iu, ""));
        if (admissibleTerm(term)) terms.push(term);
      }
    }
  }
  return [...new Map(terms.map((term) => [normalize(term), term])).values()].slice(0, MAX_TERMS);
}

function sourceNativeTerms(segments) {
  const records = new Map();
  for (const segment of segments) {
    if (!segment._text || segment.archive_state !== "ACTIVE") continue;
    const layer = segment.layer_routing?.label;
    if (!["SOURCE", "RECONSTRUCTION", "PROJECT_CLAIM", "RIVAL_OBJECTION", "UNRESOLVED"].includes(layer)) continue;
    const lexicalText = segment._text
      .replace(/https?:\/\/\S+/giu, " ")
      .replace(/\[[^\]]{1,100}\]/gu, " ")
      .replace(/^\s*SOURCE\s+[A-Z]{1,8}\d*(?::\d+)?\s*:/iu, " ");
    const tokens = lexicalText.match(/[\p{L}][\p{L}\p{M}'’‐‑-]{2,}/gu) ?? [];
    const localCounts = new Map();
    for (const token of tokens) {
      const term = cleanTerm(token);
      if (!admissibleTerm(term)) continue;
      const key = normalize(term);
      localCounts.set(key, (localCounts.get(key) ?? 0) + 1);
      if (!records.has(key)) records.set(key, {
        term,
        source_occurrences: 0,
        total_occurrences: 0,
        source_selectors: new Set(),
        all_selectors: new Set(),
        technical_boost: 0,
      });
      const record = records.get(key);
      record.total_occurrences += 1;
      record.all_selectors.add(segment.segment_id);
      if (layer === "SOURCE") {
        record.source_occurrences += 1;
        record.source_selectors.add(segment.segment_id);
      }
      if (/^[A-ZÄÖÜÀ-Ý][\p{L}\p{M}'’‐‑-]+$/u.test(term)
        || /[äöüßÄÖÜéèêàâîôûçÉÈÊÀÂÎÔÛÇ]/u.test(term)
        || /(?:ung|heit|keit|schaft|nis|lich|sein|welt|raum|ort|ding|viert|gött|nähe|ferne|tion|té|isme|ance|ence)$/iu.test(term)) {
        record.technical_boost = Math.max(record.technical_boost, 1);
      }
    }
    // Count document frequency once per segment; occurrence count above remains frequency-sensitive.
    for (const key of localCounts.keys()) {
      const record = records.get(key);
      if (layer !== "SOURCE") continue;
      // source_selectors already carries DF; no-op here by design.
      void record;
    }
  }
  return [...records.values()]
    .filter((entry) => entry.source_occurrences >= 2 && (entry.source_selectors.size >= 2 || entry.source_occurrences >= 3))
    .map((entry) => {
      const specificity = entry.total_occurrences ? entry.source_occurrences / entry.total_occurrences : 0;
      const score = entry.source_selectors.size * 5
        + Math.min(entry.source_occurrences, 10)
        + specificity * 2
        + entry.technical_boost;
      return { ...entry, specificity, score };
    })
    .sort((a, b) => b.score - a.score
      || b.source_selectors.size - a.source_selectors.size
      || b.source_occurrences - a.source_occurrences
      || a.term.localeCompare(b.term))
    .map((entry) => entry.term)
    .slice(0, MAX_TERMS);
}

function claimCandidates(segments) {
  const output = [];
  const regex = /(?:тезис|thesis)\s*:\s*([A-Z][A-Z0-9_]{3,})\s*[—–-]\s*(.+)$/iu;
  for (const segment of segments) {
    if (segment.layer_routing?.label !== "PROJECT_CLAIM" || !segment._text) continue;
    const match = segment._text.match(regex);
    if (!match) continue;
    output.push({ key: slug(match[1]), statement: match[2].trim(), selector: segment.segment_id });
  }
  return output.slice(0, MAX_HYPOTHESES);
}

function legacyCoverage(term, hypotheses) {
  const needle = normalize(term);
  return hypotheses.some((hypothesis) => {
    const haystack = normalize([hypothesis.topic_id, hypothesis.label, hypothesis.research_question, ...(hypothesis.matched_groups ?? [])].join(" "));
    return haystack.includes(needle) || haystack.includes(normalize(slug(term).replaceAll("_", " ")));
  });
}

function termRecord(term, segments, explicit) {
  const selectors = [];
  const layers = new Map();
  let score = explicit ? 10 : 0;
  for (const segment of segments) {
    if (!segment._text || !mentions(segment._text, term)) continue;
    selectors.push(segment.segment_id);
    const layer = segment.layer_routing?.label ?? "UNRESOLVED";
    layers.set(layer, (layers.get(layer) ?? 0) + 1);
    score += layer === "SOURCE" ? 5 : layer === "RECONSTRUCTION" ? 3 : layer === "PROJECT_CLAIM" ? 2.5 : layer === "RIVAL_OBJECTION" ? 1.5 : 1;
  }
  return { term, concept_id: slug(term), score, selectors: [...new Set(selectors)], layers: Object.fromEntries([...layers].sort()) };
}

const RELATION_SIGNAL_FAMILIES = [
  ["DIFFERENTIAL", /(?:difference|différence|differen[cz]|unterschied|различ\p{L}*|opposition|opposit\p{L}*|gegenüber|контраст\p{L}*)/giu],
  ["REFERENCE_RELATIVE", /(?:relation|relative|relatif|rapport|reference|référence|bezug|verhältnis|отнош\p{L}*|соотнош\p{L}*|связ\p{L}*|comparison|comparaison|vergleich)/giu],
  ["SYSTEM_FIELD", /(?:system|système|struktur|structure|ensemble|whole|field|totality|систем\p{L}*|структур\p{L}*|целост\p{L}*)/giu],
  ["ASYMMETRIC_DEPENDENCE", /(?:depends?\s+on|dependence|dependent|conceived\s+through|in\s+itself|in\s+another|present\s+in\s+a\s+subject|predicat\p{L}*|prior\s+to|primary\s+substance|dépend\p{L}*|abhäng\p{L}*|завис\p{L}*|приоритет\p{L}*)/giu],
  ["RECIPROCITY_GATHERING", /(?:recipro\p{L}*|mutual\p{L}*|co[- ]?constit\p{L}*|gather\p{L}*|versamm\p{L}*|belong\p{L}*|zusammengehör\p{L}*|zueinander|взаим\p{L}*|соопредел\p{L}*|собира\p{L}*)/giu],
  ["DISTANCE_DIFFERENTIATION", /(?:near(?:ness)?|proximity|distance|far(?:ness)?|nähe|näher\p{L}*|ferne|fern\p{L}*|proche|proximité|distance|loin|близ\p{L}*|даль\p{L}*|дистанц\p{L}*)/giu],
  ["PRIORITY", /(?:priority|prior\s+to|primary|first|vorrang|ursprüng\p{L}*|первич\p{L}*|приоритет\p{L}*)/giu],
];

function operatorCandidateForTexts(sourceTexts, records) {
  const joined = sourceTexts.join("\n");
  const signalCounts = {};
  for (const [family, regex] of RELATION_SIGNAL_FAMILIES) signalCounts[family] = [...joined.matchAll(regex)].length;
  const activeFamilies = Object.entries(signalCounts).filter(([, count]) => count > 0).map(([family]) => family);
  const centralCooccurrence = sourceTexts.filter((text) => records.filter((entry) => mentions(text, entry.term)).length >= 2).length;
  const relationScore = activeFamilies.length * 2 + Math.min(centralCooccurrence, 4);
  if (relationScore < 5 || activeFamilies.length < 2) {
    return {
      family: "GENERIC_SOURCE_FORCED_REVISION",
      candidate: "SOURCE_FORCED_TOPIC_AND_OPERATOR_CANDIDATE",
      signal_counts: signalCounts,
      active_signal_families: activeFamilies,
      central_term_cooccurrence_segments: centralCooccurrence,
      profile_hints: [],
      claim_ceiling: "REPRESENTATION_TEST_CANDIDATE_NOT_SOURCE_ONTOLOGY",
    };
  }
  const hints = [];
  if ((signalCounts.DIFFERENTIAL ?? 0) > 0 && (signalCounts.SYSTEM_FIELD ?? 0) > 0) hints.push("DIFFERENTIAL_CONSTITUTION");
  if ((signalCounts.ASYMMETRIC_DEPENDENCE ?? 0) > 0 && (signalCounts.PRIORITY ?? 0) > 0) hints.push("ASYMMETRIC_DEPENDENCE");
  if ((signalCounts.RECIPROCITY_GATHERING ?? 0) > 0) hints.push("CO_CONSTITUTIVE_OR_RECIPROCAL");
  if ((signalCounts.DISTANCE_DIFFERENTIATION ?? 0) > 0) hints.push("DIFFERENCE_PRESERVING_PROXIMITY");
  if ((signalCounts.REFERENCE_RELATIVE ?? 0) > 0 && (signalCounts.ASYMMETRIC_DEPENDENCE ?? 0) > 0) hints.push("LOCAL_MODE_VARIATION");
  if (!hints.length) hints.push("RELATION_GENESIS_UNRESOLVED");
  return {
    family: "RELATION_GENESIS_PROFILE",
    candidate: "RELATION_GENESIS_PROFILE_WITH_CO_EMERGENT_RELATA_CANDIDATE",
    signal_counts: signalCounts,
    active_signal_families: activeFamilies,
    central_term_cooccurrence_segments: centralCooccurrence,
    profile_hints: hints,
    claim_ceiling: "REPRESENTATION_TEST_CANDIDATE_NOT_RELATION_FIRST_ONTOLOGY",
  };
}

function operatorCandidateForSource(segments, records) {
  const sourceTexts = segments
    .filter((segment) => segment.archive_state === "ACTIVE" && segment.layer_routing?.label === "SOURCE" && segment._text)
    .map((segment) => segment._text);
  return operatorCandidateForTexts(sourceTexts, records);
}

function projectClaimHypothesis(candidate, centralRecords, segments) {
  const terms = centralRecords.filter((entry) => mentions(candidate.statement, entry.term)).map((entry) => entry.term);
  const fallback = centralRecords.slice(0, 6).map((entry) => entry.term);
  const emergentTerms = (terms.length ? terms : fallback).slice(0, 10);
  const selectors = new Set([candidate.selector]);
  for (const segment of segments) {
    if (!segment._text) continue;
    if (emergentTerms.some((term) => mentions(segment._text, term))) selectors.add(segment.segment_id);
  }
  return {
    hypothesis_id: `HYP-EMERGENT_CLAIM_${candidate.key}`,
    topic_id: `EMERGENT_CLAIM_${candidate.key}`,
    label: candidate.key,
    claim_statement: candidate.statement,
    research_question: `Which source-bounded discriminators support, qualify or defeat the project thesis “${candidate.key}” without presupposing the current registry?`,
    origin: "EXPLICIT_PROJECT_THESIS_CANDIDATE",
    status: "ELIGIBLE_FOR_HUMAN_REVIEW",
    matched_groups: ["EXPLICIT_PROJECT_THESIS", candidate.key, ...emergentTerms.map((term) => `TERM_${slug(term)}`)],
    evidence_segment_ids: [...selectors].slice(0, 200),
    evidence_count: selectors.size,
    selectors_truncated: selectors.size > 200,
    emergent_terms: emergentTerms,
    source_resistance_trigger: "The claim is explicit in the dossier and must remain adjudicable even when no curated topic lens recognizes it.",
    revision_condition: "Resolve the claim's source-bounded evidence, compare at least one independent rival representation, and retire the emergent topic if a better registered formulation covers the same distinctions without loss.",
  };
}

export function detectSourceResistance(segments, legacyHypotheses) {
  const explicit = explicitStressTerms(segments);
  const sourceNative = sourceNativeTerms(segments);
  const sourceNovel = sourceNative.filter((term) => !explicit.some((lemma) => mentions(term, lemma)));
  const central = [...new Map([...explicit, ...sourceNovel].map((term) => [normalize(term), term])).values()].slice(0, MAX_TERMS);
  const explicitKeys = new Set(explicit.map(normalize));
  const auditRecords = central
    .map((term) => termRecord(term, segments, explicitKeys.has(normalize(term))))
    .filter((entry) => entry.selectors.length)
    .sort((a, b) => b.score - a.score || b.selectors.length - a.selectors.length || a.term.localeCompare(b.term));
  const records = auditRecords.filter((entry) => (entry.layers.SOURCE ?? 0) > 0);
  const covered = records.filter((entry) => legacyCoverage(entry.term, legacyHypotheses));
  const uncovered = records.filter((entry) => !legacyCoverage(entry.term, legacyHypotheses));
  const ratio = records.length ? Number((covered.length / records.length).toFixed(4)) : 1;
  const blindSpot = Boolean(records.length >= 3 && (ratio < 0.65 || uncovered.length >= 5));
  const claims = claimCandidates(segments);
  const hypotheses = claims.map((candidate) => projectClaimHypothesis(candidate, auditRecords, segments));
  const operatorCandidate = operatorCandidateForSource(segments, records);
  const openSet = discoverOpenSetOperator(segments, records, {
    blindSpot,
    knownProfileForTexts: (texts, localRecords) => operatorCandidateForTexts(texts, localRecords),
  });

  if (blindSpot && uncovered.length) {
    const top = uncovered.slice(0, MAX_TERMS);
    const selectors = new Set(top.flatMap((entry) => entry.selectors));
    const anchor = top[0].term;
    hypotheses.unshift({
      hypothesis_id: `HYP-EMERGENT_SOURCE_${slug(anchor)}`,
      topic_id: `EMERGENT_SOURCE_${slug(anchor)}`,
      label: `Source-forced constellation: ${top.slice(0, 6).map((entry) => entry.term).join(" / ")}`,
      research_question: `Which distinctions, dependencies or representation failures among ${top.slice(0, 10).map((entry) => entry.term).join(", ")} become invisible when the current topic registry determines the problem in advance?`,
      origin: "SOURCE_FORCED_REGISTRY_RESISTANCE",
      status: "ELIGIBLE_FOR_HUMAN_REVIEW",
      matched_groups: ["SOURCE_RESISTANCE", ...top.slice(0, 10).map((entry) => `TERM_${entry.concept_id}`)],
      evidence_segment_ids: [...selectors].slice(0, 200),
      evidence_count: selectors.size,
      selectors_truncated: selectors.size > 200,
      emergent_terms: top.map((entry) => entry.term),
      operator_candidate: operatorCandidate,
      open_set_candidate: openSet.candidate,
      micro_local_window_ids: openSet.windows.map((window) => window.window_id),
      source_resistance_trigger: `Curated topic coverage captured ${covered.length}/${records.length} source-central terms; ${uncovered.length} remained outside the recognized problem-space.`,
      revision_condition: "Re-run after operator mutation. The emergent constellation is retired only if source-central terms become covered without forcing them into an unrelated legacy topic or erasing their local relations.",
    });
  }

  return {
    hypotheses: hypotheses.slice(0, MAX_HYPOTHESES),
    report: {
      status: blindSpot ? "REGISTRY_BLIND_SPOT" : claims.length ? "EXPLICIT_CLAIMS_REQUIRE_OPEN_ROUTING" : "NO_STRONG_REGISTRY_RESISTANCE_DETECTED",
      central_terms: records.map((entry) => entry.term),
      covered_terms: covered.map((entry) => entry.term),
      uncovered_terms: uncovered.map((entry) => entry.term),
      coverage_ratio: ratio,
      explicit_stress_terms: explicit,
      source_native_terms: sourceNative,
      centrality_basis: "MULTILINGUAL_SOURCE_FREQUENCY_PLUS_SOURCE_DOCUMENT_FREQUENCY_WITH_OPTIONAL_EXPLICIT_STRESS_HINTS",
      operator_candidate: operatorCandidate,
      open_set_status: openSet.status,
      open_set_candidate: openSet.candidate,
      micro_local_windows: openSet.windows,
      emergent_hypotheses: hypotheses.map((entry) => entry.hypothesis_id),
      principle: "SOURCE_CENTRALITY_CAN_FORCE_TOPIC_AND_OPERATOR_REVISION_BUT_CANNOT_BY_ITSELF_VALIDATE_A_PHILOSOPHICAL_CLAIM",
    },
  };
}
