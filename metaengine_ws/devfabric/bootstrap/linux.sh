#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null || { echo 'Python >=3.11 is required' >&2; exit 2; }
command -v git >/dev/null || { echo 'Git is required' >&2; exit 2; }
command -v uv >/dev/null || { echo 'uv is required; install it from https://docs.astral.sh/uv/' >&2; exit 2; }
[ -f uv.lock ] || { echo 'uv.lock is missing; resolve the toolchain on a networked machine first' >&2; exit 3; }
uv sync --locked
uv export --frozen --format pylock.toml -o pylock.toml
uv run python -m metaengine.devfabric.cli doctor --profile offline --json
