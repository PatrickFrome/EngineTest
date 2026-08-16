from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Protocol

from .external import ConnectorReceipt, require_write_intent


class DriveTransport(Protocol):
    def find_by_digest(self, digest: str) -> Mapping[str, Any] | None: ...
    def upload_manifest(self, manifest: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def upload_artifact(self, path: Path, name: str, digest: str) -> Mapping[str, Any]: ...
    def read_digest(self, remote_id: str) -> str | None: ...


class DriveArtifactAdapter:
    connector_id = "google_drive"

    def __init__(self, transport: DriveTransport):
        self._transport = transport

    @staticmethod
    def sha256_file(path: str | Path) -> str:
        target = Path(path)
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def replicate(self, path: str | Path, *, write_intent: str | None) -> ConnectorReceipt:
        require_write_intent("UPLOAD_ARTIFACT", write_intent)
        target = Path(path)
        digest = self.sha256_file(target)
        existing = self._transport.find_by_digest(digest)
        if existing and str(existing.get("digest")) == digest:
            return ConnectorReceipt.create(
                connector_id=self.connector_id,
                operation="UPLOAD_ARTIFACT",
                object_hash=digest,
                status="PASS",
                reason_code="DEDUPED",
                remote_id=str(existing.get("remote_id")) if existing.get("remote_id") else None,
            )

        manifest = {
            "name": target.name,
            "sha256": digest,
            "bytes": target.stat().st_size,
            "content_addressed": True,
        }
        self._transport.upload_manifest(manifest)
        uploaded = dict(self._transport.upload_artifact(target, target.name, digest))
        remote_id = str(uploaded.get("remote_id")) if uploaded.get("remote_id") is not None else None
        remote_digest = self._transport.read_digest(remote_id or "")
        if remote_digest != digest:
            return ConnectorReceipt.create(
                connector_id=self.connector_id,
                operation="UPLOAD_ARTIFACT",
                object_hash=digest,
                status="REJECTED",
                reason_code="REMOTE_DIGEST_MISMATCH",
                remote_id=remote_id,
                metadata={"observed_digest": str(remote_digest or "")},
            )
        return ConnectorReceipt.create(
            connector_id=self.connector_id,
            operation="UPLOAD_ARTIFACT",
            object_hash=digest,
            status="PASS",
            reason_code="OK",
            remote_id=remote_id,
        )
