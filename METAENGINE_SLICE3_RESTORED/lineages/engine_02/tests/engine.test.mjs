import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createEngine } from "../src/engine.mjs";
import { projectPath, readJson } from "../src/paths.mjs";
import { validateRun, validateRun4d } from "../src/run-validator.mjs";
import { validateProtocolRun } from "../src/protocol-runner.mjs";
import { freezeResearchPlan, verifyResearchPlan } from "../src/research-plan.mjs";
import { evaluateAgreement, krippendorffAlphaNominal } from "../src/agreement.mjs";
import { validateArgumentBundle } from "../src/argument-graph.mjs";
import { buildRoCrate, writeRoCrate } from "../src/ro-crate.mjs";
import { analyzeText, detectRelationCandidates, languageHints } from "../src/analyzer.mjs";
import { analyzePagedText } from "../src/page-analyzer.mjs";
import { buildDocxManifest, inspectDocxXml } from "../src/docx-intake.mjs";
import { buildArgumentSegments, buildHypothesisBankFromSegments, findDuplicateClusters, parseOoxmlParagraphs, refineDocx, routeCorpusLayer } from "../src/corpus-refinery.mjs";
import { buildAutomaticExpertProfile, runExpertCycle, runExpertDocx } from "../src/expert-cycle.mjs";

const engine = await createEngine();

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function codes(result) {
  return new Set(result.issues.map((item) => item.code));
}

async function repaired(name) {
  return readJson(projectPath("fixtures", "4a_repaired", name));
}

test("all repaired 4A fixtures are structurally and deterministically conformant", async () => {
  const dir = projectPath("fixtures", "4a_repaired");
  const files = (await readdir(dir)).filter((name) => name.endsWith(".json"));
  assert.equal(files.length, 8);
  for (const file of files) {
    const result = engine.validateRecord(await readJson(path.join(dir, file)), file);
    assert.equal(result.counts.ERROR, 0, `${file}: ${JSON.stringify(result.issues, null, 2)}`);
    assert.equal(result.review_required, true, "repaired fixtures must not be silently promoted to semantic gold");
  }
});

test("JSON Schema alone accepts RT99, semantic engine rejects it", async () => {
  const record = clone(await repaired("4A-EM4-HEIDEGGER-31.json"));
  record.transition.relation.rt_id = "RT99";
  assert.equal(engine.structural.validateRecord(record).length, 0);
  const result = engine.validateRecord(record);
  assert(codes(result).has("UNKNOWN_RELATION_ID"));
  assert.equal(result.conformant, false);
});

test("AAG invariants are executable rather than documentary", async () => {
  const record = clone(await repaired("4A-EM4-HEIDEGGER-31.json"));
  record.audit.activated_operators = ["O9"];
  const result = engine.validateRecord(record);
  assert(codes(result).has("AAG_INVARIANT_MISSING"));
  assert(result.counts.ERROR >= 3);
});

test("O6 requires encoded rivals", async () => {
  const record = clone(await repaired("4A-IND4-BIOLOGICAL-PLURALITY.json"));
  delete record.rivals;
  const result = engine.validateRecord(record);
  assert(codes(result).has("O6_RIVALS_REQUIRED"));
});

test("absent bridge cannot produce accepting promoted output", async () => {
  const record = clone(await repaired("4A-EM4-HEIDEGGER-31.json"));
  record.transition.bridge = { status: "ABSENT" };
  record.transition.promotion_flags = ["RELATION"];
  record.outcome = "ACCEPT";
  const result = engine.validateRecord(record);
  assert(codes(result).has("ABSENT_BRIDGE_ACCEPT"));
  assert(codes(result).has("ABSENT_BRIDGE_PROMOTION"));
});

test("extension escape is rejected", async () => {
  const record = clone(await repaired("4A-EM4-HEIDEGGER-31.json"));
  record.extensions.unregistered_profile = {};
  const result = engine.validateRecord(record);
  assert(codes(result).has("UNKNOWN_EXTENSION"));
});

test("provenance references must resolve through the source catalog", async () => {
  const record = clone(await repaired("4A-EM4-HEIDEGGER-31.json"));
  record.provenance.source_refs = ["NOT-A-SOURCE#p1"];
  const result = engine.validateRecord(record);
  assert(codes(result).has("UNKNOWN_SOURCE_ID"));
});

test("semantic heuristics expose the original RT21 category error", async () => {
  const original = await readJson(projectPath("vendor", "module4a", "fixtures_original", "4A-IND4-BIOLOGICAL-PLURALITY.json"));
  const result = engine.validateRecord(original);
  assert(codes(result).has("RT21_LEXICAL_MISMATCH"));
  assert(result.counts.ERROR > 0, "original fixture must fail strict release conformance");
});

test("valid unstable DAG requires IND4 before ID4", async () => {
  const result = await validateRun(engine, projectPath("fixtures", "runs", "unstable-valid.json"));
  assert.equal(result.conformant, true, JSON.stringify(result.issues, null, 2));
});

test("stable DAG may proceed from KC4 directly to ID4", async () => {
  const result = await validateRun(engine, projectPath("fixtures", "runs", "stable-valid.json"));
  assert.equal(result.conformant, true, JSON.stringify(result.issues, null, 2));
});

test("identity-before-relata DAG is rejected", async () => {
  const result = await validateRun(engine, projectPath("fixtures", "runs", "unstable-invalid.json"));
  assert.equal(result.conformant, false);
  assert(codes(result).has("DAG_IDENTITY_BEFORE_RELATA"));
});

test("4D epochal workflow requires reconstruction plus concrete discrimination", async () => {
  const result = await validateRun4d(engine, projectPath("fixtures", "runs4d", "epochal-valid.json"));
  assert.equal(result.conformant, true, JSON.stringify(result.issues, null, 2));
  assert.equal(result.review_required, true, "workflow conformance must not promote an epochal claim to semantic gold");
});

test("4D totalization before MA4/TO4/BS4 evidence is rejected", async () => {
  const result = await validateRun4d(engine, projectPath("fixtures", "runs4d", "epochal-invalid.json"));
  assert.equal(result.conformant, false);
  assert(codes(result).has("DAG4D_MA4_RECONSTRUCTION_REQUIRED"));
  assert(codes(result).has("DAG4D_TO4_DISCRIMINATION_REQUIRED"));
  assert(codes(result).has("DAG4D_BS4_DISCRIMINATION_REQUIRED"));
  assert(codes(result).has("DAG4D_DIACHRONIC_BRIDGE_REQUIRED"));
});

test("v3.8 protocol inventory is exhaustive at heading level and canonicalized into families", async () => {
  const occurrences = await readJson(projectPath("vendor", "v38", "protocol_occurrences.json"));
  assert.equal(occurrences.count, 123);
  assert.equal(engine.context.protocolRegistry.protocols.length, 40);
  assert.equal(occurrences.counts_by_status.CURRENT, 95);
  assert.equal(occurrences.counts_by_status.ARCHIVAL, 22);
});

test("deterministic v3.8 protocol run passes with complete evidence", async () => {
  const result = await validateProtocolRun(engine, projectPath("fixtures", "protocols", "claim-discipline-pass.json"));
  assert.equal(result.outcome, "PASS", JSON.stringify(result.issues, null, 2));
  assert.equal(result.conformant, true);
});

test("DATA/AUTH/LIC/CODER gate suspends rather than fabricating an empirical result", async () => {
  const result = await validateProtocolRun(engine, projectPath("fixtures", "protocols", "data-gate-suspend.json"));
  assert.equal(result.outcome, "SUSPEND", JSON.stringify(result.issues, null, 2));
  assert.equal(result.conformant, true);
  assert(codes(result).has("PROTOCOL_SUSPENDED"));
});

test("protocol evidence claims cannot pass without evidence references", async () => {
  const fixture = clone(await readJson(projectPath("fixtures", "protocols", "claim-discipline-pass.json")));
  fixture.answers.ORIGIN_MARKED.evidence_refs = [];
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-protocol-"));
  const temp = path.join(tempDir, "mutation.json");
  try {
    await writeFile(temp, JSON.stringify(fixture), "utf8");
    const result = await validateProtocolRun(engine, temp);
    assert.equal(result.outcome, "FAIL");
    assert(codes(result).has("PROTOCOL_EVIDENCE_REQUIRED"));
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("research plan freeze and verification preserve a canonical preregistration", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-plan-"));
  const lock = path.join(tempDir, "lock.json");
  try {
    const frozen = await freezeResearchPlan(engine, projectPath("fixtures", "research", "ro03-mini-plan.json"), lock);
    assert.equal(frozen.written, true, JSON.stringify(frozen.issues, null, 2));
    assert.equal(frozen.execution_status, "FROZEN_BUT_BLOCKED");
    const verified = await verifyResearchPlan(engine, projectPath("fixtures", "research", "ro03-mini-plan.json"), lock);
    assert.equal(verified.unchanged, true);
    assert.equal(verified.deviations.length, 0);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("research plan verification reports path-level deviations", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-plan-deviation-"));
  const lock = path.join(tempDir, "lock.json");
  const changed = path.join(tempDir, "changed.json");
  try {
    const original = projectPath("fixtures", "research", "ro03-mini-plan.json");
    await freezeResearchPlan(engine, original, lock);
    const plan = clone(await readJson(original));
    plan.sampling.seed = "POST-HOC-SEED";
    await writeFile(changed, JSON.stringify(plan), "utf8");
    const verified = await verifyResearchPlan(engine, changed, lock);
    assert.equal(verified.unchanged, false);
    assert(verified.deviations.some((item) => item.path === "/sampling/seed"));
    assert(codes(verified).has("PREREGISTRATION_DEVIATION"));
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("nominal Krippendorff alpha and multilabel metrics pass for perfect independent agreement", async () => {
  const result = await evaluateAgreement(engine, projectPath("fixtures", "research", "annotations-perfect.json"));
  assert.equal(result.threshold_passed, true, JSON.stringify(result.issues, null, 2));
  assert.equal(result.metrics.nominal.alpha, 1);
  assert.deepEqual(result.metrics.bootstrap.alpha_ci95, [1, 1]);
  assert.equal(result.metrics.multilabel.exact_match, 1);
  assert.equal(result.metrics.multilabel.pairwise_f1, 1);
});

test("agreement gate fails its frozen threshold under systematic coder disagreement", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-agreement-"));
  const changed = path.join(tempDir, "annotations.json");
  try {
    const payload = clone(await readJson(projectPath("fixtures", "research", "annotations-perfect.json")));
    const cycle = { OCC: "FUL", FUL: "VAL", VAL: "OCC" };
    for (const unit of payload.units) unit.annotations["coder-c"].dominant = cycle[unit.annotations["coder-c"].dominant];
    await writeFile(changed, JSON.stringify(payload), "utf8");
    const result = await evaluateAgreement(engine, changed);
    assert.equal(result.threshold_passed, false);
    assert(codes(result).has("AGREEMENT_THRESHOLD_FAILED"));
    assert(result.metrics.nominal.alpha < 0.8);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("alpha implementation tolerates missing ratings and uses only comparable units", () => {
  const result = krippendorffAlphaNominal([
    { annotations: { a: { dominant: "X", secondary: [] }, b: { dominant: "X", secondary: [] }, c: null } },
    { annotations: { a: { dominant: "Y", secondary: [] }, b: { dominant: "Y", secondary: [] }, c: { dominant: null, secondary: [] } } },
  ]);
  assert.equal(result.alpha, 1);
  assert.equal(result.usable_units, 2);
});

test("AIF/Carneades-inspired argument graph derives support only inside the represented graph", async () => {
  const result = await validateArgumentBundle(engine, projectPath("fixtures", "arguments", "bridge-supported.json"));
  assert.equal(result.conformant, true, JSON.stringify(result.issues, null, 2));
  assert.equal(result.issue_results[0].status, "SUPPORTED");
  assert.equal(result.claim_ceiling, "GRAPH_INTERNAL_ACCEPTABILITY_NOT_TRUTH");
});

test("open critical question suspends an argument and blocks a declared supported status", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-argument-"));
  const changed = path.join(tempDir, "argument.json");
  try {
    const bundle = clone(await readJson(projectPath("fixtures", "arguments", "bridge-supported.json")));
    bundle.arguments[0].critical_questions[1].status = "OPEN";
    delete bundle.arguments[0].critical_questions[1].evidence_refs;
    await writeFile(changed, JSON.stringify(bundle), "utf8");
    const result = await validateArgumentBundle(engine, changed);
    assert.equal(result.issue_results[0].status, "SUSPENDED");
    assert(codes(result).has("CRITICAL_QUESTION_OPEN"));
    assert(codes(result).has("ARGUMENT_STATUS_MISMATCH"));
    assert.equal(result.conformant, false);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("RO-Crate 1.3 export is attached, self-describing and records file fixity", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-crate-"));
  try {
    await writeFile(path.join(tempDir, "claim.json"), "{\"claim\":true}\n", "utf8");
    await writeFile(path.join(tempDir, "notes.md"), "# Notes\n", "utf8");
    const preview = await buildRoCrate(tempDir, { engineVersion: engine.context.engineVersion, generatedAt: "2026-08-11T12:00:00Z" });
    assert.equal(preview["@context"], "https://w3id.org/ro/crate/1.3/context");
    assert(preview["@graph"].some((entity) => entity["@id"] === "./" && entity["@type"] === "Dataset"));
    assert(preview["@graph"].some((entity) => entity["@id"] === "claim.json" && entity.identifier.startsWith("sha256:")));
    const output = path.join(tempDir, "ro-crate-metadata.json");
    const written = await writeRoCrate(tempDir, output, { engineVersion: engine.context.engineVersion });
    assert.equal(written.payload_files, 2);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("text analyzer emits provenance-bound review candidates without semantic promotion", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-analyze-"));
  const source = path.join(tempDir, "source.md");
  const output = path.join(tempDir, "analysis");
  try {
    await writeFile(source, "The intervention causes the observed change.\n", "utf8");
    const result = await analyzeText(engine, source, output);
    assert.equal(result.bundle.candidate_record_count, 1);
    assert.equal(result.validation.counts.ERROR, 0, JSON.stringify(result.validation.results, null, 2));
    assert.equal(result.validation.counts.review_required, 1);
    assert.equal(result.bundle.claim_ceiling, "CANDIDATE_GENERATION_ONLY");
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("text analyzer detects German relation signals required for Heidegger GA", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-analyze-de-"));
  const source = path.join(tempDir, "ga-smoke.md");
  const output = path.join(tempDir, "analysis");
  try {
    await writeFile(source, [
      "Die Auslegung ermöglicht den Zugang zum Phänomen.",
      "",
      "Methodische Distanz ist eine notwendige Vorbedingung der Untersuchung.",
      "",
      "Dieser Ausdruck bedeutet nicht einfach Mensch.",
    ].join("\n"), "utf8");
    const result = await analyzeText(engine, source, output);
    assert.equal(result.bundle.candidate_record_count, 3);
    assert.equal(result.validation.counts.ERROR, 0, JSON.stringify(result.validation.results, null, 2));
    assert.equal(result.bundle.language_hints[0].language, "DE");
    assert.deepEqual(result.bundle.units.map((unit) => unit.relation_candidates.map((candidate) => candidate.rt_id)), [["RT05"], ["RT04"], ["RT18"]]);
    assert(result.validation.results.every((record) => record.review_required), "German lexical candidates must remain review-only");
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("Unicode word boundaries detect Russian signals and language markers", () => {
  assert.deepEqual(detectRelationCandidates("Следовательно, вывод зависит от основания.").map((item) => item.rt_id), ["RT01", "RT08"]);
  assert.deepEqual(detectRelationCandidates("Метод должен проверять rival.").map((item) => item.rt_id), ["RT04", "RT21"]);
  assert.equal(detectRelationCandidates("Ложное слово сверхпозволяет не является сигналом.").some((item) => item.rt_id === "RT05"), false);
  const hints = languageHints("Это русский текст, и он не является немецким или английским текстом.");
  assert.equal(hints[0].language, "RU");
  assert(hints[0].marker_count >= 5);
});

test("page-aware analyzer preserves page selectors, blocks modal normativity promotion and omits source text", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-paged-"));
  const source = path.join(tempDir, "source.txt");
  const manifestFile = path.join(tempDir, "manifest.json");
  const output = path.join(tempDir, "analysis");
  const sourceText = "Methodische Distanz ist eine notwendige Vorbedingung der Untersuchung.\fDas Verfahren muss die Alternative prüfen.\f";
  const bytes = Buffer.from(sourceText, "utf8");
  const hash = createHash("sha256").update(bytes).digest("hex");
  const manifest = {
    manifest_version: "DAE-SOURCE-MANIFEST-1.0",
    source_id: "HGA-PJ25-1912-REALITAET",
    bibliographic: { author: "Test", title: "Paged test", publication: "Fixture", year: 1912, language: "de", source_url: "https://example.test/source" },
    artifact: { media_type: "text/plain", byte_length: bytes.length, sha256: hash },
    extracted_text: { media_type: "text/plain", byte_length: bytes.length, sha256: hash, method: "fixture", page_delimiter: "FORM_FEED" },
    pagination: { scheme: "PRINTED_PAGE", labels: ["1", "2"] },
    access_policy: { analysis_class: "DERIVATIVE_ONLY", raw_text_retention: "TRANSIENT", redistribution: "UNKNOWN", allow_derived_outputs: true, basis: "Synthetic fixture" },
    crosswalk: { target_edition: "Fixture", status: "NONE", target_locator: "none", evidence_refs: ["FIXTURE#crosswalk"] }
  };
  try {
    await writeFile(source, bytes);
    await writeFile(manifestFile, JSON.stringify(manifest), "utf8");
    const result = await analyzePagedText(engine, source, manifestFile, output, { generatedAt: "2026-08-11T12:00:00Z" });
    assert.equal(result.bundle.page_count, 2);
    assert.equal(result.bundle.raw_text_included, false);
    assert.equal(result.bundle.selected_record_relation_counts.RT04, 1);
    assert.equal(result.bundle.selected_record_relation_counts.RT00, 1, "bare muss must remain RT04/RT21 ambiguous");
    assert(result.bundle.units.every((unit) => !("text" in unit)), "derived bundle must not serialize source wording");
    assert(!JSON.stringify(result.bundle).includes("Alternative prüfen"), "expressive source context leaked into the bundle");
    assert.equal(result.validation.counts.ERROR, 0);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("reference-only source policy blocks page analysis before output creation", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-reference-only-"));
  const source = path.join(tempDir, "source.txt");
  const manifestFile = path.join(tempDir, "manifest.json");
  const output = path.join(tempDir, "analysis");
  const bytes = Buffer.from("Reference only.\f", "utf8");
  const hash = createHash("sha256").update(bytes).digest("hex");
  const manifest = {
    manifest_version: "DAE-SOURCE-MANIFEST-1.0",
    source_id: "HGA-PJ25-1912-REALITAET",
    bibliographic: { author: "Test", title: "Blocked", publication: "Fixture", year: 1912, language: "de", source_url: "https://example.test/source" },
    artifact: { media_type: "text/plain", byte_length: bytes.length, sha256: hash },
    extracted_text: { media_type: "text/plain", byte_length: bytes.length, sha256: hash, method: "fixture", page_delimiter: "FORM_FEED" },
    pagination: { scheme: "PRINTED_PAGE", labels: ["1"] },
    access_policy: { analysis_class: "REFERENCE_ONLY", raw_text_retention: "TRANSIENT", redistribution: "UNKNOWN", allow_derived_outputs: false, basis: "Reference-only fixture" },
    crosswalk: { target_edition: "Fixture", status: "NONE", target_locator: "none", evidence_refs: ["FIXTURE#crosswalk"] }
  };
  try {
    await writeFile(source, bytes);
    await writeFile(manifestFile, JSON.stringify(manifest), "utf8");
    await assert.rejects(() => analyzePagedText(engine, source, manifestFile, output), /SOURCE_POLICY_BLOCK/);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("page-aware intake accepts an uncatalogued source only when its LOCAL-SHA256 id is content-bound", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-paged-local-hash-"));
  const source = path.join(tempDir, "source.txt");
  const manifestFile = path.join(tempDir, "manifest.json");
  const output = path.join(tempDir, "analysis");
  const bytes = Buffer.from("Это позволяет проверить локальный источник.\f", "utf8");
  const hash = createHash("sha256").update(bytes).digest("hex");
  const manifest = {
    manifest_version: "DAE-SOURCE-MANIFEST-1.0",
    source_id: `LOCAL-SHA256-${hash.toUpperCase()}`,
    bibliographic: { author: "Test", title: "Local hash", publication: "Fixture", year: 2026, language: "ru", source_url: `urn:sha256:${hash}` },
    artifact: { media_type: "text/plain", byte_length: bytes.length, sha256: hash },
    extracted_text: { media_type: "text/plain", byte_length: bytes.length, sha256: hash, method: "fixture", page_delimiter: "FORM_FEED" },
    pagination: { scheme: "DIGITAL_PAGE", authority: "SOURCE_AUTHORED", labels: ["1"] },
    access_policy: { analysis_class: "DERIVATIVE_ONLY", raw_text_retention: "TRANSIENT", redistribution: "UNKNOWN", allow_derived_outputs: true, basis: "Synthetic fixture" },
    crosswalk: { target_edition: "Fixture", status: "NONE", target_locator: "none", evidence_refs: ["FIXTURE#none"] }
  };
  try {
    await writeFile(source, bytes);
    await writeFile(manifestFile, JSON.stringify(manifest), "utf8");
    const result = await analyzePagedText(engine, source, manifestFile, output, { generatedAt: "2026-08-11T12:00:00Z" });
    assert.equal(result.validation.counts.ERROR, 0);
    assert.equal(result.bundle.candidate_record_count, 1);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("page-aware intake blocks source-fixity and pagination mutations", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-paged-mutations-"));
  const source = path.join(tempDir, "source.txt");
  const manifestFile = path.join(tempDir, "manifest.json");
  const bytes = Buffer.from("Page one.\fPage two.\f", "utf8");
  const hash = createHash("sha256").update(bytes).digest("hex");
  const base = {
    manifest_version: "DAE-SOURCE-MANIFEST-1.0",
    source_id: "HGA-PJ25-1912-REALITAET",
    bibliographic: { author: "Test", title: "Mutation", publication: "Fixture", year: 1912, language: "de", source_url: "https://example.test/source" },
    artifact: { media_type: "text/plain", byte_length: bytes.length, sha256: hash },
    extracted_text: { media_type: "text/plain", byte_length: bytes.length, sha256: hash, method: "fixture", page_delimiter: "FORM_FEED" },
    pagination: { scheme: "PRINTED_PAGE", labels: ["1", "2"] },
    access_policy: { analysis_class: "DERIVATIVE_ONLY", raw_text_retention: "TRANSIENT", redistribution: "UNKNOWN", allow_derived_outputs: true, basis: "Synthetic fixture" },
    crosswalk: { target_edition: "Fixture", status: "NONE", target_locator: "none", evidence_refs: ["FIXTURE#crosswalk"] }
  };
  try {
    await writeFile(source, bytes);
    const badHash = clone(base);
    badHash.extracted_text.sha256 = "0".repeat(64);
    await writeFile(manifestFile, JSON.stringify(badHash), "utf8");
    await assert.rejects(() => analyzePagedText(engine, source, manifestFile, path.join(tempDir, "bad-hash")), /SOURCE_FIXITY_MISMATCH/);

    const badPages = clone(base);
    badPages.pagination.labels = ["1"];
    await writeFile(manifestFile, JSON.stringify(badPages), "utf8");
    await assert.rejects(() => analyzePagedText(engine, source, manifestFile, path.join(tempDir, "bad-pages")), /PAGE_COUNT_MISMATCH/);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("DOCX job and generated manifest distinguish renderer pages from source pagination", () => {
  const job = {
    job_version: "DAE-DOCX-JOB-1.0",
    source_admission: "LOCAL_HASH",
    bibliographic: {
      author: "Unknown",
      title: "Synthetic dossier",
      publication: "User supplied DOCX",
      year: 2026,
      language: "ru",
      genre: "research dossier"
    },
    access_policy: {
      analysis_class: "DERIVATIVE_ONLY",
      raw_text_retention: "TRANSIENT",
      redistribution: "UNKNOWN",
      allow_derived_outputs: true,
      basis: "Synthetic user-supplied fixture"
    },
    crosswalk: {
      target_edition: "No edition",
      status: "NONE",
      target_locator: "none",
      evidence_refs: ["FIXTURE#none"]
    }
  };
  assert.equal(engine.structural.validateDocxJob(job).length, 0);
  const manifest = buildDocxManifest(job, {
    artifact: { byte_length: 100, sha256: "a".repeat(64) },
    extracted_text: { byte_length: 80, sha256: "b".repeat(64), method: "fixture render" },
    page_count: 2
  });
  assert.equal(manifest.source_id, `LOCAL-SHA256-${"B".repeat(64)}`);
  assert.equal(manifest.pagination.authority, "RENDERER_DERIVED");
  assert.deepEqual(manifest.pagination.labels, ["R0001", "R0002"]);
  assert.equal(engine.structural.validateSourceManifest(manifest).length, 0);
});

test("DOCX structural audit detects missing source pagination, repetition and interaction residue", () => {
  const xml = [
    '<w:document xmlns:w="w" xmlns:m="m"><w:body>',
    '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Heading</w:t></w:r></w:p>',
    '<w:p><w:r><w:t>Перейдём к следующему этапу</w:t></w:r></w:p>',
    '<w:p><w:r><w:t>Перейдём к следующему этапу</w:t></w:r></w:p>',
    '<w:tbl><w:tr/></w:tbl><w:sectPr/>',
    '</w:body></w:document>'
  ].join("");
  const audit = inspectDocxXml(xml, '<cp:coreProperties xmlns:dc="dc"><dc:creator></dc:creator></cp:coreProperties>');
  assert.equal(audit.paragraphs_total, 3);
  assert.equal(audit.heading_style_counts.Heading1, 1);
  assert.equal(audit.explicit_page_breaks, 0);
  assert.equal(audit.page_boundary_authority, "NONE_IN_OOXML");
  assert.equal(audit.duplicate_audit.duplicate_groups, 1);
  assert.equal(audit.interaction_residue.next_stage_prompts, 2);
});

test("Corpus Refinery routes explicit layers but leaves weak or tied passages unresolved", () => {
  assert.equal(routeCorpusLayer("Перейдём к следующему этапу").label, "PROTOCOL_TOOL_LOG");
  assert.equal(routeCorpusLayer("Возражение: альтернативная модель опровергает этот вывод.").label, "RIVAL_OBJECTION");
  assert.equal(routeCorpusLayer("Хайдеггер пишет, что этот термин означает иной способ доступа.").label, "RECONSTRUCTION");
  assert.equal(routeCorpusLayer("Наш проект предлагает сохранить это различение.").label, "PROJECT_CLAIM");
  assert.equal(routeCorpusLayer("Короткий нейтральный фрагмент.").label, "UNRESOLVED");
  const quoted = routeCorpusLayer("«Das Sein ist nicht ein Seiendes.»", { style: "Quote", zone: "BODY", language_profile: { dominant: "DE" }, document_language: "ru" });
  assert.equal(quoted.label, "SOURCE");
  assert.equal(quoted.review_required, true, "source routing must never establish source identity automatically");
});

test("OOXML-native parsing separates headings and OMML while consolidation is non-destructive", () => {
  const xml = [
    '<w:document xmlns:w="w" xmlns:m="m"><w:body>',
    '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Раздел</w:t></w:r></w:p>',
    '<w:p><w:r><w:t>Наш проект предлагает различить акт, содержание и предмет.</w:t></w:r><m:oMath><m:r><m:t>x=1</m:t></m:r></m:oMath></w:p>',
    '<w:p><w:r><w:t>Наш проект предлагает различить акт, содержание и предмет.</w:t></w:r><m:oMath><m:r><m:t>x=1</m:t></m:r></m:oMath></w:p>',
    '</w:body></w:document>'
  ].join("");
  const parsed = parseOoxmlParagraphs(xml, { documentLanguage: "ru" });
  assert.equal(parsed.segments.length, 3);
  assert.equal(parsed.segments[0].zone, "HEADING");
  assert.equal(parsed.formulas.length, 2);
  assert(parsed.segments[1].heading_path.includes(parsed.segments[0].segment_id));
  const duplicates = findDuplicateClusters(parsed.segments);
  assert.equal(duplicates.exact.length, 1);
  assert.equal(duplicates.exact[0].member_count, 2);
  assert.equal(parsed.segments.length, 3, "duplicate detection must not delete a paragraph");
  assert.equal(parsed.segments[2].archive_state, "ARCHIVED_EXACT_DUPLICATE");
  const arguments_ = buildArgumentSegments(parsed.segments);
  assert(arguments_.some((segment) => segment.claim_type === "PROJECT_ASSERTION"));
});

test("Corpus Refinery completes an end-to-end derivative-only run against a fixity-checked existing page run", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-refinery-e2e-"));
  const packageDir = path.join(tempDir, "package");
  const wordDir = path.join(packageDir, "word");
  const docx = path.join(tempDir, "fixture.docx");
  const jobFile = path.join(tempDir, "job.json");
  const pageRun = path.join(tempDir, "page-run");
  const output = path.join(tempDir, "refined");
  const secretPhrase = "Уникальная исходная формулировка не должна попасть в производные JSON";
  try {
    await mkdir(wordDir, { recursive: true });
    const xml = [
      '<w:document xmlns:w="w" xmlns:m="m"><w:body>',
      '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Возражение</w:t></w:r></w:p>',
      `<w:p><w:r><w:t>${secretPhrase}.</w:t></w:r></w:p>`,
      '<w:p><w:r><w:t>Перейдём к следующему этапу</w:t></w:r></w:p>',
      '<w:p><w:r><w:t>Наш проект предлагает различить акт, содержание и предмет.</w:t></w:r><m:oMath><m:r><m:t>x=1</m:t></m:r></m:oMath></w:p>',
      '<w:p><w:r><w:t>Наш проект предлагает различить акт, содержание и предмет.</w:t></w:r><m:oMath><m:r><m:t>x=1</m:t></m:r></m:oMath></w:p>',
      '</w:body></w:document>'
    ].join("");
    await writeFile(path.join(wordDir, "document.xml"), xml, "utf8");
    execFileSync("zip", ["-q", "-r", docx, "word"], { cwd: packageDir });
    const docxBytes = await readFile(docx);
    const docxHash = createHash("sha256").update(docxBytes).digest("hex");
    const extractedBytes = Buffer.from("Synthetic renderer unit.\f", "utf8");
    const extractedHash = createHash("sha256").update(extractedBytes).digest("hex");
    const sourceId = `LOCAL-SHA256-${extractedHash.toUpperCase()}`;
    const accessPolicy = { analysis_class: "DERIVATIVE_ONLY", raw_text_retention: "TRANSIENT", redistribution: "UNKNOWN", allow_derived_outputs: true, basis: "Synthetic fixture" };
    const crosswalk = { target_edition: "Synthetic", status: "NONE", target_locator: "none", evidence_refs: ["FIXTURE#none"] };
    const job = {
      job_version: "DAE-DOCX-JOB-1.0",
      source_admission: "LOCAL_HASH",
      bibliographic: { author: "Test", title: "Refinery fixture", publication: "Fixture", year: 2026, language: "ru", genre: "composite dossier" },
      access_policy: accessPolicy,
      crosswalk
    };
    await writeFile(jobFile, JSON.stringify(job), "utf8");
    await mkdir(path.join(pageRun, "generated"), { recursive: true });
    const intakeFile = path.join(pageRun, "docx_intake.json");
    await writeFile(intakeFile, JSON.stringify({ source_id: sourceId, input: { sha256: docxHash } }), "utf8");
    await writeFile(path.join(pageRun, "source_manifest.json"), JSON.stringify({
      manifest_version: "DAE-SOURCE-MANIFEST-1.0",
      source_id: sourceId,
      bibliographic: { author: "Test", title: "Refinery fixture", publication: "Fixture", year: 2026, language: "ru", source_url: `urn:sha256:${docxHash}`, genre: "composite dossier" },
      artifact: { media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", byte_length: docxBytes.length, sha256: docxHash },
      extracted_text: { media_type: "text/plain", byte_length: extractedBytes.length, sha256: extractedHash, method: "fixture", page_delimiter: "FORM_FEED" },
      pagination: { scheme: "DIGITAL_PAGE", authority: "RENDERER_DERIVED", labels: ["R0001"] },
      access_policy: accessPolicy,
      crosswalk
    }), "utf8");
    await writeFile(path.join(pageRun, "generated", "analysis_bundle.json"), JSON.stringify({
      bundle_version: "DAE-PAGED-INTAKE-0.2",
      method_version: "DAE-PAGED-LEXICAL-CANDIDATE-0.4",
      raw_text_included: false,
      expressive_context_included: false,
      source: { source_id: sourceId },
      unit_count: 1,
      units: [{ unit_id: `${sourceId}-PR0001-U001`, page_label: "R0001", zone: "BODY", normalized_sha256: "a".repeat(64), char_length: 23, selector: { type: "TextPositionSelector", start: 0, end: 23 }, discourse_features: [], relation_candidates: [] }]
    }), "utf8");
    await writeFile(intakeFile, JSON.stringify({ source_id: sourceId, input: { sha256: "0".repeat(64) } }), "utf8");
    await assert.rejects(() => refineDocx(engine, docx, jobFile, path.join(tempDir, "mismatch"), { pageRun, generatedAt: "2026-08-11T12:00:00Z" }), /REFINERY_ARTIFACT_MISMATCH/);
    await writeFile(intakeFile, JSON.stringify({ source_id: sourceId, input: { sha256: docxHash } }), "utf8");
    const result = await refineDocx(engine, docx, jobFile, output, { pageRun, generatedAt: "2026-08-11T12:00:00Z" });
    assert.equal(result.report.validation.total_errors, 0);
    assert.equal(result.report.output_contract.deleted_segments, 0);
    assert.equal(result.formula_registry.formula_count, 2);
    assert.equal(result.archive_map.counts.exact_duplicate_groups, 1);
    assert(result.archive_map.counts.tool_log_segments_archived >= 1);
    const serializedOutputs = (await Promise.all(["segmentation_manifest.json", "source_map.json", "claim_ledger.jsonl", "hypothesis_bank.json", "archive_map.json", "formula_registry.json"].map((name) => readFile(path.join(output, name), "utf8")))).join("\n");
    assert.equal(serializedOutputs.includes(secretPhrase), false, "expressive source text leaked into derivative outputs");
    const ledgerLines = (await readFile(path.join(output, "claim_ledger.jsonl"), "utf8")).trim().split("\n").map(JSON.parse);
    assert(ledgerLines.every((entry) => entry.apb.A === null && entry.apb.P === null && entry.apb.B === null));
    const fullCycle = await runExpertDocx(engine, docx, jobFile, path.join(tempDir, "expert-docx"), { pageRun, generatedAt: "2026-08-11T12:00:00Z" });
    assert.equal(fullCycle.pipeline.finality, "FINAL_FOR_THIS_RUN");
    assert.equal(fullCycle.expert.cycle.output_contract.all_theses_terminal, true);
    assert.equal((await readFile(path.join(fullCycle.output_dir, "FINAL_ANALYTICS.md"), "utf8")).includes(secretPhrase), false);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("automatic expert profile converts every discovered topic into a terminally adjudicable thesis", async () => {
  const root = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "refinery");
  const bank = await readJson(path.join(root, "hypothesis_bank.json"));
  const segmentation = await readJson(path.join(root, "segmentation_manifest.json"));
  const sourceMap = await readJson(path.join(root, "source_map.json"));
  const profile = buildAutomaticExpertProfile(bank, segmentation, sourceMap);
  assert.equal(engine.structural.validateExpertProfile(profile).length, 0);
  assert.equal(profile.theses.length, 1 + bank.hypotheses.length + bank.case_matrices.length);
  assert(profile.theses.some((entry) => entry.evaluation_mode === "SOURCE_DEPENDENT"));
  assert(profile.theses.some((entry) => entry.evaluation_mode === "TEST_DESIGN"));
});

test("autonomous expert cycle emits final analytics and terminally adjudicates the Heidegger dossier", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-expert-cycle-"));
  const root = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026");
  const output = path.join(tempDir, "expert");
  try {
    const result = await runExpertCycle(engine, path.join(root, "refinery"), output, {
      profile: projectPath("config", "expert_profiles", "heidegger_ga_dossier_1.0.json"),
      generatedAt: "2026-08-11T12:00:00Z",
    });
    assert.equal(engine.structural.validateExpertCycle(result.cycle).length, 0);
    assert.equal(result.cycle.thesis_results.every((entry) => ["SUPPORTED", "QUALIFIED", "REJECTED", "INSUFFICIENT"].includes(entry.status)), true);
    assert.equal(result.cycle.thesis_results.find((entry) => entry.thesis_id === "DOSSIER_GENRE").status, "SUPPORTED");
    assert.equal(result.cycle.thesis_results.find((entry) => entry.thesis_id === "UNIVERSAL_ONTOLOGY_PROMOTION").status, "REJECTED");
    assert.equal(result.cycle.thesis_results.find((entry) => entry.thesis_id === "DIACHRONIC_HEIDEGGER").status, "INSUFFICIENT");
    assert.equal(result.cycle.output_contract.source_text_included, false);
    assert.deepEqual(result.cycle.prepasses, ["ETYMOLOGICAL_PASS"]);
    assert.equal(result.cycle.output_contract.mandatory_etymology_executed, true);
    assert.equal(result.cycle.etymology.coverage_complete, true);
    assert.equal(result.etymology.validation.conformant, true);
    const analytics = await readFile(path.join(output, "FINAL_ANALYTICS.md"), "utf8");
    assert.match(analytics, /Итоговый вердикт/u);
    assert.match(analytics, /Сильнейший соперник/u);
    assert.match(analytics, /Этимолого-семантический результат/u);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("external model backend requires explicit source-transfer authorization", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-expert-transfer-"));
  const refinery = projectPath("experiments", "heidegger-ga", "user-dossier-ga1-1-2026", "refinery");
  try {
    await assert.rejects(() => runExpertCycle(engine, refinery, path.join(tempDir, "blocked"), {
      provider: "openai",
      docx: projectPath("vendor", "module4d", "source_document", "Destruktion_4.0_MODULE-MIGRATION-4D_0.1_Machenschaft-Technik-Gestell-Bestand-Ordering.docx"),
      apiKey: "test-key",
    }), /EXTERNAL_SOURCE_TRANSFER_BLOCKED/);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("external model cannot override a deterministic claim ceiling", async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "dae-expert-ceiling-"));
  const fakeFetch = async (_url, request) => {
    const body = JSON.parse(request.body);
    const input = JSON.parse(body.input[1].content[0].text);
    const thesis = input.thesis;
    const assessment = {
      thesis_id: thesis.thesis_id,
      pass: input.task,
      A: "Модель предлагает реконструкцию A.",
      P: "Модель предлагает переход P.",
      B: "Модель предлагает вывод B.",
      proposed_status: "SUPPORTED",
      confidence: 0.99,
      operative_relations: thesis.reconstruction.operative_relations,
      source_origin: "MIXED",
      evidence_selectors: input.deterministic_evidence.selectors,
      strongest_rival: { statement: "Альтернативная модель.", impact: "DEFEATED", answer: "Предложен модельный ответ." },
      analysis: "Краткий модельный анализ без исходной цитаты.",
      limitations: ["Требуется внешняя проверка."],
      final_answer: "Модель предлагает поддержку.",
    };
    return new Response(JSON.stringify({ id: `resp_${input.task}`, model: "test-model", status: "completed", output_text: JSON.stringify(assessment) }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    const packageDir = path.join(tempDir, "package");
    await mkdir(path.join(packageDir, "word"), { recursive: true });
    await writeFile(path.join(packageDir, "word", "document.xml"), '<w:document xmlns:w="w"><w:body><w:p><w:r><w:t>Наш проект предлагает ограниченную аналитическую модель.</w:t></w:r></w:p></w:body></w:document>', "utf8");
    const sourceDocx = path.join(tempDir, "source.docx");
    execFileSync("zip", ["-q", "-r", sourceDocx, "word"], { cwd: packageDir });
    const docxBytes = await readFile(sourceDocx);
    const docxHash = createHash("sha256").update(docxBytes).digest("hex");
    const extractedBytes = Buffer.from("Synthetic renderer unit.\f", "utf8");
    const extractedHash = createHash("sha256").update(extractedBytes).digest("hex");
    const sourceId = `LOCAL-SHA256-${extractedHash.toUpperCase()}`;
    const accessPolicy = { analysis_class: "DERIVATIVE_ONLY", raw_text_retention: "TRANSIENT", redistribution: "UNKNOWN", allow_derived_outputs: true, basis: "Synthetic ceiling fixture" };
    const crosswalk = { target_edition: "Synthetic", status: "NONE", target_locator: "none", evidence_refs: ["FIXTURE#none"] };
    const jobFile = path.join(tempDir, "job.json");
    await writeFile(jobFile, JSON.stringify({
      job_version: "DAE-DOCX-JOB-1.0",
      source_admission: "LOCAL_HASH",
      bibliographic: { author: "Test", title: "Expert ceiling fixture", publication: "Fixture", year: 2026, language: "ru", genre: "composite dossier" },
      access_policy: accessPolicy,
      crosswalk,
    }), "utf8");
    const pageRun = path.join(tempDir, "page-run");
    await mkdir(path.join(pageRun, "generated"), { recursive: true });
    await writeFile(path.join(pageRun, "docx_intake.json"), JSON.stringify({ source_id: sourceId, input: { sha256: docxHash } }), "utf8");
    await writeFile(path.join(pageRun, "source_manifest.json"), JSON.stringify({
      manifest_version: "DAE-SOURCE-MANIFEST-1.0",
      source_id: sourceId,
      bibliographic: { author: "Test", title: "Expert ceiling fixture", publication: "Fixture", year: 2026, language: "ru", source_url: `urn:sha256:${docxHash}`, genre: "composite dossier" },
      artifact: { media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", byte_length: docxBytes.length, sha256: docxHash },
      extracted_text: { media_type: "text/plain", byte_length: extractedBytes.length, sha256: extractedHash, method: "fixture", page_delimiter: "FORM_FEED" },
      pagination: { scheme: "DIGITAL_PAGE", authority: "RENDERER_DERIVED", labels: ["R0001"] },
      access_policy: accessPolicy,
      crosswalk,
    }), "utf8");
    await writeFile(path.join(pageRun, "generated", "analysis_bundle.json"), JSON.stringify({
      bundle_version: "DAE-PAGED-INTAKE-0.2",
      method_version: "DAE-PAGED-LEXICAL-CANDIDATE-0.4",
      raw_text_included: false,
      expressive_context_included: false,
      source: { source_id: sourceId },
      unit_count: 1,
      units: [{ unit_id: `${sourceId}-PR0001-U001`, page_label: "R0001", zone: "BODY", normalized_sha256: "a".repeat(64), char_length: 23, selector: { type: "TextPositionSelector", start: 0, end: 23 }, discourse_features: [], relation_candidates: [] }],
    }), "utf8");
    const refinery = path.join(tempDir, "refinery");
    await refineDocx(engine, sourceDocx, jobFile, refinery, { pageRun, generatedAt: "2026-08-11T12:00:00Z" });
    const fullProfile = await readJson(projectPath("config", "expert_profiles", "heidegger_ga_dossier_1.0.json"));
    const profile = clone(fullProfile);
    profile.profile_id = "TEST-MODEL-CEILING";
    profile.theses = [profile.theses.find((entry) => entry.thesis_id === "REGIONAL_REALIZATION_PROFILE")];
    profile.theses[0].topic_id = null;
    profile.theses[0].case_matrix_id = null;
    profile.theses[0].minimum_evidence_count = 0;
    profile.theses[0].minimum_distinct_groups = 0;
    const profileFile = path.join(tempDir, "profile.json");
    await writeFile(profileFile, JSON.stringify(profile), "utf8");
    const result = await runExpertCycle(engine, refinery, path.join(tempDir, "result"), {
      profile: profileFile,
      provider: "openai",
      docx: sourceDocx,
      apiKey: "test-key",
      model: "test-model",
      allowExternalSourceTransfer: true,
      fetchImpl: fakeFetch,
      generatedAt: "2026-08-11T12:00:00Z",
    });
    assert.equal(result.cycle.thesis_results[0].status, "QUALIFIED", "SUPPORTED must be blocked for an internally evidenced model");
    assert.equal(result.cycle.thesis_results[0].confidence <= fullProfile.decision_policy.confidence_cap, true);
    assert.equal(result.trace.successful_model_passes, 3);
    assert.equal(result.cycle.backend.external_content_transferred, true);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("Heidegger GA pilot separates local evidence from catalog, translation and diachronic overreach", async () => {
  const root = projectPath("experiments", "heidegger-ga");
  const snapshot = await readJson(path.join(root, "catalog_snapshot.json"));
  assert.equal(snapshot.entry_count, 105);
  assert.equal(snapshot.divisions.length, 4);
  assert.equal(snapshot.volumes[0].volume_id, "1");
  assert.equal(snapshot.volumes.at(-1).volume_id, "105");
  assert.equal(snapshot.claim_ceiling, "BIBLIOGRAPHIC_CATALOG_ONLY_NOT_PRIMARY_TEXT_OR_PHILOSOPHICAL_EVIDENCE");

  const local = await validateProtocolRun(engine, path.join(root, "protocols", "ga01-local-claim-pass.json"));
  const catalog = await validateProtocolRun(engine, path.join(root, "protocols", "catalog-source-audit-review.json"));
  const development = await validateProtocolRun(engine, path.join(root, "protocols", "development-claim-suspend.json"));
  const translation = await validateProtocolRun(engine, path.join(root, "protocols", "reale-translation-suspend.json"));
  assert.equal(local.outcome, "PASS");
  assert.equal(catalog.outcome, "REVIEW");
  assert.equal(development.outcome, "SUSPEND");
  assert.equal(translation.outcome, "SUSPEND");
  assert.equal([local, catalog, development, translation].every((result) => result.conformant), true);

  const fullWork = path.join(root, "full-work-1912");
  const sourceManifest = await readJson(path.join(fullWork, "source_manifest.json"));
  assert.equal(engine.structural.validateSourceManifest(sourceManifest).length, 0);
  const paged = await readJson(path.join(fullWork, "generated", "analysis_bundle.json"));
  assert.equal(paged.page_count, 11);
  assert.equal(paged.unit_count, 280);
  assert.equal(paged.candidate_record_count, 24);
  assert.equal(paged.raw_text_included, false);
  assert.equal(paged.selected_record_relation_counts.RT00, 17);

  const plan = await readJson(path.join(root, "research_plan.json"));
  assert.equal(engine.structural.validateResearchPlan(plan).length, 0);
  const lock = await verifyResearchPlan(engine, path.join(root, "research_plan.json"), path.join(root, "research_plan.lock.json"));
  assert.equal(lock.unchanged, true);
});


test("DOCX job schema admits BCE publication years for ancient-source regression corpora", () => {
  const job = {
    job_version: "DAE-DOCX-JOB-1.0",
    source_admission: "LOCAL_HASH",
    bibliographic: {
      author: "Aristotle",
      title: "Categories",
      publication: "Ancient source witness",
      year: -350,
      language: "en",
      genre: "philosophical treatise",
    },
    access_policy: {
      analysis_class: "DERIVATIVE_ONLY",
      raw_text_retention: "TRANSIENT",
      redistribution: "UNKNOWN",
      allow_derived_outputs: true,
      basis: "Controlled public-domain regression excerpt.",
      restrictions_checked_at: "2026-08-11T15:45:00Z",
    },
    crosswalk: {
      target_edition: "Aristotle primary text",
      status: "PAGE_LEVEL_PARTIAL",
      target_locator: "Categories",
      evidence_refs: ["Categories"],
      note: "Regression dossier.",
    },
    structure: { drop_line_patterns: [], analyze_notes: true },
    rendering: { page_label_prefix: "R" },
  };
  assert.equal(engine.structural.validateDocxJob(job).length, 0);
  assert(engine.structural.validateDocxJob({ ...job, bibliographic: { ...job.bibliographic, year: 0 } }).length > 0);
});
