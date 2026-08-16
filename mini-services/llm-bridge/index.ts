/**
 * MetaEngine LLM Bridge — OpenAI-compatible HTTP server.
 *
 * Exposes:
 *   GET  /v1/models              → list of available models
 *   POST /v1/chat/completions    → OpenAI-compatible chat completion
 *   GET  /health                 → health check
 *
 * Internally uses z-ai-web-dev-sdk as the actual LLM backend, so MetaEngine's
 * LLM_MODEL adapter (which speaks OpenAI-compatible) can call this bridge and
 * execute REAL LLM calls without Ollama being installed.
 *
 * Constitution: This bridge is an EXTERNAL EXECUTOR from MetaEngine's perspective.
 *   - MetaEngine's claim_ceiling LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED
 *     remains in force — outputs are tagged as generative, never as truth.
 *   - The bridge never silently falls back; if the SDK fails, it returns HTTP 500.
 */

import { createServer, IncomingMessage, ServerResponse } from 'node:http';

// --- z-ai-web-dev-sdk: real LLM execution ---
let _zai: any = null;
async function getZAI(): Promise<any> {
  if (_zai) return _zai;
  const ZAIModule: any = await import('z-ai-web-dev-sdk');
  const ZAI = ZAIModule.default ?? ZAIModule.ZAI ?? ZAIModule;
  _zai = await ZAI.create();
  return _zai;
}

const PORT = 3031; // fixed port — used by MetaEngine via XTransformPort gateway

// --- Models list (advertised to MetaEngine) ---
const MODELS = [
  { id: 'metaengine-glm-1', object: 'model', created: 1700000000, owned_by: 'z-ai-web-dev-sdk' },
  { id: 'metaengine-glm-thinking', object: 'model', created: 1700000000, owned_by: 'z-ai-web-dev-sdk' },
];

// --- Helpers -----------------------------------------------------------------

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on('data', (c: Buffer) => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    req.on('error', reject);
  });
}

function sendJSON(res: ServerResponse, status: number, body: any) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  });
  res.end(payload);
}

function nowISO(): string {
  return new Date().toISOString();
}

// Rough token estimate: ~4 chars/token
function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.ceil(text.length / 4);
}

interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | string;
  content: string;
}

interface ChatCompletionRequest {
  model?: string;
  messages?: ChatMessage[];
  max_tokens?: number;
  temperature?: number;
  stream?: boolean;
}

/**
 * Call z-ai-web-dev-sdk with retry on rate-limit (429) and transient errors.
 * Exponential backoff: 1s, 2s, 4s, 8s, 16s — max 5 attempts.
 */
async function callZAI(req: ChatCompletionRequest): Promise<{ text: string; in_tokens: number; out_tokens: number; model: string }> {
  const zai = await getZAI();
  const messages = req.messages ?? [];
  const model = req.model || 'metaengine-glm-1';
  const enableThinking = model.includes('thinking');

  // The SDK uses role 'assistant' for system prompts.
  const sdkMessages = messages.map((m) => ({
    role: m.role === 'system' ? 'assistant' : (m.role as 'user' | 'assistant'),
    content: m.content ?? '',
  }));

  // Ensure there is at least one message
  if (sdkMessages.length === 0) {
    throw new Error('EMPTY_MESSAGES: at least one message is required');
  }

  const maxAttempts = 5;
  let lastErr: any = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const completion = await zai.chat.completions.create({
        messages: sdkMessages,
        thinking: enableThinking ? { type: 'enabled' } : { type: 'disabled' },
      } as any);

      const text: string = completion?.choices?.[0]?.message?.content ?? '';
      const in_tokens = estimateTokens(messages.map((m) => m.content).join('\n'));
      const out_tokens = estimateTokens(text);
      return { text, in_tokens, out_tokens, model };
    } catch (err: any) {
      lastErr = err;
      const msg: string = err?.message ?? String(err);
      const isRateLimit = msg.includes('429') || msg.includes('Too many requests');
      const isTransient = msg.includes('500') || msg.includes('502') || msg.includes('503') || msg.includes('timeout');
      if (attempt < maxAttempts && (isRateLimit || isTransient)) {
        const delayMs = Math.min(16000, 1000 * Math.pow(2, attempt - 1));
        console.error(`[llm-bridge] attempt ${attempt} failed (${msg.slice(0, 100)}); retrying in ${delayMs}ms`);
        await new Promise((r) => setTimeout(r, delayMs));
        continue;
      }
      throw err;
    }
  }
  throw lastErr ?? new Error('UNREACHABLE');
}

// --- HTTP server -------------------------------------------------------------

const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    sendJSON(res, 204, {});
    return;
  }

  const url = req.url ?? '/';

  // Health
  if (url === '/health' && req.method === 'GET') {
    sendJSON(res, 200, {
      status: 'ok',
      service: 'metaengine-llm-bridge',
      version: '1.0.0',
      backend: 'z-ai-web-dev-sdk',
      port: PORT,
      uptime_ms: process.uptime() * 1000,
      timestamp: nowISO(),
    });
    return;
  }

  // List models
  if (url === '/v1/models' && req.method === 'GET') {
    sendJSON(res, 200, { object: 'list', data: MODELS });
    return;
  }

  // Chat completions
  if (url === '/v1/chat/completions' && req.method === 'POST') {
    try {
      const raw = await readBody(req);
      let body: ChatCompletionRequest;
      try {
        body = JSON.parse(raw);
      } catch {
        sendJSON(res, 400, { error: { message: 'INVALID_JSON', type: 'invalid_request_error' } });
        return;
      }

      const started = Date.now();
      const { text, in_tokens, out_tokens, model } = await callZAI(body);
      const elapsed_ms = Date.now() - started;

      const completionId = `chatcmpl-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      const created = Math.floor(Date.now() / 1000);

      const response = {
        id: completionId,
        object: 'chat.completion',
        created,
        model,
        choices: [
          {
            index: 0,
            message: { role: 'assistant', content: text },
            finish_reason: 'stop',
          },
        ],
        usage: {
          prompt_tokens: in_tokens,
          completion_tokens: out_tokens,
          total_tokens: in_tokens + out_tokens,
        },
        // MetaEngine-specific provenance: real LLM execution
        meta: {
          backend: 'z-ai-web-dev-sdk',
          elapsed_ms,
          bridge: 'metaengine-llm-bridge',
          claim_ceiling: 'LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED',
          real_llm_execution: true,
        },
      };

      sendJSON(res, 200, response);
      return;
    } catch (err: any) {
      console.error('[llm-bridge] chat/completions error:', err?.message ?? err);
      sendJSON(res, 500, {
        error: {
          message: `LLM_BRIDGE_ERROR: ${err?.message ?? 'unknown'}`,
          type: 'server_error',
        },
      });
      return;
    }
  }

  // 404
  sendJSON(res, 404, { error: { message: `NOT_FOUND: ${url}`, type: 'invalid_request_error' } });
});

server.listen(PORT, () => {
  console.log(`[metaengine-llm-bridge] listening on port ${PORT}`);
  console.log(`[metaengine-llm-bridge] OpenAI-compatible endpoints:`);
  console.log(`  GET  /v1/models`);
  console.log(`  POST /v1/chat/completions`);
  console.log(`  GET  /health`);
  console.log(`[metaengine-llm-bridge] backend: z-ai-web-dev-sdk`);
});

// Graceful shutdown
const shutdown = (sig: string) => {
  console.log(`[metaengine-llm-bridge] received ${sig}, shutting down...`);
  server.close(() => {
    console.log('[metaengine-llm-bridge] closed');
    process.exit(0);
  });
  // Force exit after 5s if close hangs
  setTimeout(() => process.exit(0), 5000).unref();
};
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
