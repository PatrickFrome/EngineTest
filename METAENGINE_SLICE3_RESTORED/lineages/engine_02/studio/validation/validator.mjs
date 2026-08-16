let Ajv2020;
try {
  ({ default: Ajv2020 } = await import('ajv/dist/2020.js'));
} catch {
  ({ default: Ajv2020 } = await import('../../vendor/ajv-compat/2020.mjs'));
}
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCHEMAS = path.resolve(HERE, '../schemas');
const ajv = new Ajv2020({ allErrors: true, strict: false, validateFormats: false });

async function compile(name) {
  const schema = JSON.parse(await readFile(path.join(SCHEMAS, name), 'utf8'));
  return ajv.compile(schema);
}

const validators = {
  campaign: await compile('external_validation_campaign.schema.json'),
  system: await compile('external_system_predictions.schema.json'),
  challenge: await compile('semantic_challenge_manifest.schema.json'),
  challengeResults: await compile('semantic_challenge_results.schema.json'),
  result: await compile('external_validation_result.schema.json'),
};

function issues(validator, payload) {
  return validator(payload) ? [] : (validator.errors ?? []).map((error) => ({
    at: error.instancePath || '/',
    keyword: error.keyword,
    message: error.message ?? 'schema validation failure',
    params: error.params,
  }));
}

export const validateExternalValidationCampaign = async (payload) => issues(validators.campaign, payload);
export const validateExternalSystemPredictions = async (payload) => issues(validators.system, payload);
export const validateSemanticChallenge = async (payload) => issues(validators.challenge, payload);
export const validateSemanticChallengeResults = async (payload) => issues(validators.challengeResults, payload);
export const validateExternalValidationResult = async (payload) => issues(validators.result, payload);
