from __future__ import annotations

from .models import PrivacyClass, TaskEnvelope
from .providers.base import ProviderDescriptor, QuotaSnapshot


def privacy_allowed(task: TaskEnvelope, descriptor: ProviderDescriptor) -> tuple[bool, str | None]:
    if task.privacy_class is PrivacyClass.P3 and descriptor.external:
        return False, "PRIVACY_CLASS_BLOCKED"
    return True, None


def zero_spend_allowed(
    task: TaskEnvelope,
    descriptor: ProviderDescriptor,
    quota: QuotaSnapshot,
) -> tuple[bool, str | None]:
    if not task.zero_spend:
        return True, None
    if descriptor.billing_mode == "LOCAL_FREE":
        return True, None
    if quota.paid_fallback_enabled:
        return False, "ZERO_SPEND_PAID_FALLBACK_ENABLED"
    if descriptor.billing_mode == "PAID_CAPABLE" and not quota.known:
        return False, "ZERO_SPEND_QUOTA_UNKNOWN"
    if quota.known and quota.free_remaining is not None and quota.free_remaining <= 0:
        return False, "ZERO_SPEND_QUOTA_EXHAUSTED"
    if not quota.known and descriptor.billing_mode != "FREE_ONLY":
        return False, "ZERO_SPEND_QUOTA_UNKNOWN"
    return True, None
