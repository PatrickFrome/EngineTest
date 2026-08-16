#!/usr/bin/env python3
"""Portable ZIP extractor that relies on Python's Unicode ZIP metadata handling.

Usage:
  python studio/safe_extract.py archive.zip destination

It rejects absolute paths and path traversal. This is useful for archives whose
Unicode names are rendered poorly by some command-line unzip builds.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def safe_target(root: Path, member: str) -> Path:
    normalized = member.replace('\\', '/')
    parts = [p for p in normalized.split('/') if p not in ('', '.')]
    if normalized.startswith('/') or any(p == '..' for p in parts):
        raise ValueError(f'Unsafe ZIP path: {member!r}')
    target = root.joinpath(*parts)
    resolved_root = root.resolve()
    resolved_target = target.resolve(strict=False)
    if resolved_root != resolved_target and resolved_root not in resolved_target.parents:
        raise ValueError(f'ZIP path escapes destination: {member!r}')
    return target


def main() -> int:
    if len(sys.argv) != 3:
        print('Usage: safe_extract.py <archive.zip> <destination>', file=sys.stderr)
        return 2
    archive = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            target = safe_target(destination, info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open('wb') as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
            count += 1
    print(f'Extracted {count} files to {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
