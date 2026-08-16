let Ajv2020;
try {
  ({ default: Ajv2020 } = await import("ajv/dist/2020.js"));
} catch {
  ({ default: Ajv2020 } = await import("../../vendor/ajv-compat/2020.mjs"));
}
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCHEMAS = path.resolve(HERE, "../schemas");
const ajv = new Ajv2020({ allErrors: true, strict: false, validateFormats: false });

async function compile(name) {
  const schema = JSON.parse(await readFile(path.join(SCHEMAS, name), "utf8"));
  return ajv.compile(schema);
}

const manifestValidator = await compile("independent_family_ecology_manifest.schema.json");
const resultValidator = await compile("independent_family_ecology_result.schema.json");
const downstreamValidator = await compile("ecology_downstream_result.schema.json");

function issues(validator, payload) {
  return validator(payload) ? [] : (validator.errors ?? []).map((error) => ({
    at: error.instancePath || "/",
    keyword: error.keyword,
    message: error.message ?? "schema validation failure",
    params: error.params,
  }));
}

export async function validateIndependentFamilyManifest(payload) { return issues(manifestValidator, payload); }
export async function validateIndependentFamilyResult(payload) { return issues(resultValidator, payload); }
export async function validateEcologyDownstreamResult(payload) { return issues(downstreamValidator, payload); }
