import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createEngine } from "../src/engine.mjs";
import { analyzePagedText } from "../src/page-analyzer.mjs";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const manifestFile = path.join(root, "experiments", "heidegger-ga", "full-work-1912", "source_manifest.json");
const manifest = JSON.parse(await readFile(manifestFile, "utf8"));
const outIndex = process.argv.indexOf("--out");
if (outIndex < 0 || !process.argv[outIndex + 1]) throw new Error("Usage: npm run pilot:ga1-work -- --out <new-directory>");
const outputDir = path.resolve(process.argv[outIndex + 1]);

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

const stage = await mkdtemp(path.join(os.tmpdir(), "dae-ga1-work-"));
try {
  const response = await fetch(manifest.bibliographic.source_url, {
    headers: { "user-agent": "Destruktion-Automation-Engine/0.3.0 single-work-source-audit" }
  });
  if (!response.ok) throw new Error(`Source acquisition failed: HTTP ${response.status}`);
  const pdfBytes = Buffer.from(await response.arrayBuffer());
  if (pdfBytes.length !== manifest.artifact.byte_length || sha256(pdfBytes) !== manifest.artifact.sha256) {
    throw new Error("SOURCE_FIXITY_MISMATCH: the public archive PDF differs from the pinned artifact; update only after source review.");
  }

  const pdfFile = path.join(stage, "source.pdf");
  const textFile = path.join(stage, "source.txt");
  await writeFile(pdfFile, pdfBytes);
  try {
    execFileSync("pdftotext", ["-layout", pdfFile, textFile], { stdio: "pipe" });
  } catch (error) {
    throw new Error(`Poppler pdftotext is required for this pilot: ${error.message}`);
  }
  const textBytes = await readFile(textFile);
  if (textBytes.length !== manifest.extracted_text.byte_length || sha256(textBytes) !== manifest.extracted_text.sha256) {
    throw new Error("EXTRACTION_FIXITY_MISMATCH: pdftotext output differs from the pinned extraction; do not silently change unitization.");
  }

  const engine = await createEngine();
  const result = await analyzePagedText(engine, textFile, manifestFile, outputDir);
  await writeFile(path.join(outputDir, "acquisition_run.json"), `${JSON.stringify({
    run_version: "DAE-TRANSIENT-ACQUISITION-1.0",
    generated_at: result.bundle.generated_at,
    source_id: manifest.source_id,
    source_url: manifest.bibliographic.source_url,
    artifact_sha256: manifest.artifact.sha256,
    extracted_text_sha256: manifest.extracted_text.sha256,
    raw_artifact_retained: false,
    raw_text_retained: false,
    output_policy: manifest.access_policy.analysis_class,
    result: {
      pages: result.bundle.page_count,
      units: result.bundle.unit_count,
      candidate_records: result.bundle.candidate_record_count,
      validation: result.bundle.validation
    }
  }, null, 2)}\n`, "utf8");
  console.log(`GA 1 work pilot complete: ${result.bundle.page_count} pages, ${result.bundle.candidate_record_count} review candidates, raw source retained=false, output=${outputDir}`);
} finally {
  await rm(stage, { recursive: true, force: true });
}
