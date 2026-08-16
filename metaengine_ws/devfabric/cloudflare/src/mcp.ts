import { McpServer } from '@modelcontextprotocol/server';
import { createMcpHandler } from 'agents/mcp/server';
import { z } from 'zod';
import { budgetDecision } from './budget.ts';
import {
  createTaskRef,
  createVerificationRequest,
  listCandidateRefs,
  readQuotaSnapshot,
  readTaskStatus,
  type D1DatabaseLike,
} from './edge_state.ts';
import { canonicalSha256 } from './hash.ts';
import { sanitizeTaskReference, proposalReference } from './mcp_contract.ts';
import { FederationApiClient } from './federation_client.ts';
import { createFederationToolHandlers } from './federation_tools.ts';

interface WorkflowInstanceLike {
  id: string;
  status(): Promise<unknown>;
}

interface WorkflowBindingLike {
  create(options: { id: string; params: Record<string, unknown> }): Promise<WorkflowInstanceLike>;
  get(id: string): Promise<WorkflowInstanceLike>;
}

export type EdgeBindings = {
  ZERO_SPEND: string;
  DEPLOYMENT_GUARD: string;
  MCP_EDGE_TOKEN: string;
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE_KEY: string;
  ROUTER_DB: D1DatabaseLike;
  EDGE_WORKFLOW: WorkflowBindingLike;
};

async function responseEnvelope(kind: string, payload: unknown) {
  const body = { kind, payload };
  return {
    ...body,
    receiptHash: await canonicalSha256(body),
    canonicalAuthority: false,
  };
}

function asContent(value: unknown) {
  return { content: [{ type: 'text' as const, text: JSON.stringify(value) }] };
}

export function createMetaengineServer(env: EdgeBindings) {
  const server = new McpServer({ name: 'metaengine-devfabric-edge', version: '0.1.0-stage-d' });

  const federationClient = new FederationApiClient({
    supabaseUrl: env.SUPABASE_URL,
    serviceRoleKey: env.SUPABASE_SERVICE_ROLE_KEY,
  });
  const federation = createFederationToolHandlers(federationClient);
  const sha256 = z.string().regex(/^[0-9a-f]{64}$/i);
  const privacyClass = z.enum(['P0','P1','P2','P3']);
  const generation = z.number().int().nonnegative();
  const jsonObject = z.record(z.string(), z.unknown());
  const sessionId = z.string().min(1).max(160);
  const epochId = z.string().min(1).max(160);


  server.registerTool('project_read', { description: 'Read safe project binding metadata', inputSchema: {} }, async () => asContent(await responseEnvelope('project_read', {
    stage: 'D',
    zeroSpend: env.ZERO_SPEND === 'true',
    canonicalAuthority: false,
    sourceArtifactSha256: '8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0',
  })));

  server.registerTool('task_ref_create', {
    description: 'Create an external-safe task reference. P3 is rejected; no source body is accepted.',
    inputSchema: { taskHash: z.string().length(64), privacyClass: z.enum(['P0','P1','P2','P3']), kind: z.string().min(1).max(48) },
  }, async (input) => {
    const ref = sanitizeTaskReference(input);
    return asContent(await responseEnvelope('task_ref_create', await createTaskRef(env.ROUTER_DB, ref, Date.now())));
  });

  server.registerTool('task_status', {
    description: 'Read task status by content hash.',
    inputSchema: { taskHash: z.string().length(64) },
  }, async ({ taskHash }) => asContent(await responseEnvelope('task_status', {
    taskHash,
    row: await readTaskStatus(env.ROUTER_DB, taskHash),
  })));

  server.registerTool('candidate_list', {
    description: 'List content-addressed candidate references only.',
    inputSchema: { taskHash: z.string().length(64) },
  }, async ({ taskHash }) => asContent(await responseEnvelope('candidate_list', {
    taskHash,
    candidates: await listCandidateRefs(env.ROUTER_DB, taskHash),
  })));

  server.registerTool('verification_request', {
    description: 'Create a verification request reference and dispatch a free-quota Workflow only when quota is known.',
    inputSchema: {
      taskHash: z.string().length(64),
      candidateHash: z.string().length(64),
      privacyClass: z.enum(['P0','P1','P2','P3']),
    },
  }, async ({ taskHash, candidateHash, privacyClass }) => {
    sanitizeTaskReference({ taskHash, privacyClass, kind: 'verification' });
    const quota = await readQuotaSnapshot(env.ROUTER_DB);
    const budget = budgetDecision(quota, { workflowSteps: 3 });
    const request = await createVerificationRequest(env.ROUTER_DB, taskHash, candidateHash, Date.now());
    let workflow: unknown = { status: budget.reason };
    if (budget.eligible) {
      try {
        const instance = await env.EDGE_WORKFLOW.create({
          id: request.requestHash,
          params: { taskHash, candidateHash, privacyClass, workflowStepsRemaining: quota.workflowStepsRemaining },
        });
        workflow = { status: 'DISPATCHED', id: instance.id };
      } catch (createError) {
        try {
          const existing = await env.EDGE_WORKFLOW.get(request.requestHash);
          workflow = { status: 'ALREADY_DISPATCHED', id: existing.id };
        } catch {
          throw createError;
        }
      }
    }
    return asContent(await responseEnvelope('verification_request', { request, budget, workflow }));
  });

  server.registerTool('quota_health', { description: 'Return fail-closed free-tier quota snapshot.', inputSchema: {} }, async () => {
    const quota = await readQuotaSnapshot(env.ROUTER_DB);
    return asContent(await responseEnvelope('quota_health', {
      quota,
      unknownQuotaBehavior: 'DENY',
      paidFallback: false,
    }));
  });

  server.registerTool('checkpoint_proposal_ref', {
    description: 'Return a non-promoting checkpoint proposal reference.',
    inputSchema: { candidateHash: z.string().length(64), verifierHash: z.string().length(64) },
  }, async ({ candidateHash, verifierHash }) => asContent(await responseEnvelope('checkpoint_proposal_ref', proposalReference(candidateHash, verifierHash))));

  server.registerTool('federation_status', {
    description: 'Read a bounded federation epoch summary.',
    inputSchema: { epoch_id: epochId },
  }, async (input) => asContent(await responseEnvelope('federation_status', await federation.federation_status(input))));

  server.registerTool('slot_catalog', {
    description: 'Read the fixed C0-C7 federation slot catalogue.',
    inputSchema: {},
  }, async () => asContent(await responseEnvelope('slot_catalog', await federation.slot_catalog({}))));

  server.registerTool('session_status', {
    description: 'Read one federation session status.',
    inputSchema: { session_id: sessionId },
  }, async (input) => asContent(await responseEnvelope('session_status', await federation.session_status(input))));

  server.registerTool('epoch_status', {
    description: 'Read one federation epoch record.',
    inputSchema: { epoch_id: epochId },
  }, async (input) => asContent(await responseEnvelope('epoch_status', await federation.epoch_status(input))));

  server.registerTool('task_get', {
    description: 'Read one role-scoped task. P3 is denied and P2 is metadata-only.',
    inputSchema: { privacyClass, session_id: sessionId, task_hash: sha256 },
  }, async (input) => asContent(await responseEnvelope('task_get', await federation.task_get(input))));

  server.registerTool('task_dependencies', {
    description: 'Read task dependency references only.',
    inputSchema: { privacyClass, session_id: sessionId, task_hash: sha256 },
  }, async (input) => asContent(await responseEnvelope('task_dependencies', await federation.task_dependencies(input))));

  server.registerTool('candidate_status', {
    description: 'Read candidate status with blind-group visibility enforcement.',
    inputSchema: {
      privacyClass,
      session_id: sessionId,
      candidate_hash: sha256,
      blind_group_open: z.boolean().optional(),
      caller_candidate_hash: sha256.optional(),
    },
  }, async (input) => asContent(await responseEnvelope('candidate_status', await federation.candidate_status(input))));

  server.registerTool('conflict_status', {
    description: 'Read conflict records for the caller epoch.',
    inputSchema: { privacyClass, session_id: sessionId, epoch_id: epochId },
  }, async (input) => asContent(await responseEnvelope('conflict_status', await federation.conflict_status(input))));

  server.registerTool('sync_snapshot_get', {
    description: 'Read the latest synchronization snapshot for the caller epoch.',
    inputSchema: { privacyClass, session_id: sessionId, epoch_id: epochId },
  }, async (input) => asContent(await responseEnvelope('sync_snapshot_get', await federation.sync_snapshot_get(input))));

  server.registerTool('federation_register', {
    description: 'Register one chat session against a fixed role profile and fenced slot.',
    inputSchema: {
      epoch_id: epochId,
      requested_slot: z.enum(['AUTO','C0','C1','C2','C3','C4','C5','C6','C7']),
      session_id: sessionId,
      capsule_sha256: sha256,
      protocol_version: z.string().min(1).max(32),
      role_profile_hash: sha256,
    },
  }, async (input) => asContent(await responseEnvelope('federation_register', await federation.federation_register(input))));

  server.registerTool('session_release', {
    description: 'Release the caller session using the expected fencing generation.',
    inputSchema: { session_id: sessionId, expected_generation: generation },
  }, async (input) => asContent(await responseEnvelope('session_release', await federation.session_release(input))));

  server.registerTool('task_claim', {
    description: 'Claim a task only with the active session fencing generation.',
    inputSchema: { session_id: sessionId, task_hash: sha256, expected_generation: generation },
  }, async (input) => asContent(await responseEnvelope('task_claim', await federation.task_claim(input))));

  server.registerTool('task_progress', {
    description: 'Submit privacy-projected task progress under a fenced session.',
    inputSchema: { privacyClass, session_id: sessionId, task_hash: sha256, expected_generation: generation, progress: jsonObject },
  }, async (input) => asContent(await responseEnvelope('task_progress', await federation.task_progress(input))));

  server.registerTool('candidate_submit', {
    description: 'Submit a content-addressed candidate receipt. Patch/source bodies are not accepted for P2/P3.',
    inputSchema: { privacyClass, session_id: sessionId, expected_generation: generation, candidate_hash: sha256, task_hash: sha256, receipt: jsonObject },
  }, async (input) => asContent(await responseEnvelope('candidate_submit', await federation.candidate_submit(input))));

  server.registerTool('review_submit', {
    description: 'Submit an independent review receipt under the reviewer fence.',
    inputSchema: { privacyClass, session_id: sessionId, expected_generation: generation, review_hash: sha256, candidate_hash: sha256, receipt: jsonObject },
  }, async (input) => asContent(await responseEnvelope('review_submit', await federation.review_submit(input))));

  server.registerTool('conflict_submit', {
    description: 'Submit a content-addressed conflict event without source bodies.',
    inputSchema: { privacyClass, session_id: sessionId, expected_generation: generation, conflict_hash: sha256, epoch_id: epochId, payload: jsonObject },
  }, async (input) => asContent(await responseEnvelope('conflict_submit', await federation.conflict_submit(input))));

  server.registerTool('integration_propose', {
    description: 'C0 proposes an integration decision; this tool never promotes a checkpoint.',
    inputSchema: {
      privacyClass,
      session_id: sessionId,
      expected_generation: generation,
      decision_hash: sha256,
      epoch_id: epochId,
      candidate_hash: z.union([sha256, z.null()]),
      decision: z.enum(['INCLUDE','EXCLUDE','CONFLICT_TASK','STALE']),
      reason: z.string().min(1).max(512),
    },
  }, async (input) => asContent(await responseEnvelope('integration_propose', await federation.integration_propose(input))));

  server.registerTool('sync_snapshot_publish', {
    description: 'C0 publishes a content-addressed synchronization snapshot; no canonical write occurs.',
    inputSchema: {
      privacyClass,
      session_id: sessionId,
      expected_generation: generation,
      snapshot_hash: sha256,
      epoch_id: epochId,
      snapshot: jsonObject,
      checkpoint_proposal_hash: z.union([sha256, z.null()]),
    },
  }, async (input) => asContent(await responseEnvelope('sync_snapshot_publish', await federation.sync_snapshot_publish(input))));

  return server;
}

export function createMetaengineMcpHandler(env: EdgeBindings) {
  return createMcpHandler(() => createMetaengineServer(env), {
    route: '/mcp',
    legacy: 'reject',
    responseMode: 'json',
  });
}
