import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.anatomy.synthetic import sphere_mesh
from soma.geometry import Frame, Points, Transform
from soma.imaging.mesh_quality import mesh_quality
from soma.imaging.surfaces import Mesh
from soma.reliability.evidence import Evidence, evidence_state, surface_mask_consistency
from soma.reliability.registration import (
    phantom,
    registration_experiments,
    target_covariance,
    wilson,
)
from soma.reliability.workflows import compare_transform, require_head_mri


def test_transform_direction_and_reference_difference_not_truth():
    surface, fit, held, truth = phantom()
    require_head_mri(truth)
    with pytest.raises(ValueError):
        require_head_mri(truth.inverse())
    with pytest.raises(ValueError):
        truth.apply(truth.apply(held))
    reference = Transform(Frame.HEAD, Frame.MRI, np.eye(4))
    difference = compare_transform(truth, reference, held)
    assert difference["translation_difference_mm"] > 5
    assert difference["point_displacement_RMS_mm"] > 0
    assert len(held.xyz) == 8 and len(fit.xyz) == 4
    assert not any(np.allclose(a, b) for a in held.xyz for b in fit.xyz)


def test_independent_target_covariance_exact_centroid_oracle():
    _, fit, _, truth = phantom()
    held = Points(fit.xyz.mean(axis=0, keepdims=True), Frame.HEAD)
    c = np.kron(np.eye(4), np.diag([1e-6, 4e-6, 16e-6]))
    actual = target_covariance(fit, truth.apply(fit), held, c)
    # Rigid fitting maps the source centroid to the observed target centroid.
    assert_allclose(actual, np.diag([1e-6, 4e-6, 16e-6]) / 4, rtol=1e-8, atol=1e-15)
    with pytest.raises(ValueError):
        target_covariance(fit, fit, held, c)
    with pytest.raises(ValueError):
        target_covariance(fit, truth.apply(fit), held, -c)


def test_registration_simulation_determinism_and_heldout_errors():
    a = registration_experiments(42, 4)
    b = registration_experiments(42, 4)
    assert a == b
    assert set(a["coverage"]) == {"independent", "correlated", "anisotropic"}
    assert all(v["count"] == 4 for v in a["coverage"].values())
    assert any(r["heldout_TRE_RMS_mm"] != r["fit_RMS_mm"] for r in a["records"])
    assert any(f["case"] == "wrong_correspondence" for f in a["failures"])
    with pytest.raises(ValueError):
        registration_experiments(42, 1)


@pytest.mark.parametrize("k,n", [(0, 20), (19, 20), (20, 20)])
def test_binomial_interval(k, n):
    low, high = wilson(k, n)
    assert -1e-15 <= low <= k / n <= high <= 1 + 1e-15
    with pytest.raises(ValueError):
        wilson(n + 1, n)


def test_missing_evidence_never_certifies_anatomy():
    geometry = Evidence(
        "geometry", "computationally_verified", "PASS", "closed triangle shell", {"synthetic": True}
    )
    missing = Evidence(
        "anatomy",
        "not_assessed",
        "INDETERMINATE",
        "no independent reference",
        {"subject": "synthetic"},
    )
    heuristic = Evidence(
        "plausibility",
        "heuristically_assessed",
        "INDETERMINATE",
        "mask consistency",
        {"same_pipeline": True},
    )
    assert evidence_state([geometry, missing, heuristic]) == "INDETERMINATE"
    failed = Evidence("geometry", "failed", "FAIL", "nonmanifold", {"test": True})
    assert evidence_state([failed, missing]) == "FAIL"
    with pytest.raises(ValueError):
        Evidence("anatomy", "heuristically_assessed", "PASS", "score", {"x": 1})


def test_surface_mask_analytic_sphere_and_displacement():
    rr, tris = sphere_mesh(2, 0.02)
    mesh = Mesh(Points(rr, Frame.MRI), tris)
    shape = (61, 61, 61)
    grid = np.indices(shape).transpose(1, 2, 3, 0)
    mask = (np.linalg.norm((grid - 30) * 0.001, axis=-1) <= 0.02).astype(np.uint8)
    affine = np.diag([0.001, 0.001, 0.001, 1.0])
    affine[:3, 3] = -0.03
    check = surface_mask_consistency(mesh, mask, affine, limit=100)
    distance = np.array(check["surface_to_boundary_voxel_center_distance_m"])
    assert distance.max() < 0.0018
    assert check["mask_components_6_connected"] == 1
    assert check["Dice"] is None and not check["independent_anatomical_ground_truth"]
    outer = Mesh(Points(rr * 1.25, Frame.MRI), tris)
    shifted = surface_mask_consistency(outer, mask, affine, limit=100)
    assert 0.004 < np.median(shifted["surface_to_boundary_voxel_center_distance_m"]) < 0.0065
    assert mesh_quality(mesh)["outward_global_winding"]
    with pytest.raises(ValueError):
        surface_mask_consistency(Mesh(Points(rr, Frame.HEAD), tris), mask, affine)
    with pytest.raises(ValueError):
        surface_mask_consistency(mesh, np.zeros(shape), affine)


def test_evidence_serialization_preserves_mne_provenance_list_subclasses():
    import json

    import mne

    info = mne.create_info(["EEG001"], 160, "eeg")
    record = Evidence(
        "MRI", "external_reference", "PASS", "source receipt", {"bad_channels": info["bads"]}
    )
    assert json.loads(json.dumps(record.to_dict()))["provenance"]["bad_channels"] == []
