#!/usr/bin/env bash
set -euo pipefail
if ! grep -qi microsoft /proc/version 2>/dev/null; then
  echo 'This bootstrap is intended for WSL2.' >&2
fi
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/linux.sh" "$@"
