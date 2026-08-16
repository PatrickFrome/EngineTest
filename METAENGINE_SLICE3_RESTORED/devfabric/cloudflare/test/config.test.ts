import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const cfg = JSON.parse(fs.readFileSync(new URL('../wrangler.jsonc', import.meta.url), 'utf8'));

test('wrangler config is zero-spend safe and current', () => {
  assert.equal(cfg.compatibility_date, '2026-08-12');
  assert.ok(cfg.compatibility_flags.includes('nodejs_compat'));
  assert.equal(cfg.observability.enabled, true);
  assert.equal(cfg.vars.ZERO_SPEND, 'true');
  assert.equal(cfg.vars.DEPLOYMENT_GUARD, 'NO_DEPLOYMENT_WITHOUT_EXPLICIT_AUTH');
});

test('config contains no plaintext secrets and no remote development bindings', () => {
  const text = JSON.stringify(cfg).toLowerCase();
  for (const bad of ['service_role', 'api_key', 'secret_key', 'bearer ']) assert.equal(text.includes(bad), false);
  for (const group of ['d1_databases', 'r2_buckets']) {
    for (const binding of cfg[group] ?? []) assert.notEqual(binding.remote, true);
  }
});
