/**
 * MetaEngine WebSocket Events Service — real-time event push.
 *
 * Architecture:
 *   - Listens on port 3032 (fixed; frontend connects via io("/?XTransformPort=3032"))
 *   - Reads events from a shared JSONL log at METAENGINE_ROOT/storage/events.log
 *   - Each line is a JSON object: { type, timestamp, payload }
 *   - Pushes new events to all connected WebSocket clients as they arrive
 *   - Supports replay: on connect, client can request "?since=<offset>" to get
 *     missed events
 *
 * Event types (pushed to clients):
 *   - fitness.evaluated    — a tiered fitness evaluation completed
 *   - fitness.generation   — a PBT generation completed (mean/best fitness)
 *   - recursive.generation — a real recursive improvement generation completed
 *   - recursive.summary    — the full recursive run summary
 *   - amplify.fired        — an amplify rule fired (with rule name + weight)
 *   - distill.persisted    — a distillation was saved to history
 *   - router.faiiledover   — MultiModelRouter failed over to a different backend
 *   - router.recovered     — background reaper recovered an unhealthy backend
 *   - api.rate_limited     — an API request was rate-limited (429)
 *
 * Constitution:
 *   - All events carry truth_effect=NONE (they're observational, not truth)
 *   - No auto-promotion (events don't trigger any constitution change)
 *   - No code modification (read-only on the MetaEngine source)
 */

import { createServer, IncomingMessage } from 'node:http';
import { readFile, stat, watchFile } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocketServer, WebSocket } from 'ws';

const PORT = 3032; // fixed port — used by MetaEngine via XTransformPort gateway

// Resolve METAENGINE_ROOT relative to this file
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const METAENGINE_ROOT = process.env.METAENGINE_ROOT || '/home/z/my-project/METAENGINE_SLICE3_RESTORED';
const EVENT_LOG_PATH = join(METAENGINE_ROOT, 'storage', 'events.log');

// --- Event log reader ------------------------------------------------------

interface MetaEvent {
  type: string;
  timestamp: string;
  payload: any;
}

let lastReadOffset = 0;

/**
 * Read all events from the JSONL log starting at the given byte offset.
 * Returns { events, newOffset }.
 */
function readEventsSince(offset: number): Promise<{ events: MetaEvent[]; newOffset: number }> {
  return new Promise((resolve, reject) => {
    stat(EVENT_LOG_PATH, (statErr, stats) => {
      if (statErr) {
        // File doesn't exist yet → no events
        if (statErr.code === 'ENOENT') {
          resolve({ events: [], newOffset: offset });
          return;
        }
        reject(statErr);
        return;
      }
      if (stats.size <= offset) {
        // No new data
        resolve({ events: [], newOffset: offset });
        return;
      }
      readFile(EVENT_LOG_PATH, (readErr, data) => {
        if (readErr) {
          reject(readErr);
          return;
        }
        const newContent = data.subarray(offset).toString('utf-8');
        const lines = newContent.split('\n').filter((l) => l.trim().length > 0);
        const events: MetaEvent[] = [];
        for (const line of lines) {
          try {
            const evt = JSON.parse(line);
            if (evt && typeof evt === 'object' && evt.type) {
              events.push(evt);
            }
          } catch {
            // Skip malformed lines
          }
        }
        resolve({ events, newOffset: data.length });
      });
    });
  });
}

// --- WebSocket server ------------------------------------------------------

const server = createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      service: 'metaengine-ws-events',
      port: PORT,
      event_log: EVENT_LOG_PATH,
      connected_clients: wss ? wss.clients.size : 0,
      truth_effect: 'NONE',
    }));
    return;
  }
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'not_found', path: req.url }));
});

const wss = new WebSocketServer({ server, path: '/' });

wss.on('connection', (ws: WebSocket, req: IncomingMessage) => {
  // Parse query string for ?since=<offset>
  const url = new URL(req.url || '/', `http://localhost:${PORT}`);
  const sinceParam = url.searchParams.get('since');
  const sinceOffset = sinceParam ? parseInt(sinceParam, 10) || 0 : 0;

  console.log(`[ws-events] client connected (since=${sinceOffset}), total clients: ${wss.clients.size}`);

  // Replay missed events to this client
  readEventsSince(sinceOffset)
    .then(({ events, newOffset }) => {
      if (events.length > 0) {
        ws.send(JSON.stringify({
          type: 'replay',
          timestamp: new Date().toISOString(),
          payload: { count: events.length, events },
          truth_effect: 'NONE',
        }));
      }
      // Send the current offset so the client knows where to resume on reconnect
      ws.send(JSON.stringify({
        type: 'offset',
        timestamp: new Date().toISOString(),
        payload: { offset: newOffset },
        truth_effect: 'NONE',
      }));
    })
    .catch((err) => {
      console.error(`[ws-events] replay failed:`, err);
    });

  // Handle messages from client (e.g., ping)
  ws.on('message', (data: Buffer) => {
    try {
      const msg = JSON.parse(data.toString());
      if (msg.type === 'ping') {
        ws.send(JSON.stringify({
          type: 'pong',
          timestamp: new Date().toISOString(),
          payload: { clients: wss.clients.size },
          truth_effect: 'NONE',
        }));
      }
    } catch {
      // Ignore malformed messages
    }
  });

  ws.on('close', () => {
    console.log(`[ws-events] client disconnected, total clients: ${wss.clients.size}`);
  });
});

// --- Event log watcher (pushes new events to all clients) ------------------

async function pollAndPush(): Promise<void> {
  try {
    const { events, newOffset } = await readEventsSince(lastReadOffset);
    if (events.length === 0) return;
    lastReadOffset = newOffset;

    // Broadcast each event to all connected clients
    for (const evt of events) {
      const msg = JSON.stringify(evt);
      let sent = 0;
      for (const client of wss.clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send(msg);
          sent++;
        }
      }
      if (sent > 0) {
        console.log(`[ws-events] pushed event type="${evt.type}" to ${sent} client(s)`);
      }
    }
  } catch (err) {
    // Non-fatal: the event log might not exist yet
  }
}

// Poll every 500ms (cheap; reads only new bytes since last offset)
setInterval(pollAndPush, 500);

// Also watch the file for immediate updates (responsive + fallback to polling)
try {
  watchFile(EVENT_LOG_PATH, { interval: 500 }, () => {
    pollAndPush();
  });
} catch (err) {
  console.warn(`[ws-events] watchFile failed (will rely on polling):`, err);
}

// --- Start server ----------------------------------------------------------

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[ws-events] server running on port ${PORT}`);
  console.log(`[ws-events] event log: ${EVENT_LOG_PATH}`);
  console.log(`[ws-events] health: http://localhost:${PORT}/health`);
  console.log(`[ws-events] connect via: ws://localhost:${PORT}/?XTransformPort=${PORT}`);
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n[ws-events] shutting down...');
  wss.clients.forEach((c) => c.close());
  server.close();
  process.exit(0);
});
process.on('SIGTERM', () => {
  console.log('[ws-events] SIGTERM received, shutting down...');
  wss.clients.forEach((c) => c.close());
  server.close();
  process.exit(0);
});
