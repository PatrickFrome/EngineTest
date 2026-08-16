#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_HEAD = "7f8224a94e7e0ad21d35827f768ce59f8540d85f"
BRANCH = "recovered/metaengine-1-slice2-portable"
BUNDLE = ROOT / "01_GIT" / "METAENGINE_GIT_METAENGINE1_SLICE4_COMPLETE.bundle"

def run(*args, cwd=None):
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if p.returncode:
        raise SystemExit(f"COMMAND_FAILED: {' '.join(args)}\n{p.stderr}")
    return p.stdout.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ns = ap.parse_args()
    out = Path(ns.output).resolve()
    manifest = json.loads((ROOT / "HANDOFF_MANIFEST.json").read_text())
    for rel, expected in manifest["files"].items():
        p = ROOT / rel
        if not p.is_file():
            raise SystemExit(f"MISSING: {rel}")
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"HASH_MISMATCH:{rel}:{actual}:{expected}")
    with tempfile.TemporaryDirectory() as td:
        bare = Path(td) / "verify.git"
        run("git", "init", "--bare", "-q", str(bare))
        run("git", "-C", str(bare), "bundle", "verify", str(BUNDLE))
    if out.exists(): shutil.rmtree(out)
    run("git", "clone", "-q", str(BUNDLE), str(out))
    run("git", "checkout", "-q", BRANCH, cwd=out)
    if run("git", "rev-parse", "HEAD", cwd=out) != EXPECTED_HEAD:
        raise SystemExit("HEAD_MISMATCH")
    run("git", "fsck", "--full", "--strict", cwd=out)
    # Extract the CONTROL zip on top of the git tree (Slice 4 work is in CONTROL, not committed to git)
    import zipfile as _zipf
    with _zipf.ZipFile(str(ROOT / "02_CONTROL" / "METAENGINE_DEVFABRIC_CONTROL_METAENGINE1_SLICE4_COMPLETE.zip")) as zf:
        zf.extractall(str(out))
    # Copy reference vault
    import shutil as _sh
    _sh.copytree(str(ROOT / "03_REFERENCE_VAULT" / "reference-vault"), str(out / "reference-vault"))
    # Verify experiment receipt tamper-detection
    import sys as _sys
    _sys.path.insert(0, str(out))
    from metaengine.experiments.sparse_conditional_routing import ExperimentContract, ExperimentReceipt
    contract = ExperimentContract.from_dict(json.load(open(str(out / "research/architecture_library/experiments/sparse-conditional-routing/experiment_contract.json"))))
    receipt = ExperimentReceipt.from_dict(json.load(open(str(out / "research/architecture_library/experiments/sparse-conditional-routing/experiment_receipt.json"))))
    # Verify development review receipt
    from metaengine.devfabric.development_review import DevelopmentEvolutionReviewReceipt, verify_receipt_integrity
    r = DevelopmentEvolutionReviewReceipt.from_dict(json.load(open(out / "devfabric/artifacts/reviews/development/metaengine-1-slice-4-review.json")))
    assert verify_receipt_integrity(r).valid
    print(json.dumps({"status": "PASS", "git_head": EXPECTED_HEAD, "experiment_decision": receipt.local_decision.value, "review_receipt_hash": r.receipt_hash[:24], "transition": "METAENGINE-1-SLICE-4 -> METAENGINE-1-SLICE-5 ALLOWED"}, indent=2))

if __name__ == "__main__":
    main()
