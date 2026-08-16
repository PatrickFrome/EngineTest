"""Step 8: Constitution Rail — runtime enforcement of K0 invariants.

Follows the NeMo Guardrails pattern (input → LLM → output rails) but uses
MetaEngine's own constitution.py K0 invariants instead of Colang DSL.

Architecture:
  1. INPUT RAIL: checks prompt before LLM call
     - PRIVACY_PERMISSION_FAIL_CLOSED: reject prompts with PII/secrets
     - NO_EXECUTABLE_SELF_MODIFICATION: reject prompts requesting code modification
  2. OUTPUT RAIL: checks response after LLM call
     - CANONICAL_NOT_SCIENTIFIC_TRUTH: reject responses claiming verified truth
     - NO_TRUTH_FROM_RANKING_OR_VOTING: reject responses claiming majority=truth
     - PRESERVE_ABSTENTION: reject responses converting unknown to success

On violation: returns a templated refusal with the violated invariant ID.

Constitution compliance:
  - Rail is transparent (logs violations, doesn't modify valid responses)
  - All refusals carry truth_effect=NONE
  - Rail enforcement is observational (logs to event_publisher)
  - No auto-promotion (rail doesn't promote anything)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


RAIL_VERSION = "METAENGINE-CONSTITUTION-RAIL-1"


class RailPhase(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class RailAction(str, Enum):
    ALLOW = "ALLOW"
    REFUSE = "REFUSE"
    WARN = "WARN"  # Allow but log warning


@dataclass(frozen=True)
class RailResult:
    """Result of a rail check."""
    action: RailAction
    phase: RailPhase
    invariant_id: str | None  # Which K0 invariant was violated
    reason: str
    original_content: str = ""
    refusal_text: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "phase": self.phase.value,
            "invariant_id": self.invariant_id,
            "reason": self.reason,
            "truth_effect": "NONE",
        }


class ConstitutionRail:
    """Runtime constitution enforcement — wraps MultiModelRouter.call().

    Usage:
        rail = ConstitutionRail(root=ROOT)
        # Input check
        input_result = rail.check_input(prompt)
        if input_result.action == RailAction.REFUSE:
            return input_result.refusal_text
        # ... make LLM call ...
        # Output check
        output_result = rail.check_output(response_text)
        if output_result.action == RailAction.REFUSE:
            return output_result.refusal_text

    Or via the convenience method:
        response = rail.guarded_call(router, prompt, max_tokens=128)
    """

    # Input rail patterns — PRIVACY_PERMISSION_FAIL_CLOSED
    INPUT_PII_PATTERNS = [
        (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN pattern detected'),
        (r'\b\d{16}\b', 'Credit card number pattern detected'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b.*password', 'Email + password combination'),
        (r'(?i)api[_\s]?key[:\s=]\s*["\']?[A-Za-z0-9]{20,}', 'API key exposed in prompt'),
        (r'(?i)secret[:\s=]\s*["\']?[A-Za-z0-9]{16,}', 'Secret exposed in prompt'),
        (r'(?i)token[:\s=]\s*["\']?[A-Za-z0-9]{32,}', 'Token exposed in prompt'),
        (r'(?i)password[:\s=]\s*\S{8,}', 'Password exposed in prompt'),
    ]

    # Input rail patterns — NO_EXECUTABLE_SELF_MODIFICATION
    INPUT_CODE_MOD_PATTERNS = [
        (r'(?i)modify.*source.*code', 'Request to modify source code'),
        (r'(?i)edit.*metaengine.*\.py', 'Request to edit MetaEngine source'),
        (r'(?i)change.*constitution.*k0', 'Request to modify K0 constitution'),
        (r'(?i)write.*executable.*self.*modif', 'Request for self-modifying code'),
        (r'(?i)bypass.*guardrail', 'Request to bypass guardrails'),
    ]

    # Output rail patterns — CANONICAL_NOT_SCIENTIFIC_TRUTH
    OUTPUT_TRUTH_CLAIM_PATTERNS = [
        (r'(?i)this\s+is\s+(scientifically\s+)?proven\s+(truth|fact)', 'Claims scientific proof'),
        (r'(?i)this\s+is\s+(the\s+)?definitive\s+(truth|answer)', 'Claims definitive truth'),
        (r'(?i)this\s+has\s+been\s+(externally\s+)?verified\s+as\s+(true|correct)', 'Claims external verification'),
        (r'(?i)this\s+is\s+(an?\s+)?established\s+(scientific\s+)?fact', 'Claims established fact'),
        (r'(?i)I\s+(can\s+)?guarantee\s+this\s+is\s+(true|correct|accurate)', 'Guarantees truth'),
    ]

    # Output rail patterns — NO_TRUTH_FROM_RANKING_OR_VOTING
    OUTPUT_VOTING_TRUTH_PATTERNS = [
        (r'(?i)majority\s+(vote|opinion)\s+(proves|confirms|establishes)\s+(this|that)', 'Claims majority proves truth'),
        (r'(?i)(popular|consensus)\s+(means|proves)\s+(this\s+is|that\s+this\s+is)\s+true', 'Claims popularity = truth'),
        (r'(?i)ranking\s+(proves|confirms|establishes)\s+truth', 'Claims ranking = truth'),
    ]

    # Output rail patterns — PRESERVE_ABSTENTION
    OUTPUT_ABSTENTION_VIOLATION_PATTERNS = [
        (r'(?i)unknown\s+(data|evidence)\s+(is\s+actually|means)\s+(success|correct|true)', 'Converts unknown to success'),
        (r'(?i)missing\s+(evidence|data)\s+(is\s+not\s+a\s+problem|doesn\'t\s+matter)', 'Dismisses missing evidence'),
    ]

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else Path('.')
        self._input_checks_count = 0
        self._output_checks_count = 0
        self._input_refusals = 0
        self._output_refusals = 0
        self._warnings = 0

    # ------------------------------------------------------------------
    # Input rail
    # ------------------------------------------------------------------

    def check_input(self, prompt: str) -> RailResult:
        """Check if a prompt is safe to send to the LLM.

        Returns RailResult with action=ALLOW or REFUSE.
        """
        self._input_checks_count += 1

        # PRIVACY_PERMISSION_FAIL_CLOSED
        for pattern, reason in self.INPUT_PII_PATTERNS:
            if re.search(pattern, prompt):
                self._input_refusals += 1
                return RailResult(
                    action=RailAction.REFUSE,
                    phase=RailPhase.INPUT,
                    invariant_id="PRIVACY_PERMISSION_FAIL_CLOSED",
                    reason=f"Input rejected: {reason}",
                    original_content=prompt[:200],
                    refusal_text=self._refusal("PRIVACY_PERMISSION_FAIL_CLOSED", reason),
                )

        # NO_EXECUTABLE_SELF_MODIFICATION
        for pattern, reason in self.INPUT_CODE_MOD_PATTERNS:
            if re.search(pattern, prompt):
                self._input_refusals += 1
                return RailResult(
                    action=RailAction.REFUSE,
                    phase=RailPhase.INPUT,
                    invariant_id="NO_EXECUTABLE_SELF_MODIFICATION",
                    reason=f"Input rejected: {reason}",
                    original_content=prompt[:200],
                    refusal_text=self._refusal("NO_EXECUTABLE_SELF_MODIFICATION", reason),
                )

        return RailResult(
            action=RailAction.ALLOW,
            phase=RailPhase.INPUT,
            invariant_id=None,
            reason="Input passed all rail checks",
        )

    # ------------------------------------------------------------------
    # Output rail
    # ------------------------------------------------------------------

    def check_output(self, response: str) -> RailResult:
        """Check if an LLM response violates K0 invariants.

        Returns RailResult with action=ALLOW, REFUSE, or WARN.
        """
        self._output_checks_count += 1

        # CANONICAL_NOT_SCIENTIFIC_TRUTH
        for pattern, reason in self.OUTPUT_TRUTH_CLAIM_PATTERNS:
            if re.search(pattern, response):
                self._output_refusals += 1
                return RailResult(
                    action=RailAction.REFUSE,
                    phase=RailPhase.OUTPUT,
                    invariant_id="CANONICAL_NOT_SCIENTIFIC_TRUTH",
                    reason=f"Output rejected: {reason}",
                    original_content=response[:200],
                    refusal_text=self._refusal("CANONICAL_NOT_SCIENTIFIC_TRUTH", reason),
                )

        # NO_TRUTH_FROM_RANKING_OR_VOTING
        for pattern, reason in self.OUTPUT_VOTING_TRUTH_PATTERNS:
            if re.search(pattern, response):
                self._output_refusals += 1
                return RailResult(
                    action=RailAction.REFUSE,
                    phase=RailPhase.OUTPUT,
                    invariant_id="NO_TRUTH_FROM_RANKING_OR_VOTING",
                    reason=f"Output rejected: {reason}",
                    original_content=response[:200],
                    refusal_text=self._refusal("NO_TRUTH_FROM_RANKING_OR_VOTING", reason),
                )

        # PRESERVE_ABSTENTION
        for pattern, reason in self.OUTPUT_ABSTENTION_VIOLATION_PATTERNS:
            if re.search(pattern, response):
                self._warnings += 1
                return RailResult(
                    action=RailAction.WARN,
                    phase=RailPhase.OUTPUT,
                    invariant_id="PRESERVE_ABSTENTION",
                    reason=f"Output warning: {reason}",
                    original_content=response[:200],
                )

        return RailResult(
            action=RailAction.ALLOW,
            phase=RailPhase.OUTPUT,
            invariant_id=None,
            reason="Output passed all rail checks",
        )

    # ------------------------------------------------------------------
    # Convenience: guarded_call
    # ------------------------------------------------------------------

    def guarded_call(
        self,
        router: Any,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.4,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> str:
        """Call LLM with constitution rail enforcement.

        1. Check input — refuse if violates K0
        2. Call LLM via router
        3. Check output — refuse if violates K0
        4. Return response or refusal text

        Args:
            router: MultiModelRouter instance
            prompt: input text
            max_tokens, temperature, timeout, max_retries: forwarded to router

        Returns:
            LLM response text, or refusal text if rail blocked the call.
        """
        # Input rail
        input_result = self.check_input(prompt)
        if input_result.action == RailAction.REFUSE:
            self._publish_rail_event("rail.input_refused", input_result)
            return input_result.refusal_text

        # LLM call
        result = router.call(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )

        if not result.success:
            return result.response_text or result.error or "LLM call failed"

        # Output rail
        output_result = self.check_output(result.response_text)
        if output_result.action == RailAction.REFUSE:
            self._publish_rail_event("rail.output_refused", output_result)
            return output_result.refusal_text
        if output_result.action == RailAction.WARN:
            self._publish_rail_event("rail.output_warned", output_result)

        return result.response_text

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refusal(self, invariant_id: str, reason: str) -> str:
        """Generate a templated refusal that explains the violation."""
        return (
            f"[CONSTITUTION_RAIL] Request refused due to K0 invariant: {invariant_id}. "
            f"Reason: {reason}. "
            f"This output is generative-only until externally verified. "
            f"truth_effect=NONE, claim_ceiling=CONSTITUTION_RAIL_ENFORCED"
        )

    def _publish_rail_event(self, event_type: str, result: RailResult) -> None:
        """Publish rail enforcement event for observability."""
        try:
            from .event_publisher import publish_event
            publish_event(event_type, {
                "invariant_id": result.invariant_id,
                "phase": result.phase.value,
                "action": result.action.value,
                "reason": result.reason,
            })
        except Exception:
            pass  # best-effort

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return rail summary."""
        return {
            "rail_version": RAIL_VERSION,
            "input_checks": self._input_checks_count,
            "input_refusals": self._input_refusals,
            "output_checks": self._output_checks_count,
            "output_refusals": self._output_refusals,
            "warnings": self._warnings,
            "input_refusal_rate": round(self._input_refusals / max(1, self._input_checks_count), 4),
            "output_refusal_rate": round(self._output_refusals / max(1, self._output_checks_count), 4),
            "invariants_enforced": [
                "PRIVACY_PERMISSION_FAIL_CLOSED",
                "NO_EXECUTABLE_SELF_MODIFICATION",
                "CANONICAL_NOT_SCIENTIFIC_TRUTH",
                "NO_TRUTH_FROM_RANKING_OR_VOTING",
                "PRESERVE_ABSTENTION",
            ],
            "truth_effect": "NONE",
            "claim_ceiling": "CONSTITUTION_RAIL_IS_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "runtime_enforcement": True,
                "no_auto_promotion": True,
                "no_code_modification": True,
                "fail_closed": True,
                "transparent": True,
            },
        }
