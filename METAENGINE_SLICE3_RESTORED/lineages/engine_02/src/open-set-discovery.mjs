import { createHash } from "node:crypto";

const MAX_WINDOWS = 48;

function norm(value) {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase("und").replace(/\s+/gu, " ").trim();
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function mentions(text, term) {
  const body = escapeRegex(String(term ?? "").trim());
  if (!body) return false;
  return new RegExp(`(?<![\\p{L}\\p{N}_])${body}(?![\\p{L}\\p{N}_])`, "iu").test(String(text ?? ""));
}

function slug(value, fallback = "OPEN_SET") {
  const result = String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/gu, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/gu, "_")
    .replace(/^_+|_+$/gu, "")
    .slice(0, 72);
  return result || fallback;
}

function stableHash(value) {
  return createHash("sha256").update(String(value)).digest("hex").slice(0, 12).toUpperCase();
}

function pairKey(left, right) {
  return [left, right].map(norm).sort().join("::");
}

function contiguousSourceRuns(segments) {
  const source = segments
    .filter((segment) => segment?.archive_state === "ACTIVE" && segment?.layer_routing?.label === "SOURCE" && segment?._text)
    .sort((a, b) => (a.ordinal ?? 0) - (b.ordinal ?? 0));
  const runs = [];
  let current = [];
  for (const segment of source) {
    const previous = current.at(-1);
    if (previous && Number(segment.ordinal ?? 0) - Number(previous.ordinal ?? 0) > 2) {
      if (current.length) runs.push(current);
      current = [];
    }
    current.push(segment);
  }
  if (current.length) runs.push(current);
  return runs;
}

function windowSpecs(run) {
  if (run.length <= 2) return [run];
  const width = Math.min(3, run.length);
  const windows = [];
  for (let start = 0; start <= run.length - width; start += 1) windows.push(run.slice(start, start + width));
  return windows;
}

export function buildMicroLocalWindows(segments, centralRecords, knownProfileForTexts = null) {
  const terms = centralRecords.map((entry) => entry.term ?? entry).filter(Boolean);
  const windows = [];
  const runs = contiguousSourceRuns(segments);
  for (const run of runs) {
    for (const members of windowSpecs(run)) {
      if (windows.length >= MAX_WINDOWS) break;
      const texts = members.map((segment) => String(segment._text ?? ""));
      const joined = texts.join("\n");
      const presentTerms = terms.filter((term) => mentions(joined, term));
      if (!presentTerms.length) continue;
      const pairs = [];
      for (let i = 0; i < presentTerms.length; i += 1) {
        for (let j = i + 1; j < presentTerms.length; j += 1) pairs.push(pairKey(presentTerms[i], presentTerms[j]));
      }
      const known = typeof knownProfileForTexts === "function"
        ? knownProfileForTexts(texts, centralRecords)
        : { profile_hints: [], active_signal_families: [] };
      const ordinalStart = members[0]?.ordinal ?? 0;
      const ordinalEnd = members.at(-1)?.ordinal ?? ordinalStart;
      const signatureMaterial = `${members.map((segment) => segment.segment_id).join("|")}|${presentTerms.map(norm).sort().join("|")}`;
      windows.push({
        window_id: `MW-${String(ordinalStart).padStart(6, "0")}-${String(ordinalEnd).padStart(6, "0")}-${stableHash(signatureMaterial)}`,
        segment_ids: members.map((segment) => segment.segment_id),
        ordinal_start: ordinalStart,
        ordinal_end: ordinalEnd,
        central_terms: presentTerms,
        cooccurrence_pairs: [...new Set(pairs)].sort(),
        known_profile_hints: [...new Set(known.profile_hints ?? [])],
        known_signal_families: [...new Set(known.active_signal_families ?? [])],
        known_candidate_family: known.family ?? "UNRESOLVED",
        raw_text_included: false,
      });
    }
  }
  return windows;
}

function sourceSignature(windows) {
  const pairCounts = new Map();
  const termCounts = new Map();
  for (const window of windows) {
    for (const term of window.central_terms) termCounts.set(norm(term), (termCounts.get(norm(term)) ?? 0) + 1);
    for (const pair of window.cooccurrence_pairs) pairCounts.set(pair, (pairCounts.get(pair) ?? 0) + 1);
  }
  const recurrentPairs = [...pairCounts.entries()]
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 12)
    .map(([pair, count]) => ({ pair, windows: count }));
  const recurrentTerms = [...termCounts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 12)
    .map(([term, count]) => ({ term, windows: count }));
  return { recurrent_terms: recurrentTerms, recurrent_pairs: recurrentPairs };
}

function routeVariation(windows) {
  const signatures = windows.map((window) => [...window.known_profile_hints].sort().join("|") || "UNRESOLVED");
  let transitions = 0;
  for (let index = 1; index < signatures.length; index += 1) if (signatures[index] !== signatures[index - 1]) transitions += 1;
  return {
    distinct_known_profiles: [...new Set(signatures)],
    known_profile_transition_count: transitions,
    unresolved_windows: signatures.filter((value) => value === "UNRESOLVED").length,
  };
}

export function discoverOpenSetOperator(segments, centralRecords, options = {}) {
  const windows = buildMicroLocalWindows(segments, centralRecords, options.knownProfileForTexts);
  const signature = sourceSignature(windows);
  const variation = routeVariation(windows);
  const terms = centralRecords.map((entry) => entry.term ?? entry).filter(Boolean);
  const recurrentTermNames = signature.recurrent_terms.filter((entry) => entry.windows >= 2).map((entry) => entry.term);
  const basisTerms = (recurrentTermNames.length ? recurrentTermNames : terms.map(norm)).slice(0, 6);
  const adequateLocality = windows.length >= 1 && windows.some((window) => window.central_terms.length >= 2);
  const status = options.blindSpot && adequateLocality ? "OPEN_SET_RIVAL_REQUIRED" : "NO_OPEN_SET_PRESSURE";
  const idMaterial = `${basisTerms.join("|")}|${signature.recurrent_pairs.map((entry) => entry.pair).join("|")}`;
  const candidateId = `F-OPEN-${slug(basisTerms.slice(0, 3).join("-"), "SOURCE")}-${stableHash(idMaterial)}`;
  const sourceTermsOriginal = [];
  for (const normalizedTerm of basisTerms) {
    const original = terms.find((term) => norm(term) === normalizedTerm) ?? normalizedTerm;
    sourceTermsOriginal.push(original);
  }
  const candidate = {
    family: "UNKNOWN_OPERATOR_FAMILY",
    candidate: candidateId,
    status,
    source_signature: {
      recurrent_terms: signature.recurrent_terms,
      recurrent_pairs: signature.recurrent_pairs,
      window_count: windows.length,
      local_profile_variation: variation,
    },
    source_trigger_terms: sourceTermsOriginal,
    rival_unitizations: [
      {
        unitization_id: "U-TERM-FIELD",
        description: "Treat recurrent source-native terms as a provisional local field before assigning a known ontological relation type.",
        analytic_consequence: "The operator asks which distinctions appear from term co-presence without presupposing relation-first, relata-first, dependence or reciprocity.",
      },
      {
        unitization_id: "U-WINDOW-TRANSITION",
        description: "Treat changes between adjacent argument windows as the primary analytic event rather than assuming one corpus-wide profile.",
        analytic_consequence: "The operator preserves local regime shifts and can route different windows differently without turning variation into a universal ontology.",
      },
      {
        unitization_id: "U-NEGATIVE-BOUNDARY",
        description: "Treat recurrent absences and broken co-occurrences as provisional boundaries of the source's problem-space.",
        analytic_consequence: "The operator can register what ceases to travel together without claiming that absence itself names a metaphysical structure.",
      },
    ],
    proposed_executable_family: {
      family_id: candidateId,
      title: `Open-set source family: ${sourceTermsOriginal.slice(0, 4).join(" / ") || "unresolved source field"}`,
      protocol_refs: ["OPEN-SET-HERMENEUTIC-DISCOVERY-0.10", "SOURCE-RESISTANCE / OPERATOR-MUTATION 0.1"],
      triggers: sourceTermsOriginal.map((term) => norm(term)).filter(Boolean),
      diagnostic: `What becomes visible in the local source field (${sourceTermsOriginal.join(", ") || "unresolved terms"}) before it is translated into a pre-existing operator family?`,
      constructive_move: "Compare term-field, window-transition and negative-boundary unitizations; preserve a null result when none adds a source-linked distinction.",
      self_risk: "Open-set discovery can become an exception factory that rewards novelty; retire the family if it does not add repeatable local discrimination beyond ordinary routing.",
      positive_model: "Micro-local source-signature probe with no presupposed ontology and explicit rollback to ordinary routing.",
    },
    claim_ceiling: "OPEN_SET_OPERATOR_CANDIDATE_NOT_DISCOVERED_ONTOLOGY_OR_CORE_PROMOTION",
  };
  return { status, candidate, windows };
}
