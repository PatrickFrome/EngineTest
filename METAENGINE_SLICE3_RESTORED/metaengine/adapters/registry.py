from __future__ import annotations

from .node_native import NodeNativeAdapter
from .reference import ReferenceAdapter
from .base import Adapter


class AdapterRegistry:
    """Fail-closed adapter dispatch with explicit implementation disclosure."""

    MODES = {
        "NODE_NATIVE": (NodeNativeAdapter, "NATIVE_LOCAL", "REAL_EXECUTOR"),
        "NODE_UNIFIED": (NodeNativeAdapter, "NATIVE_LOCAL", "REAL_EXECUTOR"),
        "PYTHON_REFERENCE_CONTRACT": (ReferenceAdapter, "REFERENCE_SIMULATION", "CLEAN_ROOM_CONTRACT_STUB"),
        # Phase 24: LLM model adapter — supports Ollama and OpenAI-compatible endpoints.
        # The adapter is registered but only activated when the engine config
        # specifies execution_mode="LLM_MODEL" and provides an LLM config.
        # If no endpoint is reachable, the adapter returns a FAILED contribution
        # with a clear error — it does NOT silently fall back to simulation.
        "LLM_MODEL": (None, "LLM_MODEL", "REAL_LLM_EXECUTOR"),  # adapter created lazily with config
    }

    def create(self, record, lineage_root):
        mode = record.get("execution_mode")
        if mode not in self.MODES:
            raise ValueError(f"UNKNOWN_ADAPTER_MODE:{mode}")
        adapter_cls, _, _ = self.MODES[mode]

        # Phase 24: LLM model adapter requires a config object
        if mode == "LLM_MODEL":
            from ..llm_model_adapter import LLMModelAdapter, LLMModelConfig
            llm_config = self._build_llm_config(record)
            return LLMModelAdapter(record, lineage_root, llm_config)

        return adapter_cls(record, lineage_root)

    def disclosure(self, record):
        mode = record.get("execution_mode")
        if mode not in self.MODES:
            raise ValueError(f"UNKNOWN_ADAPTER_MODE:{mode}")
        _, kind, level = self.MODES[mode]
        return {"adapter_kind": kind, "implementation_level": level, "silent_fallback_allowed": False}

    @staticmethod
    def _build_llm_config(record):
        """Build LLMModelConfig from engine record fields."""
        from ..llm_model_adapter import LLMModelConfig
        return LLMModelConfig(
            model_id=record.get("engine_id", "llm-unknown"),
            endpoint=record.get("llm_endpoint", "http://localhost:11434/api/generate"),
            model_name=record.get("llm_model_name", "llama3.2"),
            api_key_env=record.get("llm_api_key_env", "OLLAMA_API_KEY"),
            max_tokens=record.get("llm_max_tokens", 2048),
            temperature=record.get("llm_temperature", 0.7),
            timeout=record.get("llm_timeout", 120.0),
        )
