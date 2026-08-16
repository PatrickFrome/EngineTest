from __future__ import annotations

import argparse
import json
from pathlib import Path

from metaengine.devfabric.capsule import build_control_capsule


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = build_control_capsule(Path(args.root), Path(args.out))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
