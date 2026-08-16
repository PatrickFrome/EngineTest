import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { createEngine } from "../src/engine.mjs";
import { PROJECT_ROOT } from "../src/paths.mjs";
import { readPortableProjectManifest, validatePortableProject } from "../src/portable-project.mjs";

test("AI-chat portable project is schema-valid, relocatable and cryptographically bound", async () => {
  const engine = await createEngine();
  const result = await validatePortableProject(engine, PROJECT_ROOT);
  assert.equal(result.conformant, true, JSON.stringify(result.issues, null, 2));
  assert.equal(result.counts.ERROR, 0);
  assert.equal(result.manifest.portable_project_version, "DAE-AI-CHAT-1.0");
  assert.equal(result.manifest.entrypoint, "00_START_HERE.md");
  assert.ok(result.manifest.required_assets.length >= 20);
  assert.ok(result.manifest.required_assets.every((asset) => /^[a-f0-9]{64}$/.test(asset.sha256)));
  assert.ok(result.manifest.required_assets.every((asset) => !asset.path.startsWith("/") && !asset.path.includes("../")));
  assert.deepEqual(Object.keys(result.manifest.execution_profiles).sort(), ["DOCUMENT_ONLY", "EXECUTION_AVAILABLE"]);
});

test("document-only profile mandates ETY and forbids pseudo-execution or ritual surprise", async () => {
  const manifest = await readPortableProjectManifest(PROJECT_ROOT);
  const [bootstrap, protocol] = await Promise.all([
    readFile(`${PROJECT_ROOT}/PORTABLE_CHAT_PROJECT.md`, "utf8"),
    readFile(`${PROJECT_ROOT}/portable/DOCUMENT_ONLY_PROTOCOL.md`, "utf8"),
  ]);
  assert.equal(manifest.invariants.mandatory_etymology, true);
  assert.equal(manifest.invariants.mandatory_etymological_significance, false);
  assert.equal(manifest.invariants.document_only_may_claim_code_execution, false);
  assert.equal(manifest.invariants.active_move_requires_gain, true);
  assert.match(bootstrap, /DOCUMENT_ONLY_LANGUAGE_MODEL_EXECUTION/);
  assert.match(bootstrap, /Запрещено имитировать hashes, schema validation/);
  assert.match(protocol, /ETY-MIN для каждого центрального понятия/);
  assert.match(protocol, /Если операция не добавляет GG1/);
  assert.match(protocol, /региональным Gestell/);
});

