from __future__ import annotations

ALLOWED_TELEMETRY_FIELDS = frozenset(
    {
        "provider_class",
        "task_class",
        "latency_ms",
        "compute_estimate",
        "result",
        "test_delta",
        "patch_size",
        "verifier_verdict",
        "promotion_outcome",
        "quota_state",
        "fallback",
    }
)


def build_telemetry(
    *,
    provider_class: str,
    task_class: str,
    latency_ms: int,
    compute_estimate: int | float,
    result: str,
    test_delta: int,
    patch_size: int,
    verifier_verdict: str,
    promotion_outcome: str,
    quota_state: str,
    fallback: str,
) -> dict[str, object]:
    return {
        "provider_class": str(provider_class),
        "task_class": str(task_class),
        "latency_ms": int(latency_ms),
        "compute_estimate": float(compute_estimate),
        "result": str(result),
        "test_delta": int(test_delta),
        "patch_size": int(patch_size),
        "verifier_verdict": str(verifier_verdict),
        "promotion_outcome": str(promotion_outcome),
        "quota_state": str(quota_state),
        "fallback": str(fallback),
    }
