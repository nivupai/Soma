"""End-to-end smoke run of the M33 skull runner on synthetic data with a fake SynthSeg.

Checks only that the pipeline runs and writes its outputs; no real SynthRAD case is read and
no estimator-vs-CT number is asserted.
"""

import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from scripts import run_m33_skull_validation as runner
from soma.core.provenance import sha256
from tests.skull_phantom import phantom

FAKE_SYNTHSEG = """
import sys
import nibabel as nib
import numpy as np
image = nib.load(sys.argv[1])
t1 = np.asarray(image.dataobj)
labels = np.zeros(t1.shape, np.int16)
labels[np.abs(t1 - 0.2) < 0.05] = 24
labels[np.abs(t1 - 0.6) < 0.05] = 3
out = nib.Nifti1Image(labels, image.affine)
out.header.set_xyzt_units("mm")
nib.save(out, sys.argv[2])
"""


def _save(volume, path: Path) -> None:
    affine = np.array(volume.affine_m, dtype=float)
    affine[:3] *= 1000
    image = nib.Nifti1Image(volume.array(), affine)
    image.set_qform(affine, code=1)
    image.set_sform(None, code=0)
    image.header.set_xyzt_units("mm")
    nib.save(image, path)


@pytest.mark.integration
def test_runner_end_to_end_on_synthetic_case(tmp_path: Path, monkeypatch) -> None:
    case = tmp_path / "data" / "1BA001"
    case.mkdir(parents=True)
    ph = phantom()
    for name, key in (("mr", "t1"), ("ct", "ct"), ("mask", "mask")):
        _save(ph[key], case / f"{name}.nii.gz")
    script = tmp_path / "fake_synthseg.py"
    script.write_text(FAKE_SYNTHSEG)
    protocol, freeze = tmp_path / "protocol.md", tmp_path / "freeze.json"
    protocol.write_text("synthetic protocol\n")
    freeze.write_text(json.dumps({"protocol_sha256": sha256(protocol), "owner_approved": True}))
    monkeypatch.setattr(runner, "PROTOCOL", protocol)
    monkeypatch.setattr(runner, "FREEZE", freeze)
    output = tmp_path / "out"
    runner.main(
        [
            "--synthseg-cmd",
            f"{sys.executable} {script} {{input}} {{output}}",
            "--data-root",
            str(tmp_path / "data"),
            "--output",
            str(output),
        ]
    )
    summary = json.loads((output / "cohort-summary.json").read_text())
    assert summary["failures"] == [] and summary["completed_cases"] == 1
    assert summary["cohort"]["decision"]["readiness"] in {"NOT_READY", "QC_ONLY", "VALIDATED"}
    per_case = json.loads((output / "cases" / "1BA001" / "skull-metrics.json").read_text())
    assert set(per_case["scores"]) == {"300.0", "200.0", "400.0"}
    assert per_case["centre"] == "A"
    assert "flags" in per_case and "region" in per_case["scores"]["300.0"]
