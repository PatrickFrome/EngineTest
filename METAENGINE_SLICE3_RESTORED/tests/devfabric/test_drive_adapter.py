from pathlib import Path

from metaengine.devfabric.providers.drive import DriveArtifactAdapter


class FakeDrive:
    def __init__(self, *, existing=None, remote_digest=None):
        self.existing = existing
        self.remote_digest = remote_digest
        self.calls = []

    def find_by_digest(self, digest):
        self.calls.append(("find", digest))
        return self.existing

    def upload_manifest(self, manifest):
        self.calls.append(("manifest", dict(manifest)))
        return {"remote_id": "manifest-1"}

    def upload_artifact(self, path, name, digest):
        self.calls.append(("artifact", str(path), name, digest))
        return {"remote_id": "file-1"}

    def read_digest(self, remote_id):
        self.calls.append(("read_digest", remote_id))
        return self.remote_digest


def write_artifact(tmp_path: Path) -> Path:
    path = tmp_path / "capsule.zip"
    path.write_bytes(b"portable-capsule")
    return path


def test_existing_digest_is_deduped_without_upload(tmp_path: Path):
    path = write_artifact(tmp_path)
    expected = DriveArtifactAdapter.sha256_file(path)
    drive = FakeDrive(existing={"remote_id": "existing-1", "digest": expected})
    receipt = DriveArtifactAdapter(drive).replicate(
        path, write_intent="UPLOAD_ARTIFACT"
    )
    assert receipt.status == "PASS"
    assert receipt.reason_code == "DEDUPED"
    assert receipt.remote_id == "existing-1"
    assert [c[0] for c in drive.calls] == ["find"]


def test_manifest_is_uploaded_before_artifact_and_digest_is_verified(tmp_path: Path):
    path = write_artifact(tmp_path)
    expected = DriveArtifactAdapter.sha256_file(path)
    drive = FakeDrive(remote_digest=expected)
    receipt = DriveArtifactAdapter(drive).replicate(
        path, write_intent="UPLOAD_ARTIFACT"
    )
    assert receipt.status == "PASS"
    assert [c[0] for c in drive.calls] == ["find", "manifest", "artifact", "read_digest"]
    manifest = drive.calls[1][1]
    assert manifest["sha256"] == expected
    assert manifest["bytes"] == path.stat().st_size


def test_post_upload_digest_mismatch_is_rejected(tmp_path: Path):
    path = write_artifact(tmp_path)
    drive = FakeDrive(remote_digest="0" * 64)
    receipt = DriveArtifactAdapter(drive).replicate(
        path, write_intent="UPLOAD_ARTIFACT"
    )
    assert receipt.status == "REJECTED"
    assert receipt.reason_code == "REMOTE_DIGEST_MISMATCH"
    assert receipt.remote_id == "file-1"
