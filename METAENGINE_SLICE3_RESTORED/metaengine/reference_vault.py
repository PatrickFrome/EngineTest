from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from .architecture_sources import (
    ArchitectureSourceValidationError,
    BlobDescriptor,
    SourcePack,
)
from .devfabric.codec import canonical_digest
from .security import scan_secret_bytes

VERIFICATION_RECEIPT_VERSION = "REFERENCE-VAULT-VERIFICATION-1"
_SHA256_LENGTH = 64


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ArchitectureSourceValidationError(code, detail)


def _valid_sha256(value: str) -> bool:
    return len(value) == _SHA256_LENGTH and all(char in "0123456789abcdef" for char in value)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob_id(data: bytes, expected_length: int) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    if expected_length == 40:
        return hashlib.sha1(payload, usedforsecurity=False).hexdigest()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class VaultLimits:
    max_files: int = 128
    max_total_bytes: int = 16 * 1024 * 1024
    max_file_bytes: int = 4 * 1024 * 1024

    def __post_init__(self) -> None:
        values = (self.max_files, self.max_total_bytes, self.max_file_bytes)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            _fail("VAULT_LIMIT_INVALID")


@dataclass(frozen=True)
class StagedSourceFile:
    path: Path
    relative_path: str
    media_type: str
    git_blob_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))


@dataclass(frozen=True)
class VaultFinding:
    code: str
    relative_path: str

    @classmethod
    def create(cls, *, code: str, relative_path: str) -> VaultFinding:
        code = str(code).strip()
        relative_path = str(relative_path).strip()
        if not code:
            _fail("VAULT_FINDING_CODE_REQUIRED")
        if not relative_path:
            _fail("VAULT_FINDING_PATH_REQUIRED")
        return cls(code=code, relative_path=relative_path)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> VaultFinding:
        return cls.create(**dict(value))

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "relative_path": self.relative_path}


@dataclass(frozen=True)
class VaultVerificationReceipt:
    receipt_version: str
    source_id: str
    pack_root_sha256: str
    status: str
    verified_blob_count: int
    verified_total_bytes: int
    findings: tuple[VaultFinding, ...]
    receipt_sha256: str

    @staticmethod
    def _payload(
        *,
        receipt_version: str,
        source_id: str,
        pack_root_sha256: str,
        status: str,
        verified_blob_count: int,
        verified_total_bytes: int,
        findings: tuple[VaultFinding, ...],
    ) -> dict[str, Any]:
        return {
            "receipt_version": receipt_version,
            "source_id": source_id,
            "pack_root_sha256": pack_root_sha256,
            "status": status,
            "verified_blob_count": verified_blob_count,
            "verified_total_bytes": verified_total_bytes,
            "findings": [finding.as_dict() for finding in findings],
        }

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        pack_root_sha256: str,
        verified_blob_count: int,
        verified_total_bytes: int,
        findings: Iterable[VaultFinding],
        receipt_version: str = VERIFICATION_RECEIPT_VERSION,
    ) -> VaultVerificationReceipt:
        if receipt_version != VERIFICATION_RECEIPT_VERSION:
            _fail("VERIFICATION_RECEIPT_VERSION_UNSUPPORTED")
        if not str(source_id).strip():
            _fail("SOURCE_ID_REQUIRED")
        if not _valid_sha256(pack_root_sha256):
            _fail("PACK_DIGEST_INVALID")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (verified_blob_count, verified_total_bytes)
        ):
            _fail("VERIFICATION_COUNT_INVALID")
        ordered_findings = tuple(sorted(findings, key=lambda item: (item.relative_path, item.code)))
        status = "PASS" if not ordered_findings else "FAIL"
        normalized_source_id = str(source_id)
        payload = cls._payload(
            receipt_version=receipt_version,
            source_id=normalized_source_id,
            pack_root_sha256=pack_root_sha256,
            status=status,
            verified_blob_count=verified_blob_count,
            verified_total_bytes=verified_total_bytes,
            findings=ordered_findings,
        )
        return cls(
            receipt_version=receipt_version,
            source_id=normalized_source_id,
            pack_root_sha256=pack_root_sha256,
            status=status,
            verified_blob_count=verified_blob_count,
            verified_total_bytes=verified_total_bytes,
            findings=ordered_findings,
            receipt_sha256=canonical_digest(payload),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> VaultVerificationReceipt:
        fields = dict(value)
        expected_status = fields.pop("status", None)
        expected_hash = fields.pop("receipt_sha256", None)
        fields["findings"] = tuple(VaultFinding.from_dict(item) for item in fields.get("findings", ()))
        receipt = cls.create(**fields)
        if expected_status != receipt.status or expected_hash != receipt.receipt_sha256:
            _fail("HASH_MISMATCH", receipt.source_id)
        return receipt

    def payload(self) -> dict[str, Any]:
        return self._payload(
            receipt_version=self.receipt_version,
            source_id=self.source_id,
            pack_root_sha256=self.pack_root_sha256,
            status=self.status,
            verified_blob_count=self.verified_blob_count,
            verified_total_bytes=self.verified_total_bytes,
            findings=self.findings,
        )

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_sha256": self.receipt_sha256}


class ReferenceVault:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.blobs_root = self.root / "blobs" / "sha256"

    def blob_path(self, digest: str) -> Path:
        digest = str(digest)
        if not _valid_sha256(digest):
            _fail("BLOB_DIGEST_INVALID", digest)
        return self.blobs_root / digest

    def _ensure_storage_root(self) -> None:
        self.blobs_root.mkdir(parents=True, exist_ok=True)
        resolved = self.blobs_root.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            _fail("PATH_ESCAPE", str(self.blobs_root))
            raise AssertionError("unreachable") from exc
        if resolved != self.blobs_root:
            _fail("NON_REGULAR_FILE", str(self.blobs_root))

    @staticmethod
    def _read_staged_file(staged: StagedSourceFile, limits: VaultLimits) -> bytes:
        path = staged.path
        try:
            initial = path.lstat()
        except FileNotFoundError as exc:
            _fail("STAGED_FILE_MISSING", staged.relative_path)
            raise AssertionError("unreachable") from exc
        if path.is_symlink() or not stat.S_ISREG(initial.st_mode):
            _fail("NON_REGULAR_FILE", staged.relative_path)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as exc:
            _fail("STAGED_FILE_MISSING", staged.relative_path)
            raise AssertionError("unreachable") from exc
        except OSError as exc:
            _fail("NON_REGULAR_FILE", staged.relative_path)
            raise AssertionError("unreachable") from exc
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                _fail("NON_REGULAR_FILE", staged.relative_path)
            if before.st_size > limits.max_file_bytes:
                _fail("BYTE_LIMIT_EXCEEDED", staged.relative_path)
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(1024 * 1024, limits.max_file_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limits.max_file_bytes:
                    _fail("BYTE_LIMIT_EXCEEDED", staged.relative_path)
            after = os.fstat(descriptor)
            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or total != after.st_size
            ):
                _fail("STAGED_FILE_CHANGED", staged.relative_path)
            return b"".join(chunks)
        finally:
            os.close(descriptor)

    @staticmethod
    def _verify_existing_blob(path: Path, descriptor: BlobDescriptor) -> bool:
        if path.is_symlink():
            return False
        try:
            file_stat = path.stat()
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size != descriptor.size:
            return False
        return _sha256_bytes(path.read_bytes()) == descriptor.digest

    def _store_blob(self, descriptor: BlobDescriptor, data: bytes) -> None:
        target = self.blob_path(descriptor.digest)
        if target.exists() or target.is_symlink():
            if not self._verify_existing_blob(target, descriptor):
                _fail("HASH_MISMATCH", descriptor.relative_path)
            return
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{descriptor.digest}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            temporary_path.chmod(0o444)
            try:
                os.link(temporary_path, target)
            except FileExistsError:
                if not self._verify_existing_blob(target, descriptor):
                    _fail("HASH_MISMATCH", descriptor.relative_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def ingest(
        self,
        *,
        source_id: str,
        exact_commit_or_release: str,
        files: Iterable[StagedSourceFile],
        limits: VaultLimits | None = None,
    ) -> SourcePack:
        limits = limits or VaultLimits()
        staged_files = tuple(files)
        if not staged_files:
            _fail("SOURCE_PACK_EMPTY", str(source_id))
        if len(staged_files) > limits.max_files:
            _fail("FILE_COUNT_LIMIT_EXCEEDED", str(source_id))

        retained: list[tuple[BlobDescriptor, bytes]] = []
        total_bytes = 0
        for staged in staged_files:
            data = self._read_staged_file(staged, limits)
            total_bytes += len(data)
            if total_bytes > limits.max_total_bytes:
                _fail("BYTE_LIMIT_EXCEEDED", str(source_id))
            hits = scan_secret_bytes(staged.relative_path, data)
            if hits:
                _fail("SECRET_LIKE_CONTENT", f"{staged.relative_path}:{hits[0]['pattern']}")
            if staged.git_blob_id is not None and _git_blob_id(
                data,
                len(staged.git_blob_id),
            ) != staged.git_blob_id:
                _fail("GIT_BLOB_ID_MISMATCH", staged.relative_path)
            descriptor = BlobDescriptor.create(
                media_type=staged.media_type,
                digest=_sha256_bytes(data),
                size=len(data),
                relative_path=staged.relative_path,
                git_blob_id=staged.git_blob_id,
            )
            retained.append((descriptor, data))

        pack = SourcePack.create(
            source_id=source_id,
            exact_commit_or_release=exact_commit_or_release,
            blob_descriptors=(item[0] for item in retained),
        )
        data_by_digest = {descriptor.digest: data for descriptor, data in retained}
        self._ensure_storage_root()
        for descriptor in pack.blob_descriptors:
            self._store_blob(descriptor, data_by_digest[descriptor.digest])
        verification = self.verify(pack)
        if verification.status != "PASS":
            first = verification.findings[0]
            _fail(first.code, first.relative_path)
        return pack

    def verify(self, pack: SourcePack) -> VaultVerificationReceipt:
        findings: list[VaultFinding] = []
        verified_count = 0
        verified_bytes = 0
        rebuilt = SourcePack.create(
            source_id=pack.source_id,
            exact_commit_or_release=pack.exact_commit_or_release,
            blob_descriptors=pack.blob_descriptors,
        )
        if rebuilt.pack_root_sha256 != pack.pack_root_sha256:
            findings.append(VaultFinding.create(code="HASH_MISMATCH", relative_path=pack.source_id))
        else:
            for descriptor in pack.blob_descriptors:
                path = self.blob_path(descriptor.digest)
                if not path.exists() and not path.is_symlink():
                    findings.append(
                        VaultFinding.create(
                            code="VAULT_BLOB_MISSING",
                            relative_path=descriptor.relative_path,
                        )
                    )
                    continue
                if path.is_symlink():
                    findings.append(
                        VaultFinding.create(
                            code="NON_REGULAR_FILE",
                            relative_path=descriptor.relative_path,
                        )
                    )
                    continue
                try:
                    file_stat = path.stat()
                except FileNotFoundError:
                    findings.append(
                        VaultFinding.create(
                            code="VAULT_BLOB_MISSING",
                            relative_path=descriptor.relative_path,
                        )
                    )
                    continue
                if not stat.S_ISREG(file_stat.st_mode):
                    findings.append(
                        VaultFinding.create(
                            code="NON_REGULAR_FILE",
                            relative_path=descriptor.relative_path,
                        )
                    )
                    continue
                data = path.read_bytes()
                if len(data) != descriptor.size or _sha256_bytes(data) != descriptor.digest:
                    findings.append(
                        VaultFinding.create(
                            code="HASH_MISMATCH",
                            relative_path=descriptor.relative_path,
                        )
                    )
                    continue
                hits = scan_secret_bytes(descriptor.relative_path, data)
                if hits:
                    findings.append(
                        VaultFinding.create(
                            code="SECRET_LIKE_CONTENT",
                            relative_path=descriptor.relative_path,
                        )
                    )
                    continue
                verified_count += 1
                verified_bytes += len(data)
        return VaultVerificationReceipt.create(
            source_id=pack.source_id,
            pack_root_sha256=pack.pack_root_sha256,
            verified_blob_count=verified_count,
            verified_total_bytes=verified_bytes,
            findings=findings,
        )
