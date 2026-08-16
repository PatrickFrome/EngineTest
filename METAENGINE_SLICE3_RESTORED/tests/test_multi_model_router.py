"""Tests for Phase 69 — Multi-Model Bridge Router."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.multi_model_router import (
    MultiModelRouter,
    ModelBackend,
    RoutedResult,
    BackendHealth,
    MULTI_MODEL_VERSION,
    create_default_router,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def router():
    r = MultiModelRouter()
    r.add_backend("glm-1", "metaengine-glm-1")
    r.add_backend("glm-thinking", "metaengine-glm-thinking")
    return r


@pytest.fixture
def mock_llm_response():
    return {
        "choices": [{"message": {"content": "391"}}],
        "usage": {"total_tokens": 10},
    }


# ---------------------------------------------------------------------------
# Tests: ModelBackend
# ---------------------------------------------------------------------------


class TestModelBackend:
    def test_payload(self):
        b = ModelBackend(model_id="test", model_name="test-model", endpoint="http://localhost:3031")
        p = b.payload()
        assert p["model_id"] == "test"
        assert p["health"] == "HEALTHY"
        assert p["success_rate"] == 1.0  # no failures yet

    def test_initial_health(self):
        b = ModelBackend(model_id="t", model_name="m", endpoint="e")
        assert b.health == BackendHealth.HEALTHY
        assert b.failure_count == 0


# ---------------------------------------------------------------------------
# Tests: RoutedResult
# ---------------------------------------------------------------------------


class TestRoutedResult:
    def test_payload(self):
        r = RoutedResult(
            model_id="glm-1", response_text="391",
            usage={"total_tokens": 10}, latency_ms=300.0,
            success=True, error=None, result_hash="abc",
        )
        p = r.payload()
        assert p["model_id"] == "glm-1"
        assert p["success"] is True
        assert p["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Backend management
# ---------------------------------------------------------------------------


class TestBackendManagement:
    def test_add_backend(self, router):
        assert len(router.backends) == 2

    def test_add_third_backend(self, router):
        router.add_backend("third", "third-model")
        assert len(router.backends) == 3

    def test_remove_backend(self, router):
        assert router.remove_backend("glm-1") is True
        assert len(router.backends) == 1

    def test_remove_nonexistent(self, router):
        assert router.remove_backend("nonexistent") is False

    def test_get_healthy_backends(self, router):
        healthy = router.get_healthy_backends()
        assert len(healthy) == 2

    def test_unhealthy_excluded(self, router):
        router.backends[0].health = BackendHealth.UNHEALTHY
        router.backends[0].last_failure_time = time.time()  # recent failure
        healthy = router.get_healthy_backends()
        assert len(healthy) == 1  # only the healthy one

    def test_cooldown_recovery(self, router):
        b = router.backends[0]
        b.health = BackendHealth.UNHEALTHY
        b.last_failure_time = time.time() - 120  # 2 min ago (past 60s cooldown)
        healthy = router.get_healthy_backends()
        assert len(healthy) == 2  # recovered


# ---------------------------------------------------------------------------
# Tests: Round-robin routing
# ---------------------------------------------------------------------------


class TestRoundRobin:
    def test_next_backend_returns_backend(self, router):
        b = router._next_backend()
        assert b is not None
        assert b.model_id in ("glm-1", "glm-thinking")

    def test_round_robin_cycles(self, router):
        b1 = router._next_backend()
        b2 = router._next_backend()
        b3 = router._next_backend()
        assert b1.model_id != b2.model_id  # different backends
        assert b1.model_id == b3.model_id  # cycles back

    def test_no_healthy_returns_none(self, router):
        for b in router.backends:
            b.health = BackendHealth.UNHEALTHY
            b.last_failure_time = time.time()
        assert router._next_backend() is None


# ---------------------------------------------------------------------------
# Tests: LLM call with failover
# ---------------------------------------------------------------------------


class TestLLMCall:
    def test_call_returns_result(self, router, mock_llm_response):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps(mock_llm_response).encode()
            mock_urlopen.return_value = mock_resp
            result = router.call("What is 17*23?")
        assert result.success is True
        assert "391" in result.response_text
        assert result.model_id in ("glm-1", "glm-thinking")

    def test_call_updates_stats(self, router, mock_llm_response):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps(mock_llm_response).encode()
            mock_urlopen.return_value = mock_resp
            router.call("test prompt")
        assert router.backends[0].total_requests + router.backends[1].total_requests >= 1

    def test_call_failover_on_429(self, router, mock_llm_response):
        """429 on first backend → failover to second."""
        import urllib.error
        call_count = [0]

        def mock_urlopen_side_effect(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps(mock_llm_response).encode()
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen_side_effect):
            result = router.call("test", max_retries=3)

        assert result.success is True
        assert router._total_failovers >= 1

    def test_call_all_backends_fail(self, router):
        """All backends fail → returns failure."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 500, "Error", {}, None)):
            result = router.call("test", max_retries=2)
        assert result.success is False
        assert "ALL_BACKENDS_FAILED" in result.error or "HTTP 500" in result.error

    def test_call_no_healthy_backends(self, router):
        for b in router.backends:
            b.health = BackendHealth.UNHEALTHY
            b.last_failure_time = time.time()
        result = router.call("test")
        assert result.success is False
        assert result.error == "NO_HEALTHY_BACKENDS"

    def test_call_marks_unhealthy_after_max_failures(self, router):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 500, "Error", {}, None)):
            router.call("test", max_retries=6)  # enough retries to exhaust

        # At least one backend should be unhealthy
        unhealthy = [b for b in router.backends if b.health == BackendHealth.UNHEALTHY]
        assert len(unhealthy) >= 1

    def test_call_has_latency(self, router, mock_llm_response):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps(mock_llm_response).encode()
            mock_urlopen.return_value = mock_resp
            result = router.call("test")
        assert result.latency_ms >= 0.0

    def test_call_result_has_hash(self, router, mock_llm_response):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps(mock_llm_response).encode()
            mock_urlopen.return_value = mock_resp
            result = router.call("test")
        assert result.result_hash != ""


# ---------------------------------------------------------------------------
# Tests: Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_check_returns_bool(self, router):
        result = router.health_check()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_fields(self, router):
        s = router.summary()
        assert s["multi_model_version"] == MULTI_MODEL_VERSION
        assert s["total_backends"] == 2
        assert "healthy_backends" in s
        assert "failover_rate" in s
        assert s["truth_effect"] == "NONE"

    def test_summary_after_calls(self, router, mock_llm_response):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps(mock_llm_response).encode()
            mock_urlopen.return_value = mock_resp
            router.call("test1")
            router.call("test2")

        s = router.summary()
        assert s["total_calls"] == 2
        assert len(s["backends"]) == 2

    def test_summary_constitution(self, router):
        s = router.summary()
        assert s["constitution_compliance"]["transparent_routing"] is True
        assert s["constitution_compliance"]["no_code_modification"] is True
        assert s["constitution_compliance"]["all_models_generative"] is True


# ---------------------------------------------------------------------------
# Tests: create_default_router
# ---------------------------------------------------------------------------


class TestCreateDefaultRouter:
    def test_creates_router_with_backends(self):
        router = create_default_router()
        assert len(router.backends) == 2
        assert any(b.model_id == "glm-1" for b in router.backends)
        assert any(b.model_id == "glm-thinking" for b in router.backends)

    def test_default_router_endpoints(self):
        router = create_default_router()
        for b in router.backends:
            assert "localhost:3031" in b.endpoint


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_router_doesnt_modify_prompts(self, router):
        """Router is transparent — doesn't modify prompts."""
        assert not hasattr(router, "modify_prompt")
        assert not hasattr(router, "alter_prompt")

    def test_no_code_modification(self, router):
        assert not hasattr(router, "modify_code")
        assert not hasattr(router, "execute_code")

    def test_all_results_evaluative(self, router, mock_llm_response):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps(mock_llm_response).encode()
            mock_urlopen.return_value = mock_resp
            result = router.call("test")
        assert result.payload()["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Step 1: LiteLLM integration tests
# ---------------------------------------------------------------------------


class TestLiteLLMIntegration:
    """Step 1: Tests for LiteLLM integration in MultiModelRouter."""

    def test_litellm_available(self):
        """LiteLLM package is installed."""
        from metaengine.multi_model_router import LITELLM_AVAILABLE
        assert LITELLM_AVAILABLE is True

    def test_router_has_litellm_field(self):
        """Router summary includes litellm status."""
        router = MultiModelRouter()
        router.add_backend("test", "test-model")
        s = router.summary()
        assert "litellm" in s
        assert "available" in s["litellm"]
        assert "enabled" in s["litellm"]
        assert "total_cost_usd" in s["litellm"]

    def test_backend_has_litellm_model(self):
        """ModelBackend has litellm_model field."""
        router = MultiModelRouter()
        router.add_backend("test", "test-model", litellm_model="openai/test-model")
        assert router.backends[0].litellm_model == "openai/test-model"

    def test_backend_has_cost_tracking(self):
        """ModelBackend has total_cost_usd field."""
        router = MultiModelRouter()
        router.add_backend("test", "test-model")
        assert hasattr(router.backends[0], "total_cost_usd")
        assert router.backends[0].total_cost_usd == 0.0

    def test_routed_result_has_cost(self):
        """RoutedResult has cost_usd field."""
        from metaengine.multi_model_router import RoutedResult
        result = RoutedResult(
            model_id="test", response_text="hello", usage={},
            latency_ms=100.0, success=True, cost_usd=0.001,
        )
        assert result.cost_usd == 0.001
        assert "cost_usd" in result.payload()

    def test_summary_has_cost_tracking_flag(self):
        """Summary has cost_tracking_enabled in constitution_compliance."""
        router = MultiModelRouter()
        router.add_backend("test", "test-model")
        s = router.summary()
        assert s["constitution_compliance"]["cost_tracking_enabled"] is True
        assert s["constitution_compliance"]["litellm_transparent"] is True

    def test_create_default_router_has_litellm_backends(self):
        """create_default_router configures backends with litellm_model strings."""
        router = create_default_router()
        for b in router.backends:
            assert b.litellm_model.startswith("openai/")
            assert b.litellm_api_base == "http://localhost:3031"

    def test_router_version_bumped(self):
        """Version is bumped to indicate LiteLLM integration."""
        from metaengine.multi_model_router import MULTI_MODEL_VERSION
        assert MULTI_MODEL_VERSION == "METAENGINE-MULTI-MODEL-ROUTER-2"

    def test_auto_detect_litellm(self):
        """When use_litellm=None, router auto-detects based on environment."""
        import os
        # Without OPENAI_API_KEY or METENGINE_LITELLM_FORCE, should be False
        old_key = os.environ.pop('OPENAI_API_KEY', None)
        old_force = os.environ.pop('METENGINE_LITELLM_FORCE', None)
        router = MultiModelRouter(use_litellm=None)
        assert router.use_litellm is False  # No API key → auto-detect → False
        # Restore
        if old_key: os.environ['OPENAI_API_KEY'] = old_key
        if old_force: os.environ['METENGINE_LITELLM_FORCE'] = old_force
