"""The M33 skull runner refuses to score without the owner's sealed protocol."""

import json
from pathlib import Path

import pytest

from scripts import run_m33_skull_validation as runner
from soma.core.provenance import sha256


def test_refuses_without_freeze(tmp_path: Path) -> None:
    protocol = tmp_path / "p.md"
    protocol.write_text("draft\n")
    with pytest.raises(SystemExit, match="not frozen"):
        runner.require_frozen_protocol(protocol, tmp_path / "missing.json")


@pytest.mark.parametrize(
    "seal",
    [
        {"owner_approved": False},
        {"owner_approved": "yes"},
        {"owner_approved": True, "protocol_sha256": "0" * 64},
    ],
)
def test_refuses_unapproved_or_mismatched_seal(tmp_path: Path, seal: dict) -> None:
    protocol, freeze = tmp_path / "p.md", tmp_path / "f.json"
    protocol.write_text("draft\n")
    freeze.write_text(json.dumps({"protocol_sha256": sha256(protocol), **seal}))
    with pytest.raises(SystemExit, match="scoring refused"):
        runner.require_frozen_protocol(protocol, freeze)


def test_accepts_matching_owner_seal(tmp_path: Path) -> None:
    protocol, freeze = tmp_path / "p.md", tmp_path / "f.json"
    protocol.write_text("draft\n")
    freeze.write_text(json.dumps({"protocol_sha256": sha256(protocol), "owner_approved": True}))
    assert runner.require_frozen_protocol(protocol, freeze)["owner_approved"] is True


def test_main_refuses_before_touching_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "FREEZE", tmp_path / "missing.json")
    output = tmp_path / "out"
    with pytest.raises(SystemExit, match="not frozen"):
        runner.main(["--synthseg-cmd", "x", "--data-root", "/nonexistent", "--output", str(output)])
    assert not output.exists()


def test_centre_letter_and_decision_rule() -> None:
    assert runner.centre("1BA001") == "A" and runner.centre("1BC042") == "C"
    assert runner.centre("weird") == "unknown"
    good = {"mean": 1.0, "CI95": [0.8, 1.2]}
    hd = {"mean": 3.0, "CI95": [2.5, 3.5]}
    primary = {
        b: {"mean_abs_mm": good, "HD95_mm": hd}
        for b in ("inner_skull", "outer_scalp", "outer_skull")
    }
    primary["thickness"] = {"mean_error_mm": {"mean": 0.1, "CI95": [-0.5, 0.7]}}
    assert runner.decide(primary, 20)["readiness"] == "VALIDATED"
    assert runner.decide(primary, 5)["readiness"] == "NOT_READY"
    primary["outer_skull"]["HD95_mm"] = {"mean": 6.0, "CI95": [5.0, 8.0]}
    assert runner.decide(primary, 20)["readiness"] == "QC_ONLY"
    primary["inner_skull"]["mean_abs_mm"] = {"mean": 1.9, "CI95": [1.5, 2.3]}
    assert runner.decide(primary, 20)["readiness"] == "NOT_READY"
