"""Numerical import checks wrap the unchanged M14 synthetic preprocessing pipeline."""

import json

import nibabel as nib
import pandas as pd
import pytest

from soma.core.provenance import sha256
from soma.human.preprocessing import PreprocessingManifest, audit_manifest


def refresh(d, roots, role):
    a = d["assets"][role]
    a["sha256"] = sha256(roots[a["root"]] / a["path"])


def test_complete_synthetic_audit_separates_technical_QC_and_science(imported):
    manifest, selection, roots, _ = imported
    result = audit_manifest(manifest, selection, roots)
    assert result["technical_status"] == "READY", result
    assert result["qc_status"] == "READY"
    assert result["scientific_adequacy"] == "INDETERMINATE" and not result["inference_authorized"]
    assert result["qc"]["mean_FD_mm"] == pytest.approx(0.05 * 99 / 100)
    assert result["qc"]["first_FD_missing_policy_applied"]
    assert result["qc"]["nonsteady_state_volumes"] == 1
    assert result["qc"]["DVARS_threshold"] is None
    assert result["qc"]["coverage_threshold"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "subject",
        "session",
        "run",
        "software",
        "hash",
        "missing-transform",
        "direction",
        "wrong-reference",
        "SDC",
        "config",
        "BIDS",
        "confound",
        "DVARS",
        "FD",
        "motion",
        "nonsteady",
        "mask",
        "count",
        "escaped",
    ],
)
def test_bad_preprocessing_cannot_be_promoted(imported, fault, tmp_path):
    m, s, roots, bundle = imported
    d = m.document()
    if fault in ("subject", "session", "run"):
        d["identity"][fault] = "wrong"
    elif fault == "software":
        d["software"]["version"] = "different"
    elif fault == "hash":
        bundle.confounds.write_text("changed")
    elif fault == "missing-transform":
        d["transforms"] = []
    elif fault == "direction":
        d["transforms"][0]["to_space"] = "MNI"
    elif fault == "wrong-reference":
        d["transforms"][0]["reference"] = "mask"
    elif fault == "SDC":
        d["distortion_correction"] = "UNKNOWN"
    elif fault == "config":
        d["configuration"] = {}
    elif fault == "BIDS":
        a = d["assets"]["bids-report"]
        p = roots[a["root"]] / a["path"]
        v = json.loads(p.read_text())
        v["input_snapshot_sha256"] = "0" * 64
        p.write_text(json.dumps(v))
        refresh(d, roots, "bids-report")
    elif fault in ("confound", "DVARS", "FD", "motion", "nonsteady"):
        frame = pd.read_csv(bundle.confounds, sep="\t")
        if fault == "confound":
            frame = frame.drop(columns="dvars")
        elif fault == "DVARS":
            frame.loc[3, "dvars"] = -1
        elif fault == "FD":
            frame.loc[3, "framewise_displacement"] = float("nan")
        elif fault == "motion":
            frame.loc[3, "rot_x"] = float("inf")
        else:
            frame["non_steady_state_outlier00"] = frame["non_steady_state_outlier00"].astype(float)
            frame.loc[3, "non_steady_state_outlier00"] = 0.5
        frame.to_csv(bundle.confounds, sep="\t", index=False)
        refresh(d, roots, "confounds")
    elif fault == "mask":
        im = nib.load(bundle.mask)
        a = im.affine.copy()
        a[0, 3] += 10
        nib.save(nib.Nifti1Image(im.get_fdata(), a, im.header), bundle.mask)
        refresh(d, roots, "mask")
    elif fault == "count":
        im = nib.load(bundle.bold)
        nib.save(nib.Nifti1Image(im.get_fdata()[..., :-1], im.affine, im.header), bundle.bold)
        refresh(d, roots, "bold")
    else:
        p = tmp_path / "outside.json"
        p.write_text("{}")
        (roots["derivatives"] / "escaped.json").symlink_to(p)
    result = audit_manifest(PreprocessingManifest.from_dict(d), s, roots)
    assert result["technical_status"] != "READY" or result["qc_status"] != "READY", result
    assert not result["inference_authorized"]


def test_measured_high_motion_fails_QC_without_inventing_thresholds(imported):
    m, s, roots, b = imported
    d = m.document()
    frame = pd.read_csv(b.confounds, sep="\t")
    frame["framewise_displacement"] = 0.6
    frame.to_csv(b.confounds, sep="\t", index=False)
    refresh(d, roots, "confounds")
    r = audit_manifest(PreprocessingManifest.from_dict(d), s, roots)
    assert r["qc_status"] == "BLOCKED" and r["qc"]["high_motion_fraction"] == 1
    assert len(r["qc"]["exclusion_reasons"]) == 2


@pytest.mark.parametrize("fault", ["absolute", "traversal", "unknown-root", "schema"])
def test_manifest_structure_rejects_unsafe_locations(imported, fault):
    m, *_ = imported
    d = m.document()
    if fault == "schema":
        d["schema"] = "unsupported"
    elif fault == "unknown-root":
        d["assets"]["bold"]["root"] = "other"
    else:
        d["assets"]["bold"]["path"] = "/private/file" if fault == "absolute" else "../file"
    with pytest.raises(ValueError):
        PreprocessingManifest.from_dict(d)
