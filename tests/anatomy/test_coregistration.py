import mne
import numpy as np
import pytest
from numpy.testing import assert_allclose
from scipy.spatial.transform import Rotation

from soma.geometry import Frame, Points, Transform
from soma.geometry.coregistration import align_fiducials, icp_align, rigid_align


def fixture():
    x = np.random.default_rng(2).normal(size=(20, 3)) * 0.04
    t = np.eye(4)
    t[:3, :3] = Rotation.from_euler("xyz", [10, -5, 8], degrees=True).as_matrix()
    t[:3, 3] = [0.003, -0.004, 0.005]
    transform = Transform(Frame.HEAD, Frame.MRI, t)
    source = Points(x, Frame.HEAD)
    return source, transform.apply(source), transform


@pytest.mark.parametrize("weights", [None, np.arange(1.0, 21)])
def test_weighted_rigid_independent_truth_and_MNE(weights):
    source, target, truth = fixture()
    fit = rigid_align(source, target, weights=weights)
    assert_allclose(fit.transform.matrix, truth.matrix, atol=1e-13)
    assert fit.diagnostics["weighted_RMS_m"] < 1e-14
    reference = mne.coreg.fit_matched_points(
        source.xyz, target.xyz, weights=weights, scale=False, out="trans"
    )
    assert_allclose(fit.transform.matrix, reference, atol=1e-8)
    assert_allclose(fit.transform.inverse().apply(target).xyz, source.xyz, atol=1e-14)


def test_planar_fiducials_and_named_correspondences():
    source, target, truth = fixture()
    x = Points(source.xyz[:3], Frame.HEAD)
    y = Points(target.xyz[:3], Frame.MRI)
    fit = align_fiducials(
        x, ("LPA", "nasion", "RPA"), Points(y.xyz[[2, 0, 1]], Frame.MRI), ("RPA", "LPA", "nasion")
    )
    assert_allclose(fit.transform.matrix, truth.matrix, atol=1e-13)
    assert not fit.diagnostics["reflection_identifiable"]
    with pytest.raises(ValueError):
        align_fiducials(x, ("LPA", "nasion", "LPA"), y, ("LPA", "nasion", "RPA"))
    broken = y.xyz.copy()
    broken[0] += [0.04, 0.02, 0]
    with pytest.raises(ValueError, match="mismatch"):
        align_fiducials(
            x,
            ("LPA", "nasion", "RPA"),
            Points(broken, Frame.MRI),
            ("LPA", "nasion", "RPA"),
            maximum_residual_m=0.001,
        )


@pytest.mark.parametrize("count", [1, 2, 4])
def test_collinear_or_insufficient(count):
    x = np.column_stack([np.arange(count) * 0.01, np.zeros(count), np.zeros(count)])
    with pytest.raises(ValueError):
        rigid_align(Points(x, Frame.HEAD), Points(x, Frame.MRI))


def test_reflection_rejection():
    x, y, t = fixture()
    with pytest.raises(ValueError, match="reflection"):
        rigid_align(x, Points(y.xyz * [-1, 1, 1], Frame.MRI))


@pytest.mark.parametrize("weights", [[1, 2], np.ones(20) * np.nan, [-1] + [1] * 19, [0] * 20])
def test_invalid_weights(weights):
    x, y, _ = fixture()
    with pytest.raises(ValueError):
        rigid_align(x, y, weights=weights)


def test_robust_outliers_are_reproducible_and_not_silently_accepted():
    x, y, truth = fixture()
    corrupt = y.xyz.copy()
    corrupt[:4] += [0.05, 0.02, -0.03]
    plain = rigid_align(x, Points(corrupt, Frame.MRI))
    robust = rigid_align(x, Points(corrupt, Frame.MRI), robust_cutoff_m=0.002, seed=5)
    again = rigid_align(x, Points(corrupt, Frame.MRI), robust_cutoff_m=0.002, seed=5)
    assert np.linalg.norm(plain.transform.matrix - truth.matrix) > 0.01
    assert_allclose(robust.transform.matrix, truth.matrix, atol=1e-12)
    assert_allclose(robust.transform.matrix, again.transform.matrix)
    assert robust.diagnostics["outliers"] == 4


def test_ICP_known_irregular_surface_and_frame_safety():
    x, y, truth = fixture()
    identity = Transform(Frame.HEAD, Frame.MRI, np.eye(4))
    fit = icp_align(
        x, y, identity, measurement_kind="synthetic_headshape", trim_fraction=1, max_distance_m=0.1
    )
    assert_allclose(fit.transform.matrix, truth.matrix, atol=1e-12)
    assert not fit.diagnostics["anatomical_ground_truth_claim"]
    with pytest.raises(ValueError):
        icp_align(x, y, identity, measurement_kind="EEG_electrodes")
    with pytest.raises(ValueError):
        icp_align(
            x,
            y,
            Transform(Frame.MRI, Frame.HEAD, np.eye(4)),
            measurement_kind="digitized_headshape",
        )


def test_units_and_invalid_points():
    with pytest.raises(ValueError):
        Points(np.ones((4, 3)) * 80, Frame.HEAD)
    with pytest.raises(ValueError):
        Points(np.ones((4, 3)), Frame.HEAD, "mm")
    with pytest.raises(ValueError):
        Points(np.full((4, 3), np.nan), Frame.HEAD)
    assert_allclose(Points.from_mm(np.ones((4, 3)) * 80, Frame.HEAD).xyz, 0.08)
