import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.imaging.phantoms import LANDMARKS_M, asymmetric, grid, known_transform
from soma.imaging.registration import RegistrationConfig, register
from soma.imaging.resampling import resample
from soma.imaging.validation import transform_error
from soma.imaging.volumes import Volume


@pytest.mark.parametrize("order", [0, 1, 3])
def test_identity_resampling(order):
    v = asymmetric()
    r = resample(v, v, order=order)
    assert_allclose(r.array(), v.array(), atol=1e-7)
    with pytest.raises(ValueError, match="Repeated"):
        resample(r, v)


def test_linear_analytic_signal_landmark_and_integer_intensity():
    ref = grid()
    ijk = np.moveaxis(np.indices(ref.shape), 0, -1)
    data = (ijk[..., 0] + 2 * ijk[..., 1] + 3 * ijk[..., 2]).astype(np.int16)
    v = Volume(data, ref.affine_m)
    a = ref.affine_m.copy()
    a[:3, 3] += [0.0004, 0.0006, 0.0002]
    target = Volume(np.zeros(ref.shape), a)
    r = resample(v, target)
    assert r.array().dtype.kind == "f"
    assert_allclose(r.array()[2:-2, 2:-2, 2:-2], data[2:-2, 2:-2, 2:-2] + 1.1, atol=1e-12)
    labels = Volume((data % 3).astype(np.uint8), v.affine_m, "labels")
    with pytest.raises(ValueError):
        resample(labels, target, order=1)
    assert set(np.unique(resample(labels, target, order=0).array())) <= {0, 1, 2}


@pytest.mark.parametrize("mode", ["rigid", "affine"])
def test_known_transform_recovery(mode):
    fixed = asymmetric((0.002, 0.0025, 0.003))
    truth = known_transform(mode)
    moving = resample(fixed, fixed, reference_to_source=truth.inverse())
    result = register(fixed, moving, RegistrationConfig(mode=mode))
    errors = transform_error(result.transform, truth, LANDMARKS_M)
    assert errors["median_landmark_TRE_m"] < (0.001 if mode == "rigid" else 0.0015)
    assert errors["rotation_error_deg"] < 1
    assert errors["inverse_consistency_error"] < 1e-12
    warped = result.warp(moving, fixed, allow_repeated=True)
    assert np.mean((warped.array() - fixed.array()) ** 2) < np.mean(
        (moving.array() - fixed.array()) ** 2
    )
    assert result.diagnostics["total_recorded_iterations"] > 0
    assert not result.diagnostics["anatomical_success_claim"]
    bad = grid((0.003,) * 3)
    with pytest.raises(ValueError):
        result.warp(moving, bad)


def test_failure_constant_and_invalid_config():
    v = grid()
    with pytest.raises(ValueError, match="Constant"):
        register(v, v)
    with pytest.raises(ValueError):
        RegistrationConfig(iterations=0)
    with pytest.raises(ValueError):
        RegistrationConfig(shrink_factors=(2, 1), smoothing_sigmas_mm=(0,))


def test_moments_use_raw_intensities_and_noise_blur_are_seeded():
    from soma.imaging.phantoms import transformed_asymmetric

    v = asymmetric((0.003,) * 3, seed=7, noise=0.001, bias=0.1, blur_sigma_m=0.001)
    assert_allclose(
        v.array(),
        asymmetric((0.003,) * 3, seed=7, noise=0.001, bias=0.1, blur_sigma_m=0.001).array(),
    )
    clean = asymmetric((0.003,) * 3)
    truth = known_transform()
    moving = transformed_asymmetric(clean, truth)
    r = register(clean, moving, RegistrationConfig(initialization="moments", iterations=150))
    assert transform_error(r.transform, truth, LANDMARKS_M)["median_landmark_TRE_m"] < 0.001
    with pytest.raises(ValueError):
        asymmetric(blur_sigma_m=-0.001)


def test_boolean_labels_and_unrepresentable_fill():
    v = grid()
    mask = Volume(np.zeros(v.shape, dtype=bool), v.affine_m, "labels")
    assert resample(mask, mask, order=0).array().dtype == np.dtype(bool)
    with pytest.raises(ValueError, match="represented"):
        resample(mask, mask, order=0, cval=2)
    labels = Volume(np.zeros(v.shape, dtype=np.uint8), v.affine_m, "labels")
    with pytest.raises(ValueError):
        resample(labels, labels, order=0, cval=-1)
    with pytest.raises(ValueError):
        resample(labels, labels, order=0, cval=256)
