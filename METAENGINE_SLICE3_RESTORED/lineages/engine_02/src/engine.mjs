import { readdir, stat } from "node:fs/promises";
import path from "node:path";
import { createStructuralValidator } from "./structural-validator.mjs";
import { projectPath, readJson } from "./paths.mjs";
import { countIssues, issue, sortIssues } from "./issues.mjs";
import { validateSemantics } from "./semantic-rules.mjs";

async function collectJsonFiles(inputs) {
  const files = [];
  async function visit(candidate) {
    const info = await stat(candidate);
    if (info.isDirectory()) {
      for (const name of (await readdir(candidate)).sort()) await visit(path.join(candidate, name));
    } else if (info.isFile() && candidate.toLowerCase().endsWith(".json")) {
      files.push(path.resolve(candidate));
    }
  }
  for (const input of inputs) await visit(path.resolve(input));
  return files;
}

export async function createEngine() {
  const engineVersion = (await readJson(projectPath("package.json"))).version;
  const structural = await createStructuralValidator();
  const [aag, registry, sourceCatalog, policy, protocolRegistry, argumentSchemeRegistry] = await Promise.all([
    readJson(projectPath("vendor", "core4", "aag_0_1.json")),
    readJson(projectPath("vendor", "core4", "relation_registry_rt00_rt28.json")),
    readJson(projectPath("config", "source_catalog.json")),
    readJson(projectPath("config", "engine.policy.json")),
    readJson(projectPath("config", "protocol_registry.json")),
    readJson(projectPath("config", "argument_scheme_registry.json")),
  ]);
  const relationIds = new Set(registry.entries.map((entry) => entry.rt_id));
  const context = { engineVersion, aag, registry, relationIds, sourceCatalog, policy, protocolRegistry, argumentSchemeRegistry, extensionRegistry: structural.extensionRegistry };

  function validateRecord(record, file = "<memory>") {
    const structuralIssues = structural.validateRecord(record);
    const semanticIssues = structuralIssues.length ? [] : validateSemantics(record, context);
    const issues = sortIssues([...structuralIssues, ...semanticIssues]);
    const counts = countIssues(issues);
    return {
      file,
      record_id: record?.record_id ?? null,
      conformant: counts.ERROR === 0,
      review_required: counts.REVIEW > 0,
      counts,
      issues,
    };
  }

  async function validateInputs(inputs) {
    const files = await collectJsonFiles(inputs);
    const results = [];
    for (const file of files) {
      try {
        results.push(validateRecord(await readJson(file), file));
      } catch (error) {
        const issues = [issue("ERROR", "JSON_PARSE", "/", error.message)];
        results.push({ file, record_id: null, conformant: false, review_required: false, counts: countIssues(issues), issues });
      }
    }

    const ids = new Map();
    for (const result of results) {
      if (!result.record_id) continue;
      if (!ids.has(result.record_id)) ids.set(result.record_id, []);
      ids.get(result.record_id).push(result);
    }
    for (const [recordId, duplicates] of ids) {
      if (duplicates.length < 2) continue;
      for (const result of duplicates) {
        result.issues = sortIssues([...result.issues, issue("ERROR", "DUPLICATE_RECORD_ID", "/record_id", `${recordId} occurs ${duplicates.length} times in this batch.`)]);
        result.counts = countIssues(result.issues);
        result.conformant = false;
      }
    }
    return summarize(results);
  }

  function summarize(results) {
    const counts = { files: results.length, conformant: 0, review_required: 0, ERROR: 0, REVIEW: 0, WARNING: 0, INFO: 0 };
    for (const result of results) {
      if (result.conformant) counts.conformant += 1;
      if (result.review_required) counts.review_required += 1;
      for (const severity of ["ERROR", "REVIEW", "WARNING", "INFO"]) counts[severity] += result.counts[severity] ?? 0;
    }
    return { engine_version: engineVersion, core_version: policy.core_version, counts, results };
  }

  return { context, structural, validateRecord, validateInputs, summarize };
}
