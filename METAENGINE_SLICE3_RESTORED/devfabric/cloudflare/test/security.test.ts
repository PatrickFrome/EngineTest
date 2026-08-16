import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const mcpSource = fs.readFileSync(new URL('../src/mcp.ts', import.meta.url), 'utf8');
const indexSource = fs.readFileSync(new URL('../src/index.ts', import.meta.url), 'utf8');

test('transport uses current stateless MCP handler and not deprecated McpAgent', () => {
  assert.ok(mcpSource.includes('createMcpHandler'));
  assert.equal(mcpSource.includes('McpAgent'), false);
  assert.equal(mcpSource.includes('createLegacyMcpHandler'), false);
});

test('worker requires an external secret binding and never hardcodes bearer material', () => {
  assert.ok(indexSource.includes('MCP_EDGE_TOKEN'));
  assert.equal(/Bearer\s+[A-Za-z0-9_-]{12,}/.test(indexSource), false);
});

test('MCP transport is wired to D1 state and quota-gated Workflow dispatch', () => {
  for (const symbol of ['createTaskRef', 'readTaskStatus', 'listCandidateRefs', 'createVerificationRequest', 'readQuotaSnapshot', 'budgetDecision']) {
    assert.ok(mcpSource.includes(symbol), `missing ${symbol}`);
  }
  assert.ok(mcpSource.includes('EDGE_WORKFLOW.create'));
});

test('Worker exports the configured Workflow class', () => {
  assert.ok(indexSource.includes("export { MetaengineEdgeWorkflow }"));
});
