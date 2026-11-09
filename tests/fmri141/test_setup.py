"""Readiness never starts preprocessing or fabricates metadata."""

import json
import runpy

import pytest
import yaml

from soma.core.provenance import sha256
from soma.fmri.preprocessing_setup import readiness


@pytest.mark.parametrize("BIDS_status", ["PASS", "FAIL", "INDETERMINATE"])
def test_preprocessing_plan_never_launches_or_mutates_raw(tmp_path, monkeypatch, BIDS_status):
    import soma.fmri.preprocessing_setup as module

    fixture = runpy.run_path("tests/fmri14/conftest.py")["bundle"].__wrapped__(tmp_path)
    inherited = fixture.raw_root / "task-motor_events.tsv"
    inherited.write_text("onset\tduration\ttrial_type\n0\t1\tmotor\n")
    before = sha256(fixture.raw_bold)
    config = tmp_path / "plan.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "raw": str(fixture.raw_root),
                "subject": "01",
                "sessions": ["test", "retest"],
                "task": "motor",
                "image": "nipreps/fmriprep:25.2.7",
                "platform": "linux/amd64",
                "output": str(tmp_path / "derivatives"),
                "work": str(tmp_path / "work"),
                "output_spaces": ["T1w"],
                "threads": 1,
                "memory_mb": 12000,
            }
        )
    )
    monkeypatch.setattr(
        module,
        "official_validate",
        lambda root: {"status": BIDS_status, "scope": "explicit unit-test stub"},
    )
    r = readiness(config, tmp_path / "plan", runtime={"server_available": False})
    inventory = json.loads((tmp_path / "plan/private-inventory.json").read_text())
    assert str(inherited) in inventory["files"]["events"]
    assert r["status"] == "blocked" and r["executed"] is False
    assert r["automatic_downloads_or_launches"] is False
    assert "--pull=never" in r["command"] and "--network=none" in r["command"]
    assert "--skip-bids-validation" not in r["command"]
    assert "--longitudinal" not in r["command"]
    assert r["command"][r["command"].index("--subject-anatomical-reference") + 1] == "unbiased"
    assert sha256(fixture.raw_bold) == before
    if BIDS_status != "PASS":
        assert any("BIDS" in reason for reason in r["blockers"])
    assert json.loads((tmp_path / "plan/bids-filter.json").read_text())["bold"]["task"] == "motor"
