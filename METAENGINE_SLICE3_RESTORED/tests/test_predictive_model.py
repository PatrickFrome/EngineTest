"""METAENGINE Phase 7 — Predictive Organization Model tests."""

from __future__ import annotations

import pytest

from metaengine.predictive_model import (
    OrganizationModel,
    OrganizationPrediction,
    PredictionReceipt,
    PredictionStatus,
    PREDICTIVE_MODEL_VERSION,
)


@pytest.fixture
def model_with_data():
    m = OrganizationModel.create()
    m = m.add_observation("T0", "P0", 0.8, 1.0, 0.5)
    m = m.add_observation("T1", "P0", 0.7, 1.1, 0.6)
    m = m.add_observation("T0", "P1", 0.9, 0.8, 0.4)
    return m


# ---------------------------------------------------------------------------
# OrganizationModel
# ---------------------------------------------------------------------------


def test_empty_model_predicts_defaults():
    m = OrganizationModel.create()
    p = m.predict("T0", "P0")
    assert p.predicted_quality == 0.5
    assert p.confidence == 0.0


def test_model_with_data_predicts_mean(model_with_data):
    p = m.predict("T0", "P0") if False else None  # placeholder
    m = model_with_data
    p = m.predict("T0", "P0")
    # mean of P0: (0.8 + 0.7) / 2 = 0.75
    assert p.predicted_quality == pytest.approx(0.75, abs=0.01)
    assert p.confidence > 0.0


def test_model_predicts_unknown_policy_with_global_mean(model_with_data):
    p = model_with_data.predict("T0", "P2")  # P2 has no observations
    # global mean: (0.8 + 0.7 + 0.9) / 3 = 0.8
    assert p.predicted_quality == pytest.approx(0.8, abs=0.01)
    assert p.confidence == 0.1  # low confidence


# ---------------------------------------------------------------------------
# PredictionReceipt
# ---------------------------------------------------------------------------


def test_verify_correct_prediction(model_with_data):
    p = model_with_data.predict("T0", "P0")
    # Actual is close to predicted (0.75 quality, 1.05 cost, 0.55 latency)
    r = model_with_data.verify_prediction(p, actual_quality=0.75, actual_cost=1.05, actual_latency=0.55, tolerance=0.15)
    assert r.status == PredictionStatus.CORRECT


def test_verify_incorrect_prediction(model_with_data):
    p = model_with_data.predict("T0", "P0")
    # Actual is far from predicted
    r = model_with_data.verify_prediction(p, actual_quality=0.3, actual_cost=2.0, actual_latency=1.0, tolerance=0.15)
    assert r.status == PredictionStatus.INCORRECT


# ---------------------------------------------------------------------------
# Prediction accuracy
# ---------------------------------------------------------------------------


def test_prediction_accuracy(model_with_data):
    p1 = model_with_data.predict("T0", "P0")
    r1 = model_with_data.verify_prediction(p1, 0.75, 1.05, 0.55, tolerance=0.15)
    p2 = model_with_data.predict("T0", "P0")
    r2 = model_with_data.verify_prediction(p2, 0.3, 2.0, 1.0, tolerance=0.15)
    acc = model_with_data.prediction_accuracy([r1, r2])
    assert acc == 0.5  # 1 correct out of 2


# ---------------------------------------------------------------------------
# Hash + truth_effect
# ---------------------------------------------------------------------------


def test_model_hash_deterministic(model_with_data):
    m1 = model_with_data
    m2 = OrganizationModel.create().add_observation("T0", "P0", 0.8, 1.0, 0.5).add_observation("T1", "P0", 0.7, 1.1, 0.6).add_observation("T0", "P1", 0.9, 0.8, 0.4)
    assert m1.model_hash == m2.model_hash


def test_truth_effect_none(model_with_data):
    assert model_with_data.payload()["truth_effect"] == "NONE"
    assert model_with_data.payload()["claim_ceiling"] == "PREDICTIVE_MODEL_IS_SEARCH_HEURISTIC_NOT_TRUTH"


def test_receipt_hash(model_with_data):
    p = model_with_data.predict("T0", "P0")
    r = model_with_data.verify_prediction(p, 0.75, 1.05, 0.55, tolerance=0.15)
    assert r.receipt_hash
    assert len(r.receipt_hash) == 64
