from __future__ import annotations

import re

import pytest

from metaengine.devfabric.federation.adaptation import (
    FinalizedEpochMetrics,
    build_adaptation_receipt,
)
from metaengine.devfabric.federation.telemetry import (
    TELEMETRY_SCHEMA_HASH,
    TELEMETRY_SCHEMA_VERSION,
    federation_adaptation_event,
)


def _metrics(index: int) -> FinalizedEpochMetrics:
    return FinalizedEpochMetrics(
        finalization_hash=f"{index:x}" * 64,
        recovery_cut_hash=f"{index + 8:x}" * 64,
        epoch_id=f"epoch-{index}",
        federation_policy_hash="3" * 64,
        producer_concurrency=4,
        task_count=2,
        candidate_count=2,
        eligible_candidate_count=2,
        rejected_candidate_count=0,
        stale_candidate_count=0,
        review_count=1,
        review_pass_count=1,
        review_fail_count=0,
        review_inconclusive_count=0,
        conflict_count=0,
        unresolved_conflict_count=0,
        include_count=2,
        exclude_count=0,
        stale_decision_count=0,
        integrated_candidate_count=2,
        participants=(),
        role_observations=(),
    )


def _receipt():
    window = tuple(_metrics(i) for i in (1, 2, 3))
    return build_adaptation_receipt(
        metrics_window=window,
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash=TELEMETRY_SCHEMA_HASH,
    )


def test_adaptation_telemetry_is_closed_schema_and_privacy_minimized() -> None:
    event = federation_adaptation_event(_receipt())
    assert set(event) == {
        "schema_version",
        "schema_hash",
        "protocol_version",
        "adaptation_receipt_hash",
        "adaptation_input_hash",
        "status",
        "evidence_epoch_count",
        "concurrency_current",
        "concurrency_proposed",
        "conflict_numerator",
        "conflict_denominator",
        "concurrency_reason",
        "role_proposal_count",
    }
    assert event["schema_version"] == "D6.ADAPTATION.TELEMETRY.1"
    serialized = repr(event).lower()
    for forbidden in ("objective", "prompt", "conversation", "patch", "secret", "token", "credential", "password", "p3"):
        assert forbidden not in serialized


def test_telemetry_schema_hash_is_stable_lowercase_sha256() -> None:
    assert TELEMETRY_SCHEMA_VERSION == "D6.ADAPTATION.TELEMETRY.1"
    assert re.fullmatch(r"[0-9a-f]{64}", TELEMETRY_SCHEMA_HASH)


def test_telemetry_rejects_arbitrary_mapping_escape_hatch() -> None:
    with pytest.raises(ValueError, match="FEDERATION_ADAPTATION_PRIVATE_FIELD_FORBIDDEN"):
        federation_adaptation_event({"prompt": "secret", "privacy_class": "P3"})  # type: ignore[arg-type]
