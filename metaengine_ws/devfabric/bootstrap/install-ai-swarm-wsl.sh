#!/usr/bin/env bash
set -euo pipefail
if ! grep -qi microsoft /proc/version 2>/dev/null; then
  echo 'This installer is intended for WSL2; continuing with Linux commands.' >&2
fi
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install-ai-swarm.sh" "$@"
