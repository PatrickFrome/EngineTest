from metaengine.devfabric.providers.local_tools import ToolState
from metaengine.devfabric.swarm import compose_default_swarm


def inventory(missing=()):
    names=('coder','devpod','openhands','agent-canvas','ollama','opencode')
    return {n:ToolState(n,n not in missing,'AVAILABLE' if n not in missing else 'UNAVAILABLE',path=f'/bin/{n}' if n not in missing else None,version='1') for n in names}


def test_swarm_composes_multiple_independent_nodes():
    nodes=compose_default_swarm(inventory(),coder_workspace_configured=True)
    ids={n.node_id for n in nodes if n.available}
    assert {'local-opencode-ollama','local-openhands-ollama','devpod-opencode-ollama','devpod-openhands-ollama','coder-opencode-ollama','coder-openhands-ollama'} <= ids
    assert len({n.independence_group for n in nodes if n.available}) >= 4


def test_missing_component_prunes_only_dependent_nodes():
    nodes=compose_default_swarm(inventory({'coder'}),coder_workspace_configured=True)
    available={n.node_id for n in nodes if n.available}
    assert 'local-opencode-ollama' in available
    assert 'devpod-openhands-ollama' in available
    assert not any(x.startswith('coder-') for x in available)
