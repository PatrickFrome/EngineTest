from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .providers.local_tools import ToolState


@dataclass(frozen=True)
class SwarmNode:
    node_id: str
    workspace_backend: str
    agent: str
    model_runtime: str
    required_tools: tuple[str, ...]
    external: bool
    independence_group: str
    available: bool
    reason: str = ""


def _node(
    tools: Mapping[str, ToolState],
    *,
    node_id: str,
    workspace_backend: str,
    agent: str,
    required_tools: tuple[str, ...],
    independence_group: str,
    external: bool = False,
    extra_ready: bool = True,
    extra_reason: str = "",
) -> SwarmNode:
    missing = tuple(name for name in required_tools if not tools.get(name) or not tools[name].available)
    available = not missing and extra_ready
    if missing:
        reason = "missing:" + ",".join(missing)
    elif not extra_ready:
        reason = extra_reason or "not_configured"
    else:
        reason = ""
    return SwarmNode(
        node_id=node_id,
        workspace_backend=workspace_backend,
        agent=agent,
        model_runtime="ollama",
        required_tools=required_tools,
        external=external,
        independence_group=independence_group,
        available=available,
        reason=reason,
    )


def compose_default_swarm(
    tools: Mapping[str, ToolState],
    *,
    coder_workspace_configured: bool = False,
) -> tuple[SwarmNode, ...]:
    """Return the default zero-spend Stage B swarm topology.

    Availability is declarative: this function never installs tools, starts
    services, authenticates, or creates remote workspaces.
    """
    return (
        _node(
            tools,
            node_id="local-opencode-ollama",
            workspace_backend="local-worktree",
            agent="opencode",
            required_tools=("opencode", "ollama"),
            independence_group="local-opencode",
        ),
        _node(
            tools,
            node_id="local-openhands-ollama",
            workspace_backend="local-worktree",
            agent="openhands",
            required_tools=("openhands", "ollama"),
            independence_group="local-openhands",
        ),
        _node(
            tools,
            node_id="devpod-opencode-ollama",
            workspace_backend="devpod",
            agent="opencode",
            required_tools=("devpod", "opencode", "ollama"),
            independence_group="devpod-opencode",
        ),
        _node(
            tools,
            node_id="devpod-openhands-ollama",
            workspace_backend="devpod",
            agent="openhands",
            required_tools=("devpod", "openhands", "ollama"),
            independence_group="devpod-openhands",
        ),
        _node(
            tools,
            node_id="coder-opencode-ollama",
            workspace_backend="coder",
            agent="opencode",
            required_tools=("coder", "opencode", "ollama"),
            independence_group="coder-opencode",
            external=True,
            extra_ready=coder_workspace_configured,
            extra_reason="coder_workspace_not_configured",
        ),
        _node(
            tools,
            node_id="coder-openhands-ollama",
            workspace_backend="coder",
            agent="openhands",
            required_tools=("coder", "openhands", "ollama"),
            independence_group="coder-openhands",
            external=True,
            extra_ready=coder_workspace_configured,
            extra_reason="coder_workspace_not_configured",
        ),
    )
