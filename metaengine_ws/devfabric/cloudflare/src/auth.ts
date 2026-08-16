function utf8(value: string): Uint8Array { return new TextEncoder().encode(value); }

function constantTimeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a[i] ^ b[i];
  return diff === 0;
}

export function bearerAuthorized(request: Request, expected: string): boolean {
  if (!expected) return false;
  const header = request.headers.get('authorization') ?? '';
  const prefix = 'Bearer ';
  if (!header.startsWith(prefix)) return false;
  return constantTimeEqual(utf8(header.slice(prefix.length)), utf8(expected));
}
