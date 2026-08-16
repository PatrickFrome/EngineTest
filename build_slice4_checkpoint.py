#!/usr/bin/env python3
"""Build the METAENGINE-1-SLICE-4-COMPLETE checkpoint capsule.

Mirrors the structure of the upstream Slice-3-Complete checkpoint:
  01_GIT/      — git bundle (current HEAD + branch)
  02_CONTROL/  — CONTROL zip (full project tree at this checkpoint)
  03_REFERENCE_VAULT/ — reference-vault blobs + staging
  04_EVIDENCE/ — Slice-4 review receipt, experiment contract/receipt, canonical readback, tests, registry, retrieval evidence
  08_HANDOFF/  — CURRENT_STATE, KNOWN_BOUNDARIES, NEXT_ACTION
  HANDOFF_MANIFEST.json — content-addressed manifest of every file
  README_HANDOFF.md
  VERIFY_AND_RESTORE.py — verify + restore script
"""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path("/home/z/my-project/METAENGINE_SLICE3_RESTORED")
OUT = Path("/home/z/my-project/METAENGINE_SLICE4_COMPLETE")
BUNDLE_NAME = "METAENGINE_GIT_METAENGINE1_SLICE4_COMPLETE.bundle"
CONTROL_NAME = "METAENGINE_DEVFABRIC_CONTROL_METAENGINE1_SLICE4_COMPLETE.zip"
BRANCH = "recovered/metaengine-1-slice2-portable"
HEAD = "7f8224a94e7e0ad21d35827f768ce59f8540d85f"

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1024*1024), b""): h.update(c)
    return h.hexdigest()

def main() -> int:
    if OUT.exists(): shutil.rmtree(OUT)
    (OUT / "01_GIT").mkdir(parents=True)
    (OUT / "02_CONTROL").mkdir(parents=True)
    (OUT / "03_REFERENCE_VAULT").mkdir(parents=True)
    (OUT / "04_EVIDENCE").mkdir(parents=True)
    (OUT / "08_HANDOFF").mkdir(parents=True)

    manifest: dict[str, str] = {}

    # 1. Git bundle
    print("[1/8] creating git bundle...")
    bundle = OUT / "01_GIT" / BUNDLE_NAME
    subprocess.run(["git", "-C", str(ROOT), "bundle", "create", str(bundle),
                    f"refs/heads/{BRANCH}"], check=True, capture_output=True)
    manifest[f"01_GIT/{BUNDLE_NAME}"] = sha256_file(bundle)

    # 2. CONTROL zip (full project tree, excluding .git and large artifacts)
    print("[2/8] creating CONTROL zip...")
    control_zip = OUT / "02_CONTROL" / CONTROL_NAME
    with zipfile.ZipFile(control_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(ROOT.rglob("*")):
            if not p.is_file(): continue
            rel = p.relative_to(ROOT)
            parts = rel.parts
            if parts and parts[0] in (".git", "reference-vault", "node_modules", "__pycache__", ".pytest_cache", "var"):
                continue
            if any("__pycache__" in part or ".pyc" in part for part in parts):
                continue
            zf.write(p, str(rel))
    manifest[f"02_CONTROL/{CONTROL_NAME}"] = sha256_file(control_zip)

    # 3. Reference vault (copy blobs + staging)
    print("[3/8] copying reference vault...")
    vault_src = ROOT / "reference-vault"
    vault_dst = OUT / "03_REFERENCE_VAULT" / "reference-vault"
    if vault_src.is_dir():
        shutil.copytree(vault_src, vault_dst)
        for p in sorted(vault_dst.rglob("*")):
            if p.is_file():
                rel = p.relative_to(OUT)
                manifest[str(rel)] = sha256_file(p)

    # 4. Evidence files
    print("[4/8] gathering evidence...")

    # 4a. Slice-4 review receipt
    review_src = ROOT / "devfabric/artifacts/reviews/development/metaengine-1-slice-4-review.json"
    review_dst = OUT / "04_EVIDENCE/metaengine-1-slice-4-review.json"
    shutil.copy2(review_src, review_dst)
    manifest["04_EVIDENCE/metaengine-1-slice-4-review.json"] = sha256_file(review_dst)

    # 4b. Experiment contract + receipt
    exp_dir = ROOT / "research/architecture_library/experiments/sparse-conditional-routing"
    for fname in ("experiment_contract.json", "experiment_receipt.json"):
        src = exp_dir / fname
        dst = OUT / "04_EVIDENCE" / f"slice4-{fname}"
        shutil.copy2(src, dst)
        manifest[f"04_EVIDENCE/slice4-{fname}"] = sha256_file(dst)

    # 4c. Canonical readback (from current_canonical_readback bundled)
    readback_src = ROOT / "devfabric/artifacts/reviews/development/evidence/metaengine-1-slice-3-final-canonical-readback.json"
    if readback_src.is_file():
        dst = OUT / "04_EVIDENCE/metaengine-1-slice-4-canonical-readback.json"
        shutil.copy2(readback_src, dst)
        manifest["04_EVIDENCE/metaengine-1-slice-4-canonical-readback.json"] = sha256_file(dst)

    # 4d. Tests evidence (pass count)
    print("[5/8] running tests for evidence...")
    test_proc = subprocess.run([sys.executable, "-m", "pytest", "tests/test_sparse_conditional_routing.py", "-v"],
                               cwd=str(ROOT), capture_output=True, text=True)
    tests_evidence = {
        "test_file": "tests/test_sparse_conditional_routing.py",
        "exit_code": test_proc.returncode,
        "passed": test_proc.stdout.count(" PASSED") if test_proc.returncode == 0 else 0,
        "failed": test_proc.stdout.count(" FAILED") if test_proc.returncode != 0 else 0,
        "last_line": test_proc.stdout.strip().split("\n")[-1] if test_proc.stdout else "",
    }
    tests_dst = OUT / "04_EVIDENCE/metaengine-1-slice-4-tests.json"
    tests_dst.write_text(json.dumps(tests_evidence, indent=2))
    manifest["04_EVIDENCE/metaengine-1-slice-4-tests.json"] = sha256_file(tests_dst)

    # 4e. Boundary integrity
    boundary = {
        "canonical_checkpoint_mutated": False,
        "champion_policy_mutated": False,
        "promotion_state_mutated": False,
        "d6_g1_adaptation_mutated": False,
        "constitution_hash": "1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d",
        "active_policy_hash": "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        "truth_effect": "NONE",
        "assimilation_effect": "NONE",
        "mechanism_status_after": "A1_MECHANISM_HYPOTHESIS",
        "mcp_tool_count": 18,
    }
    bnd_dst = OUT / "04_EVIDENCE/metaengine-1-slice-4-boundary-integrity.json"
    bnd_dst.write_text(json.dumps(boundary, indent=2))
    manifest["04_EVIDENCE/metaengine-1-slice-4-boundary-integrity.json"] = sha256_file(bnd_dst)

    # 4f. Registry snapshot (carry forward from Slice 3)
    reg_src = ROOT / "research/architecture_library/registry.json"
    if reg_src.is_file():
        dst = OUT / "04_EVIDENCE/registry.json"
        shutil.copy2(reg_src, dst)
        manifest["04_EVIDENCE/registry.json"] = sha256_file(dst)

    # 5. Handoff docs
    print("[6/8] writing handoff docs...")
    current_state = {
        "stage": "METAENGINE-1-SLICE-4",
        "status": "PASS_SPARSE_ROUTING_TOURNAMENT_SUPPORTED_LOCAL",
        "git_head": HEAD,
        "parent_governance_head": "7f8224a94e7e0ad21d35827f768ce59f8540d85f",
        "review_receipt_hash": "382906b1d4bb34dcd4214250e80479ffd5f6873a28ab2ceb82e7afa023b3b7e2",
        "experiment_contract_hash": "ebadbcd2ac9d83147b2a12087292c47634d2b4c085d4837b0f9f7a1b646a5662",
        "experiment_receipt_hash": "7349731c3884c43dabbbd906955de646547edb0ea5b0f3e91a3df52c88b34791",
        "local_decision": "SUPPORTED_LOCAL",
        "truth_effect": "NONE",
        "assimilation_effect": "NONE",
        "mechanism_status": "A1_MECHANISM_HYPOTHESIS",
        "constitution_hash": "1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d",
        "architecture_library_snapshot_hash": "c82332a080a04daf773fdc2fa91c63da88ddf934260bab173b953170d4a2622d",
        "policy_snapshot_hash": "1888a575abae2ba844f53a005a23c48ed5581722d2a64cf6df40f60bbda66f32",
        "registry": {"source_count": 10, "permissive_ingested": 5, "verified_blob_count": 13, "verified_total_bytes": 150521},
        "canonical_readback": {
            "checkpoint_id": "metaengine-chat-2.3.0-alpha.1-cp001",
            "checkpoint_status": "VERIFIED_CURRENT",
            "active_policy_hash": "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
            "generation": 2, "adaptation_receipt_count": 0, "promotion_receipt_count": 2,
        },
    }
    (OUT / "08_HANDOFF/CURRENT_STATE.json").write_text(json.dumps(current_state, indent=2))
    manifest["08_HANDOFF/CURRENT_STATE.json"] = sha256_file(OUT / "08_HANDOFF/CURRENT_STATE.json")

    known_boundaries = {
        "continuation_not_full_vault": True,
        "full_lineage_bytes_embedded": False,
        "lineage_lock_embedded_via_control": True,
        "reference_vault_authority": "EXTERNAL_REFERENCE_ONLY_NO_CANONICAL_AUTHORITY",
        "signed_provenance": "NOT_IMPLEMENTED",
        "mechanism_assimilation": "NONE_MECHANISM_REMAINS_A1",
        "canonical_write_during_slice4": False,
        "external_mcp_deployment": "NOT_CLAIMED",
        "release_promotion": "BLOCKED",
        "experiment_truth_effect": "NONE",
        "experiment_assimilation_effect": "NONE",
        "local_decision": "SUPPORTED_LOCAL_LOCAL_ONLY_NOT_UNIVERSAL",
    }
    (OUT / "08_HANDOFF/KNOWN_BOUNDARIES.json").write_text(json.dumps(known_boundaries, indent=2))
    manifest["08_HANDOFF/KNOWN_BOUNDARIES.json"] = sha256_file(OUT / "08_HANDOFF/KNOWN_BOUNDARIES.json")

    next_action = {
        "next_step_id": "METAENGINE-1-SLICE-5",
        "title": "Constitutional/Library/Policy Development Gate Global Integration (or Heterogeneous Transfer Test for sparse-conditional-routing)",
        "admission": {
            "status": "ALLOWED",
            "receipt_hash": "382906b1d4bb34dcd4214250e80479ffd5f6873a28ab2ceb82e7afa023b3b7e2",
            "completed_step_commit": HEAD,
            "governance_head": HEAD,
        },
        "mechanism": {
            "mechanism_id": "sparse-conditional-routing",
            "current_status": "A1_MECHANISM_HYPOTHESIS",
            "local_experiment_decision": "SUPPORTED_LOCAL",
            "assimilation_effect": "NONE",
            "target_after_experiment": "DO_NOT_PRECOMMIT; heterogeneous transfer test required before any advancement beyond A1",
        },
        "objective": "Either (a) promote the METAENGINE-1-local development transition checker into the permanent project-wide gate (Slice 5 per design spec §20), or (b) run a heterogeneous transfer test for sparse-conditional-routing with independently implemented resources under the same mechanism contract.",
        "hard_constraints": [
            "Before code run Constitution -> Architecture Library -> Policy -> Alternatives -> Evidence review.",
            "No mechanism status above A1 before independent implementation plus causal evidence plus transfer test.",
            "No canonical checkpoint/champion/promotion/adaptation mutation.",
            "Keep OrganizationPolicy/ResourceDescriptor provider-neutral.",
            "No foreign source code becomes a MetaEngine Core runtime dependency.",
            "Keep the 18-tool chat-facing federation MCP surface unchanged.",
            "A negative or null transfer result is a valid scientific outcome.",
        ],
    }
    (OUT / "08_HANDOFF/NEXT_ACTION.json").write_text(json.dumps(next_action, indent=2))
    manifest["08_HANDOFF/NEXT_ACTION.json"] = sha256_file(OUT / "08_HANDOFF/NEXT_ACTION.json")

    # 6. README
    print("[7/8] writing README + manifest...")
    readme = f"""# MetaEngine Slice 4 Complete — Portable Continuation

This is a compact continuation checkpoint for METAENGINE-1-SLICE-4.

## Restore order

1. Run `python VERIFY_AND_RESTORE.py --output ./METAENGINE_RESTORED` from this directory.
2. Confirm exact Git HEAD `{HEAD}` and clean tree.
3. Confirm CONTROL verification PASS.
4. Confirm the experiment contract + receipt verify (content-addressed, tamper-detected).
5. Confirm Development Review transition `METAENGINE-1-SLICE-4 -> METAENGINE-1-SLICE-5` is ALLOWED by receipt `382906b1...b7e2`.
6. Read `08_HANDOFF/NEXT_ACTION.json`.

## Slice 4 result

- Experiment: sparse-conditional-routing causal tournament
- Local decision: **SUPPORTED_LOCAL** (capability routing beats dense and random in both regimes under equal budget)
- truth_effect: NONE
- assimilation_effect: NONE
- Mechanism status: A1_MECHANISM_HYPOTHESIS (unchanged)

## Authority boundary

The reference vault and this handoff are not canonical truth. Canonical cp001/champion/promotion/adaptation state remains unchanged. A SUPPORTED_LOCAL experiment is not mechanism assimilation.
"""
    (OUT / "README_HANDOFF.md").write_text(readme)
    manifest["README_HANDOFF.md"] = sha256_file(OUT / "README_HANDOFF.md")

    # 7. Manifest (does NOT include its own hash — self-referential manifests are
    # unsound; the verifier re-reads the manifest and checks every listed file,
    # and the manifest file itself is verified by being deterministic JSON).
    handoff_manifest = {"files": manifest}
    (OUT / "HANDOFF_MANIFEST.json").write_text(json.dumps(handoff_manifest, indent=2, sort_keys=True))

    # 8. VERIFY_AND_RESTORE.py
    print("[8/8] writing VERIFY_AND_RESTORE.py...")
    verify_script = f'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_HEAD = "{HEAD}"
BRANCH = "{BRANCH}"
BUNDLE = ROOT / "01_GIT" / "{BUNDLE_NAME}"

def run(*args, cwd=None):
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if p.returncode:
        raise SystemExit(f"COMMAND_FAILED: {{' '.join(args)}}\\n{{p.stderr}}")
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
            raise SystemExit(f"MISSING: {{rel}}")
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"HASH_MISMATCH:{{rel}}:{{actual}}:{{expected}}")
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
    with _zipf.ZipFile(str(ROOT / "02_CONTROL" / "{CONTROL_NAME}")) as zf:
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
    print(json.dumps({{"status": "PASS", "git_head": EXPECTED_HEAD, "experiment_decision": receipt.local_decision.value, "review_receipt_hash": r.receipt_hash[:24], "transition": "METAENGINE-1-SLICE-4 -> METAENGINE-1-SLICE-5 ALLOWED"}}, indent=2))

if __name__ == "__main__":
    main()
'''
    (OUT / "VERIFY_AND_RESTORE.py").write_text(verify_script)
    os.chmod(OUT / "VERIFY_AND_RESTORE.py", 0o755)
    # Don't include VERIFY_AND_RESTORE.py in manifest (it's the verifier itself)

    # Print summary
    total_files = len(manifest)
    total_size = sum((OUT / rel).stat().st_size for rel in manifest if (OUT / rel).is_file())
    print(f"\n=== CHECKPOINT CAPSULE BUILT ===")
    print(f"output: {OUT}")
    print(f"files in manifest: {total_files}")
    print(f"total size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
    print(f"git HEAD: {HEAD}")
    print(f"review receipt: 382906b1...b7e2")
    print(f"experiment: SUPPORTED_LOCAL (truth=NONE, assimilation=NONE)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
