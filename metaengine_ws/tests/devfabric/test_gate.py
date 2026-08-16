import json

from metaengine.devfabric.capsule import make_gate_receipt, verify_gate_receipt


def test_gate_receipt_integrity_is_separate_from_certification(tmp_path):
    receipt = make_gate_receipt(
        {
            "certification_status": "BLOCKED_EXTERNAL_TOOLCHAIN",
            "git_head": "a" * 40,
            "tests": {"passed": 89, "failed": 0},
        }
    )
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(receipt))
    result = verify_gate_receipt(path)
    assert result["status"] == "PASS"
    assert result["certification_status"] == "BLOCKED_EXTERNAL_TOOLCHAIN"


def test_gate_receipt_tamper_is_detected(tmp_path):
    receipt = make_gate_receipt({"certification_status": "PASS", "git_head": "a" * 40})
    receipt["git_head"] = "b" * 40
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(receipt))
    assert verify_gate_receipt(path)["status"] == "FAIL"

def test_stage_b_gate_receipt_uses_distinct_version(tmp_path):
    receipt = make_gate_receipt(
        {'certification_status':'DEVELOPMENT_READY'},
        gate_version='METAENGINE-DEVFABRIC-STAGE-B-GATE-1',
    )
    path=tmp_path/'stage-b.json'; path.write_text(json.dumps(receipt))
    result=verify_gate_receipt(path)
    assert result['status']=='PASS'
    assert result['gate_version']=='METAENGINE-DEVFABRIC-STAGE-B-GATE-1'
