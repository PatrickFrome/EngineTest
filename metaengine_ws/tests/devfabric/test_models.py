from dataclasses import FrozenInstanceError

import pytest

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope


def test_task_envelope_is_immutable_and_hash_stable():
    task = TaskEnvelope.create(
        source_checkpoint_id="cp001",
        source_tree_hash="a" * 64,
        objective="Add a deterministic feature",
        acceptance_tests=("pytest -q",),
        allowed_paths=("metaengine/", "tests/"),
        forbidden_paths=("lineages/",),
        capabilities_required=("CODE_GENERATOR",),
        risk_class=RiskClass.NORMAL,
        privacy_class=PrivacyClass.P1,
    )
    assert task.zero_spend is True
    assert len(task.task_hash) == 64
    assert task.task_id == "task-" + task.task_hash[:20]
    with pytest.raises(FrozenInstanceError):
        task.objective = "mutated"


def test_canonical_digest_ignores_mapping_insertion_order():
    left = {"z": 3, "a": 1, "m": {"q": 2, "b": 4}}
    right = {"m": {"b": 4, "q": 2}, "a": 1, "z": 3}
    assert canonical_digest(left) == canonical_digest(right)


def test_candidate_receipt_metadata_is_deeply_immutable():
    from metaengine.devfabric.models import CandidateReceipt

    candidate = CandidateReceipt.create(
        task_id="task-1",
        provider_id="local",
        base_tree_hash="a" * 40,
        patch_hash="b" * 64,
        changed_paths=("metaengine/x.py",),
        metadata={"model": "local"},
    )
    assert candidate.metadata == (("model", "local"),)
