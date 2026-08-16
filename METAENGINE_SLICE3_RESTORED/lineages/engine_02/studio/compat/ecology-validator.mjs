import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

let Ajv2020;
try {
  ({ default: Ajv2020 } = await import('ajv/dist/2020.js'));
} catch {
  ({ default: Ajv2020 } = await import('../../vendor/ajv-compat/2020.mjs'));
}

const HERE = path.dirname(fileURLToPath(import.meta.url));
async function readJson(file) { return JSON.parse(await readFile(file, 'utf8')); }

function errorsOf(validator) {
  return (validator.errors ?? []).map((e) => ({
    severity: 'ERROR',
    code: 'STUDIO_COMPAT_SCHEMA',
    path: e.instancePath || '/',
    message: e.message ?? 'schema validation failure',
    keyword: e.keyword,
  }));
}

export async function createEcologyCompatValidator() {
  const ajv = new Ajv2020({ allErrors: true, strict: false, validateFormats: false });
  const manifestSchema = await readJson(path.join(HERE, 'schemas', 'micro_local_operator_ecology_manifest.schema.json'));
  const resultSchema = await readJson(path.join(HERE, 'schemas', 'micro_local_operator_ecology_result.schema.json'));
  const validateManifest = ajv.compile(manifestSchema);
  const validateResult = ajv.compile(resultSchema);
  return {
    validateManifest(payload) { return validateManifest(payload) ? [] : errorsOf(validateManifest); },
    validateResult(payload) { return validateResult(payload) ? [] : errorsOf(validateResult); },
  };
}
