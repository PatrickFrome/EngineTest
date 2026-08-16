"""Fix 4: Centralized LLM Bridge Client — eliminates _call_llm duplication.

Previously: _call_llm + health_check were copy-pasted in 4 modules:
  - rlaif_trainer.py
  - redteam_adversary.py
  - llm_judge.py
  - unified_benchmark.py

Now: all 4 modules import from this single source. Any bridge protocol
change is a 1-file edit.

Constitution: This client is transparent — it doesn't modify prompts
or responses. truth_effect=NONE propagated.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


class LLMBridgeClient:
    """Centralized LLM bridge client for all MetaEngine modules.

    Usage:
        client = LLMBridgeClient(endpoint='http://localhost:3031')
        response = client.chat("What is 2+2?", model='metaengine-glm-1')
        is_healthy = client.health_check()
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:3031",
        model: str = "metaengine-glm-1",
        max_tokens: int = 512,
        temperature: float = 0.4,
        timeout: float = 60.0,
    ):
        self.endpoint = endpoint.rstrip('/')
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    def chat(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request to the LLM bridge.

        Returns:
            Dict with 'content', 'usage', 'success', 'error' keys.
        """
        use_model = model or self.model
        use_max_tokens = max_tokens or self.max_tokens
        use_temperature = temperature if temperature is not None else self.temperature
        use_timeout = timeout or self.timeout

        body = json.dumps({
            "model": use_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": use_max_tokens,
            "temperature": use_temperature,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.endpoint}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=use_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return {
                "content": content,
                "usage": usage,
                "success": True,
                "error": None,
            }
        except urllib.error.HTTPError as exc:
            return {
                "content": "",
                "usage": {},
                "success": False,
                "error": f"HTTP {exc.code}: {exc.reason}",
            }
        except Exception as exc:
            return {
                "content": "",
                "usage": {},
                "success": False,
                "error": repr(exc)[:200],
            }

    def health_check(self) -> bool:
        """Check if the LLM bridge is healthy."""
        try:
            with urllib.request.urlopen(f"{self.endpoint}/health", timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok"
        except Exception:
            return False


# Singleton instance for modules that don't need custom config
_default_client: LLMBridgeClient | None = None


def get_default_client() -> LLMBridgeClient:
    """Get the default LLM bridge client (singleton)."""
    global _default_client
    if _default_client is None:
        _default_client = LLMBridgeClient()
    return _default_client
