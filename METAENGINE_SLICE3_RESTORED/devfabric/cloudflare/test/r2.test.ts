import test from 'node:test';
import assert from 'node:assert/strict';
import { artifactKey, normalizeDigest, putArtifact } from '../src/r2.ts';

class FakeBucket {
  putCalls: unknown[] = [];
  async put(key: string, body: Uint8Array, options: { sha256: string, customMetadata: Record<string,string> }) {
    this.putCalls.push([key, body.length, options]);
    return { key };
  }
}

test('artifact keys are sha256 content addresses', () => {
  const d = 'ab' + '1'.repeat(62);
  assert.equal(artifactKey(d), `sha256/ab/${d}`);
  assert.equal(normalizeDigest(d.toUpperCase()), d);
});

test('R2 put binds the expected SHA-256 checksum and rejects malformed digest', async () => {
  const bucket = new FakeBucket();
  const d = 'cd' + '2'.repeat(62);
  await putArtifact(bucket, new Uint8Array([1,2,3]), d);
  const [key, , options] = bucket.putCalls[0] as [string, number, { sha256: string, customMetadata: Record<string,string> }];
  assert.equal(key, `sha256/cd/${d}`);
  assert.equal(options.sha256, d);
  assert.equal(options.customMetadata.sha256, d);
  await assert.rejects(() => putArtifact(bucket, new Uint8Array([1]), 'not-a-digest'), /INVALID_SHA256/);
});

class FakeReadBucket {
  obj: unknown;
  constructor(obj: unknown) { this.obj = obj; }
  async get(_key: string) { return this.obj; }
}

test('R2 get rejects metadata digest mismatch before returning body', async () => {
  const { getArtifact } = await import('../src/r2.ts');
  const d = 'ef' + '3'.repeat(62);
  const bucket = new FakeReadBucket({ customMetadata: { sha256: 'aa' + '0'.repeat(62) }, body: new ReadableStream() });
  await assert.rejects(() => getArtifact(bucket, d), /R2_DIGEST_METADATA_MISMATCH/);
});
