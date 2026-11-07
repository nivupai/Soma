import copy
from pathlib import Path

import mne
import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.reliability.inverse import (
    LinearEstimate,
    array_hash,
    estimate_metrics,
    selected_calibration,
)
from soma.source.inverse import Tikhonov
from soma.source.resolution import Resolution


@pytest.mark.parametrize("lambda2", [0, 0.001, 0.1, 1, 10])
def test_exact_tikhonov_attenuation_and_noise(lambda2):
    singular = np.array([4.0, 2.0, 0.0])
    lead = np.diag(singular)
    inverse = Tikhonov(lead, lambda2)
    expected = np.array([16 / (16 + lambda2), 4 / (4 + lambda2), 0.0])
    cal = selected_calibration(inverse.kernel, lead, [0, 2], np.eye(3) * 0.2)
    assert_allclose(cal["diagonal_gain"], expected)
    assert_allclose(cal["PSF"], np.diag(expected)[:, [0, 2]])
    assert_allclose(cal["CTF"], np.diag(expected)[[0, 2]])
    expected_kernel = np.diag([4 / (16 + lambda2), 2 / (4 + lambda2), 0])
    assert_allclose(inverse.kernel, expected_kernel)
    assert_allclose(cal["noise_variance"], 0.2 * np.diag(expected_kernel) ** 2)
    assert_allclose(cal["noise_operator_norm"], np.max(np.diag(expected_kernel)))


def test_regularization_monotonicity_in_known_singular_basis():
    lead = np.diag([4.0, 2.0, 0.5])
    lambdas = np.logspace(-5, 3, 20)
    diagonals = np.stack([Resolution(Tikhonov(lead, h).kernel, lead).diagonal for h in lambdas])
    assert np.all(np.diff(diagonals, axis=0) < 0)
    residuals = [
        np.linalg.norm(lead @ Tikhonov(lead, h).solve(np.ones(3)) - np.ones(3)) for h in lambdas
    ]
    assert np.all(np.diff(residuals) > 0)


@pytest.mark.parametrize("units", ["dimensionless", "nA m", "V"])
def test_unit_incompatible_amplitude_rejected(units):
    est = LinearEstimate(np.eye(2), "dSPM", 0, 0.1, units, {})
    with pytest.raises(ValueError, match="Physical amplitude"):
        est.amplitude_ratio(np.ones(2), np.ones(2))


def test_signed_phase_and_pooled_magnitude_are_distinct():
    est = LinearEstimate(np.eye(2), "MNE", 0, 0.1, "A m", {})
    truth = np.array([[[1.0, -1.0]], [[0.0, 0.0]]])
    reverse = -truth
    assert est.amplitude_ratio(reverse, truth) == 1
    metrics = estimate_metrics(reverse, truth, np.array([[0.0, 0, 0], [0.01, 0, 0]]), 0)
    assert_allclose(metrics["normalized_pattern_cosine"], -1, atol=1e-14)
    with pytest.raises(ValueError):
        estimate_metrics(reverse.reshape(2, 2), truth, np.zeros((2, 3)), 0)
    with pytest.raises(ValueError):
        est.amplitude_ratio(np.ones(2), np.zeros(2))
    with pytest.raises(ValueError):
        estimate_metrics(np.zeros_like(truth), truth, np.zeros((2, 3)), 0)


def test_selected_resolution_matrix_free_algebra():
    rng = np.random.default_rng(3)
    lead = rng.normal(size=(4, 1500))
    kernel = rng.normal(size=(1500, 4))
    result = selected_calibration(kernel, lead, [5, 14], np.eye(4))
    assert result["PSF"].shape == (1500, 2) and result["CTF"].shape == (2, 1500)
    assert_allclose(result["diagonal_gain"], [kernel[i] @ lead[:, i] for i in range(1500)])
    current = np.zeros(1500)
    current[5] = 1
    assert_allclose(Resolution(kernel, lead).apply(current), result["PSF"][:, 0])


def test_cache_array_fingerprints_bind_shape_dtype_and_order():
    x = np.arange(6.0).reshape(2, 3)
    assert array_hash(x) == array_hash(x.copy())
    assert array_hash(x) != array_hash(x.T)
    assert array_hash(x) != array_hash(x.astype(np.float32))
    assert array_hash(x) != array_hash(x[:, ::-1])


@pytest.mark.integration
def test_actual_mne_calibration_cache_units_and_correspondence(tmp_path):
    from soma.datasets.matched import SampleAssets
    from soma.reliability.inverse import calibrated_inverse
    from soma.source.individual import individual_forward, prepare_sample
    from soma.source.inverse import CorticalInverse
    from soma.source.workflow import synthetic_covariance

    if not SampleAssets().raw_path.exists():
        pytest.skip("Explicit cached sample required")
    assets, model, src, prepared = prepare_sample()
    fwd, _ = individual_forward(model, src)
    _, cov = synthetic_covariance(fwd, seed=100042, samples=10000)
    from scipy.spatial import cKDTree

    from soma.anatomy.surfaces import distance_to_surface

    points = model.head_to_mri.apply(fwd.coordinates.points)
    triangle_distance = distance_to_surface(points, model.surfaces.meshes[0])
    shallow = int(np.argmin(triangle_distance))
    vertex_distance = cKDTree(model.surfaces.meshes[0].vertices.xyz).query(points.xyz[shallow])[0]
    assert triangle_distance[shallow] < 0.001 and vertex_distance > 0.005
    est = calibrated_inverse(fwd, cov, cache_root=tmp_path)
    assert_allclose(est.kernel, CorticalInverse(fwd, cov).kernel, atol=0, rtol=0)
    assert not est.receipt["hit"]
    hit = calibrated_inverse(fwd, cov, cache_root=tmp_path)
    assert hit.receipt["hit"]
    changed = calibrated_inverse(fwd, cov, lambda2=0.01, cache_root=tmp_path)
    assert est.receipt["cache_key"] != changed.receipt["cache_key"]
    dspm = calibrated_inverse(fwd, cov, method="dSPM", cache_root=tmp_path)
    normalized_variance = np.einsum("ij,jk,ik->i", dspm.kernel, cov.data, dspm.kernel)
    assert_allclose(normalized_variance, 1, rtol=1e-6, atol=1e-6)
    cov_changed = mne.Covariance(cov.data * 2, cov.ch_names, [], fwd.info["projs"], 9999)
    changed_cov = calibrated_inverse(fwd, cov_changed, cache_root=tmp_path)
    assert changed_cov.receipt["cache_key"] != est.receipt["cache_key"]
    normalized = calibrated_inverse(fwd, cov, method="sLORETA", cache_root=tmp_path)
    with pytest.raises(ValueError):
        normalized.amplitude_ratio(np.ones(2), np.ones(2))
    vector = calibrated_inverse(fwd, cov, loose=1, cache_root=tmp_path)
    assert_allclose(
        vector.kernel, CorticalInverse(fwd, cov, orientation="free").kernel, atol=0, rtol=0
    )
    reordered = mne.Covariance(cov.data, list(reversed(cov.ch_names)), [], fwd.info["projs"], 9999)
    with pytest.raises(ValueError, match="channel"):
        calibrated_inverse(fwd, reordered, cache_root=tmp_path)
    bad = copy.copy(fwd)
    bad.vertices = [v[::-1] for v in fwd.vertices]
    with pytest.raises(ValueError, match="ordering"):
        calibrated_inverse(bad, cov, cache_root=tmp_path)
    bad = copy.copy(fwd)
    bad.anatomy = {**fwd.anatomy, "subject": "unrelated"}
    with pytest.raises(ValueError, match="identity"):
        calibrated_inverse(bad, cov, cache_root=tmp_path)
    p = Path(est.receipt["path"])
    p.write_bytes(b"invalid-cache")
    with pytest.raises(ValueError, match="checksum"):
        calibrated_inverse(fwd, cov, cache_root=tmp_path)


@pytest.mark.parametrize(
    "settings",
    [{"method": "unsupported"}, {"loose": 0.4}, {"depth": 0.4}, {"lambda2": float("nan")}],
)
def test_invalid_inverse_settings_fail_before_assets(settings):
    from soma.reliability.inverse import calibrated_inverse

    with pytest.raises(ValueError):
        calibrated_inverse(None, None, **settings)
