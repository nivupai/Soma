"""Provenance and geometry adversarial tests use only synthetic external outputs."""

import json
from dataclasses import replace

import nibabel as nib
import numpy as np
import pandas as pd
import pytest
import SimpleITK as sitk

from soma.fmri.confounds import configure_confounds
from soma.fmri.preprocessing_audit import audit_preprocessing, discover_bundle, load_audited_run
from soma.fmri.transform_audit import audit_transform


def test_complete_audit_is_numerical_not_anatomical_certification(bundle):
    receipt = audit_preprocessing(bundle)
    assert receipt["status"] == "PASS", receipt
    assert receipt["eligible"] is True and receipt["anatomical_validity"] == "INDETERMINATE"
    r = load_audited_run(bundle, receipt)
    assert r.preprocessing == "validated" and r.identity[:3] == ("01", "test", "motor")
    discovered = discover_bundle(
        bundle.raw_root,
        bundle.derivative_root,
        subject="01",
        session="test",
        task="motor",
        run="1",
        space="T1w",
        evidence={**bundle.evidence, "transforms": list(bundle.transforms)},
    )
    assert discovered.bold == bundle.bold


@pytest.mark.parametrize(
    "fault",
    [
        "subject",
        "session",
        "TR",
        "mask",
        "count",
        "confounds",
        "software",
        "source",
        "missing",
        "transform",
        "units",
        "definitions",
        "QC",
    ],
)
def test_adversarial_audit(bundle, fault):
    if fault in ["subject", "session"]:
        bundle = replace(bundle, identity={**bundle.identity, fault: "wrong"})
    elif fault == "TR":
        path = bundle.raw_root / "task-motor_bold.json"
        path.write_text(json.dumps({"RepetitionTime": 3.0}))
    elif fault == "mask":
        image = nib.load(bundle.mask)
        a = image.affine.copy()
        a[0, 3] += 3
        nib.save(nib.Nifti1Image(image.get_fdata(), a), bundle.mask)
    elif fault == "count":
        image = nib.load(bundle.bold)
        nib.save(
            nib.Nifti1Image(image.get_fdata()[..., :-1], image.affine, image.header), bundle.bold
        )
    elif fault == "confounds":
        frame = pd.read_csv(bundle.confounds, sep="\t")
        frame.iloc[:-1].to_csv(bundle.confounds, sep="\t", index=False)
    elif fault == "software":
        p = bundle.derivative_root / "dataset_description.json"
        v = json.loads(p.read_text())
        v["GeneratedBy"] = []
        p.write_text(json.dumps(v))
    elif fault == "source":
        p = bundle.bold.with_name(bundle.bold.name.removesuffix(".nii.gz") + ".json")
        v = json.loads(p.read_text())
        v["Sources"] = []
        p.write_text(json.dumps(v))
    elif fault == "missing":
        bundle.confound_json.unlink()
    elif fault == "transform":
        bundle = replace(bundle, transforms=({**bundle.transforms[0], "to_space": "MNI"},))
    elif fault == "units":
        image = nib.load(bundle.bold)
        image.header.set_xyzt_units("mm", "msec")
        nib.save(image, bundle.bold)
    elif fault == "definitions":
        bundle.confound_json.write_text("{}")
    else:
        bundle = replace(bundle, evidence={})
    result = audit_preprocessing(bundle)
    assert result["eligible"] is False
    assert result["status"] in {"FAIL", "INDETERMINATE"}


def test_stale_preprocessing_cache_never_accepted(bundle):
    receipt = audit_preprocessing(bundle)
    metadata = json.loads(bundle.confound_json.read_text())
    metadata["extra"] = {"Description": "changed provenance"}
    bundle.confound_json.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="stale"):
        load_audited_run(bundle, receipt)


@pytest.mark.parametrize("strategy", ["minimal", "expanded", "compcor", "fd-spikes"])
def test_confound_strategies_keep_time_grid(bundle, strategy):
    run = load_audited_run(bundle, audit_preprocessing(bundle))
    cfg, report = configure_confounds(
        run, json.loads(bundle.confound_json.read_text()), strategy=strategy
    )
    assert report["eligible"] and report["deleted_observations"] == 0
    assert report["acquired_observations"] == 100 and report["design"]["residual_dof"] >= 20
    assert cfg.motion_derivatives == (strategy == "expanded")
    assert report["first_FD_missing_policy_applied"] is True


def test_motion_exclusion_and_absent_compcor(bundle):
    run = load_audited_run(bundle, audit_preprocessing(bundle))
    c = run.confounds.copy()
    c["framewise_displacement"] = 0.6
    _, report = configure_confounds(
        replace(run, confounds=c), json.loads(bundle.confound_json.read_text())
    )
    assert not report["eligible"] and len(report["exclusion_reasons"]) == 2
    with pytest.raises(ValueError, match="CompCor"):
        configure_confounds(
            replace(run, confounds=c.drop(columns="a_comp_cor_00")),
            json.loads(bundle.confound_json.read_text()),
            strategy="compcor",
        )


def test_LPS_transform_landmarks_and_nonlinear_not_affine(bundle):
    spec = bundle.transforms[0].copy()
    matrix = sitk.AffineTransform(3)
    matrix.SetTranslation((-2.0, 3.0, 1.0))
    sitk.WriteTransform(matrix, spec["path"])
    points = np.asarray(spec["landmarks_source_RAS_m"])
    spec["landmarks_target_RAS_m"] = (points + np.array([0.002, -0.003, 0.001])).tolist()
    result = audit_transform(spec, subject="01")
    assert np.max(result["landmark_error_mm"]) < 1e-10
    spec["point_direction"] = "target_to_source"
    with pytest.raises(ValueError, match="landmark"):
        audit_transform(spec, subject="01")
    field = sitk.Image([7, 7, 7], sitk.sitkVectorFloat64, 3)
    field.SetSpacing((3.0, 3.0, 3.0))
    warp = sitk.DisplacementFieldTransform(field)
    sitk.WriteTransform(warp, spec["path"])
    with pytest.raises(ValueError, match="affine"):
        audit_transform(spec, subject="01")


def test_nonlinear_composite_keeps_ITK_reference_and_composition(bundle):
    spec = bundle.transforms[0].copy()
    # Large explicit LPS-mm domain, constant displacement, then90deg rotation.
    array = np.zeros((21, 21, 21, 3))
    array[..., 0] = 1.0
    field = sitk.GetImageFromArray(array, isVector=True)
    field.SetSpacing((3.0, 3.0, 3.0))
    field.SetOrigin((-30.0, -30.0, -30.0))
    warp = sitk.DisplacementFieldTransform(field)
    affine = sitk.AffineTransform(3)
    affine.SetMatrix((0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0))
    composite = sitk.CompositeTransform([affine, warp])
    path = bundle.bold.parent / "sub-01_from-boldref_to-T1w_mode-image_xfm.h5"
    sitk.WriteTransform(composite, str(path))
    points = np.asarray(spec["landmarks_source_RAS_m"])
    target = np.c_[-points[:, 1], points[:, 0] - 0.001, points[:, 2]]
    spec.update(path=str(path), kind="nonlinear", landmarks_target_RAS_m=target.tolist())
    r = audit_transform(spec, subject="01")
    assert r["linear"] is False and r["kind"] == "nonlinear"
    assert r["landmark_status"] == "PASS" and r["inverse_available"] is False


def test_singular_affine_cannot_pass_collinear_landmarks(bundle):
    spec = bundle.transforms[0].copy()
    projection = sitk.AffineTransform(3)
    direction = np.array([-1.0, -1.0, 1.0]) / np.sqrt(3)
    projection.SetMatrix(tuple(np.outer(direction, direction).ravel()))
    sitk.WriteTransform(projection, spec["path"])
    with pytest.raises(ValueError, match="Singular affine"):
        audit_transform(spec, subject="01")
