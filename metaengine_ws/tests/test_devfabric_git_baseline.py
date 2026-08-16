from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_source_binding_matches_git_baseline():
    binding = json.loads((ROOT / "devfabric/source_binding.json").read_text())
    assert binding["artifact_sha256"] == "8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0"
    assert binding["release_version"] == "2.3.0-alpha.1"
    assert (
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        == "true"
    )
