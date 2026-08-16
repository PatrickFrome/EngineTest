from __future__ import annotations

import hashlib
import json
import os
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from ..security import scan_secret_bytes
from .codec import canonical_bytes

_MANIFEST = "devfabric/CAPSULE_MANIFEST.json"
_EXCLUDED_TOP = {
    ".git",
    ".worktrees",
    ".venv",
    "lineages",
    "release-evidence",
    "release_evidence",
    "reference-vault",
    "dist",
}
_EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", ".wrangler"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _excluded(rel: PurePosixPath) -> bool:
    parts = rel.parts
    if not parts:
        return True
    if parts[0] in _EXCLUDED_TOP:
        return True
    if any(part in _EXCLUDED_DIR_NAMES for part in parts):
        return True
    text = rel.as_posix()
    if text.startswith("devfabric/state/") and text != "devfabric/state/.gitkeep":
        return True
    if text.startswith("devfabric/artifacts/candidates/"):
        return True
    if text.startswith("devfabric/artifacts/reports/runtime/"):
        return True
    name = parts[-1]
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if name == ".dev.vars" or (name.startswith(".dev.vars.") and name != ".dev.vars.example"):
        return True
    if text == _MANIFEST:
        return True
    if text in {
        "devfabric/artifacts/manifests/stage-a-gate.json",
        "devfabric/artifacts/manifests/stage-b-gate.json",
        "devfabric/artifacts/manifests/stage-c-gate.json",
        "devfabric/artifacts/manifests/stage-d-gate.json",
        "devfabric/artifacts/manifests/stage-d6-gate.json",
        "devfabric/artifacts/manifests/stage-d6-g0-gate.json",
        "devfabric/artifacts/manifests/stage-d6-g1-gate.json",
    }:
        return True
    return False


def _payload_paths(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = PurePosixPath(path.relative_to(root).as_posix())
        if _excluded(rel):
            continue
        paths.append(path)
    return tuple(sorted(paths, key=lambda p: p.relative_to(root).as_posix()))


def _mode(path: Path) -> int:
    return 0o755 if os.access(path, os.X_OK) else 0o644


def _root_hash(rows: Iterable[dict[str, object]]) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(str(row["path"]).encode())
        h.update(b"\0")
        h.update(str(row["sha256"]).encode())
        h.update(b"\0")
        h.update(str(row["size"]).encode())
        h.update(b"\0")
        h.update(str(row["mode"]).encode())
        h.update(b"\n")
    return h.hexdigest()


def _zip_info(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100000 | mode) << 16
    return info


def build_control_capsule(root: str | Path, out: str | Path) -> dict[str, object]:
    root = Path(root).resolve()
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    binding = json.loads((root / "devfabric" / "source_binding.json").read_text())
    lineage_lock = root / "devfabric" / "LINEAGE_LOCK_SHA256.txt"
    if not lineage_lock.is_file():
        raise FileNotFoundError(lineage_lock)
    lineage_lines = [line for line in lineage_lock.read_text().splitlines() if line.strip()]

    rows: list[dict[str, object]] = []
    payload: list[tuple[str, bytes, int]] = []
    secret_hits: list[dict[str, str]] = []
    for path in _payload_paths(root):
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        mode = _mode(path)
        rows.append({"path": rel, "sha256": _sha256_bytes(data), "size": len(data), "mode": mode})
        payload.append((rel, data, mode))
        secret_hits.extend(scan_secret_bytes(rel, data))
    if secret_hits:
        raise RuntimeError(f"secret-like content detected in CONTROL payload: {secret_hits[:5]}")

    payload_root = _root_hash(rows)
    manifest = {
        "manifest_version": "METAENGINE-DEVFABRIC-CONTROL-1",
        "source_artifact_sha256": binding["artifact_sha256"],
        "release_version": binding["release_version"],
        "payload_root_sha256": payload_root,
        "file_count": len(rows),
        "lineage_file_count": len(lineage_lines),
        "lineage_lock_sha256": _sha256_file(lineage_lock),
        "excludes_lineage_bytes": True,
        "files": rows,
    }
    manifest_bytes = canonical_bytes(manifest)

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, data, mode in payload:
            zf.writestr(_zip_info(rel, mode), data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        zf.writestr(_zip_info(_MANIFEST, 0o644), manifest_bytes, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    return {
        "status": "PASS",
        "capsule_path": str(out),
        "capsule_sha256": _sha256_file(out),
        "payload_root_sha256": payload_root,
        "file_count": len(rows),
        "lineage_file_count": len(lineage_lines),
        "lineage_lock_sha256": manifest["lineage_lock_sha256"],
        "secret_hits": [],
    }


def verify_control_capsule(path: str | Path) -> dict[str, object]:
    path = Path(path).resolve()
    bad: list[str] = []
    missing: list[str] = []
    extra: list[str] = []
    secret_hits: list[dict[str, str]] = []
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            bad.append("DUPLICATE_ZIP_MEMBERS")
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts:
                bad.append(f"UNSAFE_PATH:{name}")
        if _MANIFEST not in names:
            return {
                "status": "FAIL",
                "capsule_sha256": _sha256_file(path),
                "bad": bad + ["MISSING_MANIFEST"],
                "missing": [],
                "extra": [],
                "secret_hits": [],
            }
        manifest = json.loads(zf.read(_MANIFEST))
        expected_rows = tuple(manifest.get("files", ()))
        expected = {str(row["path"]): row for row in expected_rows}
        actual_names = set(names) - {_MANIFEST}
        missing = sorted(set(expected) - actual_names)
        extra = sorted(actual_names - set(expected))
        actual_rows: list[dict[str, object]] = []
        for name in sorted(actual_names & set(expected)):
            data = zf.read(name)
            row = expected[name]
            actual = {
                "path": name,
                "sha256": _sha256_bytes(data),
                "size": len(data),
                "mode": int(row["mode"]),
            }
            actual_rows.append(actual)
            if actual["sha256"] != row["sha256"] or actual["size"] != row["size"]:
                bad.append(f"HASH_OR_SIZE_MISMATCH:{name}")
            secret_hits.extend(scan_secret_bytes(name, data))
        expected_root = _root_hash(expected_rows)
        actual_root = _root_hash(actual_rows) if not missing and not extra else ""
        if expected_root != manifest.get("payload_root_sha256"):
            bad.append("MANIFEST_PAYLOAD_ROOT_MISMATCH")
        if actual_root and actual_root != manifest.get("payload_root_sha256"):
            bad.append("ACTUAL_PAYLOAD_ROOT_MISMATCH")
        if any(name.startswith("lineages/") for name in actual_names):
            bad.append("LINEAGE_BYTES_EMBEDDED")
        lock_name = "devfabric/LINEAGE_LOCK_SHA256.txt"
        if lock_name not in actual_names:
            missing.append(lock_name)
        else:
            lock_bytes = zf.read(lock_name)
            if _sha256_bytes(lock_bytes) != manifest.get("lineage_lock_sha256"):
                bad.append("LINEAGE_LOCK_HASH_MISMATCH")
            lock_count = len([x for x in lock_bytes.decode("utf-8").splitlines() if x.strip()])
            if lock_count != manifest.get("lineage_file_count"):
                bad.append("LINEAGE_LOCK_COUNT_MISMATCH")

    status = "PASS" if not bad and not missing and not extra and not secret_hits else "FAIL"
    return {
        "status": status,
        "capsule_sha256": _sha256_file(path),
        "payload_root_sha256": manifest.get("payload_root_sha256"),
        "file_count": manifest.get("file_count"),
        "lineage_file_count": manifest.get("lineage_file_count"),
        "lineage_lock_sha256": manifest.get("lineage_lock_sha256"),
        "bad": sorted(set(bad)),
        "missing": sorted(set(missing)),
        "extra": sorted(set(extra)),
        "secret_hits": secret_hits,
    }


def make_gate_receipt(
    measurements: dict[str, object],
    *,
    gate_version: str = "METAENGINE-DEVFABRIC-STAGE-A-GATE-1",
) -> dict[str, object]:
    """Create a content-addressed gate receipt from measured values."""
    from .codec import canonical_digest

    payload = {
        "gate_version": gate_version,
        **measurements,
    }
    return {**payload, "receipt_hash": canonical_digest(payload)}


def verify_gate_receipt(path: str | Path) -> dict[str, object]:
    """Verify gate receipt integrity without confusing it with certification status."""
    from .codec import canonical_digest

    path = Path(path)
    try:
        receipt = json.loads(path.read_text())
    except Exception as exc:
        return {"status": "FAIL", "error": f"INVALID_JSON:{exc}"}
    stored = receipt.get("receipt_hash")
    payload = {k: v for k, v in receipt.items() if k != "receipt_hash"}
    actual = canonical_digest(payload)
    gate_version = payload.get("gate_version")
    ok = stored == actual and gate_version in {
        "METAENGINE-DEVFABRIC-STAGE-A-GATE-1",
        "METAENGINE-DEVFABRIC-STAGE-B-GATE-1",
        "METAENGINE-DEVFABRIC-STAGE-C-GATE-1",
        "METAENGINE-DEVFABRIC-STAGE-D-GATE-1",
        "METAENGINE-DEVFABRIC-STAGE-D6-GATE-1",
        "METAENGINE-DEVFABRIC-STAGE-D6-G0-GATE-1",
        "METAENGINE-DEVFABRIC-STAGE-D6-G1-GATE-1",
    }
    return {
        "status": "PASS" if ok else "FAIL",
        "receipt_hash": stored,
        "computed_hash": actual,
        "certification_status": payload.get("certification_status"),
        "gate_version": gate_version,
    }
