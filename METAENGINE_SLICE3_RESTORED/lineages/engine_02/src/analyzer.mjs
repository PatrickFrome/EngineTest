import { createHash } from "node:crypto";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const SIGNALS = [
  ["RT01", /(?<![\p{L}\p{N}_])(?:therefore|thus|hence|entails?|implies?|следовательно|отсюда следует|логически влеч[её]т|daher|deshalb|folglich|somit|impliziert)(?![\p{L}\p{N}_])/iu],
  ["RT02", /(?<![\p{L}\p{N}_])(?:is defined as|by definition|определяется как|по определению|ist definiert als|der definition nach)(?![\p{L}\p{N}_])/iu],
  ["RT03", /(?<![\p{L}\p{N}_])(?:is identical to|is the same as|remains the same|тождествен(?:но|на|ен)?|тот же|та же|сохраняет тождество|ist identisch mit|ist dasselbe wie|bleibt dasselbe)(?![\p{L}\p{N}_])/iu],
  ["RT04", /(?<![\p{L}\p{N}_])(?:is necessary for|is sufficient for|necessary condition|sufficient condition|необходимо для|достаточно для|необходимым условием|достаточным условием|ist notwendig für|ist hinreichend für|notwendige[rs]? (?:bedingung|vorbedingung)|hinreichende[rs]? bedingung)(?![\p{L}\p{N}_])/iu],
  ["RT05", /(?<![\p{L}\p{N}_])(?:enables?|makes? .{0,40} possible|opens? the possibility|делает .{0,40} возможн\p{L}*|позволяет|открывает возможность|ermöglicht|macht .{0,40} möglich|eröffnet die möglichkeit)(?![\p{L}\p{N}_])/iu],
  ["RT06", /(?<![\p{L}\p{N}_])(?:causes?|produces?|leads? to|вызывает|причиняет|производит|приводит к|verursacht|bewirkt|führt zu|erzeugt)(?![\p{L}\p{N}_])/iu],
  ["RT07", /(?<![\p{L}\p{N}_])(?:grounds?|in virtue of|metaphysical priority|имеет место в силу|метафизически основан\p{L}*|gründet in|kraft dessen|metaphysischer vorrang)(?![\p{L}\p{N}_])/iu],
  ["RT08", /(?<![\p{L}\p{N}_])(?:depends? on|cannot exist without|зависит от|не может существовать без|hängt von .{0,40} ab|(?:ist|sind|bleibt|werden) .{0,50}abhängig von|abhängig (?:ist|sind|bleibt|werden) von|kann nicht ohne .{0,40} existieren)(?![\p{L}\p{N}_])/iu],
  ["RT09", /(?<![\p{L}\p{N}_])(?:constitutes?|is constituted by|конституирует|конституируется|konstituiert|wird konstituiert)(?![\p{L}\p{N}_])/iu],
  ["RT10", /(?<![\p{L}\p{N}_])(?:realizes?|implements?|реализует|воплощает|имплементирует|realisiert|verwirklicht|implementiert)(?![\p{L}\p{N}_])/iu],
  ["RT11", /(?<![\p{L}\p{N}_])(?:supervenes? on|determination pattern|супервентн\p{L}*|нет различия .{0,30} без различия|superveniert auf|kein unterschied .{0,30} ohne unterschied)(?![\p{L}\p{N}_])/iu],
  ["RT12", /(?<![\p{L}\p{N}_])(?:is part of|is composed of|состоит из|является частью|часть целого|ist teil von|besteht aus)(?![\p{L}\p{N}_])/iu],
  ["RT13", /(?<![\p{L}\p{N}_])(?:is a member of|holds? office|has institutional status|является членом|занимает должность|имеет статус|ist mitglied (?:von|in)|bekleidet das amt|hat institutionellen status)(?![\p{L}\p{N}_])/iu],
  ["RT14", /(?<![\p{L}\p{N}_])(?:functions? as|contributes? to|выполняет функцию|функционирует как|вносит вклад|fungiert als|trägt zu .{0,40} bei)(?![\p{L}\p{N}_])/iu],
  ["RT15", /(?<![\p{L}\p{N}_])(?:is evidence for|supports? the claim|свидетельствует в пользу|подтверждает утверждение|служит доказательством|ist evidenz für|spricht für|stützt (?:die )?(?:these|behauptung))(?![\p{L}\p{N}_])/iu],
  ["RT16", /(?<![\p{L}\p{N}_])(?:is a reason for|justifies?|да[её]т основание|является причиной считать|оправдывает|ist ein grund für|rechtfertigt)(?![\p{L}\p{N}_])/iu],
  ["RT17", /(?<![\p{L}\p{N}_])(?:refers? to|denotes?|обозначает|реферирует|отсылает к|bezieht sich auf|bezeichnet)(?![\p{L}\p{N}_])/iu],
  ["RT18", /(?<![\p{L}\p{N}_])(?:means?|semantic constraint|означает|смысл .{0,20} ограничивает|bedeutet|heißt|semantische einschränkung)(?![\p{L}\p{N}_])/iu],
  ["RT19", /(?<![\p{L}\p{N}_])(?:discloses?|manifests?|reveals?|раскрывает|обнаруживает|являет|erschließt|offenbar(?:t|en|te|ten)|enthüllt)(?![\p{L}\p{N}_])/iu],
  ["RT20", /(?<![\p{L}\p{N}_])(?:derives? from|inherits? from|происходит из|наследует|заимствует|stammt aus|leitet sich (?:von|aus) .{0,40} ab|erbt von)(?![\p{L}\p{N}_])/iu],
  ["RT21", /(?<![\p{L}\p{N}_])(?:ought to|has a duty|is permitted|has a right|обязан|разрешено|имеет право|ist verpflichtet|darf|hat das recht)(?![\p{L}\p{N}_])/iu],
  ["RT22", /(?<![\p{L}\p{N}_])(?:authorizes?|legitimates?|has authority|уполномочивает|легитимирует|обладает властью|ermächtigt|legitimiert|hat autorität)(?![\p{L}\p{N}_])/iu],
  ["RT23", /(?<![\p{L}\p{N}_])(?:represents?|delegates?|acts for|представляет|делегирует|действует от имени|vertritt|delegiert|handelt im namen)(?![\p{L}\p{N}_])/iu],
  ["RT24", /(?<![\p{L}\p{N}_])(?:act jointly|shared intention|coordinate jointly|действуют совместно|общее намерение|координируют действия|handeln gemeinsam|gemeinsame absicht|koordinieren gemeinsam)(?![\p{L}\p{N}_])/iu],
  ["RT25", /(?<![\p{L}\p{N}_])(?:coerces?|dominates?|shapes? the options|принуждает|доминирует|ограничивает возможности|zwingt|beschränkt die möglichkeiten)(?![\p{L}\p{N}_])/iu],
  ["RT26", /(?<![\p{L}\p{N}_])(?:correlates? with|covaries? with|probabilistic association|коррелирует с|коварьирует с|статистически связан|korreliert mit|kovariiert mit|statistisch verbunden)(?![\p{L}\p{N}_])/iu],
  ["RT27", /(?<![\p{L}\p{N}_])(?:independent models? converge|robust across|convergent evidence|независимые модели сходятся|устойчив[а-я]* в разных моделях|конвергентн[а-я]*|unabhängige modelle konvergieren|robust gegenüber|konvergente evidenz)(?![\p{L}\p{N}_])/iu],
  ["RT28", /(?<![\p{L}\p{N}_])(?:precedes?|follows? in time|continues? into|before|after|предшествует|следует во времени|продолжается в|раньше|позже|geht .{0,40} voraus|folgt zeitlich|setzt sich fort|vorher|nachher)(?![\p{L}\p{N}_])/iu]
];

// Bare modal auxiliaries do not identify normativity. They may express a duty,
// an inferential necessity, a methodological requirement or only tense/mood.
// Emitting both candidates forces RT00 + rival review instead of a silent RT21
// promotion. Stronger lexical signals above remain single-relation candidates.
const AMBIGUOUS_SIGNALS = [
  [["RT04", "RT21"], /(?<![\p{L}\p{N}_])(?:must|muss|müssen|musste|müsste|soll|sollen|sollte|sollten|должен|должна|должно|должны)(?![\p{L}\p{N}_])/iu],
  [["RT04", "RT07"], /(?<![\p{L}\p{N}_])(?:fundamental prerequisite|foundational for|grundlegend für|фундаментальн\p{L}* для)(?![\p{L}\p{N}_])/iu],
];

const LANGUAGE_MARKERS = {
  DE: /(?<![\p{L}\p{N}_])(?:der|die|das|den|dem|des|und|oder|nicht|ist|sind|wird|werden|durch|für|mit|von|zu)(?![\p{L}\p{N}_])/giu,
  RU: /(?<![\p{L}\p{N}_])(?:и|или|не|это|как|что|для|из|на|по|к|от|является)(?![\p{L}\p{N}_])/giu,
  EN: /(?<![\p{L}\p{N}_])(?:the|a|an|and|or|not|is|are|was|were|for|from|with|to|of)(?![\p{L}\p{N}_])/giu,
};

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function slug(value) {
  const cleaned = value.normalize("NFKD").replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-|-$/g, "").toUpperCase();
  return (cleaned || "SOURCE").slice(0, 40);
}

function unitsFromText(text) {
  const lines = text.split(/\r?\n/);
  const units = [];
  let buffer = [];
  let start = 1;
  function flush(end) {
    const unitText = buffer.join(" ").replace(/\s+/g, " ").trim();
    if (unitText) units.push({ line_start: start, line_end: end, text: unitText });
    buffer = [];
  }
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim()) {
      flush(index);
      start = index + 2;
    } else {
      if (!buffer.length) start = index + 1;
      buffer.push(line.trim());
    }
  }
  flush(lines.length);
  return units;
}

export function detectRelationCandidates(unitText) {
  const matches = [];
  for (const [rtId, regex] of SIGNALS) {
    const match = regex.exec(unitText);
    if (match) matches.push({ rt_id: rtId, signal: match[0], index: match.index, length: match[0].length, signal_class: "STRONG_LEXICAL" });
  }
  for (const [rtIds, regex] of AMBIGUOUS_SIGNALS) {
    const match = regex.exec(unitText);
    if (!match) continue;
    for (const rtId of rtIds) {
      matches.push({ rt_id: rtId, signal: match[0], index: match.index, length: match[0].length, signal_class: "AMBIGUOUS_MODAL" });
    }
  }
  return matches.sort((a, b) => a.index - b.index || a.rt_id.localeCompare(b.rt_id));
}

export function languageHints(text) {
  return Object.entries(LANGUAGE_MARKERS)
    .map(([language, regex]) => ({ language, marker_count: [...text.matchAll(regex)].length }))
    .filter((item) => item.marker_count > 0)
    .sort((left, right) => right.marker_count - left.marker_count || left.language.localeCompare(right.language));
}

function makeRecord({ baseId, index, unit, candidates, sourceRef, sourceHash, timestamp }) {
  const pivot = candidates[0];
  const left = unit.text.slice(0, pivot.index).trim().replace(/[,:;—-]+$/u, "").trim();
  const right = unit.text.slice(pivot.index + pivot.length).trim().replace(/^[,:;—-]+/u, "").trim();
  const ambiguous = candidates.length > 1;
  const rtId = ambiguous ? "RT00" : pivot.rt_id;
  const activated = ["O0", "O1", "O4", "O9", ...(ambiguous ? ["O6"] : [])];
  const locatedRef = `${sourceRef}#L${unit.line_start}-L${unit.line_end}`;
  const relationList = candidates.map((candidate) => `${candidate.rt_id} ('${candidate.signal}')`).join(", ");
  return {
    record_id: `${baseId}-AUTO-${String(index + 1).padStart(3, "0")}`,
    api_version: "TRC-0.3",
    profile: "ANALYTIC",
    provenance: {
      source_refs: [locatedRef],
      method_version: "CORE 4.0.0-alpha.1 + DAE-LEXICAL-CANDIDATE-0.2",
      agent: "dae-lexical-candidate-generator",
      activity_id: `${baseId}-INTAKE`,
      timestamp,
      artifact_hash: `sha256:${sourceHash}`
    },
    from_node: {
      node_id: "A",
      kind: "CLAIM",
      description: left || `Unresolved source-side claim in: ${unit.text}`,
      claim_facets: { basis: ["TXT"], force: "HYPOTHETICAL", normativity: "UNRESOLVED" },
      support_refs: [locatedRef]
    },
    to_node: {
      node_id: "B",
      kind: "CLAIM",
      description: right || `Unresolved target-side claim in: ${unit.text}`,
      claim_facets: { basis: ["TXT"], force: "HYPOTHETICAL", normativity: "UNRESOLVED" },
      support_refs: [locatedRef]
    },
    transition: {
      inference_mode: rtId === "RT06" ? "CAUSAL" : rtId === "RT21" ? "NORMATIVE" : "UNRESOLVED",
      relation: { rt_id: rtId },
      bridge: {
        status: "UNRESOLVED",
        statement: unit.text,
        support_refs: [locatedRef],
        discriminator: "Compare the lexical candidate with the registry assertion, minimum bridge evidence and strongest live rival."
      }
    },
    scale_check: { applicable: false },
    audit: {
      native_domain: "UNRESOLVED",
      native_method: "Lexical candidate generation; domain method not yet identified",
      activated_operators: activated,
      trv: ambiguous ? ["OPACITY", "UNDERDETERMINATION"] : ["OPACITY"],
      ncv: [],
      rtr: "HIGH",
      cost_note: "Automatic lexical detection only; semantic and domain review mandatory."
    },
    ...(ambiguous ? {
      rivals: candidates.map((candidate) => ({
        description: `Lexical candidate ${candidate.rt_id} triggered by '${candidate.signal}'.`,
        relation_rt_id: candidate.rt_id,
        bridge: "Not yet established.",
        discriminator: "Apply the frozen relation definition and minimum bridge burden to the cited source span."
      }))
    } : {}),
    extensions: {
      audit_semantics: {
        schema_version: "0.1",
        transition_role: "INFERENCE_AUDIT",
        relation_applies_to: "TRANSITION",
        relation_rationale: `Automatic lexical candidates: ${relationList}. No candidate is promoted to semantic gold by the generator.`,
        semantic_review_status: "STRUCTURAL_ONLY",
        human_review_required: true,
        review_notes: [
          "Verify unitization and reconstruct the strongest source claim.",
          "Check whether the lexical signal names the operative relation or merely mentions it.",
          "Add domain-native method and evidence before promotion."
        ]
      }
    },
    outcome: "DEFER",
    open_questions: [
      "Are A and B the correct transition relata?",
      "Which RT, if any, survives explicit bridge and rival comparison?"
    ]
  };
}

export async function analyzeText(engine, inputFile, outputDir) {
  const input = path.resolve(inputFile);
  const out = path.resolve(outputDir);
  try {
    await stat(out);
    throw new Error(`Output directory already exists: ${out}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const bytes = await readFile(input);
  const text = bytes.toString("utf8");
  const sourceHash = sha256(bytes);
  const sourceRef = `LOCAL-SHA256-${sourceHash}`;
  const baseId = slug(path.basename(input, path.extname(input)));
  const timestamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const units = unitsFromText(text).map((unit, index) => ({ unit_id: `${baseId}-U${String(index + 1).padStart(3, "0")}`, ...unit }));
  const detected = units.map((unit) => ({ ...unit, relation_candidates: detectRelationCandidates(unit.text) }));
  const candidates = detected.filter((unit) => unit.relation_candidates.length);

  await mkdir(path.join(out, "records"), { recursive: true });
  const recordFiles = [];
  for (let index = 0; index < candidates.length; index += 1) {
    const record = makeRecord({ baseId, index, unit: candidates[index], candidates: candidates[index].relation_candidates, sourceRef, sourceHash, timestamp });
    const file = path.join(out, "records", `${record.record_id}.json`);
    await writeFile(file, `${JSON.stringify(record, null, 2)}\n`, "utf8");
    recordFiles.push(file);
    candidates[index].record_id = record.record_id;
  }
  const validation = await engine.validateInputs(recordFiles.length ? [path.join(out, "records")] : []);
  const bundle = {
    bundle_version: "DAE-INTAKE-0.1",
    generated_at: timestamp,
    source: {
      original_path: path.basename(input),
      path_scope: "BASENAME_ONLY",
      media_type: [".md", ".markdown"].includes(path.extname(input).toLowerCase()) ? "text/markdown" : "text/plain",
      byte_length: bytes.length,
      sha256: sourceHash,
      source_id: sourceRef
    },
    method: "PARAGRAPH_UNITIZATION_PLUS_TRILINGUAL_DE_RU_EN_LEXICAL_RT_CANDIDATES",
    language_hints: languageHints(text),
    claim_ceiling: "CANDIDATE_GENERATION_ONLY",
    unit_count: detected.length,
    candidate_record_count: recordFiles.length,
    units: detected,
    validation: validation.counts
  };
  await writeFile(path.join(out, "analysis_bundle.json"), `${JSON.stringify(bundle, null, 2)}\n`, "utf8");
  return { output_dir: out, bundle, validation };
}
