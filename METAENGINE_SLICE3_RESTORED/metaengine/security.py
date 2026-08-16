from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
from dataclasses import dataclass
from typing import Any

from .util import canonical_hash

IMMUTABLE_GUARDRAILS = (
    "ORIGINAL_SOURCE_IS_THE_ONLY_PRIMARY_EVIDENCE",
    "DERIVED_CONTEXT_IS_GENERATIVE_ONLY",
    "NO_TRUTH_PROMOTION_FROM_RANKING_OR_VOTING",
    "ABSTENTION_MUST_BE_PRESERVED",
    "EVERY_MUTATION_REQUIRES_A_RECEIPT",
    "SELF_UPDATE_CANNOT_MUTATE_VERIFIERS_OR_SAFETY_BOUNDARY",
)
IMMUTABLE_GUARDRAIL_HASH = canonical_hash(IMMUTABLE_GUARDRAILS)
LEGACY_INCOMPLETE_HANDOFF_GUARDRAILS_2_3 = IMMUTABLE_GUARDRAILS[:5]
LEGACY_INCOMPLETE_HANDOFF_GUARDRAIL_HASH_2_3 = canonical_hash(LEGACY_INCOMPLETE_HANDOFF_GUARDRAILS_2_3)


class SecurityViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class GuardrailReceipt:
    contract_verified: bool
    objective_acknowledged: bool
    guardrails_applied: bool
    guardrail_hash: str
    violations: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_verified": self.contract_verified,
            "objective_acknowledged": self.objective_acknowledged,
            "guardrails_applied": self.guardrails_applied,
            "guardrail_hash": self.guardrail_hash,
            "violations": list(self.violations),
        }


def verify_handoff(handoff: dict[str, Any] | None) -> GuardrailReceipt:
    if not handoff:
        raise SecurityViolation("HANDOFF_REQUIRED")
    claimed = handoff.get("handoff_hash")
    payload = {key: value for key, value in handoff.items() if key != "handoff_hash"}
    if not claimed or canonical_hash(payload) != claimed:
        raise SecurityViolation("HANDOFF_INTEGRITY_FAILURE")
    supplied = tuple(handoff.get("guardrails", ()))
    missing = tuple(rule for rule in IMMUTABLE_GUARDRAILS if rule not in supplied)
    if missing:
        raise SecurityViolation("HANDOFF_GUARDRAIL_MISSING:" + ",".join(missing))
    if not str(handoff.get("objective", "")).strip():
        raise SecurityViolation("HANDOFF_OBJECTIVE_MISSING")
    return GuardrailReceipt(True, True, True, IMMUTABLE_GUARDRAIL_HASH)


def legacy_guardrail_set_status(supplied: Any) -> str:
    normalized = tuple(supplied or ())
    if normalized == IMMUTABLE_GUARDRAILS:
        return "CURRENT_COMPLETE"
    if normalized == LEGACY_INCOMPLETE_HANDOFF_GUARDRAILS_2_3:
        return "LEGACY_INCOMPLETE_READ_ONLY"
    return "UNKNOWN"


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)postgres(?:ql)?://[^\s]+"),
)

SECRET_BYTE_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("PRIVATE_KEY", re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("OPENAI_STYLE_KEY", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("PASSWORD_POSTGRES_URI", re.compile(rb"postgres(?:ql)?://[^:/\s]+:[^@/\s]+@", re.IGNORECASE)),
)


def scan_secret_bytes(path: str, data: bytes) -> tuple[dict[str, str], ...]:
    return tuple(
        {"path": path, "pattern": pattern_id}
        for pattern_id, pattern in SECRET_BYTE_PATTERNS
        if pattern.search(data)
    )


def redact_secrets(text: str) -> str:
    value = text
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def classify_untrusted_input(text: str) -> dict[str, Any]:
    markers = {
        "instruction_override": re.compile(r"(?i)\b(ignore|disregard|override|forget)\b.{0,50}\b(instruction|rule|system|guardrail)s?\b"),
        "credential_request": re.compile(r"(?i)\b(reveal|print|send|extract)\b.{0,50}\b(secret|token|password|api.?key)s?\b"),
        "tool_escalation": re.compile(r"(?i)\b(run|execute|call|invoke)\b.{0,50}\b(shell|terminal|tool|command)s?\b"),
    }
    detected = sorted(name for name, pattern in markers.items() if pattern.search(text))
    result = {
        "classification_version": "16X-UNTRUSTED-INPUT-BOUNDARY-2.3",
        "detected_markers": detected,
        "risk": "ADVERSARIAL_CONTENT_PRESENT" if detected else "NO_LEXICAL_INJECTION_MARKER",
        "control_plane_authority": False,
        "tool_permission_effect": "NONE",
        "policy_mutation_effect": "NONE",
    }
    result["classification_hash"] = canonical_hash(result)
    return result


def verify_release_file(project_root, path) -> str:
    """Fail closed if an executable lineage file differs from the signed release inventory."""
    project_root = os.path.abspath(os.fspath(project_root))
    absolute = os.path.abspath(os.fspath(path))
    relative = os.path.relpath(absolute, project_root).replace(os.sep, "/")
    expected = None
    with open(os.path.join(project_root, "SHA256SUMS.txt"), encoding="utf-8") as handle:
        for line in handle:
            digest, separator, candidate = line.rstrip("\n").partition("  ")
            if separator and candidate == relative:
                expected = digest
                break
    if not expected:
        raise SecurityViolation(f"RELEASE_INVENTORY_ENTRY_MISSING:{relative}")
    with open(absolute, "rb") as handle:
        actual = hashlib.sha256(handle.read()).hexdigest()
    if actual != expected:
        raise SecurityViolation(f"LINEAGE_INTEGRITY_FAILURE:{relative}")
    return actual


def run_sandboxed(command, cwd, timeout: float, **kwargs):
    """Bound a native subprocess and kill its process group on timeout.

    This is a resource boundary, not a complete OS/network sandbox. External tools remain denied
    by adapter capability policy unless an explicit real-adapter grant is installed.
    """
    popen_kwargs = {
        "cwd": cwd,
        "text": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "start_new_session": True,
        **kwargs,
    }
    process = subprocess.Popen(command, **popen_kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        raise TimeoutError(f"PROCESS_TREE_TIMEOUT:{timeout}s:{command[0]}")
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
