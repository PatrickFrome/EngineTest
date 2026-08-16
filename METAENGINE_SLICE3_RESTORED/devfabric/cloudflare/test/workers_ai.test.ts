import test from 'node:test';
import assert from 'node:assert/strict';
import { workersAiEligibility, buildReviewPrompt } from '../src/workers_ai.ts';

test('Workers AI is limited to P0/P1 and quota-known requests', () => {
  assert.equal(workersAiEligibility('P2', 10000).eligible, false);
  assert.equal(workersAiEligibility('P1', null).reason, 'QUOTA_UNKNOWN');
  assert.equal(workersAiEligibility('P1', 0).reason, 'QUOTA_EXHAUSTED');
  assert.equal(workersAiEligibility('P1', 1).eligible, true);
});

test('review prompt contains refs and criteria but no code/source body', () => {
  const prompt = buildReviewPrompt({ taskHash: 'a'.repeat(64), candidateHash: 'b'.repeat(64), verifierHash: 'c'.repeat(64), privacyClass: 'P1' });
  assert.ok(prompt.includes('candidate_hash'));
  assert.equal(prompt.includes('source_code'), false);
  assert.equal(prompt.includes('patch_body'), false);
});

class FakeAI {
  calls = 0;
  async run(_model: string, input: { prompt: string }) {
    this.calls += 1;
    return { response: input.prompt.includes('candidate_hash') ? 'risk:low' : 'bad' };
  }
}

test('Workers AI review returns a content-addressed metadata-only receipt', async () => {
  const { runWorkersAiReview } = await import('../src/workers_ai.ts');
  const ai = new FakeAI();
  const result = await runWorkersAiReview(ai, {
    taskHash: 'a'.repeat(64), candidateHash: 'b'.repeat(64), verifierHash: 'c'.repeat(64), privacyClass: 'P1'
  }, 100);
  assert.equal(ai.calls, 1);
  assert.match(result.receiptHash, /^[a-f0-9]{64}$/);
  assert.equal(JSON.stringify(result).includes('patch_body'), false);
});

test('Workers AI review never invokes binding when quota is unknown', async () => {
  const { runWorkersAiReview } = await import('../src/workers_ai.ts');
  const ai = new FakeAI();
  await assert.rejects(() => runWorkersAiReview(ai, {
    taskHash: 'a'.repeat(64), candidateHash: 'b'.repeat(64), verifierHash: 'c'.repeat(64), privacyClass: 'P1'
  }, null), /QUOTA_UNKNOWN/);
  assert.equal(ai.calls, 0);
});
