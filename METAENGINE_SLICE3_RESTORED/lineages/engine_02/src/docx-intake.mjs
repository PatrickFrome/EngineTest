import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";
import { analyzePagedText } from "./page-analyzer.mjs";
import { readJson } from "./paths.mjs";

const execFileAsync = promisify(execFile);
const DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function issueSummary(issues) {
  return issues.map((item) => `${item.code} ${item.at}: ${item.message}`).join("; ");
}

async function requireNewDirectory(directory) {
  try {
    await stat(directory);
    throw new Error(`Output directory already exists: ${directory}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

async function command(command, args, options = {}) {
  try {
    const result = await execFileAsync(command, args, {
      cwd: options.cwd,
      encoding: options.encoding ?? "utf8",
      maxBuffer: options.maxBuffer ?? 64 * 1024 * 1024,
    });
    return { ok: true, code: 0, stdout: result.stdout ?? "", stderr: result.stderr ?? "" };
  } catch (error) {
    return {
      ok: false,
      code: Number.isInteger(error.code) ? error.code : null,
      stdout: error.stdout ?? "",
      stderr: error.stderr ?? error.message ?? "",
    };
  }
}

function countMatches(text, regex) {
  return [...text.matchAll(regex)].length;
}

function decodeXml(value) {
  return value
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", "\"")
    .replaceAll("&apos;", "'")
    .replaceAll("&amp;", "&");
}

function elementText(xml, qualifiedName) {
  const match = xml.match(new RegExp(`<${qualifiedName}(?:\\s[^>]*)?>([\\s\\S]*?)</${qualifiedName}>`, "u"));
  return match ? decodeXml(match[1]).trim() : null;
}

function paragraphTexts(documentXml) {
  const paragraphs = [];
  for (const match of documentXml.matchAll(/<w:p(?:\s[^>]*)?>([\s\S]*?)<\/w:p>/gu)) {
    const body = match[1];
    const pieces = [...body.matchAll(/<(?:w|m):t(?:\s[^>]*)?>([\s\S]*?)<\/(?:w|m):t>/gu)].map((item) => decodeXml(item[1]));
    paragraphs.push(pieces.join("").normalize("NFC"));
  }
  return paragraphs;
}

function normalizedParagraph(value) {
  return value.normalize("NFKC").toLocaleLowerCase("ru").replace(/\s+/gu, " ").trim();
}

function duplicateAudit(paragraphs) {
  const eligible = paragraphs.map(normalizedParagraph).filter((item) => item.length >= 20);
  const counts = new Map();
  for (const paragraph of eligible) counts.set(paragraph, (counts.get(paragraph) ?? 0) + 1);
  const duplicateGroups = [...counts.entries()].filter(([, occurrences]) => occurrences > 1);
  const duplicateOccurrences = duplicateGroups.reduce((sum, [, occurrences]) => sum + occurrences - 1, 0);
  const fingerprints = duplicateGroups
    .map(([text, occurrences]) => ({ sha256: sha256(text), occurrences, char_length: text.length }))
    .sort((left, right) => right.occurrences - left.occurrences || right.char_length - left.char_length || left.sha256.localeCompare(right.sha256))
    .slice(0, 20);
  return {
    eligible_paragraphs: eligible.length,
    unique_normalized_paragraphs: counts.size,
    duplicate_groups: duplicateGroups.length,
    duplicate_occurrences: duplicateOccurrences,
    duplicate_occurrence_share: eligible.length ? Number((duplicateOccurrences / eligible.length).toFixed(6)) : 0,
    max_group_occurrences: duplicateGroups.reduce((max, [, occurrences]) => Math.max(max, occurrences), 1),
    top_group_fingerprints: fingerprints,
  };
}

function residueCounts(paragraphs) {
  const joined = paragraphs.join("\n");
  return {
    next_stage_prompts: countMatches(joined, /перейд[её]м к следующему этапу/giu),
    search_completed_notices: countMatches(joined, /поиск выполнен/giu),
    guide_read_notices: countMatches(joined, /изучено руководство/giu),
    checked_notices: paragraphs.filter((item) => /^проверил(?:а|и)?\b/iu.test(item.trim())).length,
    empty_array_lines: paragraphs.filter((item) => item.trim() === "[]").length,
    pseudo_citation_markers: countMatches(joined, /\[[^\]\n]{0,120}(?:\+\d+|Beyng|PhilPapers|philosophisches-jahrbuch)[^\]\n]{0,120}\]/giu),
    visible_urls: countMatches(joined, /https?:\/\/[^\s<>]+/giu),
    version_markers: countMatches(joined, /\b(?:v|версия\s*)\d+(?:\.\d+)+\b/giu),
  };
}

export function inspectDocxXml(documentXml, coreXml = "") {
  const paragraphs = paragraphTexts(documentXml);
  const styleCounts = {};
  for (const match of documentXml.matchAll(/<w:pStyle[^>]*w:val="([^"]+)"[^>]*\/>/gu)) {
    styleCounts[match[1]] = (styleCounts[match[1]] ?? 0) + 1;
  }
  const headingStyleCounts = Object.fromEntries(Object.entries(styleCounts).filter(([style]) => /^Heading[1-6]$/iu.test(style)));
  const nonempty = paragraphs.filter((item) => item.trim());
  const shortFragments = nonempty.filter((item) => normalizedParagraph(item).length <= 3).length;
  const lastRenderedPageBreaks = countMatches(documentXml, /<w:lastRenderedPageBreak\s*\/>/gu);
  const explicitPageBreaks = countMatches(documentXml, /<w:br[^>]*w:type="page"[^>]*\/>/gu);
  return {
    package_profile: "OOXML_WORDPROCESSINGML",
    paragraphs_total: paragraphs.length,
    paragraphs_with_text: nonempty.length,
    text_runs: countMatches(documentXml, /<w:t(?:\s|>)/gu),
    math_text_runs: countMatches(documentXml, /<m:t(?:\s|>)/gu),
    tables: countMatches(documentXml, /<w:tbl(?:\s|>)/gu),
    hyperlinks: countMatches(documentXml, /<w:hyperlink(?:\s|>)/gu),
    comments: countMatches(documentXml, /<w:commentRangeStart(?:\s|>)/gu),
    sections: countMatches(documentXml, /<w:sectPr(?:\s|>)/gu),
    explicit_page_breaks: explicitPageBreaks,
    last_rendered_page_breaks: lastRenderedPageBreaks,
    page_boundary_authority: explicitPageBreaks || lastRenderedPageBreaks ? "MIXED_OR_SOURCE_RECORDED" : "NONE_IN_OOXML",
    style_counts: styleCounts,
    heading_style_counts: headingStyleCounts,
    short_fragment_paragraphs: shortFragments,
    short_fragment_share: nonempty.length ? Number((shortFragments / nonempty.length).toFixed(6)) : 0,
    duplicate_audit: duplicateAudit(paragraphs),
    interaction_residue: residueCounts(paragraphs),
    core_properties: {
      creator_present: Boolean(elementText(coreXml, "dc:creator")),
      title_present: Boolean(elementText(coreXml, "dc:title")),
      created: elementText(coreXml, "dcterms:created"),
      modified: elementText(coreXml, "dcterms:modified"),
    },
  };
}

function textProfile(text) {
  const letters = countMatches(text, /\p{L}/gu);
  const cyrillic = countMatches(text, /\p{Script=Cyrillic}/gu);
  const latin = countMatches(text, /\p{Script=Latin}/gu);
  const tokens = countMatches(text, /\p{L}[\p{L}\p{M}'’‐‑-]*/gu);
  const lines = text.replace(/\r\n?/gu, "\n").split("\n");
  return {
    byte_length: Buffer.byteLength(text, "utf8"),
    character_length: text.length,
    line_count: lines.length,
    token_count_unicode: tokens,
    letter_count: letters,
    cyrillic_letter_count: cyrillic,
    latin_letter_count: latin,
    cyrillic_letter_share: letters ? Number((cyrillic / letters).toFixed(6)) : 0,
    latin_letter_share: letters ? Number((latin / letters).toFixed(6)) : 0,
    one_character_nonempty_lines: lines.filter((line) => [...line.trim()].length === 1).length,
    short_nonempty_lines_le_3: lines.filter((line) => line.trim() && [...line.trim()].length <= 3).length,
  };
}

function parsePdfInfo(output) {
  const fields = {};
  for (const line of output.split(/\r?\n/u)) {
    const index = line.indexOf(":");
    if (index < 0) continue;
    fields[line.slice(0, index).trim()] = line.slice(index + 1).trim();
  }
  const pages = Number(fields.Pages);
  if (!Number.isInteger(pages) || pages < 1) throw new Error("PDFINFO_INVALID: rendered PDF has no positive page count.");
  return {
    pages,
    page_size: fields["Page size"] ?? null,
    producer: fields.Producer ?? null,
    pdf_version: fields["PDF version"] ?? null,
    tagged: fields.Tagged ?? null,
  };
}

export function buildDocxManifest(job, facts) {
  const sourceId = job.source_admission === "LOCAL_HASH" ? `LOCAL-SHA256-${facts.extracted_text.sha256.toUpperCase()}` : job.source_id;
  const prefix = job.rendering?.page_label_prefix ?? "R";
  const width = Math.max(4, String(facts.page_count).length);
  return {
    manifest_version: "DAE-SOURCE-MANIFEST-1.0",
    source_id: sourceId,
    bibliographic: {
      ...job.bibliographic,
      source_url: job.bibliographic.source_url ?? `urn:sha256:${facts.artifact.sha256}`,
    },
    artifact: {
      media_type: DOCX_MEDIA_TYPE,
      byte_length: facts.artifact.byte_length,
      sha256: facts.artifact.sha256,
    },
    extracted_text: {
      media_type: "text/plain",
      byte_length: facts.extracted_text.byte_length,
      sha256: facts.extracted_text.sha256,
      method: facts.extracted_text.method,
      page_delimiter: "FORM_FEED",
      normalization: "No byte normalization before fixity; page analysis joins visual line wraps and omits expressive source text from derivative outputs.",
    },
    pagination: {
      scheme: "DIGITAL_PAGE",
      authority: "RENDERER_DERIVED",
      labels: Array.from({ length: facts.page_count }, (_, index) => `${prefix}${String(index + 1).padStart(width, "0")}`),
    },
    access_policy: job.access_policy,
    crosswalk: job.crosswalk,
    ...(job.structure ? { structure: job.structure } : {}),
  };
}

function formatVersion(result) {
  return `${result.stdout}\n${result.stderr}`.trim().split(/\r?\n/u)[0] || null;
}

export async function analyzeDocx(engine, inputFile, jobFile, outputDir, options = {}) {
  const input = path.resolve(inputFile);
  const jobPath = path.resolve(jobFile);
  const out = path.resolve(outputDir);
  await requireNewDirectory(out);
  if (path.extname(input).toLowerCase() !== ".docx") throw new Error("analyze-docx requires a .docx input file.");

  const job = await readJson(jobPath);
  const jobIssues = engine.structural.validateDocxJob(job);
  if (jobIssues.length) throw new Error(`Invalid DOCX job: ${issueSummary(jobIssues)}`);
  if (job.source_admission === "CATALOGUED" && !engine.context.sourceCatalog.sources[job.source_id]) {
    throw new Error(`SOURCE_ADMISSION_BLOCK: '${job.source_id}' is not present in config/source_catalog.json.`);
  }

  const artifactBytes = await readFile(input);
  const artifactHash = sha256(artifactBytes);
  const temp = await mkdtemp(path.join(os.tmpdir(), "dae-docx-"));
  const generatedAt = options.generatedAt ?? new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
  try {
    const integrity = await command("unzip", ["-t", input]);
    if (!integrity.ok) throw new Error(`DOCX_INTEGRITY_FAILED: ${integrity.stderr.trim()}`);
    const documentPart = await command("unzip", ["-p", input, "word/document.xml"]);
    const corePart = await command("unzip", ["-p", input, "docProps/core.xml"]);
    if (!documentPart.ok) throw new Error(`DOCX_DOCUMENT_PART_FAILED: ${documentPart.stderr.trim()}`);

    const profile = path.join(temp, "lo-profile");
    const render = await command("soffice", [
      "--headless",
      `-env:UserInstallation=${pathToFileURL(profile).href}`,
      "--convert-to", "pdf",
      "--outdir", temp,
      input,
    ]);
    const expectedPdf = path.join(temp, `${path.basename(input, path.extname(input))}.pdf`);
    let pdf = expectedPdf;
    try {
      await stat(pdf);
    } catch {
      const candidates = (await readdir(temp)).filter((name) => name.toLowerCase().endsWith(".pdf"));
      if (candidates.length === 1) pdf = path.join(temp, candidates[0]);
      else throw new Error(`DOCX_RENDER_FAILED: ${render.stderr.trim() || "soffice produced no unique PDF"}`);
    }
    const pdfBytes = await readFile(pdf);
    const pdfInformation = await command("pdfinfo", [pdf]);
    if (!pdfInformation.ok) throw new Error(`PDFINFO_FAILED: ${pdfInformation.stderr.trim()}`);
    const pdfInfo = parsePdfInfo(pdfInformation.stdout);
    const extracted = path.join(temp, "rendered.txt");
    const textExtraction = await command("pdftotext", ["-layout", pdf, extracted]);
    if (!textExtraction.ok) throw new Error(`PDFTOTEXT_FAILED: ${textExtraction.stderr.trim()}`);
    const extractedBytes = await readFile(extracted);
    const pageSegments = extractedBytes.toString("utf8").split("\f");
    if (!pageSegments.at(-1)?.trim()) pageSegments.pop();
    if (pageSegments.length !== pdfInfo.pages) {
      throw new Error(`DOCX_RENDER_PAGE_MISMATCH: pdfinfo=${pdfInfo.pages}, pdftotext=${pageSegments.length}.`);
    }

    const manifest = buildDocxManifest(job, {
      artifact: { byte_length: artifactBytes.length, sha256: artifactHash },
      extracted_text: {
        byte_length: extractedBytes.length,
        sha256: sha256(extractedBytes),
        method: "LibreOffice headless PDF render followed by Poppler pdftotext -layout",
      },
      page_count: pdfInfo.pages,
    });
    const manifestIssues = engine.structural.validateSourceManifest(manifest);
    if (manifestIssues.length) throw new Error(`Generated source manifest is invalid: ${issueSummary(manifestIssues)}`);
    const manifestTemp = path.join(temp, "source_manifest.json");
    await writeFile(manifestTemp, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

    const result = await analyzePagedText(engine, extracted, manifestTemp, path.join(out, "generated"), { generatedAt });
    const [sofficeVersion, pdftotextVersion] = await Promise.all([
      command("soffice", ["--version"]),
      command("pdftotext", ["-v"]),
    ]);
    const xmlAudit = inspectDocxXml(documentPart.stdout, corePart.ok ? corePart.stdout : "");
    const intake = {
      intake_version: "DAE-DOCX-INTAKE-0.1",
      generated_at: generatedAt,
      source_id: manifest.source_id,
      source_admission: job.source_admission,
      input: {
        basename: path.basename(input),
        path_scope: "BASENAME_ONLY",
        media_type: DOCX_MEDIA_TYPE,
        byte_length: artifactBytes.length,
        sha256: artifactHash,
        zip_integrity: "PASS",
      },
      ooxml_audit: xmlAudit,
      rendering: {
        pagination_authority: "RENDERER_DERIVED_NOT_GA_OR_SOURCE_AUTHORED",
        page_count: pdfInfo.pages,
        page_size: pdfInfo.page_size,
        renderer: formatVersion(sofficeVersion),
        renderer_exit: render.ok ? "ZERO" : "NONZERO_WITH_PDF_OUTPUT",
        pdf_sha256: sha256(pdfBytes),
        pdf_sha256_role: "TRANSIENT_RUN_DIAGNOSTIC_NOT_REPRODUCIBILITY_ANCHOR",
        pdf_byte_length: pdfBytes.length,
        pdf_profile: pdfInfo,
      },
      extracted_text: {
        method: "pdftotext -layout",
        extractor: formatVersion(pdftotextVersion),
        byte_length: extractedBytes.length,
        sha256: sha256(extractedBytes),
        page_count: pageSegments.length,
        text_profile: textProfile(extractedBytes.toString("utf8")),
      },
      retention: {
        original_docx_copied_to_output: false,
        rendered_pdf_retained: false,
        extracted_text_retained: false,
        expressive_source_context_in_records: false,
      },
      risk_flags: [
        ...(!xmlAudit.core_properties.creator_present ? ["NO_DOCUMENT_AUTHOR_METADATA"] : []),
        ...(!xmlAudit.explicit_page_breaks && !xmlAudit.last_rendered_page_breaks ? ["NO_SOURCE_RECORDED_PAGE_BOUNDARIES"] : []),
        ...(!xmlAudit.hyperlinks ? ["NO_OOXML_HYPERLINKS"] : []),
        ...(xmlAudit.short_fragment_share > 0.1 ? ["HIGH_SHORT_FRAGMENT_SHARE"] : []),
        ...(Object.values(xmlAudit.heading_style_counts).reduce((sum, value) => sum + value, 0) > 1000 ? ["HEADING_HIERARCHY_OVERSEGMENTED"] : []),
        ...(xmlAudit.duplicate_audit.duplicate_occurrence_share > 0.05 ? ["SUBSTANTIAL_EXACT_REPETITION"] : []),
        ...(Object.values(xmlAudit.interaction_residue).some((value) => value > 0) ? ["INTERACTION_OR_TOOL_RESIDUE"] : []),
        ...(xmlAudit.interaction_residue.pseudo_citation_markers > 0 && !xmlAudit.hyperlinks && !xmlAudit.interaction_residue.visible_urls ? ["PSEUDO_CITATIONS_WITHOUT_RESOLVABLE_LINKS"] : []),
      ],
      reproducibility_anchors: {
        original_docx_sha256: artifactHash,
        extracted_text_sha256: sha256(extractedBytes),
        renderer_pdf_hash_is_anchor: false,
      },
      classification: "COMPOSITE_RESEARCH_DOSSIER_PENDING_HUMAN_GENRE_AND_SOURCE_REVIEW",
      claim_ceiling: "DOCUMENT_STRUCTURE_AND_DERIVATIVE_LEXICAL_CANDIDATES_ONLY_NOT_PRIMARY_TEXT_AUTHORITY_OR_PHILOSOPHICAL_TRUTH",
    };
    await writeFile(path.join(out, "source_manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
    await writeFile(path.join(out, "docx_intake.json"), `${JSON.stringify(intake, null, 2)}\n`, "utf8");
    return { ...result, output_dir: out, manifest, intake };
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
}
