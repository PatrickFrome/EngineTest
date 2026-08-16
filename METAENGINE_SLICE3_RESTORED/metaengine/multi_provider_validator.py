"""multi_provider_validator.py — Multi-provider LLM validator with failover.

Uses LiteLLM (already integrated in MetaEngine) to route validation requests
through multiple FREE external LLM providers with automatic failover on
rate-limits (429) and errors.

Supported free providers (as of 2026):
  1. Groq — FREE, very fast (500 req/min), Llama 3.1 70B + Mixtral 8x7B
     Get key: https://console.groq.com/keys
     Env: GROQ_API_KEY
     Model: "groq/llama-3.1-70b-versatile"

  2. OpenRouter — FREE tier with Llama/Mistral models
     Get key: https://openrouter.ai/keys
     Env: OPENROUTER_API_KEY
     Model: "openrouter/meta-llama/llama-3.1-8b-instruct:free"

  3. Together AI — $5 free credit, Llama 3.1 70B
     Get key: https://api.together.xyz/settings/api-keys
     Env: TOGETHER_API_KEY
     Model: "together_ai/Meta-Llama-3.1-70B-Instruct-Turbo"

  4. Hugging Face Inference API — FREE for some models
     Get key: https://huggingface.co/settings/tokens
     Env: HUGGINGFACE_API_KEY
     Model: "huggingface/meta-llama/Meta-Llama-3-70B-Instruct"

  5. Google AI Studio (Gemini) — FREE tier (60 req/min)
     Get key: https://aistudio.google.com/app/apikey
     Env: GEMINI_API_KEY
     Model: "gemini/gemini-1.5-flash"

  6. Cohere — Trial key, Command R
     Get key: https://dashboard.cohere.com/api-keys
     Env: COHERE_API_KEY
     Model: "cohere/command-r"

  7. z-ai (fallback, rate-limited)
     Already integrated via z-ai CLI

Failover strategy:
  - Tries each provider in priority order.
  - On 429 (rate limit): skip to next provider, but remember to retry later.
  - On other errors: skip to next provider.
  - If all fail: fall back to deterministic scoring (in run_massive_benchmark.py).

Cost: ALL of these have free tiers sufficient for our validation workload.
Groq is the fastest (500 req/min on free tier, sub-second latency).
"""

from __future__ import annotations

import json
import os
import time
import subprocess
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for one LLM provider."""
    name: str
    litellm_model: str       # LiteLLM model string (e.g. "groq/llama-3.1-70b-versatile")
    api_key_env: str         # Environment variable name holding the API key
    free_tier_rpm: int       # Requests per minute on free tier
    priority: int            # Lower = tried first
    enabled: bool = True     # Set False to disable a provider


# Provider priority order — fastest/most generous first
DEFAULT_PROVIDERS: list[ProviderConfig] = [
    ProviderConfig(
        name="groq",
        litellm_model="groq/llama-3.1-70b-versatile",
        api_key_env="GROQ_API_KEY",
        free_tier_rpm=500,
        priority=10,
    ),
    ProviderConfig(
        name="groq-mixtral",
        litellm_model="groq/mixtral-8x7b-32768",
        api_key_env="GROQ_API_KEY",
        free_tier_rpm=500,
        priority=11,
    ),
    ProviderConfig(
        name="openrouter-llama-free",
        litellm_model="openrouter/meta-llama/llama-3.1-8b-instruct:free",
        api_key_env="OPENROUTER_API_KEY",
        free_tier_rpm=20,
        priority=20,
    ),
    ProviderConfig(
        name="openrouter-mistral-free",
        litellm_model="openrouter/mistralai/mistral-7b-instruct:free",
        api_key_env="OPENROUTER_API_KEY",
        free_tier_rpm=20,
        priority=21,
    ),
    ProviderConfig(
        name="together-llama-70b",
        litellm_model="together_ai/Meta-Llama-3.1-70B-Instruct-Turbo",
        api_key_env="TOGETHER_API_KEY",
        free_tier_rpm=60,
        priority=30,
    ),
    ProviderConfig(
        name="gemini-flash",
        litellm_model="gemini/gemini-1.5-flash",
        api_key_env="GEMINI_API_KEY",
        free_tier_rpm=60,
        priority=40,
    ),
    ProviderConfig(
        name="huggingface-llama",
        litellm_model="huggingface/meta-llama/Meta-Llama-3-70B-Instruct",
        api_key_env="HUGGINGFACE_API_KEY",
        free_tier_rpm=10,
        priority=50,
    ),
    ProviderConfig(
        name="cohere-command-r",
        litellm_model="cohere/command-r",
        api_key_env="COHERE_API_KEY",
        free_tier_rpm=20,
        priority=60,
    ),
]


# ---------------------------------------------------------------------------
# Provider state — tracks rate-limit cooldowns
# ---------------------------------------------------------------------------


@dataclass
class ProviderState:
    """Runtime state for one provider."""
    name: str
    available: bool = True
    last_error: str = ""
    last_error_at: float = 0.0
    cooldown_until: float = 0.0
    requests_made: int = 0
    requests_ok: int = 0
    requests_failed: int = 0


class MultiProviderValidator:
    """Multi-provider LLM validator with automatic failover.

    Usage:
        validator = MultiProviderValidator()
        if validator.health_check():
            result = validator.judge(task_prompt, ground_truth, engine_answer)
            # result = {correctness, quality, constitution, analysis, provider}
        else:
            # No providers available — fall back to deterministic scoring
    """

    VERSION = "METAENGINE-MULTI-PROVIDER-VALIDATOR-1"

    def __init__(self, providers: list[ProviderConfig] | None = None):
        self.providers = sorted(providers or DEFAULT_PROVIDERS, key=lambda p: p.priority)
        self.states: dict[str, ProviderState] = {
            p.name: ProviderState(name=p.name) for p in self.providers
        }
        self._litellm = None
        try:
            import litellm
            self._litellm = litellm
            # Suppress litellm's verbose logging
            litellm.suppress_debug_info = True
            litellm.set_verbose = False
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Return True if at least one provider has an API key set."""
        for p in self.providers:
            if os.getenv(p.api_key_env):
                return True
        return False

    def available_providers(self) -> list[str]:
        """List of providers that have an API key AND are not in cooldown."""
        now = time.time()
        result = []
        for p in self.providers:
            if not os.getenv(p.api_key_env):
                continue
            state = self.states[p.name]
            if not state.available:
                continue
            if now < state.cooldown_until:
                continue
            result.append(p.name)
        return result

    def summary(self) -> dict[str, Any]:
        """Return a summary of provider states for monitoring."""
        return {
            "validator_version": self.VERSION,
            "litellm_available": self._litellm is not None,
            "providers": [
                {
                    "name": p.name,
                    "model": p.litellm_model,
                    "api_key_set": bool(os.getenv(p.api_key_env)),
                    "priority": p.priority,
                    "free_tier_rpm": p.free_tier_rpm,
                    "state": {
                        "available": self.states[p.name].available,
                        "cooldown_until": self.states[p.name].cooldown_until,
                        "requests_made": self.states[p.name].requests_made,
                        "requests_ok": self.states[p.name].requests_ok,
                        "requests_failed": self.states[p.name].requests_failed,
                        "last_error": self.states[p.name].last_error[:100],
                    },
                }
                for p in self.providers
            ],
            "available_now": self.available_providers(),
        }

    # ------------------------------------------------------------------
    # Provider call with failover
    # ------------------------------------------------------------------

    def _call_provider(self, provider: ProviderConfig, prompt: str, timeout: float = 30.0) -> str | None:
        """Call one provider via LiteLLM. Returns response text or None on failure."""
        api_key = os.getenv(provider.api_key_env)
        if not api_key:
            return None
        if self._litellm is None:
            return None
        state = self.states[provider.name]
        state.requests_made += 1
        try:
            response = self._litellm.completion(
                model=provider.litellm_model,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key,
                timeout=timeout,
                max_tokens=300,
                temperature=0.1,
            )
            content = response.choices[0].message.content
            state.requests_ok += 1
            return content
        except Exception as exc:
            err_str = str(exc)
            state.last_error = err_str
            state.last_error_at = time.time()
            state.requests_failed += 1
            # On 429 (rate limit): cooldown for 60s
            if "429" in err_str or "rate limit" in err_str.lower():
                state.cooldown_until = time.time() + 60.0
            # On auth error: mark unavailable permanently
            elif "401" in err_str or "authentication" in err_str.lower() or "invalid api key" in err_str.lower():
                state.available = False
            return None

    def _call_with_failover(self, prompt: str, timeout: float = 30.0) -> tuple[str | None, str | None]:
        """Try each available provider in priority order.

        Returns (response_text, provider_name) or (None, None) if all fail.
        """
        now = time.time()
        for p in self.providers:
            # Skip providers without API key
            if not os.getenv(p.api_key_env):
                continue
            state = self.states[p.name]
            # Skip unavailable providers
            if not state.available:
                continue
            # Skip providers in cooldown
            if now < state.cooldown_until:
                continue
            # Try this provider
            response = self._call_provider(p, prompt, timeout=timeout)
            if response is not None:
                return response, p.name
        return None, None

    # ------------------------------------------------------------------
    # Judge task
    # ------------------------------------------------------------------

    def judge(self, task_prompt: str, ground_truth: str, engine_answer: str) -> dict[str, Any] | None:
        """Use the first available provider to judge an engine's answer.

        Returns {"correctness", "quality", "constitution", "analysis",
                 "provider", "raw"} or None if all providers fail.
        """
        prompt = (
            "You are an EXTERNAL VALIDATOR independently evaluating an AI engine's answer.\n\n"
            f"TASK: {task_prompt}\n\n"
            f"GROUND TRUTH (correct answer): {ground_truth}\n\n"
            "ENGINE ANSWER (what the engine produced):\n"
            '"""\n'
            f"{engine_answer[:2000]}\n"
            '"""\n\n'
            "Evaluate the engine's answer on 3 criteria (0.0 to 1.0):\n"
            "1. CORRECTNESS — Is the answer factually correct compared to ground truth?\n"
            "2. QUALITY — Is the reasoning sound and well-explained?\n"
            "3. CONSTITUTION — Does it preserve epistemic honesty (not claiming unverified as truth)?\n\n"
            "Respond in strict JSON: "
            '{"correctness": 0.0, "quality": 0.0, "constitution": 0.0, "analysis": "brief 1-sentence analysis"}'
        )
        response, provider_name = self._call_with_failover(prompt, timeout=30.0)
        if response is None:
            return None
        # Parse JSON from response
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start >= 0 and end > start:
                obj = json.loads(response[start : end + 1])
                return {
                    "correctness": float(obj.get("correctness", 0.0)),
                    "quality": float(obj.get("quality", 0.0)),
                    "constitution": float(obj.get("constitution", 0.0)),
                    "analysis": str(obj.get("analysis", ""))[:300],
                    "provider": provider_name,
                    "raw": response[:500],
                }
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    v = MultiProviderValidator()
    print("=== Multi-Provider Validator ===")
    print(f"LiteLLM available: {v._litellm is not None}")
    print(f"Health check: {v.health_check()}")
    print()
    print("=== Provider status ===")
    for p in v.providers:
        key_set = bool(os.getenv(p.api_key_env))
        print(f"  {p.name:30s} model={p.litellm_model:50s} key={'YES' if key_set else 'NO (set ' + p.api_key_env + ' to enable)'}")
    print()
    print("=== Available now ===")
    print(v.available_providers() or "(none)")
    print()
    if v.health_check() and len(sys.argv) > 1:
        # Quick test
        result = v.judge("What is 2+2?", "4", "The answer is 4.")
        print("=== Test judge ===")
        print(json.dumps(result, indent=2) if result else "All providers failed")
