import type { FederationApiClient } from './federation_client.ts';
import {
  projectFederationPayload,
  type FederationPrivacyClass,
} from './federation_contract.ts';

type FederationClientLike = Pick<
  FederationApiClient,
  | 'federation_status'
  | 'slot_catalog'
  | 'session_status'
  | 'epoch_status'
  | 'task_get'
  | 'task_dependencies'
  | 'candidate_status'
  | 'conflict_status'
  | 'sync_snapshot_get'
  | 'federation_register'
  | 'session_release'
  | 'task_claim'
  | 'task_progress'
  | 'candidate_submit'
  | 'review_submit'
  | 'conflict_submit'
  | 'integration_propose'
  | 'sync_snapshot_publish'
>;

type PrivacyInput = { privacyClass: FederationPrivacyClass };
type JsonObject = Record<string, unknown>;

function projected<T>(privacyClass: FederationPrivacyClass, value: T): T {
  return projectFederationPayload(privacyClass, value);
}

export function createFederationToolHandlers(client: FederationClientLike) {
  return {
    federation_status: (input: { epoch_id: string }) => client.federation_status(input),
    slot_catalog: (_input: JsonObject = {}) => client.slot_catalog({}),
    session_status: (input: { session_id: string }) => client.session_status(input),
    epoch_status: (input: { epoch_id: string }) => client.epoch_status(input),

    task_get: async (input: PrivacyInput & { session_id: string; task_hash: string }) => {
      projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.task_get({ session_id: input.session_id, task_hash: input.task_hash }));
    },

    task_dependencies: async (input: PrivacyInput & { session_id: string; task_hash: string }) => {
      projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.task_dependencies({ session_id: input.session_id, task_hash: input.task_hash }));
    },

    candidate_status: async (input: PrivacyInput & {
      session_id: string;
      candidate_hash: string;
      blind_group_open?: boolean;
      caller_candidate_hash?: string | null;
    }) => {
      projected(input.privacyClass, input);
      if (input.blind_group_open && input.caller_candidate_hash !== input.candidate_hash) {
        return { blindGroupOpen: true, visible: false };
      }
      return projected(input.privacyClass, await client.candidate_status({
        session_id: input.session_id,
        candidate_hash: input.candidate_hash,
      }));
    },

    conflict_status: async (input: PrivacyInput & { session_id: string; epoch_id: string }) => {
      projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.conflict_status({ session_id: input.session_id, epoch_id: input.epoch_id }));
    },

    sync_snapshot_get: async (input: PrivacyInput & { session_id: string; epoch_id: string }) => {
      projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.sync_snapshot_get({ session_id: input.session_id, epoch_id: input.epoch_id }));
    },

    federation_register: (input: {
      epoch_id: string;
      requested_slot: string;
      session_id: string;
      capsule_sha256: string;
      protocol_version: string;
      role_profile_hash: string;
    }) => client.federation_register(input),

    session_release: (input: { session_id: string; expected_generation: number }) => client.session_release(input),
    task_claim: (input: { session_id: string; task_hash: string; expected_generation: number }) => client.task_claim(input),

    task_progress: async (input: PrivacyInput & {
      session_id: string;
      task_hash: string;
      expected_generation: number;
      progress: JsonObject;
    }) => {
      const safe = projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.task_progress({
        session_id: safe.session_id,
        task_hash: safe.task_hash,
        expected_generation: safe.expected_generation,
        progress: safe.progress,
      }));
    },

    candidate_submit: async (input: PrivacyInput & {
      session_id: string;
      expected_generation: number;
      candidate_hash: string;
      task_hash: string;
      receipt: JsonObject;
    }) => {
      const safe = projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.candidate_submit({
        session_id: safe.session_id,
        expected_generation: safe.expected_generation,
        candidate_hash: safe.candidate_hash,
        task_hash: safe.task_hash,
        receipt: safe.receipt,
      }));
    },

    review_submit: async (input: PrivacyInput & {
      session_id: string;
      expected_generation: number;
      review_hash: string;
      candidate_hash: string;
      receipt: JsonObject;
    }) => {
      const safe = projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.review_submit({
        session_id: safe.session_id,
        expected_generation: safe.expected_generation,
        review_hash: safe.review_hash,
        candidate_hash: safe.candidate_hash,
        receipt: safe.receipt,
      }));
    },

    conflict_submit: async (input: PrivacyInput & {
      session_id: string;
      expected_generation: number;
      conflict_hash: string;
      epoch_id: string;
      payload: JsonObject;
    }) => {
      const safe = projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.conflict_submit({
        session_id: safe.session_id,
        expected_generation: safe.expected_generation,
        conflict_hash: safe.conflict_hash,
        epoch_id: safe.epoch_id,
        payload: safe.payload,
      }));
    },

    integration_propose: async (input: PrivacyInput & {
      session_id: string;
      expected_generation: number;
      decision_hash: string;
      epoch_id: string;
      candidate_hash: string | null;
      decision: string;
      reason: string;
    }) => {
      projected(input.privacyClass, input);
      const reason = input.privacyClass === 'P2' ? 'P2_METADATA_ONLY' : input.reason;
      return projected(input.privacyClass, await client.integration_propose({
        session_id: input.session_id,
        expected_generation: input.expected_generation,
        decision_hash: input.decision_hash,
        epoch_id: input.epoch_id,
        candidate_hash: input.candidate_hash,
        decision: input.decision,
        reason,
      }));
    },

    sync_snapshot_publish: async (input: PrivacyInput & {
      session_id: string;
      expected_generation: number;
      snapshot_hash: string;
      epoch_id: string;
      snapshot: JsonObject;
      checkpoint_proposal_hash: string | null;
    }) => {
      const safe = projected(input.privacyClass, input);
      return projected(input.privacyClass, await client.sync_snapshot_publish({
        session_id: safe.session_id,
        expected_generation: safe.expected_generation,
        snapshot_hash: safe.snapshot_hash,
        epoch_id: safe.epoch_id,
        snapshot: safe.snapshot,
        checkpoint_proposal_hash: safe.checkpoint_proposal_hash,
      }));
    },
  } as const;
}
