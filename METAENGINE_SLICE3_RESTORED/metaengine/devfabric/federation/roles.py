from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.models import PrivacyClass

from .types import IntegrationMode, SlotId


@dataclass(frozen=True)
class HardRoleGenome:
    slot: SlotId
    role: str
    authority_boundaries: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    subsystem_ownership: tuple[str, ...]
    privacy_ceiling: PrivacyClass
    mandatory_reviewers: tuple[SlotId, ...]
    allowed_integration_modes: tuple[IntegrationMode, ...]


@dataclass(frozen=True)
class SoftRoleGenome:
    capability_weights: tuple[tuple[str, float], ...]
    preferred_workers: tuple[str, ...]
    preferred_task_classes: tuple[str, ...]
    review_pairings: tuple[SlotId, ...]
    exploration_weight: float
    concurrency_preference: int
    provider_priors: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class RoleGenome:
    version: str
    hard: HardRoleGenome
    soft: SoftRoleGenome

    @property
    def profile_hash(self) -> str:
        return canonical_digest({"version": self.version, "hard": self.hard, "soft": self.soft})

    def with_soft_update(self, changes: Mapping[str, object]) -> "RoleGenome":
        allowed = {
            "capability_weights",
            "preferred_workers",
            "preferred_task_classes",
            "review_pairings",
            "exploration_weight",
            "concurrency_preference",
            "provider_priors",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"soft update cannot modify hard or unknown fields: {sorted(unknown)}")

        values: dict[str, object] = {
            "capability_weights": self.soft.capability_weights,
            "preferred_workers": self.soft.preferred_workers,
            "preferred_task_classes": self.soft.preferred_task_classes,
            "review_pairings": self.soft.review_pairings,
            "exploration_weight": self.soft.exploration_weight,
            "concurrency_preference": self.soft.concurrency_preference,
            "provider_priors": self.soft.provider_priors,
        }

        for key, raw in changes.items():
            if key in {"capability_weights", "provider_priors"}:
                if not isinstance(raw, Mapping):
                    raise ValueError(f"{key} must be a mapping")
                current = dict(values[key])
                current.update((str(k), float(v)) for k, v in raw.items())
                values[key] = tuple(sorted(current.items()))
            elif key in {"preferred_workers", "preferred_task_classes"}:
                if isinstance(raw, (str, bytes)):
                    raise ValueError(f"{key} must be an iterable of strings")
                values[key] = tuple(str(v) for v in raw)  # type: ignore[arg-type]
            elif key == "review_pairings":
                if isinstance(raw, (str, bytes)):
                    raise ValueError("review_pairings must be an iterable of slot IDs")
                values[key] = tuple(v if isinstance(v, SlotId) else SlotId(str(v)) for v in raw)  # type: ignore[arg-type]
            elif key == "exploration_weight":
                values[key] = float(raw)  # type: ignore[arg-type]
            elif key == "concurrency_preference":
                values[key] = int(raw)  # type: ignore[arg-type]

        updated = replace(
            self.soft,
            capability_weights=tuple(values["capability_weights"]),  # type: ignore[arg-type]
            preferred_workers=tuple(values["preferred_workers"]),  # type: ignore[arg-type]
            preferred_task_classes=tuple(values["preferred_task_classes"]),  # type: ignore[arg-type]
            review_pairings=tuple(values["review_pairings"]),  # type: ignore[arg-type]
            exploration_weight=float(values["exploration_weight"]),
            concurrency_preference=int(values["concurrency_preference"]),
            provider_priors=tuple(values["provider_priors"]),  # type: ignore[arg-type]
        )
        _validate_soft(updated)
        return RoleGenome(version=self.version, hard=self.hard, soft=updated)


def _validate_weight_pairs(name: str, values: tuple[tuple[str, float], ...]) -> None:
    for key, value in values:
        if not 0.0 <= float(value) <= 1.0:
            label = "capability weight" if name == "capability_weights" else "provider prior"
            raise ValueError(f"{label} {key!r} must be within [0.0, 1.0]")


def _validate_soft(soft: SoftRoleGenome) -> None:
    _validate_weight_pairs("capability_weights", soft.capability_weights)
    _validate_weight_pairs("provider_priors", soft.provider_priors)
    if not 0.0 <= soft.exploration_weight <= 0.25:
        raise ValueError("exploration_weight must be within [0.0, 0.25]")
    if not 2 <= soft.concurrency_preference <= 6:
        raise ValueError("concurrency_preference must be within [2, 6]")


def _forbidden_runtime_keys(payload: object, prefix: str = "") -> tuple[str, ...]:
    found: list[str] = []
    forbidden = ("secret", "token", "session", "lease", "credential", "password")
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key).lower()
            path = f"{prefix}.{key}" if prefix else str(key)
            if any(fragment in key_text for fragment in forbidden):
                found.append(path)
            found.extend(_forbidden_runtime_keys(value, path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_forbidden_runtime_keys(value, f"{prefix}[{index}]"))
    return tuple(found)


def _parse_hard(payload: Mapping[str, object]) -> HardRoleGenome:
    return HardRoleGenome(
        slot=SlotId(str(payload["slot"])),
        role=str(payload["role"]),
        authority_boundaries=tuple(str(v) for v in payload.get("authority_boundaries", ())),  # type: ignore[arg-type]
        prohibited_actions=tuple(str(v) for v in payload.get("prohibited_actions", ())),  # type: ignore[arg-type]
        subsystem_ownership=tuple(str(v) for v in payload.get("subsystem_ownership", ())),  # type: ignore[arg-type]
        privacy_ceiling=PrivacyClass(str(payload["privacy_ceiling"])),
        mandatory_reviewers=tuple(SlotId(str(v)) for v in payload.get("mandatory_reviewers", ())),  # type: ignore[arg-type]
        allowed_integration_modes=tuple(
            IntegrationMode(str(v)) for v in payload.get("allowed_integration_modes", ())  # type: ignore[arg-type]
        ),
    )


def _parse_soft(payload: Mapping[str, object]) -> SoftRoleGenome:
    capability_weights = payload.get("capability_weights", {})
    provider_priors = payload.get("provider_priors", {})
    if not isinstance(capability_weights, Mapping) or not isinstance(provider_priors, Mapping):
        raise ValueError("capability_weights and provider_priors must be mappings")
    soft = SoftRoleGenome(
        capability_weights=tuple(sorted((str(k), float(v)) for k, v in capability_weights.items())),
        preferred_workers=tuple(str(v) for v in payload.get("preferred_workers", ())),  # type: ignore[arg-type]
        preferred_task_classes=tuple(str(v) for v in payload.get("preferred_task_classes", ())),  # type: ignore[arg-type]
        review_pairings=tuple(SlotId(str(v)) for v in payload.get("review_pairings", ())),  # type: ignore[arg-type]
        exploration_weight=float(payload.get("exploration_weight", 0.0)),
        concurrency_preference=int(payload.get("concurrency_preference", 2)),
        provider_priors=tuple(sorted((str(k), float(v)) for k, v in provider_priors.items())),
    )
    _validate_soft(soft)
    return soft


def load_role_genome(root: Path, slot: SlotId) -> RoleGenome:
    path = Path(root) / "chat_federation" / "ROLE_GENOMES" / f"{slot.value}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("role genome must be a JSON object")
    forbidden = _forbidden_runtime_keys(payload)
    if forbidden:
        raise ValueError(f"role genome contains forbidden runtime/secret fields: {forbidden}")
    hard_raw = payload.get("hard")
    soft_raw = payload.get("soft")
    if not isinstance(hard_raw, Mapping) or not isinstance(soft_raw, Mapping):
        raise ValueError("role genome must contain object-valued hard and soft sections")
    hard = _parse_hard(hard_raw)
    if hard.slot is not slot:
        raise ValueError(f"filename slot {slot.value} does not match payload slot {hard.slot.value}")
    prohibited = set(hard.prohibited_actions)
    if not {"CANONICAL_BYPASS", "SECRET_RETRIEVAL"}.issubset(prohibited):
        raise ValueError("every role must prohibit CANONICAL_BYPASS and SECRET_RETRIEVAL")
    soft = _parse_soft(soft_raw)
    version = str(payload.get("version", ""))
    if not version:
        raise ValueError("role genome version is required")
    return RoleGenome(version=version, hard=hard, soft=soft)
