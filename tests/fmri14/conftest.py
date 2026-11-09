"""Synthetic fMRIPrep-shaped fixtures, never externally preprocessed human data."""

import json

import nibabel as nib
import numpy as np
import pandas as pd
import pytest
import SimpleITK as sitk

from soma.experiments.fmri_simulation import simulate
from soma.fmri.confounds import MOTION
from soma.fmri.preprocessing_audit import PreprocessingBundle
from soma.imaging.nifti import save_nifti
from soma.imaging.volumes import Volume


@pytest.fixture
def bundle(tmp_path):
    run, _ = simulate(14042)
    raw = tmp_path / "raw"
    deriv = tmp_path / "fmriprep"
    raw.mkdir()
    deriv.mkdir()
    (raw / "dataset_description.json").write_text(
        json.dumps({"Name": "Synthetic fMRIPrep adapter fixture", "BIDSVersion": "1.11.2"})
    )
    (raw / "task-motor_bold.json").write_text(
        json.dumps({"TaskName": "motor", "RepetitionTime": run.tr})
    )
    (deriv / "dataset_description.json").write_text(
        json.dumps(
            {
                "Name": "Synthetic fMRIPrep-shaped outputs, no actual fMRIPrep execution",
                "DatasetType": "derivative",
                "BIDSVersion": "1.11.2",
                "GeneratedBy": [{"Name": "fMRIPrep", "Version": "synthetic-fixture"}],
                "SourceDatasets": [{"URL": raw.as_uri()}],
                "DatasetLinks": {"raw": raw.as_uri()},
            }
        )
    )
    rf = raw / "sub-01/ses-test/func"
    rf.mkdir(parents=True)
    df = deriv / "sub-01/ses-test/func"
    df.mkdir(parents=True)
    stem = "sub-01_ses-test_task-motor_run-1"
    rb = rf / (stem + "_bold.nii.gz")
    nib.save(run.image, rb)
    events = run.events.copy()
    events.to_csv(rf / (stem + "_events.tsv"), sep="\t", index=False)
    b = df / (stem + "_space-T1w_desc-preproc_bold.nii.gz")
    nib.save(run.image, b)
    sidecar = b.with_name(b.name.removesuffix(".nii.gz") + ".json")
    sidecar.write_text(
        json.dumps(
            {
                "RepetitionTime": run.tr,
                "SpatialReference": "T1w",
                "Sources": ["bids:raw:" + rb.relative_to(raw).as_posix()],
            }
        )
    )
    mask = df / (stem + "_space-T1w_desc-brain_mask.nii.gz")
    save_nifti(run.mask, mask)
    source = df / (stem + "_boldref.nii.gz")
    save_nifti(Volume(run.image.get_fdata()[..., 0], run.mask.affine_m), source)
    tf = deriv / "sub-01/anat"
    tf.mkdir(parents=True)
    t1 = tf / "sub-01_desc-preproc_T1w.nii.gz"
    save_nifti(Volume(run.image.get_fdata().mean(axis=-1), run.mask.affine_m), t1)
    rta = raw / "sub-01/ses-test/anat"
    rta.mkdir(parents=True)
    raw_t1 = rta / "sub-01_ses-test_T1w.nii.gz"
    save_nifti(Volume(run.image.get_fdata().mean(axis=-1), run.mask.affine_m), raw_t1)
    rng = np.random.default_rng(14042)
    conf = pd.DataFrame({name: rng.normal(0, 0.01, run.n_scans) for name in MOTION})
    conf["framewise_displacement"] = 0.05
    conf.loc[0, "framewise_displacement"] = np.nan
    conf["dvars"] = rng.normal(1, 0.1, run.n_scans)
    conf["a_comp_cor_00"] = rng.normal(size=run.n_scans)
    conf["non_steady_state_outlier00"] = (np.arange(run.n_scans) == 0).astype(int)
    cp = df / (stem + "_desc-confounds_timeseries.tsv")
    conf.to_csv(cp, sep="\t", index=False)
    md = {
        name: {
            "Description": "synthetic measured nuisance",
            "Units": "mm" if name.startswith("trans") else "rad",
        }
        for name in MOTION
    }
    md.update(
        {
            "framewise_displacement": {"Description": "synthetic FD", "Units": "mm"},
            "dvars": {"Description": "synthetic DVARS"},
            "a_comp_cor_00": {"Method": "aCompCor", "Retained": True},
            "non_steady_state_outlier00": {"Description": "synthetic nonsteady-state indicator"},
        }
    )
    cj = cp.with_suffix(".json")
    cj.write_text(json.dumps(md))
    transform = df / (stem + "_from-boldref_to-T1w_mode-image_xfm.txt")
    sitk.WriteTransform(sitk.AffineTransform(3), str(transform))
    points = [[-0.006, -0.006, -0.006], [0.0, 0.0, 0.0], [0.006, 0.006, 0.006]]
    spec = {
        "path": str(transform),
        "subject": "01",
        "from_space": "boldref",
        "to_space": "T1w",
        "kind": "affine",
        "point_direction": "source_to_target",
        "reference": str(t1),
        "source_image": str(source),
        "landmarks_source_RAS_m": points,
        "landmarks_target_RAS_m": points,
    }
    qc = deriv / "sub-01.html"
    qc.write_text("<html><body>Synthetic identity geometry fixture</body></html>")
    return PreprocessingBundle(
        raw,
        deriv,
        rb,
        b,
        mask,
        cp,
        cj,
        t1,
        {"subject": "01", "session": "test", "task": "motor", "run": "1"},
        "T1w",
        (spec,),
        (qc,),
        {
            "visual_QC_review": "synthetic identity checked",
            "slice_time_ref": 0.0,
            "effect_scale_identity": "synthetic-native-units-v1",
            "cross_session_alignment": "analytic common frame",
            "T1_sources": [str(raw_t1)],
        },
    )
