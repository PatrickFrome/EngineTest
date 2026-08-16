export type R2PutOptions = { sha256: string; customMetadata: Record<string, string> };
export interface R2ObjectLike { customMetadata?: Record<string, string>; body: ReadableStream }
export interface R2BucketLike {
  put(key: string, body: Uint8Array | ReadableStream, options: R2PutOptions): Promise<unknown>;
  get?(key: string): Promise<R2ObjectLike | null>;
}


export function normalizeDigest(digest: string): string {
  const normalized = digest.toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(normalized)) throw new Error('INVALID_SHA256');
  return normalized;
}

export function artifactKey(digest: string): string {
  const d = normalizeDigest(digest);
  return `sha256/${d.slice(0, 2)}/${d}`;
}

export async function putArtifact(bucket: R2BucketLike, body: Uint8Array | ReadableStream, expectedDigest: string): Promise<unknown> {
  const digest = normalizeDigest(expectedDigest);
  return bucket.put(artifactKey(digest), body, { sha256: digest, customMetadata: { sha256: digest, addressing: 'content-addressed' } });
}

export async function getArtifact(bucket: { get(key: string): Promise<R2ObjectLike | null> }, expectedDigest: string): Promise<R2ObjectLike> {
  const digest = normalizeDigest(expectedDigest);
  const object = await bucket.get(artifactKey(digest));
  if (!object) throw new Error('R2_ARTIFACT_NOT_FOUND');
  if (object.customMetadata?.sha256 !== digest) throw new Error('R2_DIGEST_METADATA_MISMATCH');
  return object;
}
