from pathlib import Path

from metaengine.devfabric.doctor import Doctor

ROOT = Path(__file__).resolve().parents[2]


def test_offline_doctor_does_not_check_cloud_credentials():
    report = Doctor(ROOT).inspect("offline")
    assert report.profile == "offline"
    assert report.requires_cloud_credentials is False
    assert all(not check.code.startswith("CLOUD_") for check in report.checks)


def test_offline_doctor_protects_lineages_and_source_binding():
    report = Doctor(ROOT).inspect("offline")
    codes = {check.code for check in report.checks}
    assert "SOURCE_BINDING" in codes
    assert "LINEAGE_UNMODIFIED" in codes


def test_doctor_and_bootstrap_require_pep751_audit_export():
    report = Doctor(ROOT).inspect("offline")
    codes = {check.code for check in report.checks}
    assert "PYLOCK_AUDIT_EXPORT" in codes
    bootstrap = (ROOT / "devfabric/bootstrap/linux.sh").read_text()
    assert "uv export --frozen --format pylock.toml -o pylock.toml" in bootstrap
