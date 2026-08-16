#!/usr/bin/env bash
set -euo pipefail
MODE=print
case "${1:-}" in
  "") ;;
  --print) MODE=print ;;
  --install) MODE=install ;;
  *) echo "usage: $0 [--print|--install]" >&2; exit 2 ;;
esac
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="$ROOT/devfabric/toolchain/AI_SWARM_MANIFEST.json"
python3 - "$MANIFEST" "$MODE" <<'PY'
import json, platform, subprocess, sys
from pathlib import Path

manifest=json.loads(Path(sys.argv[1]).read_text())
mode=sys.argv[2]
machine=platform.machine().lower()
arch='arm64' if machine in {'aarch64','arm64'} else 'amd64'
key=f'linux_{arch}'
print(f"Metaengine Stage B optional AI swarm installer mode={mode} arch={arch}")
print("Policy: zero-spend; no model downloads; no paid provider configuration; no service autostart.")
for name, spec in manifest['tools'].items():
    command=spec.get(key)
    if not command:
        print(f"SKIP {name}: no command for {key}")
        continue
    print(f"{name}: {command}")
    if mode == 'install':
        subprocess.run(['bash','-lc',command],check=True)
PY
