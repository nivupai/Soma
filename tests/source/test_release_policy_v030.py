"""Prospective policy retains scientific FAIL and rejects invalid/new evidence."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from scripts import report_native_mesh_diagnostic as diagnostic
from scripts.compare_mesh_grids import compare as frozen_compare
from soma.source.bem_discrepancy import homogeneous_series
from soma.source.noise import average_projector


@pytest.fixture
def reports(tmp_path):
    # Real archived numerical inputs copied only into isolated unit-test directories.
    primary = Path("experiments/canonical-mesh-v1/platforms")
    detailed = Path("experiments/milestone30-platform-investigation/platforms")
    for folder in primary.iterdir():
        dest = tmp_path / folder.name
        dest.mkdir()
        shutil.copyfile(folder / "mesh-grid-synthetic.json", dest / "mesh-grid-synthetic.json")
        companion = json.loads((detailed / folder.name / "mesh-grid-diagnostic.json").read_text())
        fixture = json.loads(Path("configs/mesh-grid-control-v30.json").read_text())
        # Schema enrichment is a unit-test fixture, never actual runner evidence.
        companion.update(
            shared_sources_m=fixture["sources_m"],
            shared_sensors_m=fixture["sensors_m"],
            C_runtime_random_seed=30042,
            C_runtime_random_sequence=[0] * 8,
        )
        companion["environment"]["blas"] = {
            "numpy": {"name": "unit_fixture"},
            "scipy": {"name": "unit_fixture"},
        }
        (dest / "mesh-grid-diagnostic.json").write_text(json.dumps(companion))
    return tmp_path


def modify(path, fn):
    value = json.loads(path.read_text())
    fn(value)
    path.write_text(json.dumps(value))


def late(root):
    return root / "synthetic-repro-ubuntu-24.04-3.12"


def replace_native_field(folder, field):
    path = folder / "mesh-grid-diagnostic.json"
    detail = json.loads(path.read_text())
    detail["controls"]["native"]["lead"] = field.tolist()
    path.write_text(json.dumps(detail))
    primary = json.loads((folder / "mesh-grid-synthetic.json").read_text())
    primary["lead"] = field.tolist()
    exact = average_projector(32) @ homogeneous_series(
        np.array(detail["sources_m"]), np.array(detail["sensors_m"])
    )
    primary["relative"] = float(np.linalg.norm(field - exact) / np.linalg.norm(exact))
    (folder / "mesh-grid-synthetic.json").write_text(json.dumps(primary))


def test_known_disagreement_is_never_a_scientific_pass(reports):
    with pytest.raises(ValueError, match="Cross-platform field disagreement"):
        frozen_compare(reports)
    value = diagnostic.report(reports)
    assert value["scientific_status"] == "FAIL" and value["original_M30_gate"] == "FAIL_PRESERVED"
    assert value["all_passed"] is False and value["native_portability_established"] is False
    assert value["release_policy_satisfied"] is True
    assert value["release_disposition"] == "NONBLOCKING_CHARACTERIZED_SCIENTIFIC_FAILURE"
    assert sum(p["failed_entries"] for p in value["pairs"]) == 60


@pytest.mark.parametrize("name", ["mesh-grid-synthetic.json", "mesh-grid-diagnostic.json"])
def test_missing_late_reports_fail_even_after_a_known_mismatch(reports, name):
    (late(reports) / name).unlink()
    with pytest.raises(ValueError, match="Missing"):
        diagnostic.report(reports)


@pytest.mark.parametrize(
    "fault",
    [
        "shape",
        "nan",
        "relative",
        "boundary",
        "volume",
        "nearest",
        "protocol",
        "boolean",
        "missing",
        "environment",
    ],
)
def test_invalid_primary_reports_are_blocking(reports, fault):
    path = late(reports) / "mesh-grid-synthetic.json"

    def change(v):
        if fault == "shape":
            v["lead"].pop()
        elif fault == "nan":
            v["lead"][0][0] = float("nan")
        elif fault == "relative":
            v["relative"] = None
        elif fault == "boundary":
            v["boundary_coordinate_max_m"] = float("inf")
        elif fault == "volume":
            v["tissue_volumes_m3"][0] = -1
        elif fault == "nearest":
            v["nearest_mm"] = []
        elif fault == "protocol":
            v["protocol"] = "0" * 64
        elif fault == "boolean":
            v["min_mean_ratio"] = True
        elif fault == "missing":
            v.pop("relative")
        elif fault == "environment":
            v["environment"]["python"] = "3.11.18"

    modify(path, change)
    with pytest.raises((ValueError, KeyError)):
        diagnostic.report(reports)


@pytest.mark.parametrize(
    "fault",
    [
        "inverted",
        "label",
        "mesh_hash",
        "units",
        "residual",
        "CSR",
        "control_missing",
        "control_failure",
        "options",
        "lead",
    ],
)
def test_invalid_companion_physics_and_structure_are_blocking(reports, fault):
    path = late(reports) / "mesh-grid-diagnostic.json"

    def change(v):
        c = v["controls"]["native"]
        if fault == "inverted":
            c["mesh"]["tetrahedra"][0][:2] = c["mesh"]["tetrahedra"][0][1::-1]
        elif fault == "label":
            c["mesh"]["labels"][0] = 9
        elif fault == "mesh_hash":
            c["mesh_hash"] = "0" * 64
        elif fault == "units":
            c["diagnostics"]["units"] = "uV/(A*m)"
        elif fault == "residual":
            c["diagnostics"]["relative_residual"] = float("nan")
        elif fault == "CSR":
            c["stiffness"]["indices"][0] = 1000000
        elif fault == "control_missing":
            v["controls"].pop("shared_mesh_q6")
        elif fault == "control_failure":
            v["controls"]["shared_mesh_q6"]["status"] = "FAILED"
        elif fault == "options":
            c["options"]["General.NumThreads"] = 2
        elif fault == "lead":
            c["lead"][0][0] += 0.1

    modify(path, change)
    with pytest.raises((ValueError, KeyError)):
        diagnostic.report(reports)


def test_changed_discrepancy_with_same_failed_cells_is_not_permitted(reports):
    folder = late(reports)
    field = np.array(json.loads((folder / "mesh-grid-synthetic.json").read_text())["lead"])
    field[0, 3] += 0.001
    field[1, 3] -= 0.001
    replace_native_field(folder, field)
    with pytest.raises(ValueError, match="discrepancy vector"):
        diagnostic.report(reports)


def test_unexpected_native_pass_requires_policy_review(reports):
    baseline = np.array(
        json.loads(
            (reports / "synthetic-repro-macos-15-3.11/mesh-grid-synthetic.json").read_text()
        )["lead"]
    )
    for folder in reports.iterdir():
        replace_native_field(folder, baseline)
    assert frozen_compare(reports)["all_passed"]
    with pytest.raises(ValueError, match="unexpectedly passed"):
        diagnostic.report(reports)


def test_unrelated_comparator_failure_is_not_reclassified(reports, monkeypatch):
    def fail(_):
        raise ValueError("Invalid physical mesh")

    monkeypatch.setattr(diagnostic, "frozen_compare", fail)
    with pytest.raises(ValueError, match="Invalid physical mesh"):
        diagnostic.report(reports)


def test_malformed_json_cli_is_nonzero_and_records_blocked_status(reports, tmp_path):
    (late(reports) / "mesh-grid-synthetic.json").write_text("{bad JSON")
    output = tmp_path / "result.json"
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.report_native_mesh_diagnostic",
            str(reports),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert p.returncode != 0
    value = json.loads(output.read_text())
    assert value["release_disposition"] == "BLOCK_RELEASE" and not value["release_policy_satisfied"]


def test_policy_cannot_be_changed_without_versioned_review(tmp_path):
    p = tmp_path / "policy.json"
    v = json.loads(diagnostic.POLICY_PATH.read_text())
    v["native_field_rtol"] = 0.03
    p.write_text(json.dumps(v))
    with pytest.raises(ValueError, match="policy integrity"):
        diagnostic.report(tmp_path, policy_path=p)


def test_canonical_security_and_native_execution_remain_mandatory():
    jobs = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())["jobs"]
    canonical = jobs["canonical-mesh-v1-comparison"]
    assert "if" not in canonical and canonical["needs"] == "reproducibility"
    assert any(
        "python -m scripts.compare_canonical_mesh " in s.get("run", "") for s in canonical["steps"]
    )
    native = jobs["cross-platform-comparison"]
    assert any(
        "python -m scripts.report_native_mesh_diagnostic " in s.get("run", "")
        for s in native["steps"]
    )
    for job in jobs.values():
        assert not job.get("continue-on-error", False)
        for step in job["steps"]:
            assert not step.get("continue-on-error", False)
    assert any(
        s.get("run") == "npm --prefix apps/explorer audit --audit-level=moderate"
        for s in jobs["explorer"]["steps"]
    )
    assert any("pip_audit" in s.get("run", "") for s in jobs["security"]["steps"])


@pytest.mark.parametrize("has_summary", [False, True])
def test_cli_honest_failure_summary_is_required_in_ci(reports, tmp_path, has_summary):
    output = tmp_path / "status.json"
    summary = tmp_path / "summary.md"
    env = dict(os.environ)
    env.pop("GITHUB_STEP_SUMMARY", None)
    if has_summary:
        env["GITHUB_STEP_SUMMARY"] = str(summary)
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.report_native_mesh_diagnostic",
            str(reports),
            "--output",
            str(output),
            "--github-summary",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    value = json.loads(output.read_text())
    if has_summary:
        assert p.returncode == 0
        assert value["scientific_status"] == "FAIL" and not value["all_passed"]
        assert "scientific diagnostic: FAIL" in summary.read_text()
    else:
        assert p.returncode != 0 and value["release_disposition"] == "BLOCK_RELEASE"


def test_duplicate_json_keys_cannot_hide_invalid_metadata(reports):
    path = late(reports) / "mesh-grid-synthetic.json"
    text = path.read_text()
    path.write_text(text.replace('"relative":', '"relative": 0.99, "relative":', 1))
    with pytest.raises(ValueError, match="Duplicate native diagnostic JSON keys"):
        diagnostic.report(reports)
