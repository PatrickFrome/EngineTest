import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { parseOoxmlParagraphs, refineDocx } from "./corpus-refinery.mjs";
import { projectPath, readJson } from "./paths.mjs";
import { buildEtymologyPass } from "./etymology.mjs";

const execFileAsync = promisify(execFile);
const TERMINAL_STATUSES = new Set(["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"]);
const PASSES = ["RECONSTRUCTOR", "CRITIC", "ADJUDICATOR", "SYNTHESIS"];
const MAX_EVIDENCE_SELECTORS = 12;
const MAX_MODEL_SOURCE_SEGMENTS = 12;
const MAX_MODEL_SOURCE_CHARACTERS = 14_000;

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  }
  return value;
}

function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

function issueSummary(issues, limit = 5) {
  return issues.slice(0, limit).map((item) => `${item.code} ${item.at}: ${item.message}`).join("; ");
}

async function requireNewDirectory(directory) {
  try {
    await stat(directory);
    throw new Error(`Output directory already exists: ${directory}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

function clamp(value, floor, cap) {
  return Number(Math.max(floor, Math.min(cap, value)).toFixed(3));
}

function spreadPick(values, limit) {
  if (values.length <= limit) return [...values];
  const picked = [];
  for (let index = 0; index < limit; index += 1) {
    picked.push(values[Math.round(index * (values.length - 1) / (limit - 1))]);
  }
  return [...new Set(picked)];
}

function normalizeIdentifier(value, fallback = "AUTO") {
  const normalized = String(value ?? "")
    .normalize("NFKD")
    .replace(/[^A-Za-z0-9_-]+/gu, "-")
    .replace(/^-+|-+$/gu, "")
    .toUpperCase();
  return normalized.length >= 2 ? normalized : fallback;
}

function autoCorpusThesis() {
  return {
    thesis_id: "AUTO_CORPUS_GENRE",
    title: "Статус анализируемого корпуса",
    statement: "Корпус должен оцениваться в соответствии с его структурно установленным жанром и происхождением слоёв, а не как автоматически единый первичный источник.",
    evaluation_mode: "CORPUS_GENRE",
    topic_id: null,
    case_matrix_id: null,
    scale: "DOCUMENT",
    source_burden: "STRUCTURAL",
    minimum_evidence_count: 1,
    minimum_distinct_groups: 1,
    minimum_resolved_sources: 0,
    reconstruction: {
      A: "Автоматическая сегментация различает источниковые, реконструктивные, проектные, критические и процедурные слои.",
      P: "Жанровый статус корпуса ограничивает доказательную роль содержащихся в нём утверждений.",
      B: "Система должна отделять структурную характеристику документа от содержательной истинности его тезисов.",
      operative_relations: ["RT02", "RT15", "RT17"],
    },
    rivals: [{
      rival_id: "AUTO_RIVAL_UNIFIED_SOURCE",
      statement: "Все сегменты документа принадлежат одному источниковому голосу и могут суммироваться без различения происхождения.",
      discriminator: "Проверить маршруты слоёв, роль контейнера и разрешение ссылок на уровне отдельных утверждений.",
    }],
    deterministic_analysis: {
      key_points: ["Структурная классификация задаёт допустимый предел последующих выводов."],
      limitations: ["Маршрутизация происхождения остаётся консервативной и не заменяет источниковедческую проверку."],
      recommendation: "Сохранять происхождение каждого существенного утверждения во всех последующих проходах.",
    },
  };
}

function automaticHypothesisPolicy(hypothesis) {
  const statement = String(hypothesis.claim_statement ?? "");
  const haystack = `${hypothesis.topic_id} ${hypothesis.label} ${statement}`.normalize("NFKC").toLocaleLowerCase("und");
  const explicit = hypothesis.origin === "EXPLICIT_PROJECT_THESIS_CANDIDATE" && statement.trim();
  const method = /method|operator|graph|node[- ]?edge|mutation|метод|оператор|граф|узел|ребр|мутац/iu.test(haystack);
  const universal = /universal|universality|as such|reality as such|универсал|реальност[ьи] как таков|всей реальност/iu.test(haystack);
  const diachronic = /DIACHRONIC|GENEALOGY|HISTORY|CHRONO|diachron|genealog|истор|генеалог|диахрон/iu.test(haystack);
  const strongOntology = /ontolog(?:y|ical|ically)|онтолог\p{L}*|primary to|prior to|первич\p{L}* по отношению/iu.test(haystack);

  if (method) return {
    evaluationMode: "META_METHOD",
    scale: "METHOD",
    sourceBurden: "INTERNAL_DOSSIER",
    minimumResolvedSources: 0,
    burdenNote: "Метаметодический тезис оценивается как кандидат изменения процедуры, а не как свидетельство истинности объекта.",
  };
  if (universal) return {
    evaluationMode: "UNIVERSALIZATION",
    scale: "UNIVERSAL",
    sourceBurden: "MULTI_SOURCE",
    minimumResolvedSources: 3,
    burdenNote: "Универсализация требует независимого межисточникового и контрпримерного бремени; локальный корпус этого сам не даёт.",
  };
  if (diachronic) return {
    evaluationMode: "SOURCE_DEPENDENT",
    scale: "DIACHRONIC",
    sourceBurden: "MULTI_SOURCE",
    minimumResolvedSources: 2,
    burdenNote: "Диахроническое утверждение требует датированных, независимо разрешённых источников и явного моста наследования.",
  };
  if (explicit && strongOntology) return {
    evaluationMode: "SOURCE_DEPENDENT",
    scale: "WORK",
    sourceBurden: "MULTI_SOURCE",
    minimumResolvedSources: 1,
    burdenNote: "Сильная онтологическая промоция не может быть квалифицирована только локальной совместностью терминов; нужен независимо разрешённый первичный контекст.",
  };
  if (explicit) return {
    evaluationMode: "SOURCE_DEPENDENT",
    scale: "WORK",
    sourceBurden: "PRIMARY_TEXT",
    minimumResolvedSources: 0,
    burdenNote: "Тезис допускается только как source-bounded reconstruction: локальные SOURCE-сегменты могут сделать его содержательно проверяемым, но не внешне подтверждённым.",
  };
  const sourceDependent = /DIACHRONIC|GENEALOGY|HISTORY|CHRONO/iu.test(hypothesis.topic_id);
  const meta = /META/iu.test(hypothesis.topic_id);
  return {
    evaluationMode: sourceDependent ? "SOURCE_DEPENDENT" : meta ? "META_METHOD" : "INTERNAL_MODEL",
    scale: sourceDependent ? "DIACHRONIC" : meta ? "METHOD" : "LOCAL",
    sourceBurden: sourceDependent ? "MULTI_SOURCE" : "INTERNAL_DOSSIER",
    minimumResolvedSources: sourceDependent ? 2 : 0,
    burdenNote: sourceDependent
      ? "Историческая/генеалогическая гипотеза требует разрешённого внешнего источникового моста."
      : "Лексико-структурное обнаружение допускает внутреннюю модель, но не внешнюю семантическую валидацию.",
  };
}

function explicitClaimReconstruction(hypothesis, policy) {
  const terms = (hypothesis.emergent_terms ?? []).slice(0, 10);
  const termText = terms.length ? terms.join(", ") : hypothesis.matched_groups.join(", ");
  return {
    A: `Досье явно сохраняет тезис «${hypothesis.label}» как отдельный объект проверки и связывает его с source-central полем: ${termText}.`,
    P: "Явная формулировка проекта не является собственным доказательством. Тезис должен быть проверен по SOURCE-селекторам, соседнему контексту, конкурирующей unitization и цене перевода в метаязык проекта.",
    B: `Проверяемый тезис: ${hypothesis.claim_statement}`,
    operative_relations: ["RT15", "RT18", ...(policy.evaluationMode === "SOURCE_DEPENDENT" ? ["RT20"] : []), ...(policy.evaluationMode === "UNIVERSALIZATION" ? ["RT26", "RT27"] : [])],
  };
}

export function buildAutomaticExpertProfile(hypothesisBank, segmentationManifest, sourceMap, options = {}) {
  const theses = [autoCorpusThesis()];
  for (const hypothesis of hypothesisBank.hypotheses) {
    const policy = automaticHypothesisPolicy(hypothesis);
    const explicit = hypothesis.origin === "EXPLICIT_PROJECT_THESIS_CANDIDATE" && Boolean(hypothesis.claim_statement?.trim());
    const groups = hypothesis.matched_groups.join(", ");
    theses.push({
      thesis_id: `AUTO_${normalizeIdentifier(hypothesis.topic_id)}`,
      title: hypothesis.label,
      statement: explicit
        ? hypothesis.claim_statement
        : `Корпус делает исследовательский вопрос «${hypothesis.research_question}» содержательно доступным для экспертной проверки, но сам факт тематического обнаружения ещё не является внешним подтверждением ответа.`,
      evaluation_mode: policy.evaluationMode,
      topic_id: hypothesis.topic_id,
      case_matrix_id: null,
      scale: policy.scale,
      source_burden: policy.sourceBurden,
      minimum_evidence_count: hypothesis.origin === "EXPLICIT_PROJECT_THESIS_CANDIDATE" ? 2 : hypothesis.origin === "SOURCE_FORCED_REGISTRY_RESISTANCE" ? 3 : Math.max(1, Math.min(3, hypothesis.evidence_count)),
      minimum_distinct_groups: hypothesis.origin === "EXPLICIT_PROJECT_THESIS_CANDIDATE" || hypothesis.origin === "SOURCE_FORCED_REGISTRY_RESISTANCE" ? 2 : Math.max(1, Math.min(2, hypothesis.matched_groups.length)),
      minimum_resolved_sources: policy.minimumResolvedSources,
      reconstruction: explicit
        ? explicitClaimReconstruction(hypothesis, policy)
        : {
          A: `В корпусе совместно обнаружены тематические группы: ${groups}.`,
          P: "Устойчивая тематическая совместность лицензирует постановку и реконструкцию вопроса, но не истинность ответа и не авторскую атрибуцию.",
          B: `Тема «${hypothesis.label}» допускается как внутренняя аналитическая гипотеза с обязательной проверкой происхождения и сильнейшего соперника.`,
          operative_relations: ["RT15", "RT18", ...(policy.evaluationMode === "SOURCE_DEPENDENT" ? ["RT20", "RT28"] : [])],
        },
      rivals: [{
        rival_id: `AUTO_RIVAL_${normalizeIdentifier(hypothesis.topic_id)}`,
        statement: explicit
          ? "Проектная формулировка может быть эффектом выбранной unitization или метаязыка: те же исходные фрагменты могут поддерживать более слабую, иначе структурированную или несводимую реконструкцию."
          : "Кластер порождён лексической совместностью, повтором или смешением слоёв и не выражает устойчивой аргументативной структуры.",
        discriminator: explicit
          ? "Сопоставить тезис с точными SOURCE-селекторами и соседним контекстом, затем повторить анализ минимум с одной rival unitization; отдельно зафиксировать различия, которые каждая репрезентация делает видимыми и стирает."
          : "Разрешить происхождение селекторов, удалить влияние повторов и независимо проверить A/P/B и функцию терминов.",
      }],
      deterministic_analysis: {
        key_points: explicit ? [
          `Явный проектный тезис сохранён как самостоятельный объект adjudication вместо растворения в topic registry: ${hypothesis.label}.`,
          `Он связан с ${hypothesis.evidence_count} селекторными кандидатами; source-central terms: ${(hypothesis.emergent_terms ?? []).join(", ") || "не выделены"}.`,
          policy.burdenNote,
        ] : [
          `Обнаружено ${hypothesis.evidence_count} селекторных кандидатов и ${hypothesis.matched_groups.length} различимых тематических групп.`,
          "Автоматическое обнаружение темы — основание для анализа, но не семантическая валидация.",
        ],
        limitations: [hypothesis.revision_condition, ...(hypothesis.source_resistance_trigger ? [hypothesis.source_resistance_trigger] : [])],
        recommendation: explicit
          ? "Проверить фактический тезис, а не только факт его тематического обнаружения; сохранить source-bounded ceiling, rival unitization и rollback при operator mutation."
          : policy.evaluationMode === "SOURCE_DEPENDENT"
            ? "Завершить внешнее разрешение источников и датированных переходов до исторического вывода."
            : "Проверить гипотезу на стратифицированной выборке и против сильнейшей альтернативы.",
      },
    });
  }
  for (const matrix of hypothesisBank.case_matrices) {
    theses.push({
      thesis_id: `AUTO_TEST_${normalizeIdentifier(matrix.matrix_id)}`,
      title: matrix.label,
      statement: `Матрица «${matrix.label}» пригодна как гетерогенный стресс-тест, но не как самостоятельное доказательство универсальной теории.`,
      evaluation_mode: "TEST_DESIGN",
      topic_id: null,
      case_matrix_id: matrix.matrix_id,
      scale: "METHOD",
      source_burden: "DOMAIN_HETEROGENEOUS",
      minimum_evidence_count: matrix.required_case_count,
      minimum_distinct_groups: matrix.required_case_count,
      minimum_resolved_sources: 0,
      reconstruction: {
        A: `Матрица содержит ${matrix.matched_case_count} разнородных случаев при минимуме ${matrix.required_case_count}.`,
        P: "Гетерогенный набор методически полезен, если используется для поиска провалов и категориальных ошибок, а не для автоматической универсализации.",
        B: "Матрица допускается как дизайн стресс-теста с отдельными критериями по каждому случаю.",
        operative_relations: ["RT15", "RT26", "RT27"],
      },
      rivals: [{
        rival_id: `AUTO_RIVAL_${normalizeIdentifier(matrix.matrix_id)}`,
        statement: "Случаи подобраны постфактум и создают видимость охвата без независимых критериев провала.",
        discriminator: "Пререгистрировать критерии включения и провала, затем добавить отрицательные и пограничные случаи.",
      }],
      deterministic_analysis: {
        key_points: ["Гетерогенность повышает диагностическую ценность дизайна, но не силу универсального подтверждения."],
        limitations: [matrix.revision_condition],
        recommendation: "Использовать каждый случай как самостоятельный домен и явно фиксировать контрпримеры.",
      },
    });
  }
  const sourceId = segmentationManifest.source.source_id;
  return {
    profile_version: "DAE-EXPERT-PROFILE-1.0",
    profile_id: `AUTO-${normalizeIdentifier(sourceId)}`,
    title: options.title ?? `Автоматический экспертный профиль: ${sourceId}`,
    language: options.language ?? "und",
    domain: options.domain ?? "автоматическая критическая аналитика корпуса",
    decision_policy: {
      automatic_finalization: true,
      terminal_statuses: ["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"],
      insufficient_is_terminal: true,
      model_may_not_override_deterministic_gates: true,
      supported_requires_burden_satisfaction: true,
      confidence_floor: 0.45,
      confidence_cap: 0.9,
    },
    theses,
    global_synthesis: {
      title: "Финальная автоматическая аналитика корпуса",
      core_finding: `Корпус ${sourceId} автоматически разделён на структурные слои, тематические гипотезы и проверяемые тезисы; окончательная сила каждого результата ограничена разрешением источников и типом доказательного бремени.`,
      decisive_reasons: [
        `Выявлено ${hypothesisBank.hypotheses.length} тематических гипотез и ${hypothesisBank.case_matrices.length} гетерогенных матриц.`,
        `На уровне утверждений разрешено ${sourceMap.coverage.resolved_claim_level_citations} внешних ссылок.`,
        "Каждый тезис завершён одним из четырёх терминальных статусов без превращения нехватки данных в положительный результат.",
      ],
      rejected_conclusions: ["Лексическая совместность сама по себе доказывает истинность, авторство или универсальность тезиса."],
      next_actions: [
        "Разрешить происхождение ключевых селекторов на уровне утверждений.",
        "Проверить A/P/B, типы отношений и сильнейших соперников на независимой выборке.",
      ],
    },
  };
}

async function loadRefinery(engine, refineryDirectory) {
  const directory = path.resolve(refineryDirectory);
  const files = {
    segmentationManifest: path.join(directory, "segmentation_manifest.json"),
    sourceMap: path.join(directory, "source_map.json"),
    hypothesisBank: path.join(directory, "hypothesis_bank.json"),
    archiveMap: path.join(directory, "archive_map.json"),
    formulaRegistry: path.join(directory, "formula_registry.json"),
    ledgerSummary: path.join(directory, "claim_ledger_summary.json"),
    claimLedger: path.join(directory, "claim_ledger.jsonl"),
    report: path.join(directory, "REFINERY_REPORT.json"),
  };
  const [
    segmentationText,
    sourceMap,
    hypothesisBank,
    archiveMap,
    formulaRegistry,
    ledgerSummary,
    ledgerText,
    report,
  ] = await Promise.all([
    readFile(files.segmentationManifest, "utf8"),
    readJson(files.sourceMap),
    readJson(files.hypothesisBank),
    readJson(files.archiveMap),
    readJson(files.formulaRegistry),
    readJson(files.ledgerSummary),
    readFile(files.claimLedger, "utf8"),
    readJson(files.report),
  ]);
  let segmentationManifest;
  try {
    segmentationManifest = JSON.parse(segmentationText);
  } catch (error) {
    throw new Error(`${files.segmentationManifest}: ${error.message}`);
  }
  const validationSets = [
    ["segmentation_manifest", engine.structural.validateSegmentationManifest(segmentationManifest)],
    ["source_map", engine.structural.validateSourceMap(sourceMap)],
    ["hypothesis_bank", engine.structural.validateHypothesisBank(hypothesisBank)],
    ["archive_map", engine.structural.validateArchiveMap(archiveMap)],
    ["formula_registry", engine.structural.validateFormulaRegistry(formulaRegistry)],
  ];
  const invalid = validationSets.filter(([, issues]) => issues.length);
  if (invalid.length) throw new Error(`EXPERT_REFINERY_SCHEMA_FAILED: ${invalid.map(([name, issues]) => `${name}: ${issueSummary(issues)}`).join(" | ")}`);
  const ledger = ledgerText.split(/\r?\n/u).filter(Boolean).map((line, index) => {
    try {
      return JSON.parse(line);
    } catch (error) {
      throw new Error(`${files.claimLedger}:${index + 1}: ${error.message}`);
    }
  });
  const ledgerIssues = ledger.flatMap((entry, index) => engine.structural.validateClaimLedgerEntry(entry).map((item) => ({ ...item, at: `/line/${index + 1}${item.at}` })));
  if (ledgerIssues.length) throw new Error(`EXPERT_CLAIM_LEDGER_SCHEMA_FAILED: ${issueSummary(ledgerIssues)}`);
  const sourceIds = new Set([
    segmentationManifest.source.source_id,
    sourceMap.document_source_id,
    hypothesisBank.source_id,
    archiveMap.source_id,
    formulaRegistry.source_id,
    ledgerSummary.source_id,
    report.source_id,
  ]);
  if (sourceIds.size !== 1) throw new Error(`EXPERT_SOURCE_ID_MISMATCH: ${[...sourceIds].join(", ")}`);
  if (ledger.length !== ledgerSummary.entry_count || ledger.length !== report.counts.claim_ledger_entries) {
    throw new Error(`EXPERT_LEDGER_COUNT_MISMATCH: lines=${ledger.length}, summary=${ledgerSummary.entry_count}, report=${report.counts.claim_ledger_entries}`);
  }
  const artifactHashes = new Set([
    segmentationManifest.source.artifact_sha256,
    sourceMap.document_artifact.sha256,
    report.artifact_sha256,
  ]);
  if (artifactHashes.size !== 1) throw new Error(`EXPERT_ARTIFACT_HASH_MISMATCH: ${[...artifactHashes].join(", ")}`);
  return {
    directory,
    files,
    segmentationText,
    segmentationManifest,
    sourceMap,
    hypothesisBank,
    archiveMap,
    formulaRegistry,
    ledgerSummary,
    ledger,
    report,
  };
}

function topicEvidence(thesis, refinery) {
  const topic = thesis.topic_id
    ? refinery.hypothesisBank.hypotheses.find((entry) => entry.topic_id === thesis.topic_id)
    : null;
  const matrix = thesis.case_matrix_id
    ? refinery.hypothesisBank.case_matrices.find((entry) => entry.matrix_id === thesis.case_matrix_id)
    : null;
  const matrixSelectors = matrix?.cases.flatMap((entry) => entry.evidence_segment_ids.slice(0, 1)) ?? [];
  let evidenceCount = topic?.evidence_count ?? 0;
  let distinctGroupCount = topic?.matched_groups.length ?? 0;
  let selectors = topic?.evidence_segment_ids ?? [];
  let selectorsTruncated = topic?.selectors_truncated ?? false;
  if (matrix && thesis.evaluation_mode === "TEST_DESIGN") {
    evidenceCount = matrix.cases.reduce((sum, entry) => sum + entry.evidence_count, 0);
    distinctGroupCount = matrix.matched_case_count;
    selectors = matrixSelectors;
    selectorsTruncated = matrix.cases.some((entry) => entry.evidence_count > entry.evidence_segment_ids.length);
  } else if (matrix) {
    selectors = [...selectors, ...matrixSelectors];
  }
  if (thesis.evaluation_mode === "CORPUS_GENRE") {
    const layerCounts = refinery.segmentationManifest.counts.layer_routes;
    const routedLayers = Object.entries(layerCounts).filter(([layer, count]) => layer !== "UNRESOLVED" && count > 0);
    evidenceCount = routedLayers.reduce((sum, [, count]) => sum + count, 0);
    distinctGroupCount = routedLayers.length;
    selectors = routedLayers.flatMap(([layer]) => {
      const segment = refinery.segmentationManifest.ooxml_segments.find((entry) => entry.layer_routing.label === layer);
      return segment ? [segment.segment_id] : [];
    });
    selectorsTruncated = evidenceCount > selectors.length;
  }
  const uniqueSelectors = [...new Set(selectors)];
  const layerBySelector = new Map(refinery.segmentationManifest.ooxml_segments.map((entry) => [entry.segment_id, entry.layer_routing?.label ?? "UNRESOLVED"]));
  const sourceLayerSelectorCount = uniqueSelectors.filter((selector) => layerBySelector.get(selector) === "SOURCE").length;
  const projectClaimSelectorCount = uniqueSelectors.filter((selector) => layerBySelector.get(selector) === "PROJECT_CLAIM").length;
  if (topic && ["EXPLICIT_PROJECT_THESIS_CANDIDATE", "SOURCE_FORCED_REGISTRY_RESISTANCE"].includes(topic.origin)) {
    distinctGroupCount = new Set(uniqueSelectors.map((selector) => layerBySelector.get(selector) ?? "UNRESOLVED")).size;
  }
  const selected = spreadPick(uniqueSelectors, MAX_EVIDENCE_SELECTORS);
  return {
    topic_id: thesis.topic_id,
    topic_present: thesis.topic_id === null || Boolean(topic),
    evidence_count: evidenceCount,
    distinct_group_count: distinctGroupCount,
    case_matrix_present: thesis.case_matrix_id === null || Boolean(matrix),
    resolved_source_count: refinery.sourceMap.coverage.resolved_claim_level_citations,
    source_layer_selector_count: sourceLayerSelectorCount,
    project_claim_selector_count: projectClaimSelectorCount,
    selectors: selected,
    selectors_truncated: selectorsTruncated || uniqueSelectors.length > selected.length,
  };
}

function adjudicateDeterministically(thesis, evidence, refinery) {
  const policy = {
    status: "INSUFFICIENT",
    confidence: 0.9,
    allowed_statuses: ["INSUFFICIENT"],
    gate: "EVIDENCE_THRESHOLD_NOT_MET",
    decisive_reasons: [],
  };
  const missing = [];
  if (!evidence.topic_present) missing.push("тематическая гипотеза отсутствует");
  if (!evidence.case_matrix_present) missing.push("заданная матрица случаев отсутствует");
  if (evidence.evidence_count < thesis.minimum_evidence_count) missing.push(`селекторов ${evidence.evidence_count} < ${thesis.minimum_evidence_count}`);
  if (evidence.distinct_group_count < thesis.minimum_distinct_groups) missing.push(`различимых групп ${evidence.distinct_group_count} < ${thesis.minimum_distinct_groups}`);
  if (missing.length) {
    policy.decisive_reasons = [`Не выполнен минимальный доказательный порог: ${missing.join("; ")}.`];
    return policy;
  }
  const sourceShortfall = evidence.resolved_source_count < thesis.minimum_resolved_sources;
  if (thesis.evaluation_mode === "CORPUS_GENRE") {
    const composite = refinery.sourceMap.document_artifact.role === "COMPOSITE_CONTAINER";
    const multiLayer = evidence.distinct_group_count >= 4;
    policy.status = composite && multiLayer ? "SUPPORTED" : "QUALIFIED";
    policy.confidence = composite && multiLayer ? 0.98 : 0.76;
    policy.allowed_statuses = [policy.status];
    policy.gate = composite && multiLayer ? "STRUCTURAL_COMPOSITE_GENRE_CONFIRMED" : "STRUCTURAL_GENRE_PARTIALLY_CONFIRMED";
    policy.decisive_reasons = [
      `Роль контейнера: ${refinery.sourceMap.document_artifact.role}.`,
      `Непустых маршрутизированных слоёв происхождения: ${evidence.distinct_group_count}.`,
      `Разрешённых ссылок на уровне утверждений: ${evidence.resolved_source_count}.`,
    ];
    return policy;
  }
  if (thesis.evaluation_mode === "TEST_DESIGN") {
    policy.status = "SUPPORTED";
    policy.confidence = 0.9;
    policy.allowed_statuses = ["SUPPORTED"];
    policy.gate = "HETEROGENEOUS_TEST_DESIGN_THRESHOLD_MET_SCOPE_LOCKED_TO_DESIGN";
    policy.decisive_reasons = [
      `Матрица содержит ${evidence.distinct_group_count} различимых случаев и проходит заданный минимум ${thesis.minimum_distinct_groups}.`,
      "Статус относится к пригодности дизайна для стресс-теста, а не к истинности проверяемой онтологии.",
    ];
    return policy;
  }
  if (thesis.evaluation_mode === "UNIVERSALIZATION") {
    if (sourceShortfall) {
      policy.status = "REJECTED";
      policy.confidence = 0.95;
      policy.allowed_statuses = ["REJECTED"];
      policy.gate = "UNIVERSAL_PROMOTION_REJECTED_SOURCE_AND_DOMAIN_BURDEN_UNMET";
      policy.decisive_reasons = [
        `Универсальный тезис требует ${thesis.minimum_resolved_sources} разрешённых источников, доступно ${evidence.resolved_source_count}.`,
        "Лексическая применимость общей рамки к выбранным случаям не влечёт универсальную онтологическую структуру.",
      ];
    } else {
      policy.status = "QUALIFIED";
      policy.confidence = 0.65;
      policy.allowed_statuses = ["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"];
      policy.gate = "UNIVERSAL_BURDEN_STRUCTURALLY_MET_SEMANTIC_ADJUDICATION_OPEN";
      policy.decisive_reasons = ["Формальные минимумы выполнены; универсальный вывод всё ещё требует содержательной проверки мостов и контрпримеров."];
    }
    return policy;
  }
  if (thesis.evaluation_mode === "SOURCE_DEPENDENT") {
    const sourceBoundedDossier = thesis.source_burden === "PRIMARY_TEXT" && thesis.minimum_resolved_sources === 0;
    if (sourceBoundedDossier) {
      if (evidence.source_layer_selector_count < 1) {
        policy.status = "INSUFFICIENT";
        policy.confidence = 0.94;
        policy.allowed_statuses = ["INSUFFICIENT"];
        policy.gate = "SOURCE_BOUNDED_RECONSTRUCTION_REQUIRES_LOCAL_SOURCE_LAYER";
        policy.decisive_reasons = [
          "Явный проектный тезис сохранён, но среди его evidence selectors нет SOURCE-сегмента, поэтому source-bounded реконструкция пока невозможна.",
        ];
      } else {
        policy.status = "QUALIFIED";
        policy.confidence = 0.72;
        policy.allowed_statuses = ["QUALIFIED", "REJECTED", "INSUFFICIENT"];
        policy.gate = "SOURCE_BOUNDED_RECONSTRUCTION_OPEN_EXTERNAL_VALIDATION_PENDING";
        policy.decisive_reasons = [
          `Локальное доказательное поле содержит ${evidence.source_layer_selector_count} SOURCE-селектор(ов) и ${evidence.project_claim_selector_count} PROJECT_CLAIM-селектор(ов).`,
          "Это делает фактический тезис содержательно проверяемым внутри досье, но не разрешает статус SUPPORTED без независимого source resolution и семантического adjudication.",
          "Rival unitization остаётся обязательной: source-central terms не должны автоматически наследовать relation ontology проекта.",
        ];
      }
      return policy;
    }
    if (sourceShortfall) {
      policy.status = "INSUFFICIENT";
      policy.confidence = 0.96;
      policy.allowed_statuses = ["INSUFFICIENT"];
      policy.gate = "SOURCE_DEPENDENT_CLAIM_BLOCKED_BY_UNRESOLVED_CITATIONS";
      policy.decisive_reasons = [
        `Тезис требует ${thesis.minimum_resolved_sources} разрешённых источников на уровне утверждений, доступно ${evidence.resolved_source_count}.`,
        "Частота терминов и локатороподобных маркеров не заменяет датированного источникового моста.",
      ];
    } else {
      policy.status = "QUALIFIED";
      policy.confidence = 0.7;
      policy.allowed_statuses = ["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"];
      policy.gate = "SOURCE_BURDEN_STRUCTURALLY_MET_SEMANTIC_ADJUDICATION_OPEN";
      policy.decisive_reasons = ["Минимальное источниковое бремя выполнено; содержательная сила определяется экспертной проверкой переходов."];
    }
    return policy;
  }
  if (thesis.evaluation_mode === "META_METHOD") {
    policy.status = "QUALIFIED";
    policy.confidence = 0.82;
    policy.allowed_statuses = ["QUALIFIED", "REJECTED", "INSUFFICIENT"];
    policy.gate = "META_METHOD_SUPPORTED_AS_CONTROL_NOT_AS_TRUTH_EVIDENCE";
    policy.decisive_reasons = [
      "Самоприменение критики является процедурным контролем против циркуляции.",
      "Прохождение внутренней процедуры не доказывает внешнюю истинность результата.",
    ];
    return policy;
  }
  policy.status = "QUALIFIED";
  policy.confidence = sourceShortfall ? 0.76 : 0.84;
  policy.allowed_statuses = ["QUALIFIED", "REJECTED", "INSUFFICIENT"];
  policy.gate = sourceShortfall ? "INTERNAL_MODEL_ONLY_EXTERNAL_SOURCE_BURDEN_UNMET" : "INTERNAL_MODEL_COHERENCE_ONLY";
  policy.decisive_reasons = [
    `Тематический порог выполнен: ${evidence.evidence_count} селекторов, ${evidence.distinct_group_count} групп.`,
    "Результат ограничен статусом внутренней модели: лексическое и структурное покрытие не устанавливает истинность или авторскую атрибуцию.",
  ];
  return policy;
}

function rivalImpact(status, mode) {
  if (status === "REJECTED") return "DECISIVE";
  if (status === "INSUFFICIENT") return "UNRESOLVED";
  if (mode === "CORPUS_GENRE") return "DEFEATED";
  return "LIMITS_CLAIM";
}

function rivalAnswer(status, mode) {
  if (status === "REJECTED") return "Соперник выявляет недопустимый переход и является решающим для отвержения тезиса в текущем прогоне.";
  if (status === "INSUFFICIENT") return "Доступных разрешённых свидетельств недостаточно, чтобы устранить соперника или предпочесть ему исходный тезис.";
  if (mode === "CORPUS_GENRE") return "Структурные признаки многослойного составного контейнера непосредственно различают документ и единый первичный источник.";
  return "Соперник не уничтожает ограниченную методическую или реконструктивную ценность, но запрещает её промоцию в более сильный вывод.";
}

function deterministicAssessment(thesis, pass, gate, evidence) {
  const rival = thesis.rivals[0];
  const sourceOrigin = thesis.evaluation_mode === "CORPUS_GENRE" ? "MIXED" : "UNRESOLVED";
  const passAnalysis = {
    RECONSTRUCTOR: `Восстановлена схема A/P/B для тезиса «${thesis.title}»; типы отношений сохранены раздельно.`,
    CRITIC: `Проверен сильнейший соперник: ${rival.statement}`,
    ADJUDICATOR: gate.decisive_reasons.join(" "),
  }[pass];
  return {
    thesis_id: thesis.thesis_id,
    pass,
    A: thesis.reconstruction.A,
    P: thesis.reconstruction.P,
    B: thesis.reconstruction.B,
    proposed_status: gate.status,
    confidence: gate.confidence,
    operative_relations: thesis.reconstruction.operative_relations,
    source_origin: sourceOrigin,
    evidence_selectors: evidence.selectors,
    strongest_rival: {
      statement: rival.statement,
      impact: rivalImpact(gate.status, thesis.evaluation_mode),
      answer: rivalAnswer(gate.status, thesis.evaluation_mode),
    },
    analysis: passAnalysis,
    limitations: thesis.deterministic_analysis.limitations,
    final_answer: pass === "ADJUDICATOR" ? `${gate.status}: ${gate.decisive_reasons.join(" ")}` : "Промежуточный проход; финальный статус назначает арбитр.",
  };
}

function compactModelSchema(schema) {
  const clone = structuredClone(schema);
  delete clone.$schema;
  delete clone.$id;
  delete clone.title;
  return clone;
}

function openAIOutputText(payload) {
  if (typeof payload.output_text === "string" && payload.output_text.trim()) return payload.output_text;
  const pieces = [];
  for (const item of payload.output ?? []) {
    for (const content of item.content ?? []) {
      if (content.type === "refusal") throw new Error(`MODEL_REFUSAL: ${content.refusal ?? "request refused"}`);
      if (content.type === "output_text" && typeof content.text === "string") pieces.push(content.text);
    }
  }
  return pieces.join("\n").trim();
}

function words(value) {
  return [...String(value).normalize("NFKC").toLocaleLowerCase("ru").matchAll(/[\p{L}\p{N}][\p{L}\p{N}\p{M}'’‐‑-]*/gu)].map((match) => match[0]);
}

function containsVerbatimSequence(modelValue, sourceTexts, size = 8) {
  const output = words(modelValue).join(" ");
  if (!output) return false;
  for (const source of sourceTexts) {
    const tokens = words(source);
    for (let index = 0; index <= tokens.length - size; index += 1) {
      if (output.includes(tokens.slice(index, index + size).join(" "))) return true;
    }
  }
  return false;
}

function assessmentText(assessment) {
  return [assessment.A, assessment.P, assessment.B, assessment.analysis, assessment.final_answer, assessment.strongest_rival.statement, assessment.strongest_rival.answer, ...assessment.limitations].join("\n");
}

async function callOpenAIAssessment(engine, thesis, pass, evidence, snippets, previous, options) {
  const system = [
    `Ты выполняешь проход ${pass} автономного философского экспертного цикла Destruktion.`,
    "Разделяй происхождение, A/P/B, тип отношения, свидетельство и сильнейшего соперника.",
    "Не цитируй исходные фрагменты: только кратко пересказывай их своими словами.",
    "Не придумывай селекторы, источники и локаторы. Не повышай тезис выше доступного доказательного бремени.",
    "Верни только объект, соответствующий заданной JSON Schema.",
  ].join(" ");
  const input = {
    task: pass,
    thesis,
    deterministic_evidence: evidence,
    deterministic_status_ceiling: options.gate.allowed_statuses,
    source_snippets: snippets,
    previous_passes: previous,
  };
  const endpoint = `${options.baseUrl.replace(/\/+$/u, "")}/responses`;
  const response = await options.fetchImpl(endpoint, {
    method: "POST",
    headers: {
      authorization: `Bearer ${options.apiKey}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: options.model,
      store: false,
      input: [
        { role: "system", content: [{ type: "input_text", text: system }] },
        { role: "user", content: [{ type: "input_text", text: JSON.stringify(input) }] },
      ],
      text: {
        format: {
          type: "json_schema",
          name: "dae_expert_assessment",
          strict: true,
          schema: compactModelSchema(options.modelSchema),
        },
      },
      max_output_tokens: 3500,
    }),
  });
  if (!response.ok) {
    const detail = (await response.text()).replace(/\s+/gu, " ").slice(0, 500);
    throw new Error(`OPENAI_RESPONSES_HTTP_${response.status}: ${detail}`);
  }
  const payload = await response.json();
  if (payload.status === "incomplete") throw new Error(`OPENAI_RESPONSE_INCOMPLETE: ${JSON.stringify(payload.incomplete_details ?? {})}`);
  const text = openAIOutputText(payload);
  if (!text) throw new Error("OPENAI_RESPONSE_EMPTY: no structured output text returned");
  let assessment;
  try {
    assessment = JSON.parse(text);
  } catch (error) {
    throw new Error(`OPENAI_RESPONSE_NOT_JSON: ${error.message}`);
  }
  const issues = engine.structural.validateModelExpertAssessment(assessment);
  if (issues.length) throw new Error(`OPENAI_ASSESSMENT_SCHEMA_FAILED: ${issueSummary(issues)}`);
  if (assessment.thesis_id !== thesis.thesis_id || assessment.pass !== pass) {
    throw new Error(`OPENAI_ASSESSMENT_IDENTITY_MISMATCH: expected ${thesis.thesis_id}/${pass}, received ${assessment.thesis_id}/${assessment.pass}`);
  }
  const admittedSelectors = new Set(evidence.selectors);
  if (assessment.evidence_selectors.some((selector) => !admittedSelectors.has(selector))) {
    throw new Error("OPENAI_ASSESSMENT_SELECTOR_FABRICATION: assessment contains a selector outside the deterministic evidence set");
  }
  if (containsVerbatimSequence(assessmentText(assessment), snippets.map((entry) => entry.text))) {
    throw new Error("OPENAI_ASSESSMENT_VERBATIM_SOURCE_LEAK: output shares an eight-token source sequence");
  }
  return { assessment, response_id: payload.id ?? null, model: payload.model ?? options.model };
}

async function readDocxParagraphMap(docxFile, expectedHash, language) {
  const resolved = path.resolve(docxFile);
  if (path.extname(resolved).toLowerCase() !== ".docx") throw new Error("expert-cycle --docx requires a .docx file");
  const bytes = await readFile(resolved);
  const actualHash = sha256(bytes);
  if (actualHash !== expectedHash) throw new Error(`EXPERT_DOCX_HASH_MISMATCH: expected ${expectedHash}, received ${actualHash}`);
  let xml;
  try {
    const result = await execFileAsync("unzip", ["-p", resolved, "word/document.xml"], { encoding: "utf8", maxBuffer: 96 * 1024 * 1024 });
    xml = result.stdout;
  } catch (error) {
    throw new Error(`EXPERT_DOCX_READ_FAILED: ${error.stderr ?? error.message}`);
  }
  const parsed = parseOoxmlParagraphs(xml, { documentLanguage: language });
  return new Map(parsed.segments.map((segment) => [segment.segment_id, segment]));
}

function snippetsForEvidence(evidence, paragraphMap) {
  const output = [];
  let characters = 0;
  for (const selector of evidence.selectors) {
    if (output.length >= MAX_MODEL_SOURCE_SEGMENTS) break;
    const segment = paragraphMap.get(selector);
    if (!segment?._text?.trim()) continue;
    const remaining = MAX_MODEL_SOURCE_CHARACTERS - characters;
    if (remaining <= 0) break;
    const text = segment._text.trim().slice(0, Math.min(1800, remaining));
    output.push({ selector, origin_route: segment.layer_routing.label, text });
    characters += text.length;
  }
  return output;
}

function finalResult(thesis, evidence, gate, adjudicator, policy, modelTraceAvailable) {
  const proposed = adjudicator.proposed_status;
  const status = gate.allowed_statuses.includes(proposed) ? proposed : gate.status;
  if (!TERMINAL_STATUSES.has(status)) throw new Error(`NON_TERMINAL_EXPERT_STATUS: ${status}`);
  const confidence = clamp(
    status === proposed ? adjudicator.confidence : gate.confidence,
    policy.confidence_floor,
    policy.confidence_cap,
  );
  const rival = thesis.rivals[0];
  return {
    thesis_id: thesis.thesis_id,
    title: thesis.title,
    statement: thesis.statement,
    status,
    confidence,
    finality: "FINAL_FOR_THIS_RUN",
    scale: thesis.scale,
    reconstruction: {
      A: adjudicator.A || thesis.reconstruction.A,
      P: adjudicator.P || thesis.reconstruction.P,
      B: adjudicator.B || thesis.reconstruction.B,
    },
    operative_relations: adjudicator.operative_relations.length ? adjudicator.operative_relations : thesis.reconstruction.operative_relations,
    evidence,
    strongest_rival: {
      rival_id: rival.rival_id,
      statement: adjudicator.strongest_rival.statement || rival.statement,
      impact: status === gate.status ? rivalImpact(status, thesis.evaluation_mode) : adjudicator.strongest_rival.impact,
      answer: adjudicator.strongest_rival.answer || rivalAnswer(status, thesis.evaluation_mode),
      discriminator: rival.discriminator,
    },
    decisive_reasons: gate.decisive_reasons,
    analysis: [...new Set([...thesis.deterministic_analysis.key_points, adjudicator.analysis].filter(Boolean))].join(" "),
    limitations: [...new Set([...thesis.deterministic_analysis.limitations, ...adjudicator.limitations])],
    recommendation: thesis.deterministic_analysis.recommendation,
    deterministic_gate: gate.gate,
    model_trace_available: modelTraceAvailable,
  };
}

function statusGroups(results) {
  return Object.fromEntries([...TERMINAL_STATUSES].map((status) => [status, results.filter((entry) => entry.status === status).map((entry) => entry.thesis_id)]));
}

function markdownList(items, empty = "Нет.") {
  return items.length ? items.map((item) => `- ${item}`).join("\n") : empty;
}

function statusLabel(status) {
  return {
    SUPPORTED: "поддержан",
    QUALIFIED: "поддержан с ограничениями",
    REJECTED: "отвергнут",
    INSUFFICIENT: "недостаточно оснований",
  }[status];
}

function escapeTable(value) {
  return String(value).replaceAll("|", "\\|").replace(/\s+/gu, " ").trim();
}

function formatFinalAnalytics(cycle, refinery, etymologyPass) {
  const table = cycle.thesis_results.map((entry) => `| ${escapeTable(entry.thesis_id)} | ${escapeTable(entry.title)} | ${entry.status} | ${entry.confidence.toFixed(3)} | ${entry.scale} |`).join("\n");
  const sections = cycle.thesis_results.map((entry, index) => `## ${index + 1}. ${entry.title}

**Вердикт:** ${entry.status} — ${statusLabel(entry.status)} для данного прогона. Уверенность в вердикте: ${entry.confidence.toFixed(3)}.

**Оцениваемый тезис.** ${entry.statement}

**Реконструкция A/P/B**

- A: ${entry.reconstruction.A}
- P: ${entry.reconstruction.P}
- B: ${entry.reconstruction.B}

**Доказательная база.** Кандидатов свидетельства: ${entry.evidence.evidence_count}; различимых групп/случаев: ${entry.evidence.distinct_group_count}; разрешённых claim-level источников: ${entry.evidence.resolved_source_count}. Репрезентативные селекторы: ${entry.evidence.selectors.length ? entry.evidence.selectors.join(", ") : "нет"}${entry.evidence.selectors_truncated ? " (список сокращён)" : ""}.

**Решающие основания**

${markdownList(entry.decisive_reasons)}

**Экспертный анализ.** ${entry.analysis}

**Сильнейший соперник.** ${entry.strongest_rival.statement}

**Воздействие соперника:** ${entry.strongest_rival.impact}. ${entry.strongest_rival.answer}

**Различающий тест.** ${entry.strongest_rival.discriminator}

**Ограничения**

${markdownList(entry.limitations)}

**Рекомендация.** ${entry.recommendation}

**Детерминированный шлюз:** \`${entry.deterministic_gate}\`. Оперативные отношения: ${entry.operative_relations.map((rt) => `\`${rt}\``).join(", ") || "не установлены"}.`).join("\n\n---\n\n");
  const counts = statusGroups(cycle.thesis_results);
  return `# ${cycle.global_analytics.title}

Статус аналитики: **FINAL_FOR_THIS_RUN**. Run ID: \`${cycle.run_id}\`.

## Итоговый вердикт

${cycle.global_analytics.final_verdict}

## Что именно установлено

${cycle.global_analytics.core_finding}

Термин «финальная» означает завершённое решение по всем тезисам данного прогона. Он не означает непогрешимость, окончательность философского спора или внешнюю валидацию.

## Решения в одном представлении

| ID | Тезис | Статус | Уверенность | Масштаб |
|---|---|---|---:|---|
${table}

- SUPPORTED: ${counts.SUPPORTED.length}.
- QUALIFIED: ${counts.QUALIFIED.length}.
- REJECTED: ${counts.REJECTED.length}.
- INSUFFICIENT: ${counts.INSUFFICIENT.length}.

## Доказательный контекст

- Источник/контейнер: \`${cycle.source.source_id}\`.
- Зафиксированный SHA-256: \`${cycle.source.artifact_sha256}\`.
- OOXML-сегменты: ${refinery.segmentationManifest.counts.ooxml_total.toLocaleString("ru-RU")}.
- Кандидаты claim ledger: ${cycle.source.claim_ledger_entries.toLocaleString("ru-RU")}.
- Разрешённые ссылки на уровне утверждений: ${cycle.source.resolved_claim_level_citations}.
- Backend: ${cycle.backend.kind}${cycle.backend.model ? ` (${cycle.backend.model})` : ""}; внешний перенос содержимого: ${cycle.backend.external_content_transferred ? "да" : "нет"}.
- Исходный текст в артефакты результата не включён.

## Этимолого-семантический результат

ETY-0.2 выполнен до сильной реконструкции: ${etymologyPass.coverage.cards_emitted} центральных понятий получили ETY-MIN, ${etymologyPass.coverage.ety_full_executed} — ETY-FULL. Неразрешённых полей: ${etymologyPass.coverage.unresolved_fields}; knowledge resolution: ${etymologyPass.coverage.knowledge_resolution}.

${etymologyPass.cards.map((card) => `- **${card.ety_min.source_form.value}** (${card.level}): ${card.generative_result.lost_distinction.value} Предел: ${card.ety_min.etymological_risk.value}`).join("\n")}

Проверка этимологии обязательна, её философская значимость — нет. Локальное употребление имеет приоритет перед происхождением; authorial wordplay отделяется от historical linguistics; ни одна карточка не разрешает etymology→ontology promotion без независимого bridge.

## Решающие основания общей оценки

${markdownList(cycle.global_analytics.decisive_reasons)}

## Тезисы и решения

${sections}

## Отвергнутые выводы

${markdownList(cycle.global_analytics.rejected_conclusions)}

## Следующие действия

${markdownList(cycle.global_analytics.next_actions)}

## Метод и предел вывода

Цикл выполнен последовательно: RECONSTRUCTOR → CRITIC → ADJUDICATOR → SYNTHESIS. Детерминированные пороги источников, масштаба и доказательного бремени имеют приоритет над предложением модели. Каждый тезис получил один терминальный статус; нехватка данных завершена статусом INSUFFICIENT, а не скрыта или превращена в положительное утверждение.

Claim ceiling: \`${cycle.claim_ceiling}\`.
`;
}

function formatRunSummary(cycle, trace) {
  const groups = statusGroups(cycle.thesis_results);
  return `# Expert cycle run summary

- Run: \`${cycle.run_id}\`
- Source: \`${cycle.source.source_id}\`
- Backend: ${cycle.backend.kind}${cycle.backend.model ? ` / ${cycle.backend.model}` : ""}
- Theses finalized: ${cycle.thesis_results.length}/${cycle.thesis_results.length}
- SUPPORTED: ${groups.SUPPORTED.length}
- QUALIFIED: ${groups.QUALIFIED.length}
- REJECTED: ${groups.REJECTED.length}
- INSUFFICIENT: ${groups.INSUFFICIENT.length}
- Model pass fallbacks: ${trace.model_fallback_count}
- Source text retained: no

Primary human-readable output: \`FINAL_ANALYTICS.md\`. Canonical machine output: \`expert_cycle.json\`.
`;
}

export async function runExpertCycle(engine, refineryDirectory, outputDirectory, options = {}) {
  const out = path.resolve(outputDirectory);
  await requireNewDirectory(out);
  const provider = String(options.provider ?? "deterministic").toLowerCase();
  if (!["deterministic", "openai"].includes(provider)) throw new Error(`Unknown expert provider '${provider}'. Use deterministic or openai.`);
  if (provider === "openai") {
    if (!options.allowExternalSourceTransfer) throw new Error("EXTERNAL_SOURCE_TRANSFER_BLOCKED: openai provider requires --allow-external-source-transfer");
    if (!options.docx) throw new Error("OPENAI_EXPERT_DOCX_REQUIRED: provide the fixity-matched source with --docx");
    if (!(options.apiKey ?? process.env.OPENAI_API_KEY)) throw new Error("OPENAI_API_KEY_REQUIRED: openai provider was requested but OPENAI_API_KEY is unavailable");
  }
  const refinery = await loadRefinery(engine, refineryDirectory);
  const generatedAt = options.generatedAt ?? new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
  let profile;
  let profileBytes;
  let profileOrigin;
  if (options.profile && options.profile !== "auto") {
    const profilePath = path.resolve(options.profile);
    profileBytes = await readFile(profilePath);
    profile = JSON.parse(profileBytes.toString("utf8"));
    profileOrigin = profilePath;
  } else {
    profile = buildAutomaticExpertProfile(refinery.hypothesisBank, refinery.segmentationManifest, refinery.sourceMap, options.autoProfile ?? {});
    profileBytes = Buffer.from(`${canonicalJson(profile)}\n`, "utf8");
    profileOrigin = "AUTO_GENERATED_FROM_REFINERY";
  }
  const profileIssues = engine.structural.validateExpertProfile(profile);
  if (profileIssues.length) throw new Error(`EXPERT_PROFILE_SCHEMA_FAILED: ${issueSummary(profileIssues)}`);
  const etymology = await buildEtymologyPass(engine, refineryDirectory, { generatedAt, conceptHints: profile.theses });
  const profileHash = sha256(profileBytes);
  const refineryManifestHash = sha256(refinery.segmentationText);
  const runDigest = sha256(`${refinery.segmentationManifest.source.source_id}\n${profileHash}\n${refineryManifestHash}`).slice(0, 12).toUpperCase();
  const runId = `EXPERT-${normalizeIdentifier(profile.profile_id)}-${runDigest}`;
  const modelSchema = await readJson(projectPath("schemas", "model_expert_assessment.schema.json"));
  let paragraphMap = null;
  if (provider === "openai") {
    paragraphMap = await readDocxParagraphMap(options.docx, refinery.segmentationManifest.source.artifact_sha256, profile.language);
  }
  const modelOptions = provider === "openai" ? {
    apiKey: options.apiKey ?? process.env.OPENAI_API_KEY,
    baseUrl: options.baseUrl ?? process.env.DAE_OPENAI_BASE_URL ?? "https://api.openai.com/v1",
    model: options.model ?? "gpt-5.6",
    fetchImpl: options.fetchImpl ?? globalThis.fetch,
    modelSchema,
  } : null;
  const results = [];
  const traces = [];
  let modelFallbackCount = 0;
  let successfulModelPasses = 0;
  for (const thesis of profile.theses) {
    const evidence = topicEvidence(thesis, refinery);
    const gate = adjudicateDeterministically(thesis, evidence, refinery);
    const passTrace = [];
    const assessments = [];
    const snippets = paragraphMap ? snippetsForEvidence(evidence, paragraphMap) : [];
    for (const pass of ["RECONSTRUCTOR", "CRITIC", "ADJUDICATOR"]) {
      let assessment = deterministicAssessment(thesis, pass, gate, evidence);
      let backend = "DETERMINISTIC_PROFILE";
      let responseId = null;
      let fallbackReason = null;
      if (provider === "openai") {
        try {
          const modelResult = await callOpenAIAssessment(engine, thesis, pass, evidence, snippets, assessments, { ...modelOptions, gate });
          assessment = modelResult.assessment;
          backend = "OPENAI_RESPONSES";
          responseId = modelResult.response_id;
          successfulModelPasses += 1;
        } catch (error) {
          modelFallbackCount += 1;
          fallbackReason = String(error.message).slice(0, 800);
        }
      }
      const assessmentIssues = engine.structural.validateModelExpertAssessment(assessment);
      if (assessmentIssues.length) throw new Error(`EXPERT_PASS_SCHEMA_FAILED ${thesis.thesis_id}/${pass}: ${issueSummary(assessmentIssues)}`);
      assessments.push(assessment);
      passTrace.push({
        pass,
        backend,
        response_id: responseId,
        fallback_reason: fallbackReason,
        proposed_status: assessment.proposed_status,
        deterministic_status_ceiling: gate.allowed_statuses,
        evidence_selector_count: evidence.selectors.length,
        source_snippet_count_transferred: backend === "OPENAI_RESPONSES" ? snippets.length : 0,
        assessment,
      });
    }
    const adjudicator = assessments.at(-1);
    results.push(finalResult(thesis, evidence, gate, adjudicator, profile.decision_policy, passTrace.some((entry) => entry.backend === "OPENAI_RESPONSES")));
    traces.push({ thesis_id: thesis.thesis_id, deterministic_gate: gate, passes: passTrace });
  }
  if (!results.every((entry) => TERMINAL_STATUSES.has(entry.status))) throw new Error("EXPERT_FINALIZATION_FAILED: at least one thesis is non-terminal");
  const groups = statusGroups(results);
  const globalAnalytics = {
    analytic_status: "FINAL_FOR_THIS_RUN",
    title: profile.global_synthesis.title,
    core_finding: profile.global_synthesis.core_finding,
    supported_theses: groups.SUPPORTED,
    qualified_theses: groups.QUALIFIED,
    rejected_theses: groups.REJECTED,
    insufficient_theses: groups.INSUFFICIENT,
    decisive_reasons: profile.global_synthesis.decisive_reasons,
    rejected_conclusions: profile.global_synthesis.rejected_conclusions,
    next_actions: profile.global_synthesis.next_actions,
    final_verdict: `${profile.global_synthesis.core_finding} В текущем прогоне: SUPPORTED — ${groups.SUPPORTED.length}, QUALIFIED — ${groups.QUALIFIED.length}, REJECTED — ${groups.REJECTED.length}, INSUFFICIENT — ${groups.INSUFFICIENT.length}.`,
  };
  const cycle = {
    cycle_version: "DAE-AUTONOMOUS-EXPERT-CYCLE-1.0",
    engine_version: engine.context.engineVersion,
    generated_at: generatedAt,
    run_id: runId,
    profile: {
      profile_id: profile.profile_id,
      profile_sha256: profileHash,
      title: profile.title,
      language: profile.language,
      domain: profile.domain,
    },
    source: {
      source_id: refinery.segmentationManifest.source.source_id,
      artifact_sha256: refinery.segmentationManifest.source.artifact_sha256,
      refinery_manifest_sha256: refineryManifestHash,
      claim_ledger_entries: refinery.ledger.length,
      resolved_claim_level_citations: refinery.sourceMap.coverage.resolved_claim_level_citations,
    },
    backend: {
      kind: provider === "openai" ? "OPENAI_RESPONSES" : "DETERMINISTIC_PROFILE",
      model: provider === "openai" ? modelOptions.model : null,
      external_content_transferred: provider === "openai",
      structured_output: provider === "openai",
      deterministic_gates_enforced: true,
    },
    prepasses: ["ETYMOLOGICAL_PASS"],
    etymology: {
      protocol_version: etymology.pass.protocol_version,
      run_id: etymology.pass.run_id,
      pass_sha256: etymology.sha256,
      cards: etymology.pass.coverage.cards_emitted,
      full_cards: etymology.pass.coverage.ety_full_executed,
      coverage_complete: etymology.pass.coverage.coverage_complete,
      unresolved_fields: etymology.pass.coverage.unresolved_fields,
      semantic_promotion_without_independent_bridge: false,
    },
    passes: PASSES,
    thesis_results: results,
    global_analytics: globalAnalytics,
    output_contract: {
      final_analytics_emitted: true,
      all_theses_terminal: true,
      source_text_included: false,
      model_generated_paraphrase_included: successfulModelPasses > 0,
      uncertainty_disclosed: true,
      mandatory_etymology_executed: true,
      mandatory_etymological_significance: false,
    },
    claim_ceiling: "AUTONOMOUS_RUN_BOUND_EXPERT_ADJUDICATION_NOT_INFALLIBILITY_OR_EXTERNAL_VALIDATION",
  };
  const cycleIssues = engine.structural.validateExpertCycle(cycle);
  if (cycleIssues.length) throw new Error(`EXPERT_CYCLE_SCHEMA_FAILED: ${issueSummary(cycleIssues, 12)}`);
  const trace = {
    trace_version: "DAE-AUTONOMOUS-EXPERT-TRACE-1.0",
    engine_version: engine.context.engineVersion,
    generated_at: generatedAt,
    run_id: runId,
    profile_origin: profileOrigin,
    profile_sha256: profileHash,
    refinery_manifest_sha256: refineryManifestHash,
    passes: PASSES,
    prepasses: [
      {
        pass: "ETYMOLOGICAL_PASS",
        protocol_version: etymology.pass.protocol_version,
        run_id: etymology.pass.run_id,
        pass_sha256: etymology.sha256,
        cards: etymology.pass.coverage.cards_emitted,
        full_cards: etymology.pass.coverage.ety_full_executed,
        unresolved_fields: etymology.pass.coverage.unresolved_fields,
        semantic_promotion_performed: false,
      },
    ],
    privacy: {
      source_text_retained: false,
      prompts_retained: false,
      model_response_ids_retained: provider === "openai",
      verbatim_output_guard: "EIGHT_TOKEN_SEQUENCE_BLOCK_WITH_DETERMINISTIC_PASS_FALLBACK",
    },
    model_fallback_count: modelFallbackCount,
    successful_model_passes: successfulModelPasses,
    theses: traces,
  };
  const markdown = formatFinalAnalytics(cycle, refinery, etymology.pass);
  await mkdir(out, { recursive: true });
  await Promise.all([
    writeFile(path.join(out, "expert_cycle.json"), `${JSON.stringify(cycle, null, 2)}\n`, "utf8"),
    writeFile(path.join(out, "FINAL_ANALYTICS.json"), `${JSON.stringify(cycle, null, 2)}\n`, "utf8"),
    writeFile(path.join(out, "expert_trace.json"), `${JSON.stringify(trace, null, 2)}\n`, "utf8"),
    writeFile(path.join(out, "FINAL_ANALYTICS.md"), markdown, "utf8"),
    writeFile(path.join(out, "RUN_SUMMARY.md"), formatRunSummary(cycle, trace), "utf8"),
    writeFile(path.join(out, "etymology_pass.json"), etymology.bytes),
    writeFile(path.join(out, "ETYMOLOGICAL_ANALYSIS.md"), etymology.markdown, "utf8"),
  ]);
  return { output_dir: out, cycle, trace, etymology, final_analytics: path.join(out, "FINAL_ANALYTICS.md") };
}

export async function runExpertDocx(engine, inputFile, jobFile, outputDirectory, options = {}) {
  const out = path.resolve(outputDirectory);
  await requireNewDirectory(out);
  const refineryDir = path.join(out, "refinery");
  const expertDir = path.join(out, "expert-cycle");
  const refineryResult = await refineDocx(engine, inputFile, jobFile, refineryDir, {
    ...(options.pageRun ? { pageRun: options.pageRun } : {}),
    ...(options.generatedAt ? { generatedAt: options.generatedAt } : {}),
  });
  const expertResult = await runExpertCycle(engine, refineryDir, expertDir, {
    ...options,
    docx: inputFile,
  });
  await Promise.all([
    copyFile(path.join(expertDir, "FINAL_ANALYTICS.md"), path.join(out, "FINAL_ANALYTICS.md")),
    copyFile(path.join(expertDir, "FINAL_ANALYTICS.json"), path.join(out, "FINAL_ANALYTICS.json")),
    copyFile(path.join(expertDir, "etymology_pass.json"), path.join(out, "etymology_pass.json")),
    copyFile(path.join(expertDir, "ETYMOLOGICAL_ANALYSIS.md"), path.join(out, "ETYMOLOGICAL_ANALYSIS.md")),
  ]);
  const pipeline = {
    pipeline_version: "DAE-EXPERT-DOCX-PIPELINE-1.0",
    engine_version: engine.context.engineVersion,
    generated_at: expertResult.cycle.generated_at,
    source_id: refineryResult.report.source_id,
    source_artifact_sha256: refineryResult.report.artifact_sha256,
    stages: [
      { stage: "CORPUS_REFINERY", status: "COMPLETE", output: "refinery" },
      { stage: "MANDATORY_ETYMOLOGY", status: "COMPLETE", output: "etymology_pass.json" },
      { stage: "AUTONOMOUS_EXPERT_CYCLE", status: "COMPLETE", output: "expert-cycle" },
      { stage: "FINAL_ANALYTICS", status: "COMPLETE", output: "FINAL_ANALYTICS.md" },
    ],
    finality: "FINAL_FOR_THIS_RUN",
    source_text_in_output: false,
    run_id: expertResult.cycle.run_id,
  };
  await writeFile(path.join(out, "PIPELINE_RUN.json"), `${JSON.stringify(pipeline, null, 2)}\n`, "utf8");
  return { output_dir: out, refinery: refineryResult, expert: expertResult, pipeline };
}
