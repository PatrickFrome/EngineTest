from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .codec import to_primitive
from .doctor import Doctor
from .journal import Journal
from .models import PrivacyClass, RiskClass, TaskEnvelope
from .verifier import Verifier


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _emit(value: object) -> None:
    print(json.dumps(to_primitive(value), ensure_ascii=False, indent=2, sort_keys=True))


def _doctor(args: argparse.Namespace) -> int:
    report = Doctor(_root()).inspect(args.profile)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for check in report.checks:
            mark = "OK" if check.ok else "FAIL"
            print(f"[{mark}] {check.code}: {check.detail}")
        print(f"STATUS={report.status}")
    return 0 if report.status == "PASS" else 3



def _swarm_status(args: argparse.Namespace) -> int:
    report = Doctor(_root()).inspect_ai_swarm()
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for check in report.checks:
            mark = "OK" if check.ok else "MISS"
            print(f"[{mark}] {check.code}: {check.detail}")
        print(f"STATUS={report.status}")
    return 0


def _connected_status(args: argparse.Namespace) -> int:
    path = _root() / "devfabric" / "artifacts" / "manifests" / "connected-services.json"
    payload = json.loads(path.read_text())
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for name, item in sorted(payload["services"].items()):
            print(f"{name}: {item['health']}")
        print(f"ACTUAL_GATE_WRITES={payload['actual_gate_writes']}")
    return 0



def _edge_status(args: argparse.Namespace) -> int:
    path = _root() / "devfabric" / "artifacts" / "manifests" / "remote-edge.json"
    payload = json.loads(path.read_text())
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for name, item in sorted(payload["components"].items()):
            print(f"{name}: {item['status']}")
        print(f"DEPLOYMENT={payload['deployment']}")
        print(f"ACTUAL_CLOUD_WRITES={payload['actual_cloud_writes']}")
    return 0



def _federation_status(args: argparse.Namespace) -> int:
    from .federation.bootstrap import load_bootstrap

    context = load_bootstrap(_root())
    payload = {
        "status": "STATIC_READY",
        "protocol_version": context.protocol_version,
        "canonical_authority": context.canonical_authority,
        "slot_count": context.slot_count,
        "role_catalog": {slot.value: role for slot, role in context.role_catalog},
        "role_profile_hashes": {slot.value: digest for slot, digest in context.role_profile_hashes},
        "source_artifact_sha256": context.source_artifact_sha256,
        "release_version": context.release_version,
        "requires_cloud_credentials": False,
    }
    _emit(payload)
    return 0


def _role_show(args: argparse.Namespace) -> int:
    from .federation.bootstrap import activate_role, load_bootstrap
    from .federation.types import SlotId

    context = load_bootstrap(_root())
    slot = SlotId(args.slot)
    role = activate_role(context, slot)
    _emit({
        "slot_id": slot.value,
        "role": role.hard.role,
        "role_profile_hash": role.profile_hash,
        "role_genome": role,
    })
    return 0


def _federation_bootstrap(args: argparse.Namespace) -> int:
    from .federation.bootstrap import load_bootstrap, offline_role_packet
    from .federation.types import SlotId

    context = load_bootstrap(_root())
    _emit(offline_role_packet(context, SlotId(args.slot), pinned_task=None))
    return 0


def _federation_sim_register(args: argparse.Namespace) -> int:
    from .federation.bootstrap import load_bootstrap
    from .federation.simulator import FederationSimulator
    from .federation.store import FederationStore

    context = load_bootstrap(_root())
    profile_hashes = {slot: digest for slot, digest in context.role_profile_hashes}
    store = FederationStore(Path(args.db))
    try:
        registration = FederationSimulator(store).register(
            epoch_id=args.epoch,
            requested_slot=args.slot,
            capsule_sha256=args.capsule_sha256,
            protocol_version=context.protocol_version,
            role_profile_hash=profile_hashes,
            registration_nonce=args.registration_nonce,
        )
    finally:
        store.close()
    _emit(registration)
    return 0


def _task_create(args: argparse.Namespace) -> int:
    task = TaskEnvelope.create(
        source_checkpoint_id=args.source_checkpoint,
        source_tree_hash=args.source_tree_hash,
        objective=args.objective,
        acceptance_tests=tuple(args.acceptance_test or ("python -m pytest -q",)),
        allowed_paths=tuple(args.allowed_path or ("metaengine/", "tests/")),
        forbidden_paths=tuple(args.forbidden_path or ("lineages/",)),
        capabilities_required=tuple(args.capability),
        risk_class=RiskClass(args.risk_class),
        privacy_class=PrivacyClass(args.privacy_class),
        zero_spend=True,
    )
    _emit(task)
    return 0


def _journal_verify(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else _root() / "devfabric" / "state" / "session.sqlite"
    errors = Journal(path).verify_chain()
    payload = {"path": str(path), "status": "PASS" if not errors else "FAIL", "errors": errors}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["status"])
        for error in errors:
            print(error)
    return 0 if not errors else 4


def _verify(args: argparse.Namespace) -> int:
    verifier = Verifier(_root() / "devfabric" / "verification" / "profiles.toml")
    receipt = verifier.run(args.profile, Path(args.candidate_dir))
    _emit(receipt)
    return 0 if receipt.verdict.value == "PASS" else 5


def _capsule_build(args: argparse.Namespace) -> int:
    from .capsule import build_control_capsule

    result = build_control_capsule(_root(), Path(args.out))
    _emit(result)
    return 0


def _recover_test(args: argparse.Namespace) -> int:
    from .capsule import verify_control_capsule

    result = verify_control_capsule(Path(args.control_capsule))
    _emit(result)
    return 0 if result["status"] == "PASS" else 6


def _gate_verify(args: argparse.Namespace) -> int:
    from .capsule import verify_gate_receipt

    result = verify_gate_receipt(Path(args.receipt))
    _emit(result)
    return 0 if result["status"] == "PASS" else 7


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="metaengine-dev")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="inspect a portable development profile")
    p.add_argument("--profile", default="offline")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_doctor)

    p = sub.add_parser("swarm-status", help="inspect optional Stage B AI swarm tools")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_swarm_status)

    p = sub.add_parser("connected-status", help="show sanitized Stage C connector health snapshot")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_connected_status)

    p = sub.add_parser("edge-status", help="show sanitized Stage D remote edge snapshot")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_edge_status)


    p = sub.add_parser("federation-status", help="show static Stage D6 federation bootstrap status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_federation_status)

    p = sub.add_parser("role-show", help="show one verified Stage D6 role genome")
    p.add_argument("slot", choices=[f"C{i}" for i in range(8)])
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_role_show)

    p = sub.add_parser("federation-bootstrap", help="build a static frozen-offline role packet")
    p.add_argument("--slot", required=True, choices=[f"C{i}" for i in range(8)])
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_federation_bootstrap)

    p = sub.add_parser("federation-sim-register", help="register a chat in an explicit local federation simulator DB")
    p.add_argument("--db", required=True)
    p.add_argument("--epoch", required=True)
    p.add_argument("--slot", default="AUTO", choices=["AUTO", *[f"C{i}" for i in range(8)]])
    p.add_argument("--capsule-sha256", required=True)
    p.add_argument("--registration-nonce", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_federation_sim_register)

    p = sub.add_parser("task-create", help="create an immutable TaskEnvelope")
    p.add_argument("--objective", required=True)
    p.add_argument("--source-checkpoint", required=True)
    p.add_argument("--source-tree-hash", required=True)
    p.add_argument("--capability", action="append", required=True)
    p.add_argument("--acceptance-test", action="append")
    p.add_argument("--allowed-path", action="append")
    p.add_argument("--forbidden-path", action="append")
    p.add_argument("--risk-class", choices=[x.value for x in RiskClass], default=RiskClass.NORMAL.value)
    p.add_argument("--privacy-class", choices=[x.value for x in PrivacyClass], default=PrivacyClass.P1.value)
    p.set_defaults(func=_task_create)

    p = sub.add_parser("journal-verify", help="verify local hash-chained journal")
    p.add_argument("--path")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_journal_verify)

    p = sub.add_parser("verify", help="run a deterministic verifier profile")
    p.add_argument("--profile", default="normal")
    p.add_argument("--candidate-dir", default=".")
    p.set_defaults(func=_verify)

    p = sub.add_parser("capsule-build", help="build portable CONTROL capsule")
    p.add_argument("--out", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_capsule_build)

    p = sub.add_parser("recover-test", help="verify a CONTROL capsule")
    p.add_argument("--control-capsule", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_recover_test)

    p = sub.add_parser("gate-verify", help="verify a Stage A gate receipt")
    p.add_argument("receipt")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_gate_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
