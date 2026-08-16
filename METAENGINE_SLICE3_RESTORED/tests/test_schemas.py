import json
import pathlib

import jsonschema
import pytest

import metaengine

ROOT=pathlib.Path(__file__).resolve().parents[1]
SMOKE=ROOT/'release-evidence'/'2.0'/'smoke'

def _load(p): return json.loads(pathlib.Path(p).read_text())

def test_all_schema_documents_compile():
    for p in (ROOT/'schemas').glob('*.schema.json'):
        jsonschema.validators.validator_for(_load(p)).check_schema(_load(p))


def test_architecture_source_schemas_enforce_contract():
    record_schema = _load(ROOT / "schemas" / "architecture_source_record.schema.json")
    pack_schema = _load(ROOT / "schemas" / "reference_vault_pack.schema.json")
    valid_record = {
        "registry_schema_version": "ARCHITECTURE-SOURCE-REGISTRY-1",
        "source_id": "closed-model-public",
        "publisher": "Closed Publisher",
        "system_name": "Closed Model",
        "version": "public-docs-2026-08-13",
        "source_class": "CLOSED_BEHAVIORAL_ONLY",
        "ingestion_status": "REGISTERED_ONLY",
        "official_source_locator": "https://example.invalid/docs",
        "exact_commit_or_release": "public-docs-retrieved-2026-08-13",
        "retrieved_at": "2026-08-13T12:00:00Z",
        "source_sha256": None,
        "source_sha256_scope": None,
        "license_name": "Proprietary public documentation",
        "license_expression": "LicenseRef-Proprietary-Public-Documentation",
        "license_sha256": None,
        "license_evidence_locator": "https://example.invalid/terms",
        "allowed_use": ["BEHAVIORAL_REFERENCE"],
        "forbidden_use": ["INTERNAL_ARCHITECTURE_FACT"],
        "epistemic_ceiling": "A1_MECHANISM_HYPOTHESIS",
        "architecture_claims": [
            {
                "claim_id": "public-capability",
                "kind": "PUBLISHER_CLAIM",
                "statement": "The publisher documents a public capability.",
                "evidence_locator": "https://example.invalid/docs",
            }
        ],
        "retained_reference_paths": [],
        "blob_descriptors": [],
        "mechanism_candidates": [],
        "blockers": [],
        "record_sha256": "a" * 64,
    }
    valid_pack = {
        "pack_schema_version": "ARCHITECTURE-SOURCE-PACK-1",
        "source_id": "example-model-deadbee",
        "exact_commit_or_release": "1" * 40,
        "blob_descriptors": [
            {
                "media_type": "text/plain",
                "digest_algorithm": "sha256",
                "digest": "b" * 64,
                "size": 2,
                "relative_path": "LICENSE",
                "git_blob_id": None,
            }
        ],
        "pack_root_sha256": "c" * 64,
    }

    jsonschema.validate(valid_record, record_schema)
    jsonschema.validate(valid_pack, pack_schema)

    invalid_record = dict(valid_record)
    invalid_record.pop("source_class")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_record, record_schema)

    invalid_pack = dict(valid_pack)
    invalid_pack["pack_root_sha256"] = "not-a-sha256"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_pack, pack_schema)

def test_2_0_release_evidence_validates():
    pairs=[
      ('META_RUN.json','meta_run.schema.json'),
      ('ROUTING_PLAN.json','routing_plan.schema.json'),
      ('HYBRID_MESH.json','hybrid_mesh.schema.json'),
      ('CLAIM_GRAPH.json','claim_graph.schema.json'),
      ('DISAGREEMENT_MAP.json','disagreement_map.schema.json'),
      ('ARBITRATION.json','arbitration.schema.json'),
      ('SELF_ORGANIZING_ECOLOGY.json','self_organizing_ecology.schema.json'),
      ('TRANSFORMATION_GRAPH.json','transformation_graph.schema.json'),
      ('SELF_ORGANIZING_METRICS.json','self_organizing_metrics.schema.json'),
      ('USEFUL_EFFECTS_2.0.json','useful_effects_2_0.schema.json'),
      ('ENGINE_BIOGRAPHIES_AFTER_RUN.json','engine_biographies.schema.json'),
      ('EPISTEMIC_SAFETY_2.0.json','epistemic_safety_2_0.schema.json'),
    ]
    for data_fn,schema_fn in pairs:
        jsonschema.validate(_load(SMOKE/data_fn),_load(ROOT/'schemas'/schema_fn))
    receipts=list((SMOKE/'native_receipts').glob('*.json'))
    assert receipts
    schema=_load(ROOT/'schemas/native_reentry_receipt.schema.json')
    for p in receipts: jsonschema.validate(_load(p),schema)

def test_2_1_release_smoke_validates_core_schemas():
    smoke=ROOT/'release-evidence'/'2.1'/'smoke'
    pairs=[
      ('META_RUN.json','meta_run.schema.json'),('ROUTING_PLAN.json','routing_plan.schema.json'),('SELF_ORGANIZING_ECOLOGY.json','self_organizing_ecology.schema.json'),('TRANSFORMATION_GRAPH.json','transformation_graph.schema.json'),('SELF_ORGANIZING_METRICS.json','self_organizing_metrics.schema.json'),('EPISTEMIC_SAFETY_2.0.json','epistemic_safety_2_0.schema.json')]
    for data_fn,schema_fn in pairs: jsonschema.validate(_load(smoke/data_fn),_load(ROOT/'schemas'/schema_fn))

def test_parallel_freeze_artifacts_validate():
    e=ROOT/'release-evidence'/'2.1'
    jsonschema.validate(_load(e/'PARALLEL_SMOKE_EXPERIMENT_PLAN.json'),_load(ROOT/'schemas/parallel_experiment_plan.schema.json'))
    jsonschema.validate(_load(e/'PARALLEL_SMOKE_FREEZE_BARRIER.json'),_load(ROOT/'schemas/freeze_barrier.schema.json'))

def test_2_2_frontier_smoke_validates():
    smoke=ROOT/'release-evidence'/'2.2'/'smoke'
    jsonschema.validate(_load(smoke/'META_RUN.json'),_load(ROOT/'schemas/meta_run.schema.json'))
    jsonschema.validate(_load(smoke/'SELF_ORGANIZING_ECOLOGY.json'),_load(ROOT/'schemas/self_organizing_ecology.schema.json'))
    jsonschema.validate(_load(smoke/'FRONTIER_CONTROL_PLANE.json'),_load(ROOT/'schemas/frontier_control_plane.schema.json'))

def test_2_3_outcome_gated_smoke_validates():
    assert metaengine.__version__ == '2.3.0-alpha.1'
    smoke=ROOT/'release-evidence'/'2.3'/'smoke'
    jsonschema.validate(_load(smoke/'ACTIVE_ARCHITECTURE_POLICY.json'),_load(ROOT/'schemas/architecture_policy.schema.json'))
    jsonschema.validate(_load(smoke/'DIALECTICAL_GRAPH.json'),_load(ROOT/'schemas/dialectical_graph.schema.json'))
    jsonschema.validate(_load(smoke/'DIALECTICAL_GRAPH_VERIFICATION.json'),_load(ROOT/'schemas/verifier_report.schema.json'))
    jsonschema.validate(_load(smoke/'TELEMETRY.json'),_load(ROOT/'schemas/telemetry.schema.json'))
    final_smoke=ROOT/'release-evidence'/'2.3'/'final_smoke'
    jsonschema.validate(_load(final_smoke/'ACTIVE_ARCHITECTURE_POLICY.json'),_load(ROOT/'schemas/architecture_policy.schema.json'))
    jsonschema.validate(_load(final_smoke/'DIALECTICAL_GRAPH.json'),_load(ROOT/'schemas/dialectical_graph.schema.json'))
    campaign=ROOT/'release-evidence'/'2.3'/'outcome_gated_evolution_campaign'/'EVOLUTION_CAMPAIGN.json'
    jsonschema.validate(_load(campaign),_load(ROOT/'schemas/evolution_campaign.schema.json'))
    champion=ROOT/'release-evidence'/'2.3'/'champion_smoke'
    jsonschema.validate(_load(champion/'META_RUN.json'),_load(ROOT/'schemas/meta_run.schema.json'))
    jsonschema.validate(_load(champion/'AUDITABLE_SYNTHESIS.json'),_load(ROOT/'schemas/auditable_synthesis.schema.json'))
    jsonschema.validate(_load(champion/'INPUT_SECURITY_CLASSIFICATION.json'),_load(ROOT/'schemas/input_security_classification.schema.json'))
