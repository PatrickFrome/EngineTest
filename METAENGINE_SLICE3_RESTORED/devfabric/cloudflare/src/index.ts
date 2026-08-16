export { MetaengineEdgeWorkflow } from './workflow.ts';
import { bearerAuthorized } from './auth.ts';
import { createMetaengineMcpHandler, type EdgeBindings } from './mcp.ts';

export type Env = EdgeBindings;

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === '/health') {
      return Response.json({ status: 'ok', stage: 'D', canonical_authority: false, zero_spend: env.ZERO_SPEND === 'true' });
    }
    if (url.pathname !== '/mcp') return new Response('Not found', { status: 404 });
    if (!bearerAuthorized(request, env.MCP_EDGE_TOKEN)) return new Response('Unauthorized', { status: 401 });
    return createMetaengineMcpHandler(env)(request, env, ctx);
  },
};
