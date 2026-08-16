"""METAENGINE — networked transport client for the local federation shadow store.

Implements :class:`metaengine.devfabric.providers.supabase.SupabaseTransport`
(and the subset of :class:`FederationRpcTransport` needed for read-only use)
by issuing HTTP JSON-RPC calls to the local federation shadow store server.

This lets the existing :class:`SupabaseCanonicalAdapter` consume the shadow
store unchanged. Read methods are live network queries; mutation methods are
fail-closed (the adapter is constructed ``read_only=True`` and the transport
also refuses mutations independent of the adapter flag).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping


class FederationStoreTransportError(RuntimeError):
    pass


class NetworkedFederationTransport:
    """A :class:`SupabaseTransport` backed by the local shadow store server."""

    connector_id = "federation-shadow-store"
    store_kind = "LOCAL_FEDERATION_SHADOW_STORE"

    def __init__(self, base_url: str, *, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = float(timeout)

    # -- internal RPC ----------------------------------------------------

    def _rpc(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        envelope = {"method": method, "params": dict(params or {})}
        body = json.dumps(envelope, sort_keys=True).encode("utf-8")
        req = urllib.request.Request(
            self._base_url + "/rpc",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                err = json.loads(exc.read().decode("utf-8"))
            except Exception:
                err = {"error": {"code": "HTTP_ERROR", "message": str(exc)}}
            raise FederationStoreTransportError(
                f"RPC {method} failed: {err.get('error', err)}"
            ) from exc
        except urllib.error.URLError as exc:
            raise FederationStoreTransportError(
                f"RPC {method} unreachable: {exc.reason}"
            ) from exc
        if "error" in payload:
            raise FederationStoreTransportError(
                f"RPC {method} error: {payload['error']}"
            )
        return payload.get("result")

    # -- SupabaseTransport read methods ----------------------------------

    def read_current_checkpoint(self) -> Mapping[str, Any]:
        return self._rpc("read_current_checkpoint")

    def read_champion(self) -> Mapping[str, Any]:
        return self._rpc("read_champion")

    def read_store_manifest(self) -> Mapping[str, Any]:
        return self._rpc("read_store_manifest")

    # -- mutation methods: fail-closed by construction --------------------

    def append_development_receipt(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        from ..devfabric.providers.external import ConnectorPolicyError

        raise ConnectorPolicyError(
            "CANONICAL_MUTATION_BLOCKED",
            "federation shadow store transport is read-only: append refused",
        )

    def propose_checkpoint(
        self, payload: Mapping[str, Any], expected_parent: str
    ) -> Mapping[str, Any]:
        from ..devfabric.providers.external import ConnectorPolicyError

        raise ConnectorPolicyError(
            "CANONICAL_MUTATION_BLOCKED",
            "federation shadow store transport is read-only: propose refused",
        )

    def call_rpc(self, rpc_name: str, params: Mapping[str, object]) -> object:
        # Generic RPC surface is intentionally NOT exposed (Boundary 5: no
        # generic SQL/shell tool). Only the typed read methods above.
        raise FederationStoreTransportError(
            "GENERIC_RPC_NOT_EXPOSED: only typed read methods are available"
        )
