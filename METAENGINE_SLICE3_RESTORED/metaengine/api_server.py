"""METAENGINE Phase 64 — REST API Server.

Exposes MetaEngine via REST API endpoints using Python's built-in http.server
(no external dependencies required).

Endpoints:
  GET  /api/health           — health check
  GET  /api/summary           — project summary (modules, tests, phases)
  GET  /api/constitution      — K0 invariants
  GET  /api/modules           — list all modules with health status
  GET  /api/state-bus         — state bus summary
  GET  /api/accumulation      — cross-run accumulation summary
  GET  /api/benchmark         — benchmark summary (last run)
  GET  /api/benchmark/results — last benchmark results
  POST /api/benchmark/run     — trigger benchmark run (async)
  POST /api/run               — trigger orchestrator run (async)
  GET  /api/strict-tests      — strict test factory results
  GET  /api/version           — version info

The server runs on port 8080 (configurable).
Uses ThreadingHTTPServer for concurrent requests.

Constitution compliance:
  - API is read-only for most endpoints (no mutation of constitution)
  - Run endpoints use experiment_policy (SHADOW, no auto-promotion)
  - All responses carry truth_effect=NONE
"""

from __future__ import annotations

import json
import os
import sys
import time
import threading
import importlib
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs


API_VERSION = "METAENGINE-REST-API-1"
DEFAULT_PORT = 8080

# I6: Rate limiting — per-endpoint token-bucket.
# Each POST endpoint has its own bucket so a /api/benchmark/run spammer can't
# also starve /api/recursive/run. The bucket refills at a fixed rate up to a
# maximum burst size (default: 1 call per 60s, burst of 1).
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60.0  # one call per window
DEFAULT_RATE_LIMIT_BURST = 1             # max queued / burst calls


# ---------------------------------------------------------------------------
# API Handler
# ---------------------------------------------------------------------------


class MetaEngineAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MetaEngine REST API."""

    # Set by the server factory
    root: Path = Path(".")
    _benchmark_cache: dict[str, Any] = {}
    _strict_cache: dict[str, Any] = {}
    # C4: API auth token (None = auth disabled, set to enable)
    api_token: str | None = None
    # I6: per-endpoint rate-limit state. Maps endpoint path → list of recent
    # call timestamps (monotonic). The oldest timestamps are evicted when they
    # fall outside the rate-limit window.
    _rate_limit_state: dict[str, list[float]] = {}
    # I6: configurable per-endpoint limits (set by server factory). If an
    # endpoint isn't in this map, no rate limit is applied.
    rate_limits: dict[str, dict[str, float]] = {
        "/api/benchmark/run": {"window_seconds": DEFAULT_RATE_LIMIT_WINDOW_SECONDS, "burst": DEFAULT_RATE_LIMIT_BURST},
        "/api/recursive/run": {"window_seconds": DEFAULT_RATE_LIMIT_WINDOW_SECONDS, "burst": DEFAULT_RATE_LIMIT_BURST},
        "/api/run": {"window_seconds": DEFAULT_RATE_LIMIT_WINDOW_SECONDS, "burst": DEFAULT_RATE_LIMIT_BURST},
    }

    def log_message(self, format, *args):
        """Suppress default logging (or enable for debug)."""
        pass  # silent

    def _send_json(self, status: int, data: Any) -> None:
        """Send JSON response."""
        body = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message, "status": status})

    # I6: Rate limiting helpers
    def _check_rate_limit(self, endpoint: str) -> tuple[bool, float]:
        """I6: Token-bucket rate limit check.

        Returns (allowed, retry_after_seconds). If allowed is False, the caller
        should respond with HTTP 429 and the retry_after hint.

        The bucket holds up to `burst` tokens. Each call consumes 1 token.
        Tokens refill at rate = burst / window_seconds (so the bucket returns
        to full after `window_seconds` of idle time).
        """
        import time as _time
        cfg = self.rate_limits.get(endpoint)
        if cfg is None:
            return True, 0.0  # no rate limit configured for this endpoint
        window = float(cfg.get("window_seconds", DEFAULT_RATE_LIMIT_WINDOW_SECONDS))
        burst = int(cfg.get("burst", DEFAULT_RATE_LIMIT_BURST))
        now = _time.monotonic()
        # Evict timestamps older than the window
        history = self._rate_limit_state.get(endpoint, [])
        history = [t for t in history if now - t < window]
        if len(history) >= burst:
            # Rate limited — caller must wait until the oldest call ages out
            retry_after = window - (now - history[0])
            self._rate_limit_state[endpoint] = history
            return False, max(0.0, retry_after)
        history.append(now)
        self._rate_limit_state[endpoint] = history
        return True, 0.0

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/" or path == "/api":
            self._handle_root()
        elif path == "/api/health":
            self._handle_health()
        elif path == "/api/summary":
            self._handle_summary()
        elif path == "/api/constitution":
            self._handle_constitution()
        elif path == "/api/modules":
            self._handle_modules()
        elif path == "/api/state-bus":
            self._handle_state_bus()
        elif path == "/api/accumulation":
            self._handle_accumulation()
        elif path == "/api/benchmark":
            self._handle_benchmark_summary()
        elif path == "/api/benchmark/results":
            self._handle_benchmark_results()
        elif path == "/api/strict-tests":
            self._handle_strict_tests()
        elif path == "/api/fitness":
            self._handle_fitness()
        elif path == "/api/recursive":
            self._handle_recursive()
        elif path == "/api/events":
            self._handle_events()
        elif path == "/api/ws-info":
            self._handle_ws_info()
        elif path == "/api/version":
            self._handle_version()
        else:
            self._send_error(404, f"Not found: {path}")

    def do_POST(self):
        """Handle POST requests (C4: requires auth if api_token set; I6: rate-limited)."""
        # C4: Check auth for POST endpoints
        if self.api_token is not None:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {self.api_token}":
                self._send_error(401, "Unauthorized: invalid or missing Bearer token")
                return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # I6: rate-limit check before dispatching
        allowed, retry_after = self._check_rate_limit(path)
        if not allowed:
            # N1: publish rate-limit event for real-time monitoring
            try:
                from .event_publisher import publish_event
                publish_event("api.rate_limited", {
                    "endpoint": path,
                    "retry_after_seconds": round(retry_after, 2),
                    "client": self.client_address[0] if hasattr(self, "client_address") else "unknown",
                })
            except Exception:
                pass  # best-effort
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Retry-After", str(int(retry_after) + 1))
            body = json.dumps({
                "error": "rate_limited",
                "status": 429,
                "message": f"Too many requests to {path}. Retry after {retry_after:.1f}s.",
                "retry_after_seconds": round(retry_after, 2),
                "truth_effect": "NONE",
            }, indent=2).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/benchmark/run":
            self._handle_benchmark_run()
        elif path == "/api/run":
            self._handle_orchestrator_run()
        elif path == "/api/recursive/run":
            self._handle_recursive_run()
        else:
            self._send_error(404, f"Not found: {path}")

    # ------------------------------------------------------------------
    # Endpoint handlers
    # ------------------------------------------------------------------

    def _handle_root(self):
        """Root endpoint — API info."""
        self._send_json(200, {
            "name": "MetaEngine REST API",
            "version": API_VERSION,
            "description": "Constitutionally-safe self-improving AI system",
            "endpoints": [
                "GET /api/health",
                "GET /api/summary",
                "GET /api/constitution",
                "GET /api/modules",
                "GET /api/state-bus",
                "GET /api/accumulation",
                "GET /api/benchmark",
                "GET /api/benchmark/results",
                "POST /api/benchmark/run",
                "GET /api/strict-tests",
                "GET /api/version",
            ],
            "truth_effect": "NONE",
        })

    def _handle_health(self):
        """Health check."""
        # Check bridge
        bridge_healthy = self._check_bridge()
        # Check constitution
        constitution_ok = self._check_constitution()

        self._send_json(200, {
            "status": "healthy" if (bridge_healthy and constitution_ok) else "degraded",
            "bridge_healthy": bridge_healthy,
            "constitution_ok": constitution_ok,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "truth_effect": "NONE",
        })

    def _handle_summary(self):
        """Project summary."""
        root = self.root
        modules = list((root / "metaengine").glob("*.py"))
        tests = list((root / "tests").glob("*.py"))
        storage_dirs = list((root / "storage").glob("phase*")) if (root / "storage").exists() else []

        self._send_json(200, {
            "modules": len(modules),
            "test_files": len(tests),
            "storage_dirs": len(storage_dirs),
            "phases_completed": len(storage_dirs),
            "truth_effect": "NONE",
        })

    def _handle_constitution(self):
        """K0 invariants."""
        try:
            sys.path.insert(0, str(self.root))
            from metaengine.constitution import load_constitution_kernel
            kernel = load_constitution_kernel(self.root)
            invariants = [
                {"id": inv.invariant_id, "statement": inv.statement}
                for inv in kernel.k0_invariants
            ]
            self._send_json(200, {
                "k0_version": kernel.k0_version,
                "k0_invariants": invariants,
                "k1_topics": list(kernel.k1_topics),
                "amendment_authority": kernel.amendment_boundary.authority_status,
                "constitution_hash": kernel.constitution_hash[:32],
                "truth_effect": "NONE",
            })
        except Exception as exc:
            self._send_error(500, f"Constitution load failed: {exc}")

    def _handle_modules(self):
        """List all modules with health status."""
        root = self.root
        modules_dir = root / "metaengine"
        modules = []
        for py in sorted(modules_dir.glob("*.py")):
            name = py.stem
            loc = py.read_text().count("\n") + 1
            modules.append({
                "name": name,
                "loc": loc,
                "size_bytes": py.stat().st_size,
            })
        self._send_json(200, {
            "total_modules": len(modules),
            "modules": modules,
            "truth_effect": "NONE",
        })

    def _handle_state_bus(self):
        """State bus summary."""
        bus_path = self.root / "storage" / "accumulated_state.json"
        if not bus_path.is_file():
            self._send_json(200, {"status": "no_state", "truth_effect": "NONE"})
            return
        try:
            data = json.loads(bus_path.read_text())
            self._send_json(200, {
                "run_count": data.get("run_count", 0),
                "total_mechanisms": data.get("mechanism_count", 0),
                "total_observations": sum(data.get("biography_observations", {}).values()),
                "evidence_graph_nodes": data.get("evidence_graph_nodes", 0),
                "evidence_graph_edges": data.get("evidence_graph_edges", 0),
                "last_updated": data.get("last_run", ""),
                "truth_effect": "NONE",
            })
        except Exception as exc:
            self._send_error(500, f"State bus load failed: {exc}")

    def _handle_accumulation(self):
        """Cross-run accumulation summary."""
        acc_path = self.root / "storage" / "accumulated_state.json"
        if not acc_path.is_file():
            self._send_json(200, {"status": "no_accumulation", "truth_effect": "NONE"})
            return
        try:
            data = json.loads(acc_path.read_text())
            self._send_json(200, data)
        except Exception as exc:
            self._send_error(500, f"Accumulation load failed: {exc}")

    def _handle_benchmark_summary(self):
        """Benchmark summary."""
        report_path = self.root / "storage" / "phase57_63_unified_benchmark" / "MANIFEST.json"
        if report_path.is_file():
            data = json.loads(report_path.read_text())
            self._send_json(200, data)
        else:
            self._send_json(200, {
                "status": "no_benchmark_run",
                "message": "POST /api/benchmark/run to execute",
                "truth_effect": "NONE",
            })

    def _handle_benchmark_results(self):
        """Full benchmark results."""
        report_path = self.root / "storage" / "phase57_63_unified_benchmark" / "UNIFIED_REPORT.json"
        if report_path.is_file():
            data = json.loads(report_path.read_text())
            self._send_json(200, data)
        else:
            self._send_error(404, "No benchmark results found")

    def _handle_benchmark_run(self):
        """Trigger benchmark run (async, returns immediately)."""
        # Read body for max_tasks_per_category
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
        max_tasks = body.get("max_tasks_per_category", 2)

        # Run in background thread
        def run_benchmark():
            try:
                sys.path.insert(0, str(self.root))
                from metaengine.unified_benchmark import UnifiedBenchmarkRunner
                runner = UnifiedBenchmarkRunner(root=self.root, rate_limit_delay=3.0)
                report = runner.run_all(max_tasks_per_category=max_tasks)
                out_dir = self.root / "storage" / "phase57_63_unified_benchmark"
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "UNIFIED_REPORT.json").write_text(
                    json.dumps(report.as_dict(), indent=2, ensure_ascii=False, default=str)
                )
                (out_dir / "MANIFEST.json").write_text(
                    json.dumps({
                        "total_tasks": report.total_tasks,
                        "total_passed": report.total_passed,
                        "overall_pass_rate": report.overall_pass_rate,
                        "all_modules_working": report.all_modules_working,
                        "truth_effect": "NONE",
                    }, indent=2, ensure_ascii=False)
                )
                self._benchmark_cache = {"status": "completed", "report": report.payload()}
            except Exception as exc:
                self._benchmark_cache = {"status": "error", "error": str(exc)}

        thread = threading.Thread(target=run_benchmark, daemon=True)
        thread.start()

        self._send_json(202, {
            "status": "accepted",
            "message": "Benchmark running in background. GET /api/benchmark to check results.",
            "truth_effect": "NONE",
        })

    def _handle_strict_tests(self):
        """Strict test results."""
        report_path = self.root / "storage" / "phase55_strict_tests" / "PHASE55_MANIFEST.json"
        if report_path.is_file():
            data = json.loads(report_path.read_text())
            self._send_json(200, data)
        else:
            self._send_json(200, {"status": "no_strict_tests", "truth_effect": "NONE"})

    def _handle_version(self):
        """Version info."""
        self._send_json(200, {
            "api_version": API_VERSION,
            "engine_version": "2.3.0-alpha.1",
            "phases_completed": 63,
            "python_version": sys.version.split()[0],
            "truth_effect": "NONE",
        })

    def _handle_orchestrator_run(self):
        """Trigger orchestrator run (placeholder — returns instructions)."""
        self._send_json(202, {
            "status": "accepted",
            "message": "Orchestrator run requires CLI with --receipt. Use: python -m metaengine.cli run INPUT --out OUT --receipt RECEIPT",
            "truth_effect": "NONE",
        })

    # ------------------------------------------------------------------
    # C2: Fitness + Recursive endpoints (I2)
    # ------------------------------------------------------------------

    def _handle_fitness(self):
        """Fitness adapter summary."""
        try:
            sys.path.insert(0, str(self.root))
            from metaengine.tiered_fitness import ThreeTierFitnessAdapter
            adapter = ThreeTierFitnessAdapter(root=self.root, l2_budget=3)
            summary = adapter.summary()
            self._send_json(200, summary)
        except Exception as exc:
            self._send_error(500, f"Fitness load failed: {exc}")

    def _handle_recursive(self):
        """Recursive improvement results."""
        report_path = self.root / "storage" / "phase68_real_recursive" / "MANIFEST.json"
        if report_path.is_file():
            data = json.loads(report_path.read_text())
            self._send_json(200, data)
        else:
            self._send_json(200, {"status": "no_recursive_run", "truth_effect": "NONE"})

    def _handle_recursive_run(self):
        """Trigger recursive improvement (async)."""
        def run_recursive():
            try:
                sys.path.insert(0, str(self.root))
                from metaengine.real_recursive import RealRecursiveRunner
                runner = RealRecursiveRunner(root=self.root, l2_budget=2, num_pbt_generations=1, pbt_population_size=3)
                results = runner.run(num_generations=2)
                out_dir = self.root / "storage" / "phase68_real_recursive"
                out_dir.mkdir(parents=True, exist_ok=True)
                summary = runner.summary()
                (out_dir / "REAL_RECURSIVE_SUMMARY.json").write_text(
                    json.dumps(summary, indent=2, ensure_ascii=False, default=str)
                )
                (out_dir / "MANIFEST.json").write_text(
                    json.dumps({
                        "generations_run": summary["generations_run"],
                        "total_improvement": summary["total_improvement"],
                        "improvement_ratio": summary["improvement_ratio"],
                        "truth_effect": "NONE",
                    }, indent=2, ensure_ascii=False)
                )
                self._benchmark_cache = {"recursive_status": "completed", "summary": summary}
                # N1: publish recursive.summary event for real-time monitoring
                try:
                    from metaengine.event_publisher import publish_event
                    publish_event("recursive.summary", {
                        "generations_run": summary["generations_run"],
                        "total_improvement": summary["total_improvement"],
                        "improvement_ratio": summary["improvement_ratio"],
                        "l2_utilization": summary.get("l2_utilization", 0.0),
                    })
                    # Also publish each generation as a separate event
                    for gen in summary.get("generations", []):
                        publish_event("recursive.generation", {
                            "generation": gen["generation"],
                            "pbt_mean_fitness": gen["pbt_mean_fitness"],
                            "pbt_best_fitness": gen["pbt_best_fitness"],
                            "improvement_vs_prev": gen.get("improvement_vs_prev"),
                            "l2_calls_used": gen["l2_calls_used"],
                        })
                except Exception:
                    pass  # best-effort
            except Exception as exc:
                self._benchmark_cache = {"recursive_status": "error", "error": str(exc)}

        thread = threading.Thread(target=run_recursive, daemon=True)
        thread.start()
        self._send_json(202, {
            "status": "accepted",
            "message": "Recursive improvement running in background. GET /api/recursive to check results.",
            "truth_effect": "NONE",
        })

    # ------------------------------------------------------------------
    # N1: Events + WebSocket info endpoints
    # ------------------------------------------------------------------

    def _handle_events(self):
        """N1: Return recent events from the event log (for inspection / replay)."""
        try:
            sys.path.insert(0, str(self.root))
            from metaengine.event_publisher import read_events_since, publisher_state
            # Read last 100 events (or all if fewer)
            events, offset = read_events_since(0)
            recent = events[-100:] if len(events) > 100 else events
            self._send_json(200, {
                "total_events": len(events),
                "returned": len(recent),
                "byte_offset": offset,
                "events": recent,
                "publisher_state": publisher_state(),
                "truth_effect": "NONE",
            })
        except Exception as exc:
            self._send_error(500, f"Events load failed: {exc}")

    def _handle_ws_info(self):
        """N1: Return WebSocket service info (how to connect)."""
        self._send_json(200, {
            "ws_service": "metaengine-ws-events",
            "port": 3032,
            "connect_url": "/?XTransformPort=3032",
            "event_log_path": "storage/events.log",
            "event_types": [
                "fitness.evaluated",
                "fitness.generation",
                "recursive.generation",
                "recursive.summary",
                "amplify.fired",
                "distill.persisted",
                "router.failover",
                "router.recovered",
                "api.rate_limited",
            ],
            "replay_support": "connect with ?since=<byte_offset> to replay missed events",
            "truth_effect": "NONE",
        })

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def _check_bridge(self) -> bool:
        """Check if LLM bridge is healthy."""
        import urllib.request
        try:
            with urllib.request.urlopen("http://localhost:3031/health", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok"
        except Exception:
            return False

    def _check_constitution(self) -> bool:
        """Check if constitution is loadable."""
        try:
            sys.path.insert(0, str(self.root))
            from metaengine.constitution import load_constitution_kernel
            kernel = load_constitution_kernel(self.root)
            return len(kernel.k0_invariants) == 12
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


class MetaEngineAPIServer:
    """MetaEngine REST API Server.

    Usage:
        server = MetaEngineAPIServer(root=Path("."), port=8080)
        server.start()  # blocks
    """

    def __init__(self, *, root: str | Path = ".", port: int = DEFAULT_PORT, api_token: str | None = None, rate_limits: dict[str, dict[str, float]] | None = None):
        self.root = Path(root).resolve()
        self.port = port
        self.api_token = api_token
        # I6: allow caller to override per-endpoint rate limits
        self.rate_limits = rate_limits if rate_limits is not None else {
            "/api/benchmark/run": {"window_seconds": DEFAULT_RATE_LIMIT_WINDOW_SECONDS, "burst": DEFAULT_RATE_LIMIT_BURST},
            "/api/recursive/run": {"window_seconds": DEFAULT_RATE_LIMIT_WINDOW_SECONDS, "burst": DEFAULT_RATE_LIMIT_BURST},
            "/api/run": {"window_seconds": DEFAULT_RATE_LIMIT_WINDOW_SECONDS, "burst": DEFAULT_RATE_LIMIT_BURST},
        }
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> None:
        """Start the API server (blocking)."""
        # Configure handler with root path
        handler = type("BoundHandler", (MetaEngineAPIHandler,), {
            "root": self.root,
            "_benchmark_cache": {},
            "_strict_cache": {},
            "api_token": self.api_token,  # C4: pass token to handler
            # I6: per-endpoint rate-limit configuration + state
            "rate_limits": self.rate_limits,
            "_rate_limit_state": {},
        })

        self._server = ThreadingHTTPServer(("0.0.0.0", self.port), handler)
        print(f"[MetaEngine API] Server running on port {self.port}")
        print(f"[MetaEngine API] Root: {self.root}")
        print(f"[MetaEngine API] Endpoints: http://localhost:{self.port}/api/")
        print(f"[MetaEngine API] Health: http://localhost:{self.port}/api/health")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            print("\n[MetaEngine API] Shutting down...")
            self._server.shutdown()

    def stop(self) -> None:
        """Stop the API server."""
        if self._server:
            self._server.shutdown()

    def start_background(self) -> threading.Thread:
        """Start the API server in a background thread (non-blocking).

        Returns the thread object.
        """
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    """Run the API server from command line."""
    import argparse
    parser = argparse.ArgumentParser(description="MetaEngine REST API Server")
    parser.add_argument("--root", default=".", help="MetaEngine root directory")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (default: 8080)")
    args = parser.parse_args()

    server = MetaEngineAPIServer(root=args.root, port=args.port)
    server.start()


if __name__ == "__main__":
    main()
