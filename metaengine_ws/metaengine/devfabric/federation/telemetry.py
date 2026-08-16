from __future__ import annotations

from metaengine.devfabric.codec import canonical_digest

from .adaptation import AdaptationReceipt

TELEMETRY_SCHEMA_VERSION = "D6.ADAPTATION.TELEMETRY.1"
_TELEMETRY_FIELDS = (
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
)
TELEMETRY_SCHEMA_HASH = canonical_digest(
    {"schema_version": TELEMETRY_SCHEMA_VERSION, "fields": _TELEMETRY_FIELDS}
)


def federation_adaptation_event(receipt: AdaptationReceipt) -> dict[str, object]:
    if not isinstance(receipt, AdaptationReceipt):
        raise ValueError("FEDERATION_ADAPTATION_PRIVATE_FIELD_FORBIDDEN")
    decision = receipt.concurrency_decision
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "schema_hash": TELEMETRY_SCHEMA_HASH,
        "protocol_version": receipt.protocol_version,
        "adaptation_receipt_hash": receipt.adaptation_receipt_hash,
        "adaptation_input_hash": receipt.adaptation_input_hash,
        "status": receipt.status,
        "evidence_epoch_count": len(receipt.evidence_finalization_hashes),
        "concurrency_current": decision.current,
        "concurrency_proposed": decision.proposed,
        "conflict_numerator": decision.conflict_numerator,
        "conflict_denominator": decision.conflict_denominator,
        "concurrency_reason": decision.reason,
        "role_proposal_count": len(receipt.role_proposals),
    }
