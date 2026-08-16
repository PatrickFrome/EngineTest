from __future__ import annotations

from .node_native import NodeNativeAdapter
from .reference import ReferenceAdapter


class AdapterRegistry:
    """Fail-closed adapter dispatch with explicit implementation disclosure."""

    MODES = {
        "NODE_NATIVE": (NodeNativeAdapter, "NATIVE_LOCAL", "REAL_EXECUTOR"),
        "NODE_UNIFIED": (NodeNativeAdapter, "NATIVE_LOCAL", "REAL_EXECUTOR"),
        "PYTHON_REFERENCE_CONTRACT": (ReferenceAdapter, "REFERENCE_SIMULATION", "CLEAN_ROOM_CONTRACT_STUB"),
    }

    def create(self, record, lineage_root):
        mode = record.get("execution_mode")
        if mode not in self.MODES:
            raise ValueError(f"UNKNOWN_ADAPTER_MODE:{mode}")
        adapter, _, _ = self.MODES[mode]
        return adapter(record, lineage_root)

    def disclosure(self, record):
        mode = record.get("execution_mode")
        if mode not in self.MODES:
            raise ValueError(f"UNKNOWN_ADAPTER_MODE:{mode}")
        _, kind, level = self.MODES[mode]
        return {"adapter_kind": kind, "implementation_level": level, "silent_fallback_allowed": False}
