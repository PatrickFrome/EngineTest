"""Tests for Phase 64 — REST API Server."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.api_server import MetaEngineAPIServer, MetaEngineAPIHandler, API_VERSION


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server():
    """Start API server on port 8081 (test port)."""
    s = MetaEngineAPIServer(root=ROOT, port=8081)
    s.start_background()
    time.sleep(1)  # wait for server to start
    yield s
    s.stop()
    time.sleep(0.5)


def _get(port: int, path: str) -> dict:
    """Make GET request to API."""
    with urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Tests: Server starts
# ---------------------------------------------------------------------------


class TestServerStarts:
    def test_server_starts_and_responds(self, server):
        data = _get(8081, "/api/health")
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")

    def test_root_endpoint(self, server):
        data = _get(8081, "/")
        assert data["name"] == "MetaEngine REST API"
        assert data["version"] == API_VERSION

    def test_version_endpoint(self, server):
        data = _get(8081, "/api/version")
        assert data["api_version"] == API_VERSION
        assert data["engine_version"] == "2.3.0-alpha.1"


# ---------------------------------------------------------------------------
# Tests: Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_has_bridge_status(self, server):
        data = _get(8081, "/api/health")
        assert "bridge_healthy" in data
        assert isinstance(data["bridge_healthy"], bool)

    def test_health_has_constitution_status(self, server):
        data = _get(8081, "/api/health")
        assert "constitution_ok" in data
        assert isinstance(data["constitution_ok"], bool)

    def test_health_has_timestamp(self, server):
        data = _get(8081, "/api/health")
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format


# ---------------------------------------------------------------------------
# Tests: Constitution
# ---------------------------------------------------------------------------


class TestConstitution:
    def test_constitution_has_k0_invariants(self, server):
        data = _get(8081, "/api/constitution")
        assert "k0_invariants" in data
        assert len(data["k0_invariants"]) == 12

    def test_constitution_has_amendment_authority(self, server):
        data = _get(8081, "/api/constitution")
        assert data["amendment_authority"] == "NOT_IMPLEMENTED"

    def test_constitution_has_hash(self, server):
        data = _get(8081, "/api/constitution")
        assert "constitution_hash" in data
        assert len(data["constitution_hash"]) > 0

    def test_constitution_has_k1_topics(self, server):
        data = _get(8081, "/api/constitution")
        assert "k1_topics" in data
        assert len(data["k1_topics"]) == 11

    def test_constitution_truth_effect_none(self, server):
        data = _get(8081, "/api/constitution")
        assert data["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Modules
# ---------------------------------------------------------------------------


class TestModules:
    def test_modules_listed(self, server):
        data = _get(8081, "/api/modules")
        assert "modules" in data
        assert data["total_modules"] > 50  # we have 97+

    def test_modules_have_names(self, server):
        data = _get(8081, "/api/modules")
        names = [m["name"] for m in data["modules"]]
        assert "orchestrator" in names
        assert "rlaif_trainer" in names

    def test_modules_have_loc(self, server):
        data = _get(8081, "/api/modules")
        for m in data["modules"][:5]:
            assert m["loc"] > 0


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_has_module_count(self, server):
        data = _get(8081, "/api/summary")
        assert data["modules"] > 50

    def test_summary_has_test_count(self, server):
        data = _get(8081, "/api/summary")
        assert data["test_files"] > 30


# ---------------------------------------------------------------------------
# Tests: State bus
# ---------------------------------------------------------------------------


class TestStateBus:
    def test_state_bus_endpoint(self, server):
        data = _get(8081, "/api/state-bus")
        assert "truth_effect" in data
        # Either has data or "no_state"
        assert "status" in data or "run_count" in data

    def test_accumulation_endpoint(self, server):
        data = _get(8081, "/api/accumulation")
        assert "truth_effect" in data


# ---------------------------------------------------------------------------
# Tests: Benchmark
# ---------------------------------------------------------------------------


class TestBenchmark:
    def test_benchmark_summary(self, server):
        data = _get(8081, "/api/benchmark")
        assert "truth_effect" in data

    def test_benchmark_results(self, server):
        try:
            data = _get(8081, "/api/benchmark/results")
            assert "benchmark_version" in data or "error" in data
        except urllib.error.HTTPError:
            pass  # 404 if no results — acceptable


# ---------------------------------------------------------------------------
# Tests: Strict tests
# ---------------------------------------------------------------------------


class TestStrictTests:
    def test_strict_tests_endpoint(self, server):
        data = _get(8081, "/api/strict-tests")
        assert "truth_effect" in data


# ---------------------------------------------------------------------------
# Tests: 404 handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_404_for_unknown_path(self, server):
        try:
            _get(8081, "/api/unknown")
            assert False, "Should have raised HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404


# ---------------------------------------------------------------------------
# Tests: CORS headers
# ---------------------------------------------------------------------------


class TestCORS:
    def test_cors_headers_present(self, server):
        import urllib.request
        req = urllib.request.Request(f"http://localhost:8081/api/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_all_endpoints_have_truth_effect_none(self, server):
        endpoints = [
            "/api/health",
            "/api/summary",
            "/api/constitution",
            "/api/modules",
            "/api/state-bus",
            "/api/accumulation",
            "/api/benchmark",
            "/api/version",
        ]
        for ep in endpoints:
            data = _get(8081, ep)
            assert data.get("truth_effect") == "NONE", f"{ep} missing truth_effect=NONE"
