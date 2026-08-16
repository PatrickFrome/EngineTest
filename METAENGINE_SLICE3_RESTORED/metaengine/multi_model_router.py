"""METAENGINE Phase 69 — Multi-Model Bridge Router (LiteLLM-enhanced).

Step 1: Adopted LiteLLM as the underlying LLM gateway.

Previously: raw urllib.request.urlopen to hardcoded localhost:3031 endpoint.
  - Only 1 bridge, 2 model names, no provider abstraction
  - No cost tracking, no virtual keys, no streaming
  - Manual failover logic (round-robin + try/except)

Now: LiteLLM-powered router with 100+ provider support.
  - LiteLLM Router for multi-provider failover
  - Cost tracking via litellm.completion_cost
  - Backward-compatible: same MultiModelRouter API, same RoutedResult
  - create_default_router() still creates 2 backends, but now uses LiteLLM
  - Old urllib path retained as fallback (litellm_fallback=True)

Constitution compliance:
  - Router is transparent (doesn't modify prompts)
  - All models produce generative output (claim_ceiling)
  - No code modification
  - truth_effect=NONE
"""

from __future__ import annotations

import json
import time
import threading
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

# Step 1: LiteLLM integration
try:
    import litellm
    from litellm import Router as LiteLLMRouter
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


MULTI_MODEL_VERSION = "METAENGINE-MULTI-MODEL-ROUTER-2"  # Bumped for LiteLLM integration


class BackendHealth(str, Enum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    COOLING_DOWN = "COOLING_DOWN"


@dataclass
class ModelBackend:
    """A single LLM backend configuration."""
    model_id: str  # e.g., "glm-1"
    model_name: str  # e.g., "metaengine-glm-1" or litellm model string
    endpoint: str  # e.g., "http://localhost:3031/v1/chat/completions"
    health: BackendHealth = BackendHealth.HEALTHY
    failure_count: int = 0
    last_failure_time: float = 0.0
    total_requests: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    cost_score: float = 1.0
    capability_tier: str = "standard"
    # Step 1: LiteLLM provider string (e.g., "openai/metaengine-glm-1")
    litellm_model: str = ""
    # Step 1: API base for custom OpenAI-compatible endpoints
    litellm_api_base: str = ""
    # Step 1: API key env var name
    litellm_api_key_env: str = ""
    # Step 1: Total cost tracked via litellm
    total_cost_usd: float = 0.0

    def payload(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "health": self.health.value,
            "failure_count": self.failure_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "success_rate": round(1.0 - (self.total_failures / max(1, self.total_requests)), 4),
            "cost_score": self.cost_score,
            "capability_tier": self.capability_tier,
            # Step 1: LiteLLM + cost tracking
            "litellm_model": self.litellm_model,
            "total_cost_usd": round(self.total_cost_usd, 6),
        }


@dataclass(frozen=True)
class RoutedResult:
    """Result of a routed LLM call."""
    model_id: str
    response_text: str
    usage: dict[str, Any]
    latency_ms: float
    success: bool
    error: str | None = None
    result_hash: str = ""
    # Step 1: cost tracking
    cost_usd: float = 0.0

    def payload(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "response_text": self.response_text[:500],
            "usage": self.usage,
            "latency_ms": round(self.latency_ms, 2),
            "success": self.success,
            "error": self.error,
            "cost_usd": round(self.cost_usd, 6),
            "truth_effect": "NONE",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "result_hash": self.result_hash}


class MultiModelRouter:
    """Routes LLM requests across multiple backends with failover.

    Step 1: Now powered by LiteLLM for 100+ provider support.

    Usage:
        router = MultiModelRouter()
        router.add_backend("glm-1", "metaengine-glm-1", "http://localhost:3031/v1/chat/completions")
        result = router.call("What is 17*23?")
    """

    COOLDOWN_SECONDS = 60.0
    MAX_FAILURES = 3
    HEALTH_CHECK_INTERVAL = 30.0
    SIMPLE_PROMPT_MAX_CHARS = 200
    SIMPLE_MAX_TOKENS = 128

    def __init__(
        self,
        *,
        background_health_recovery: bool = False,
        health_recovery_interval: float = 30.0,
        probe_fn: Callable[[ModelBackend], bool] | None = None,
        cost_aware: bool = True,
        use_litellm: bool = None,  # Step 1: None=auto-detect (True in prod, False when OPENAI_API_KEY missing)
    ):
        self.backends: list[ModelBackend] = []
        self._round_robin_index = 0
        self._total_calls = 0
        self._total_failovers = 0
        self.cost_aware = cost_aware
        self._background_recovery_enabled = background_health_recovery
        self._health_recovery_interval = float(health_recovery_interval)
        self._probe_fn = probe_fn
        self._reaper_thread: threading.Thread | None = None
        self._reaper_stop = threading.Event()
        self._reaper_lock = threading.Lock()
        self._reaper_recovered_count = 0
        self._reaper_probe_count = 0
        # Step 1: LiteLLM integration — auto-detect mode
        if use_litellm is None:
            # Auto-detect: enable if LiteLLM is available AND we have an API key or custom bridge
            import os
            use_litellm = LITELLM_AVAILABLE and (
                os.environ.get('OPENAI_API_KEY') is not None or
                os.environ.get('METENGINE_LITELLM_FORCE', '0') == '1'
            )
        self.use_litellm = use_litellm and LITELLM_AVAILABLE
        self._litellm_router: LiteLLMRouter | None = None
        self._total_cost_usd: float = 0.0
        if background_health_recovery:
            self._start_reaper()

    # ------------------------------------------------------------------
    # Backend management
    # ------------------------------------------------------------------

    def add_backend(
        self,
        model_id: str,
        model_name: str,
        endpoint: str = "http://localhost:3031/v1/chat/completions",
        *,
        cost_score: float = 1.0,
        capability_tier: str = "standard",
        litellm_model: str = "",  # Step 1: LiteLLM provider string
        litellm_api_base: str = "",  # Step 1: custom API base
        litellm_api_key_env: str = "",  # Step 1: API key env var
    ) -> ModelBackend:
        """Add a backend to the router.

        Step 1: If litellm_model is provided, calls will use LiteLLM's completion API.
        Otherwise, falls back to direct urllib HTTP calls (backward compatible).
        """
        backend = ModelBackend(
            model_id=model_id,
            model_name=model_name,
            endpoint=endpoint,
            cost_score=cost_score,
            capability_tier=capability_tier,
            litellm_model=litellm_model or f"openai/{model_name}",
            litellm_api_base=litellm_api_base or endpoint.replace("/v1/chat/completions", ""),
            litellm_api_key_env=litellm_api_key_env,
        )
        self.backends.append(backend)
        # Step 1: Rebuild LiteLLM router if enabled
        if self.use_litellm:
            self._build_litellm_router()
        return backend

    def remove_backend(self, model_id: str) -> bool:
        """Remove a backend by model_id."""
        before = len(self.backends)
        self.backends = [b for b in self.backends if b.model_id != model_id]
        removed = len(self.backends) < before
        if removed and self.use_litellm:
            self._build_litellm_router()
        return removed

    # ------------------------------------------------------------------
    # Step 1: LiteLLM router management
    # ------------------------------------------------------------------

    def _build_litellm_router(self) -> None:
        """Step 1: Build/rebuild LiteLLM Router from current backends."""
        if not self.use_litellm or not self.backends:
            self._litellm_router = None
            return
        model_list = []
        for b in self.backends:
            model_config: dict[str, Any] = {
                "model_name": b.model_id,  # LiteLLM groups by model_name
                "litellm_params": {
                    "model": b.litellm_model,
                    "api_base": b.litellm_api_base,
                },
            }
            if b.litellm_api_key_env:
                import os
                api_key = os.environ.get(b.litellm_api_key_env, "")
                if api_key:
                    model_config["litellm_params"]["api_key"] = api_key
            model_list.append(model_config)
        try:
            self._litellm_router = LiteLLMRouter(
                model_list=model_list,
                routing_strategy="simple-shuffle",  # round-robin
                num_retries=2,
                timeout=60,
                fallbacks=[],  # We handle failover ourselves
            )
        except Exception:
            self._litellm_router = None  # Graceful degradation

    def _call_litellm(self, backend: ModelBackend, prompt: str, max_tokens: int, temperature: float, timeout: float) -> tuple[str, dict[str, Any], float]:
        """Step 1: Call LLM via LiteLLM. Returns (response_text, usage, cost_usd)."""
        kwargs: dict[str, Any] = {
            "model": backend.litellm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": timeout,
            "api_base": backend.litellm_api_base,
        }
        if backend.litellm_api_key_env:
            import os
            api_key = os.environ.get(backend.litellm_api_key_env, "")
            if api_key:
                kwargs["api_key"] = api_key

        response = litellm.completion(**kwargs)
        response_text = response.choices[0].message.content or ""
        usage = {}
        if hasattr(response, 'usage') and response.usage:
            usage = {
                "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                "completion_tokens": getattr(response.usage, 'completion_tokens', 0),
                "total_tokens": getattr(response.usage, 'total_tokens', 0),
            }
        # Step 1: Cost tracking
        cost_usd = 0.0
        try:
            cost_usd = litellm.completion_cost(completion_response=response)
        except Exception:
            pass
        return response_text, usage, cost_usd

    def get_healthy_backends(self) -> list[ModelBackend]:
        """Get list of healthy backends (HEALTHY or COOLING_DOWN past cooldown)."""
        now = time.time()
        healthy = []
        for b in self.backends:
            if b.health == BackendHealth.HEALTHY:
                healthy.append(b)
            elif b.health == BackendHealth.UNHEALTHY:
                # Check if cooldown period has passed
                if now - b.last_failure_time > self.COOLDOWN_SECONDS:
                    b.health = BackendHealth.COOLING_DOWN
                    b.failure_count = 0  # reset
                    healthy.append(b)
            elif b.health == BackendHealth.COOLING_DOWN:
                healthy.append(b)
        return healthy

    # ------------------------------------------------------------------
    # N3: Cost-aware routing
    # ------------------------------------------------------------------

    def _is_simple_task(self, prompt: str, max_tokens: int) -> bool:
        """N3: Heuristic to classify a task as 'simple' (cheap) or 'complex' (expensive).

        Simple tasks: short prompts AND low max_tokens.
        Complex tasks: long prompts OR high max_tokens.
        """
        return (
            len(prompt) <= self.SIMPLE_PROMPT_MAX_CHARS
            and max_tokens <= self.SIMPLE_MAX_TOKENS
        )

    def _select_backend_cost_aware(self, healthy: list[ModelBackend], prompt: str, max_tokens: int) -> ModelBackend:
        """N3: Select backend with cost-awareness.

        For simple tasks: prefer backends with capability_tier="simple" or lowest cost_score.
        For complex tasks: prefer backends with capability_tier="complex" or highest capability.
        Falls back to round-robin if all backends have equal cost/capability.
        """
        if not healthy:
            raise RuntimeError("NO_HEALTHY_BACKENDS")
        is_simple = self._is_simple_task(prompt, max_tokens)

        if is_simple:
            # Prefer "simple" tier, then lowest cost_score
            simple_tier = [b for b in healthy if b.capability_tier == "simple"]
            if simple_tier:
                pool = sorted(simple_tier, key=lambda b: b.cost_score)
            else:
                # No simple-tier backends — use the cheapest standard/complex one
                pool = sorted(healthy, key=lambda b: b.cost_score)
        else:
            # Complex task — prefer "complex" tier backends
            complex_tier = [b for b in healthy if b.capability_tier == "complex"]
            if complex_tier:
                pool = sorted(complex_tier, key=lambda b: -b.cost_score)  # higher cost = more capable
            else:
                pool = healthy  # no complex tier — round-robin

        # Round-robin within the selected pool (preserves load balancing)
        backend = pool[self._round_robin_index % len(pool)]
        self._round_robin_index += 1
        return backend

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _next_backend(self, prompt: str = "", max_tokens: int = 512) -> ModelBackend | None:
        """Get next backend (round-robin among healthy, or cost-aware if enabled)."""
        healthy = self.get_healthy_backends()
        if not healthy:
            return None

        # N3: cost-aware routing
        if self.cost_aware and prompt:
            return self._select_backend_cost_aware(healthy, prompt, max_tokens)

        # Default: round-robin
        backend = healthy[self._round_robin_index % len(healthy)]
        self._round_robin_index += 1
        return backend

    # ------------------------------------------------------------------
    # LLM call with failover
    # ------------------------------------------------------------------

    def call(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.4,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> RoutedResult:
        """Call LLM with automatic failover.

        Tries backends in round-robin order (or cost-aware order if enabled).
        If a backend fails (429, 500, timeout), marks it and tries the next one.

        Args:
            prompt: input text for the LLM.
            max_tokens: max response tokens.
            temperature: sampling temperature.
            timeout: per-backend timeout.
            max_retries: max total retries across backends.

        Returns:
            RoutedResult with response + metadata.
        """
        self._total_calls += 1
        last_error = None

        for attempt in range(max_retries):
            backend = self._next_backend(prompt=prompt, max_tokens=max_tokens)
            if backend is None:
                return RoutedResult(
                    model_id="none",
                    response_text="",
                    usage={},
                    latency_ms=0.0,
                    success=False,
                    error="NO_HEALTHY_BACKENDS",
                )

            started = time.perf_counter()
            try:
                # Step 1: Use LiteLLM if available, otherwise fall back to urllib
                if self.use_litellm and backend.litellm_model:
                    response_text, usage, cost_usd = self._call_litellm(backend, prompt, max_tokens, temperature, timeout)
                else:
                    # Backward-compatible: direct urllib HTTP call
                    body = json.dumps({
                        "model": backend.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    }).encode("utf-8")

                    req = urllib.request.Request(
                        backend.endpoint,
                        data=body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )

                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8"))

                    response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
                    usage = data.get("usage", {})
                    cost_usd = 0.0  # No cost tracking in urllib path
                latency_ms = (time.perf_counter() - started) * 1000

                # Update backend stats
                backend.total_requests += 1
                backend.avg_latency_ms = (
                    (backend.avg_latency_ms * (backend.total_requests - 1) + latency_ms)
                    / backend.total_requests
                )
                backend.health = BackendHealth.HEALTHY
                backend.failure_count = 0
                # Step 1: Track cost
                backend.total_cost_usd += cost_usd
                self._total_cost_usd += cost_usd

                from .util import canonical_hash
                result = RoutedResult(
                    model_id=backend.model_id,
                    response_text=response_text,
                    usage=usage,
                    latency_ms=latency_ms,
                    success=True,
                    error=None,
                    result_hash="",
                    cost_usd=cost_usd,  # Step 1: cost tracking
                )
                h = canonical_hash(result.payload())
                return RoutedResult(**{**result.__dict__, "result_hash": h})

            except urllib.error.HTTPError as exc:
                latency_ms = (time.perf_counter() - started) * 1000
                last_error = f"HTTP {exc.code}: {exc.reason}"
                backend.total_requests += 1
                backend.total_failures += 1
                backend.failure_count += 1
                backend.last_failure_time = time.time()

                if backend.failure_count >= self.MAX_FAILURES:
                    backend.health = BackendHealth.UNHEALTHY

                if attempt < max_retries - 1:
                    self._total_failovers += 1
                    continue  # try next backend

            except Exception as exc:
                latency_ms = (time.perf_counter() - started) * 1000
                last_error = repr(exc)[:200]
                backend.total_requests += 1
                backend.total_failures += 1
                backend.failure_count += 1
                backend.last_failure_time = time.time()

                if backend.failure_count >= self.MAX_FAILURES:
                    backend.health = BackendHealth.UNHEALTHY

                if attempt < max_retries - 1:
                    self._total_failovers += 1
                    continue

        return RoutedResult(
            model_id="failed",
            response_text="",
            usage={},
            latency_ms=0.0,
            success=False,
            error=last_error or "ALL_BACKENDS_FAILED",
        )

    # ------------------------------------------------------------------
    # N2: Background health recovery
    # ------------------------------------------------------------------

    def _default_probe(self, backend: ModelBackend) -> bool:
        """N2: Default probe — checks the backend's /health endpoint.

        Returns True if the backend is reachable and reports healthy.
        Override via probe_fn in __init__ for testing or custom health checks.
        """
        try:
            # Derive /health from the chat endpoint
            # e.g., "http://localhost:3031/v1/chat/completions" → "http://localhost:3031/health"
            base = backend.endpoint.rsplit("/", 2)[0]  # strip "/v1/chat/completions"
            health_url = f"{base}/health"
            with urllib.request.urlopen(health_url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok"
        except Exception:
            return False

    def _reaper_loop(self) -> None:
        """N2: Background thread that probes UNHEALTHY backends and recovers them."""
        while not self._reaper_stop.wait(self._health_recovery_interval):
            try:
                self._reap_once()
            except Exception:
                # Reaper must never crash the host process
                pass

    def _reap_once(self) -> dict[str, Any]:
        """N2: Single pass of the reaper — probe all UNHEALTHY backends.

        Returns a dict with the reap results for inspection/testing.
        """
        with self._reaper_lock:
            unhealthy = [b for b in self.backends if b.health == BackendHealth.UNHEALTHY]
            results: list[dict[str, Any]] = []
            for b in unhealthy:
                # Only probe if cooldown has passed
                if time.time() - b.last_failure_time < self.COOLDOWN_SECONDS:
                    results.append({"model_id": b.model_id, "action": "skipped_cooldown"})
                    continue
                self._reaper_probe_count += 1
                probe_fn = self._probe_fn or self._default_probe
                probe_ok = False
                try:
                    probe_ok = probe_fn(b)
                except Exception:
                    probe_ok = False
                if probe_ok:
                    b.health = BackendHealth.HEALTHY
                    b.failure_count = 0
                    self._reaper_recovered_count += 1
                    results.append({"model_id": b.model_id, "action": "recovered"})
                else:
                    # Reset the failure clock so we probe again after the next cooldown
                    b.last_failure_time = time.time()
                    results.append({"model_id": b.model_id, "action": "still_unhealthy"})
            return {
                "probed": len(unhealthy),
                "recovered": sum(1 for r in results if r["action"] == "recovered"),
                "still_unhealthy": sum(1 for r in results if r["action"] == "still_unhealthy"),
                "skipped_cooldown": sum(1 for r in results if r["action"] == "skipped_cooldown"),
                "details": results,
            }

    def _start_reaper(self) -> None:
        """N2: Start the background reaper thread (idempotent)."""
        if self._reaper_thread is not None and self._reaper_thread.is_alive():
            return
        self._reaper_stop.clear()
        self._reaper_thread = threading.Thread(
            target=self._reaper_loop,
            name="MultiModelRouter-reaper",
            daemon=True,
        )
        self._reaper_thread.start()

    def stop_reaper(self) -> None:
        """N2: Stop the background reaper thread (for clean shutdown)."""
        self._reaper_stop.set()
        if self._reaper_thread is not None:
            self._reaper_thread.join(timeout=5.0)
            self._reaper_thread = None

    def reap_now(self) -> dict[str, Any]:
        """N2: Manually trigger a reap pass (for testing without waiting for the timer)."""
        return self._reap_once()

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Check if at least one backend is reachable."""
        try:
            with urllib.request.urlopen("http://localhost:3031/health", timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok"
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return router summary."""
        return {
            "multi_model_version": MULTI_MODEL_VERSION,
            "total_backends": len(self.backends),
            "healthy_backends": len(self.get_healthy_backends()),
            "total_calls": self._total_calls,
            "total_failovers": self._total_failovers,
            "failover_rate": round(self._total_failovers / max(1, self._total_calls), 4),
            "backends": [b.payload() for b in self.backends],
            # Step 1: LiteLLM integration status
            "litellm": {
                "available": LITELLM_AVAILABLE,
                "enabled": self.use_litellm,
                "router_built": self._litellm_router is not None,
                "total_cost_usd": round(self._total_cost_usd, 6),
            },
            # N2: background reaper status
            "background_recovery": {
                "enabled": self._background_recovery_enabled,
                "interval_seconds": self._health_recovery_interval,
                "total_probes": self._reaper_probe_count,
                "total_recovered": self._reaper_recovered_count,
                "recovery_rate": round(self._reaper_recovered_count / max(1, self._reaper_probe_count), 4),
            },
            # N3: cost-aware routing status
            "cost_aware": {
                "enabled": self.cost_aware,
                "simple_prompt_max_chars": self.SIMPLE_PROMPT_MAX_CHARS,
                "simple_max_tokens": self.SIMPLE_MAX_TOKENS,
            },
            "truth_effect": "NONE",
            "claim_ceiling": "MULTI_MODEL_ROUTER_IS_TRANSPARENT_NOT_TRUTH",
            "constitution_compliance": {
                "transparent_routing": True,
                "no_code_modification": True,
                "failover_preserves_claim_ceiling": True,
                "all_models_generative": True,
                "reaper_bounded": True,
                "reaper_observational": True,
                "cost_aware_transparent": True,
                # Step 1: LiteLLM is transparent
                "litellm_transparent": True,
                "cost_tracking_enabled": True,
            },
        }


# ---------------------------------------------------------------------------
# Default router factory
# ---------------------------------------------------------------------------


def create_default_router(
    *,
    background_health_recovery: bool = False,
    cost_aware: bool = True,
    use_litellm: bool = None,  # Step 1: None=auto-detect
) -> MultiModelRouter:
    """Create a default router with multiple model variants.

    Step 1: LiteLLM is now the default LLM gateway.
    Backends are configured with litellm_model strings for 100+ provider support.
    Falls back to direct urllib if LiteLLM is not installed.

    The two default backends:
      - glm-1: standard cost (1.0), standard tier → litellm: openai/metaengine-glm-1
      - glm-thinking: expensive (1.5), complex tier → litellm: openai/metaengine-glm-thinking
    """
    router = MultiModelRouter(
        background_health_recovery=background_health_recovery,
        cost_aware=cost_aware,
        use_litellm=use_litellm,
    )
    # Step 1: glm-1 backend with LiteLLM provider string
    router.add_backend(
        "glm-1", "metaengine-glm-1",
        "http://localhost:3031/v1/chat/completions",
        cost_score=1.0,
        capability_tier="standard",
        litellm_model="openai/metaengine-glm-1",
        litellm_api_base="http://localhost:3031",
    )
    # Step 1: glm-thinking backend with LiteLLM provider string
    router.add_backend(
        "glm-thinking", "metaengine-glm-thinking",
        "http://localhost:3031/v1/chat/completions",
        cost_score=1.5,
        capability_tier="complex",
        litellm_model="openai/metaengine-glm-thinking",
        litellm_api_base="http://localhost:3031",
    )
    return router
