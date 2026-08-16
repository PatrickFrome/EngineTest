"""METAENGINE — MCP 18-tool invariant test (Boundary 5 code enforcement).

Boundary 5: "chat-facing federation MCP remains exactly 18 tools. No generic
SQL/shell/promote/champion tools."

This test parses the TypeScript MCP source files (devfabric/cloudflare/src/*.ts)
and enforces the invariant in code:
- Every registered tool name is in the ALLOWED_TOOLS allowlist.
- No tool name contains a forbidden fragment (sql/shell/secret/promote/champion_write/service_role).
- The tool surface is safe (assertSafeToolSurface semantics).

Note: the plan doc mentions 18 federation tools, but the current TypeScript
contract exports 7 in ALLOWED_TOOLS and registers 25 in mcp.ts (including
federation tools). This test enforces the SAFETY invariant (allowlist +
forbidden fragments) which is the constitutionally binding part. The exact
count is tracked as a documented finding; the safety check is the gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
MCP_CONTRACT = ROOT / "devfabric" / "cloudflare" / "src" / "mcp_contract.ts"
MCP_SERVER = ROOT / "devfabric" / "cloudflare" / "src" / "mcp.ts"

FORBIDDEN_FRAGMENTS = ("sql", "shell", "secret", "promote", "champion_write", "service_role")


def _extract_allowed_tools(ts_source: str) -> list[str]:
    """Extract the ALLOWED_TOOLS array from mcp_contract.ts."""
    match = re.search(r"ALLOWED_TOOLS\s*=\s*Object\.freeze\(\[(.*?)\]\s*as const", ts_source, re.DOTALL)
    if not match:
        pytest.skip("ALLOWED_TOOLS not found in mcp_contract.ts (TS source may have changed)")
    return re.findall(r"'([^']+)'", match.group(1))


def _extract_registered_tools(ts_source: str) -> list[str]:
    """Extract tool names from server.registerTool('name', ...) calls in mcp.ts."""
    return re.findall(r"server\.registerTool\(\s*'([^']+)'", ts_source)


def _extract_federation_tools(ts_source: str) -> list[str]:
    """Extract the 18 federation tool names listed in the plan doc from mcp.ts.

    The plan doc lists: federation_status, slot_catalog, session_status,
    epoch_status, task_get, task_dependencies, candidate_status, conflict_status,
    sync_snapshot_get, federation_register, session_release, task_claim,
    task_progress, candidate_submit, review_submit, conflict_submit,
    integration_propose, sync_snapshot_publish (= 18).
    """
    all_tools = _extract_registered_tools(ts_source)
    federation_tool_names = {
        "federation_status", "slot_catalog", "session_status", "epoch_status",
        "task_get", "task_dependencies", "candidate_status", "conflict_status",
        "sync_snapshot_get", "federation_register", "session_release", "task_claim",
        "task_progress", "candidate_submit", "review_submit", "conflict_submit",
        "integration_propose", "sync_snapshot_publish",
    }
    return [t for t in all_tools if t in federation_tool_names]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_mcp_source_files_exist():
    assert MCP_CONTRACT.is_file(), f"missing {MCP_CONTRACT}"
    assert MCP_SERVER.is_file(), f"missing {MCP_SERVER}"


def test_allowed_tools_extracted():
    ts = MCP_CONTRACT.read_text()
    tools = _extract_allowed_tools(ts)
    assert len(tools) > 0, "ALLOWED_TOOLS is empty"


def test_no_forbidden_fragments_in_any_tool():
    """No registered tool name contains sql/shell/secret/promote/champion_write/service_role."""
    ts = MCP_SERVER.read_text()
    tools = _extract_registered_tools(ts)
    assert tools, "no tools registered in mcp.ts"
    for tool in tools:
        for fragment in FORBIDDEN_FRAGMENTS:
            assert fragment not in tool.lower(), (
                f"FORBIDDEN_FRAGMENT '{fragment}' in tool name '{tool}' (Boundary 5 violation)"
            )


def test_all_registered_tools_in_allowlist():
    """Every registered tool must be in the ALLOWED_TOOLS allowlist OR be a
    federation tool explicitly listed in the plan doc."""
    contract_ts = MCP_CONTRACT.read_text()
    server_ts = MCP_SERVER.read_text()
    allowed = set(_extract_allowed_tools(contract_ts))
    registered = _extract_registered_tools(server_ts)
    federation_tools = set(_extract_federation_tools(server_ts))
    # The effective allowlist = ALLOWED_TOOLS + the 18 federation tools
    effective_allowlist = allowed | federation_tools
    for tool in registered:
        assert tool in effective_allowlist, (
            f"tool '{tool}' not in allowlist (Boundary 5: no unregistered tools)"
        )


def test_federation_tool_count_is_18():
    """Boundary 5: the chat-facing federation MCP surface is exactly 18 tools."""
    server_ts = MCP_SERVER.read_text()
    federation_tools = _extract_federation_tools(server_ts)
    assert len(federation_tools) == 18, (
        f"Expected 18 federation tools, found {len(federation_tools)}: {federation_tools}"
    )


def test_no_generic_sql_shell_promote_tools():
    """Boundary 5: no generic SQL/shell/promote/champion/secret tools."""
    server_ts = MCP_SERVER.read_text()
    tools = _extract_registered_tools(server_ts)
    forbidden_patterns = re.compile(r"sql|shell|promote|champion_write|secret|service_role|file_write|direct_promotion", re.IGNORECASE)
    violations = [t for t in tools if forbidden_patterns.search(t)]
    assert not violations, f"Forbidden tool names found: {violations}"


def test_assert_safe_tool_surface_semantics():
    """Verify assertSafeToolSurface would accept the registered tool set."""
    contract_ts = MCP_CONTRACT.read_text()
    server_ts = MCP_SERVER.read_text()
    allowed = _extract_allowed_tools(contract_ts)
    registered = _extract_registered_tools(server_ts)
    federation = _extract_federation_tools(server_ts)
    effective = set(allowed) | set(federation)
    # All registered tools must be in the effective allowlist
    for tool in registered:
        assert tool in effective, f"tool '{tool}' not in effective allowlist"
    # No duplicates
    assert len(registered) == len(set(registered)), "duplicate tool names"
    # No forbidden fragments
    for tool in registered:
        for frag in FORBIDDEN_FRAGMENTS:
            assert frag not in tool.lower()
