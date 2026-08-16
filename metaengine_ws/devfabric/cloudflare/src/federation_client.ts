export type FederationClientConfig = {
  supabaseUrl: string;
  serviceRoleKey: string;
  fetchImpl?: typeof fetch;
};

type JsonObject = Record<string, unknown>;

const RPC = Object.freeze({
  federation_status: 'metaengine_federation_status_v1',
  slot_catalog: 'metaengine_federation_slot_catalog_v1',
  session_status: 'metaengine_federation_session_status_v1',
  epoch_status: 'metaengine_federation_epoch_status_v1',
  task_get: 'metaengine_federation_task_get_v1',
  task_dependencies: 'metaengine_federation_task_dependencies_v1',
  candidate_status: 'metaengine_federation_candidate_status_v1',
  conflict_status: 'metaengine_federation_conflict_status_v1',
  sync_snapshot_get: 'metaengine_federation_sync_snapshot_get_v1',
  federation_register: 'metaengine_federation_register_v1',
  session_release: 'metaengine_federation_release_v1',
  task_claim: 'metaengine_federation_claim_task_v1',
  task_progress: 'metaengine_federation_progress_v1',
  candidate_submit: 'metaengine_federation_submit_candidate_v1',
  review_submit: 'metaengine_federation_submit_review_v1',
  conflict_submit: 'metaengine_federation_submit_conflict_v1',
  integration_propose: 'metaengine_federation_propose_integration_v1',
  sync_snapshot_publish: 'metaengine_federation_publish_snapshot_v1',
} as const);

export class FederationApiClient {
  readonly #baseUrl: string;
  readonly #serviceRoleKey: string;
  readonly #fetch: typeof fetch;

  constructor(config: FederationClientConfig) {
    const url = new URL(config.supabaseUrl);
    if (url.protocol !== 'https:') throw new Error('FEDERATION_SUPABASE_URL_INVALID');
    if (!config.serviceRoleKey) throw new Error('FEDERATION_SERVICE_ROLE_KEY_MISSING');
    this.#baseUrl = url.toString().replace(/\/$/, '');
    this.#serviceRoleKey = config.serviceRoleKey;
    this.#fetch = config.fetchImpl ?? fetch;
  }

  async #post(rpc: keyof typeof RPC, payload: JsonObject = {}): Promise<unknown> {
    const response = await this.#fetch(`${this.#baseUrl}/rest/v1/rpc/${RPC[rpc]}`, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${this.#serviceRoleKey}`,
        apikey: this.#serviceRoleKey,
        'content-type': 'application/json',
        accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`FEDERATION_RPC_ERROR:${response.status}`);
    try {
      return await response.json();
    } catch {
      throw new Error('FEDERATION_RPC_RESPONSE_INVALID');
    }
  }

  federation_status(input: { epoch_id: string }) { return this.#post('federation_status', { p_epoch_id: input.epoch_id }); }
  slot_catalog(_input: JsonObject = {}) { return this.#post('slot_catalog'); }
  session_status(input: { session_id: string }) { return this.#post('session_status', { p_session_id: input.session_id }); }
  epoch_status(input: { epoch_id: string }) { return this.#post('epoch_status', { p_epoch_id: input.epoch_id }); }
  task_get(input: { session_id: string; task_hash: string }) { return this.#post('task_get', { p_session_id: input.session_id, p_task_hash: input.task_hash }); }
  task_dependencies(input: { session_id: string; task_hash: string }) { return this.#post('task_dependencies', { p_session_id: input.session_id, p_task_hash: input.task_hash }); }
  candidate_status(input: { session_id: string; candidate_hash: string }) { return this.#post('candidate_status', { p_session_id: input.session_id, p_candidate_hash: input.candidate_hash }); }
  conflict_status(input: { session_id: string; epoch_id: string }) { return this.#post('conflict_status', { p_session_id: input.session_id, p_epoch_id: input.epoch_id }); }
  sync_snapshot_get(input: { session_id: string; epoch_id: string }) { return this.#post('sync_snapshot_get', { p_session_id: input.session_id, p_epoch_id: input.epoch_id }); }
  federation_register(input: { epoch_id: string; requested_slot: string; session_id: string; capsule_sha256: string; protocol_version: string; role_profile_hash: string }) {
    return this.#post('federation_register', {
      p_epoch_id: input.epoch_id,
      p_requested_slot: input.requested_slot,
      p_session_id: input.session_id,
      p_capsule_sha256: input.capsule_sha256,
      p_protocol_version: input.protocol_version,
      p_role_profile_hash: input.role_profile_hash,
    });
  }
  session_release(input: { session_id: string; expected_generation: number }) { return this.#post('session_release', { p_session_id: input.session_id, p_expected_generation: input.expected_generation }); }
  task_claim(input: { session_id: string; task_hash: string; expected_generation: number }) { return this.#post('task_claim', { p_session_id: input.session_id, p_task_hash: input.task_hash, p_expected_generation: input.expected_generation }); }
  task_progress(input: { session_id: string; task_hash: string; expected_generation: number; progress: JsonObject }) { return this.#post('task_progress', { p_session_id: input.session_id, p_task_hash: input.task_hash, p_expected_generation: input.expected_generation, p_progress: input.progress }); }
  candidate_submit(input: { session_id: string; expected_generation: number; candidate_hash: string; task_hash: string; receipt: JsonObject }) { return this.#post('candidate_submit', { p_session_id: input.session_id, p_expected_generation: input.expected_generation, p_candidate_hash: input.candidate_hash, p_task_hash: input.task_hash, p_receipt: input.receipt }); }
  review_submit(input: { session_id: string; expected_generation: number; review_hash: string; candidate_hash: string; receipt: JsonObject }) { return this.#post('review_submit', { p_session_id: input.session_id, p_expected_generation: input.expected_generation, p_review_hash: input.review_hash, p_candidate_hash: input.candidate_hash, p_receipt: input.receipt }); }
  conflict_submit(input: { session_id: string; expected_generation: number; conflict_hash: string; epoch_id: string; payload: JsonObject }) { return this.#post('conflict_submit', { p_session_id: input.session_id, p_expected_generation: input.expected_generation, p_conflict_hash: input.conflict_hash, p_epoch_id: input.epoch_id, p_payload: input.payload }); }
  integration_propose(input: { session_id: string; expected_generation: number; decision_hash: string; epoch_id: string; candidate_hash: string | null; decision: string; reason: string }) { return this.#post('integration_propose', { p_session_id: input.session_id, p_expected_generation: input.expected_generation, p_decision_hash: input.decision_hash, p_epoch_id: input.epoch_id, p_candidate_hash: input.candidate_hash, p_decision: input.decision, p_reason: input.reason }); }
  sync_snapshot_publish(input: { session_id: string; expected_generation: number; snapshot_hash: string; epoch_id: string; snapshot: JsonObject; checkpoint_proposal_hash: string | null }) { return this.#post('sync_snapshot_publish', { p_session_id: input.session_id, p_expected_generation: input.expected_generation, p_snapshot_hash: input.snapshot_hash, p_epoch_id: input.epoch_id, p_snapshot: input.snapshot, p_checkpoint_proposal_hash: input.checkpoint_proposal_hash }); }
}
