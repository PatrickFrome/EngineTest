from __future__ import annotations

from dataclasses import replace

import pytest

from metaengine.resource_descriptor import (
    DeterminismClass,
    EvidenceBoundObservation,
    ObservationStatus,
    ResourceDescriptor,
    ResourceKind,
    ResourceSecurityClass,
)


def _model(**overrides):
    fields = dict(
        constitution_hash="a" * 64,
        resource_id="model.reasoner.v1",
        resource_kind=ResourceKind.MODEL,
        runtime_identity="runtime:model:reasoner:v1",
        capabilities=("tool-use", "reasoning", "reasoning"),
        context_characteristics=(("context_window", "large"), ("state", "stateless")),
        tool_capabilities=("search", "search"),
        input_modes=("text/plain",),
        output_modes=("application/json", "text/plain"),
        determinism_class=DeterminismClass.STOCHASTIC,
        security_class=ResourceSecurityClass.P2,
        adapter_ref="adapter:model-runtime:v1",
    )
    fields.update(overrides)
    return ResourceDescriptor.create(**fields)


def _verifier():
    return ResourceDescriptor.create(
        constitution_hash="a" * 64,
        resource_id="python.pytest.v1",
        resource_kind=ResourceKind.VERIFIER,
        runtime_identity="python:3.13:pytest",
        capabilities=("deterministic-verification",),
        context_characteristics=(("workspace", "local"),),
        tool_capabilities=(),
        input_modes=("application/json",),
        output_modes=("application/json",),
        determinism_class=DeterminismClass.DETERMINISTIC,
        security_class=ResourceSecurityClass.P3,
        adapter_ref="adapter:local-python:v1",
    )


def test_model_and_deterministic_worker_share_one_descriptor_contract():
    model = _model()
    verifier = _verifier()
    assert model.resource_kind is ResourceKind.MODEL
    assert verifier.resource_kind is ResourceKind.VERIFIER
    assert model.capabilities == ("reasoning", "tool-use")
    assert model.tool_capabilities == ("search",)
    assert model.output_modes == ("application/json", "text/plain")
    assert ResourceDescriptor.from_dict(model.as_dict()).descriptor_hash == model.descriptor_hash
    assert ResourceDescriptor.from_dict(verifier.as_dict()).descriptor_hash == verifier.descriptor_hash


def test_descriptor_hash_is_order_independent_for_unordered_fields():
    left = _model(
        capabilities=("reasoning", "tool-use"),
        context_characteristics=(("state", "stateless"), ("context_window", "large")),
        output_modes=("text/plain", "application/json"),
    )
    right = _model(
        capabilities=("tool-use", "reasoning"),
        context_characteristics=(("context_window", "large"), ("state", "stateless")),
        output_modes=("application/json", "text/plain"),
    )
    assert left.descriptor_hash == right.descriptor_hash


def test_unobserved_never_defaults_to_zero_false_or_success():
    value = EvidenceBoundObservation.unobserved()
    assert value.status is ObservationStatus.UNOBSERVED
    assert value.value is None
    assert value.unit is None
    assert value.evidence_hashes == ()
    for hidden_value in (0, 0.0, False, ""):
        with pytest.raises(ValueError, match="RESOURCE_OBSERVATION_UNOBSERVED_HAS_VALUE"):
            EvidenceBoundObservation(
                status=ObservationStatus.UNOBSERVED,
                value=hidden_value,
                unit=None,
                evidence_hashes=(),
            ).validate()


def test_observed_property_requires_content_addressed_evidence():
    observed = EvidenceBoundObservation.observed(value=12.5, unit="ms", evidence_hashes=("b" * 64,))
    assert observed.status is ObservationStatus.OBSERVED
    assert observed.value == 12.5
    with pytest.raises(ValueError, match="RESOURCE_OBSERVATION_EVIDENCE_REQUIRED"):
        EvidenceBoundObservation.observed(value=12.5, unit="ms", evidence_hashes=())
    with pytest.raises(ValueError, match="RESOURCE_OBSERVATION_EVIDENCE_HASH_INVALID"):
        EvidenceBoundObservation.observed(value=12.5, unit="ms", evidence_hashes=("not-a-hash",))


def test_descriptor_rejects_bad_constitution_and_empty_identity():
    with pytest.raises(ValueError, match="RESOURCE_CONSTITUTION_HASH_INVALID"):
        _model(constitution_hash="bad")
    with pytest.raises(ValueError, match="RESOURCE_ID_REQUIRED"):
        _model(resource_id="")
    with pytest.raises(ValueError, match="RESOURCE_ADAPTER_REF_REQUIRED"):
        _model(adapter_ref="")


def test_descriptor_tamper_fails_hash_verification():
    descriptor = _model()
    value = descriptor.as_dict()
    value["runtime_identity"] = "runtime:tampered"
    with pytest.raises(ValueError, match="RESOURCE_DESCRIPTOR_HASH_MISMATCH"):
        ResourceDescriptor.from_dict(value)


def test_cost_latency_reliability_default_to_unobserved():
    descriptor = _model()
    assert descriptor.cost.status is ObservationStatus.UNOBSERVED
    assert descriptor.latency.status is ObservationStatus.UNOBSERVED
    assert descriptor.reliability.status is ObservationStatus.UNOBSERVED
