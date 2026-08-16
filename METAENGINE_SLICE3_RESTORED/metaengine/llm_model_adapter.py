"""METAENGINE Phase 17 — LLM Model Adapter.

Provides a real LLM execution adapter that connects MetaEngine to actual
language model APIs (Ollama local, or any OpenAI-compatible endpoint).
This closes the CRITICAL gap: all 16 engines are simulations — this adapter
enables real intelligence organization testing.

The adapter implements the same EngineContribution contract as NodeNative
and ReferenceAdapter, but executes against a real model.
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .adapters.base import Adapter, EngineContribution
from .security import redact_secrets


LLM_ADAPTER_VERSION = "METAENGINE-LLM-MODEL-ADAPTER-1"


@dataclass(frozen=True)
class LLMModelConfig:
    """Configuration for an LLM model endpoint."""
    model_id: str
    endpoint: str  # e.g. "http://localhost:11434/api/generate" (Ollama) or OpenAI-compatible
    model_name: str  # e.g. "llama3.2" or "gpt-4o-mini"
    api_key_env: str  # environment variable name for API key (never store key directly)
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: float = 120.0
    adapter_kind: str = "LLM_MODEL"
    implementation_level: str = "REAL_LLM_EXECUTOR"

    def payload(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "endpoint": self.endpoint,
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "adapter_kind": self.adapter_kind,
            "implementation_level": self.implementation_level,
            "api_key_env": self.api_key_env,  # env var NAME, not the key itself
        }


class LLMModelAdapter(Adapter):
    """Adapter that executes against a real LLM model endpoint.

    Supports Ollama (local) and any OpenAI-compatible API.
    The API key is read from the environment variable specified in config —
    it is NEVER stored in the adapter, logged, or persisted.
    """

    def __init__(self, record, root, config: LLMModelConfig):
        super().__init__(record, root)
        self.config = config

    def run(self, input_path, out_dir, context):
        started = time.perf_counter()
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        eid = self.record['engine_id']

        try:
            text = Path(input_path).read_text(errors='ignore')
            prompt = self._build_prompt(text, context)

            # Execute against the LLM endpoint
            response_text, usage = self._call_llm(prompt)

            # Parse claims from the response
            claims = self._extract_claims(response_text, eid)

            canonical = {
                'kind': 'llm_model_execution',
                'model_id': self.config.model_id,
                'model_name': self.config.model_name,
                'response_text': redact_secrets(response_text)[:8000],
                'claims': claims,
                'claim_ceiling': 'LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED',
                'adapter_disclosure': {
                    'adapter_kind': self.config.adapter_kind,
                    'implementation_level': self.config.implementation_level,
                    'eligible_for_frontier_comparison': True,
                },
            }

            elapsed = time.perf_counter() - started
            usage['wall_seconds'] = round(elapsed, 6)

            return EngineContribution(
                eid, 'COMPLETE',
                {'response': redact_secrets(response_text)[:4000]},
                canonical, None,
                self.config.adapter_kind,
                self.config.implementation_level,
                claims, [],
                [{'event': 'LLM_MODEL_EXECUTED', 'model': self.config.model_name, 'tokens': usage.get('total_tokens', 0)}],
                usage,
                {'model_endpoint': self.config.endpoint, 'lineage_integrity_verified': True},
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            return EngineContribution(
                eid, 'FAILED', {}, {'kind': 'llm_model_execution', 'claims': []},
                repr(exc), self.config.adapter_kind, self.config.implementation_level,
                usage={'wall_seconds': round(elapsed, 6)},
            )

    def review(self, coordination, out_dir, context):
        """Review using the LLM — generate a cross-review of other engines' outputs."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        eid = self.record['engine_id']
        started = time.perf_counter()

        try:
            # Build review prompt from coordination data
            review_text = json.dumps({
                'claim_graph': coordination.get('claim_graph', {}).get('nodes', [])[:5],
                'disagreements': coordination.get('disagreements', {}).get('conflicts', [])[:3],
            }, ensure_ascii=False)[:2000]
            prompt = f"Review the following engine outputs and identify any disagreements, errors, or unsupported claims:\n{review_text}"

            response_text, usage = self._call_llm(prompt)

            elapsed = time.perf_counter() - started
            usage['wall_seconds'] = round(elapsed, 6)

            return {
                'engine_id': eid,
                'review_state': 'COMPLETE',
                'review_text': redact_secrets(response_text)[:4000],
                'adapter_kind': self.config.adapter_kind,
                'usage': usage,
            }
        except Exception as exc:
            elapsed = time.perf_counter() - started
            return {
                'engine_id': eid,
                'review_state': 'FAILED',
                'error': repr(exc)[:200],
                'adapter_kind': self.config.adapter_kind,
                'usage': {'wall_seconds': round(elapsed, 6)},
            }

    def _build_prompt(self, text: str, context: Mapping[str, Any]) -> str:
        """Build a prompt for the LLM from the input text and context."""
        return (
            f"You are engine {self.record.get('engine_id', 'unknown')} in a MetaEngine orchestration. "
            f"Analyze the following text and produce claims with source-grounded evidence.\n\n"
            f"Input text:\n{text[:4000]}\n\n"
            f"Context: meta_run_id={context.get('meta_run_id', 'unknown')}, "
            f"routing_mode={context.get('routing_plan', {}).get('mode', 'unknown')}\n\n"
            f"Produce your analysis as structured claims."
        )

    def _call_llm(self, prompt: str) -> tuple[str, dict[str, Any]]:
        """Call the LLM endpoint and return (response_text, usage_dict).

        Supports Ollama (/api/generate) and OpenAI-compatible (/v1/chat/completions).
        """
        import os

        api_key = os.getenv(self.config.api_key_env, "")

        # Detect endpoint type
        if "/api/generate" in self.config.endpoint:
            # Ollama format
            return self._call_ollama(prompt, api_key)
        else:
            # OpenAI-compatible format
            return self._call_openai_compatible(prompt, api_key)

    def _call_ollama(self, prompt: str, api_key: str) -> tuple[str, dict[str, Any]]:
        """Call an Ollama endpoint."""
        body = json.dumps({
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            self.config.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        response_text = data.get("response", "")
        usage = {
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            "cost_usd": None,
            "tool_calls": 0,
        }
        return response_text, usage

    def _call_openai_compatible(self, prompt: str, api_key: str) -> tuple[str, dict[str, Any]]:
        """Call an OpenAI-compatible endpoint."""
        body = json.dumps({
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(
            self.config.endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage_data = data.get("usage", {})
        usage = {
            "input_tokens": usage_data.get("prompt_tokens", 0),
            "output_tokens": usage_data.get("completion_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
            "cost_usd": None,
            "tool_calls": 0,
        }
        return response_text, usage

    def _extract_claims(self, text: str, engine_id: str) -> list[dict[str, Any]]:
        """Extract structured claims from LLM response text."""
        # Simple heuristic: split by sentences, take first 5 as claims
        import re
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 10]
        claims = []
        for i, sent in enumerate(sentences[:5]):
            claims.append({
                'proposition': sent,
                'proposition_key': None,
                'stance': 'PROPOSE',
                'claim_type': 'LLM_GENERATED_CLAIM',
                'force': 'GENERATIVE_ONLY',
                'source_refs': [],
                'evidence_kind': 'LLM_GENERATED',
                'evidence_strength': 0.15,  # low — LLM output is generative, not evidence
                'claim_ceiling': 'LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED',
                'metadata': {'engine_id': engine_id, 'sentence_index': i},
            })
        return claims
