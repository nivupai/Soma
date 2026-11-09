"""Actual PyBIDS metadata inheritance, selection and local official validation."""

import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from soma.cli import app
from soma.imaging.nifti import save_nifti
from soma.imaging.volumes import Volume
from soma.pipeline.derivatives import official_validate, validate_derivatives
from soma.pipeline.engine import configuration, run_pipeline
from soma.pipeline.ingestion import inspect_bids, select_bids


def bids_dataset(tmp_path, runs=1):
    root = tmp_path / "bids"
    root.mkdir()
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "Synthetic fixture", "BIDSVersion": "1.11.2", "DatasetType": "raw"})
    )
    (root / "T1w.json").write_text(
        json.dumps(
            {
                "RepetitionTime": 2.0,
                "EchoTime": 0.003,
                "Manufacturer": "Synthetic",
                "MagneticFieldStrength": 3.0,
            }
        )
    )
    d = root / "sub-01/ses-A/anat"
    d.mkdir(parents=True)
    (root / "sub-01/sub-01_T1w.json").write_text(json.dumps({"RepetitionTime": 3.0}))
    x = np.zeros((15, 15, 15), np.float32)
    x[2:13, 2:13, 2:13] = 20
    x[4:11, 4:11, 4:11] = 70
    x[6:9, 6:9, 6:9] = 120
    for run in range(1, runs + 1):
        save_nifti(
            Volume(x, np.diag([0.001, 0.001, 0.001, 1])), d / f"sub-01_ses-A_run-{run}_T1w.nii.gz"
        )
    return root


def test_actual_pybids_inheritance_subject_session_selection(tmp_path):
    root = bids_dataset(tmp_path)
    info = inspect_bids(root)
    assert info["subjects"] == ["01"] and info["sessions"] == ["A"]
    assert info["T1w"][0]["metadata"]["RepetitionTime"] == 3.0
    assert info["T1w"][0]["metadata"]["EchoTime"] == 0.003
    record = select_bids(root, "sub-01", session="ses-A")
    assert record.subject == "01" and record.session == "A"


def test_ambiguous_acquisition_requires_policy(tmp_path):
    root = bids_dataset(tmp_path, runs=2)
    with pytest.raises(ValueError, match="Ambiguous"):
        select_bids(root, "01")
    assert select_bids(root, "01", filters={"run": 2}).entities["run"] == 2
    assert select_bids(root, "01", selection="first-sorted").entities["run"] == 1
    with pytest.raises(ValueError, match="not found"):
        select_bids(root, "99")


@pytest.mark.parametrize(
    "description",
    [
        {},
        {"Name": "x"},
        {"Name": "x", "BIDSVersion": "invalid"},
        {"Name": "x", "BIDSVersion": "1.11.2", "DatasetType": "derivative"},
    ],
)
def test_invalid_description(tmp_path, description):
    root = tmp_path / "bids"
    root.mkdir()
    (root / "dataset_description.json").write_text(json.dumps(description))
    with pytest.raises(ValueError):
        inspect_bids(root)


def test_full_schema_raw_and_generated_derivatives(tmp_path):
    pytest.importorskip("bids_validator_deno")
    root = bids_dataset(tmp_path)
    assert official_validate(root)["status"] == "PASS"
    cfg = configuration(Path("configs/mri-pipeline.yaml"))
    cfg["visualization"] = False
    run_pipeline(
        select_bids(root, "01"),
        cfg,
        tmp_path / "soma",
        report_root=tmp_path / "reports",
        cache_root=tmp_path / "cache",
    )
    result = validate_derivatives(tmp_path / "soma")
    assert result["full_schema_status"] == "PASS" and result["BIDS_compliance_claimed"]
    description = json.loads((tmp_path / "soma/dataset_description.json").read_text())
    assert description["GeneratedBy"][0]["Name"] == "Soma"
    lut = next((tmp_path / "soma").rglob("*dseg.tsv")).read_text()
    assert "Cerebrospinal Fluid\tCSF\t3" in lut


def test_official_validator_rejects_invalid_metadata(tmp_path):
    pytest.importorskip("bids_validator_deno")
    root = bids_dataset(tmp_path)
    (root / "dataset_description.json").write_text("{}")
    assert official_validate(root)["status"] == "FAIL"


def test_cli_bids_inspection_and_dry_run(tmp_path):
    root = bids_dataset(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["mri", "bids-inspect", "--input", str(root)])
    assert result.exit_code == 0 and "PyBIDS" in result.stdout
    result = runner.invoke(
        app,
        [
            "mri",
            "pipeline",
            "--input",
            str(root),
            "--participant-label",
            "01",
            "--dry-run",
            "--output",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0 and "dry-run" in result.stdout and not (tmp_path / "out").exists()
