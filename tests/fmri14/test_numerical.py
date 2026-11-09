"""Independent GLS/ICC arithmetic and controlled correlated-noise checks."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from scipy.linalg import toeplitz

from soma.experiments.fmri_simulation import simulate
from soma.fmri.calibration import calibration_run, gls_oracle, stationary_covariance
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import contrast, fit
from soma.fmri.reliability import cohort_reliability, session_reliability


@pytest.mark.parametrize("rho", [0.0, 0.2, 0.6, -0.4])
def test_GLS_independent_precision_normal_equation(rho):
    rng = np.random.default_rng(14042)
    x = np.c_[np.ones(50), np.linspace(-1, 1, 50), rng.normal(size=50)]
    covariance = toeplitz(rho ** np.arange(50)) / (1 - rho * rho)
    y = (
        x @ np.array([[2.0, 3.0], [1.0, -0.5], [0.3, 2.0]])
        + rng.multivariate_normal(np.zeros(50), covariance, 2).T * 0.2
    )
    c = np.array([0.0, 1.0, -1.0])
    result = gls_oracle(x, y, covariance, c)
    precision = np.linalg.inv(covariance)
    inverse = np.linalg.inv(x.T @ precision @ x)
    beta = inverse @ x.T @ precision @ y
    residual = y - x @ beta
    scale = np.einsum("ij,jk,ki->i", residual.T, precision, residual) / 47
    np.testing.assert_allclose(result["beta"], beta, atol=1e-12)
    np.testing.assert_allclose(result["variance"], scale * (c @ inverse @ c), atol=1e-12)
    np.testing.assert_allclose(
        result["whitened_residual"].T @ result["whitened_residual"],
        residual.T @ precision @ residual,
        atol=1e-12,
    )
    np.testing.assert_allclose(stationary_covariance(50, (rho,)), covariance, atol=1e-12)


@pytest.mark.parametrize(
    "fault", ["rank", "nonpositive", "asymmetric", "shape", "contrast", "unstableAR"]
)
def test_invalid_GLS(fault):
    x = np.c_[np.ones(20), np.arange(20.0)]
    y = np.ones((20, 1))
    v = np.eye(20)
    c = np.array([0.0, 1.0])
    with pytest.raises((ValueError, np.linalg.LinAlgError)):
        if fault == "rank":
            x[:, 1] = 1
        elif fault == "nonpositive":
            v[1, 1] = -1
        elif fault == "asymmetric":
            v[1, 2] = 1
        elif fault == "shape":
            y = y[:-1]
        elif fault == "contrast":
            c = np.array([1.0])
        else:
            stationary_covariance(20, (1.0,))
        gls_oracle(x, y, v, c)


def test_stationary_AR2_covariance_independent_recurrence():
    covariance = stationary_covariance(20, (0.5, 0.2))
    np.linalg.cholesky(covariance)
    gamma = covariance[:, 0]
    assert gamma[1] == pytest.approx(0.5 / (1 - 0.2) * gamma[0])
    np.testing.assert_allclose(gamma[2:], 0.5 * gamma[1:-1] + 0.2 * gamma[:-2], atol=1e-12)
    assert gamma[0] == pytest.approx(0.5 * gamma[1] + 0.2 * gamma[2] + 1)


@pytest.mark.parametrize(
    "scenario", ["gaussian-null", "ar1-null", "ar1-effect", "ar2-null", "hrf-delay"]
)
def test_calibration_streams_deterministic_and_different(scenario):
    a, t, _ = calibration_run(14142, scenario)
    b, _, _ = calibration_run(14142, scenario)
    np.testing.assert_array_equal(a.image.dataobj, b.image.dataobj)
    c, _, _ = calibration_run(14143, scenario)
    assert not np.array_equal(a.image.dataobj, c.image.dataobj)
    if scenario.endswith("null"):
        assert not np.any(t["beta"])


@pytest.mark.parametrize("model", ["ols", "ar1", "ar2"])
def test_noise_models_and_whitening(model):
    run, _, _ = calibration_run(14142, "ar1-effect")
    f = fit(
        run, ModelConfig(noise_model=model, drift_model=None, confound_columns=("motion", "trend"))
    )
    e = contrast(f, Contrast("task", {"task": 1}))
    assert np.isfinite(e.maps["stat"].get_fdata()).all()
    assert f.diagnostics["residual_dof"] == 96
    if model != "ols":
        assert abs(f.diagnostics["mean_whitened_residual_lag1"]) < 0.15


def test_ICC_exact_perfect_and_constant_session_bias():
    values = np.arange(1.0, 11.0)
    table = pd.DataFrame(
        {
            "subject": np.repeat([str(i) for i in range(10)], 2),
            "session": ["A", "B"] * 10,
            "effect": np.repeat(values, 2),
        }
    )
    result = cohort_reliability(table, n_bootstrap=100)
    assert result["ICC"] == pytest.approx(1)
    table.loc[table.session == "B", "effect"] += 2
    result = cohort_reliability(table, n_bootstrap=100)
    # MSsubject=2*sample_var(values), MSsession=n*2, MSerror=0.
    expected = (2 * np.var(values, ddof=1)) / (2 * np.var(values, ddof=1) + 4)
    assert result["ICC"] == pytest.approx(expected)
    assert result["ICC"] < 1 and result["mean_paired_effect_change"]["estimate"] == 2


def test_ICC_rejects_voxel_units_single_subject_and_duplicates():
    data = pd.DataFrame({"subject": ["s", "s"], "session": ["A", "B"], "effect": [1.0, 2.0]})
    with pytest.raises(ValueError, match="participants"):
        cohort_reliability(data, statistical_unit="voxel")
    with pytest.raises(ValueError, match="5"):
        cohort_reliability(data)
    with pytest.raises(ValueError, match="Unique"):
        cohort_reliability(pd.concat([data, data]))


def test_session_sign_flip_not_same_activation_and_model_guards():
    run, _ = simulate(14042)
    other, _ = simulate(14043, session="retest")
    cfg = ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    c = Contrast("task", {"task": 1})
    a = contrast(fit(run, cfg), c)
    b = contrast(fit(other, cfg), c)
    result = session_reliability(a, b)
    assert result["sign_specific"]["positive"]["Dice"] > 0.8
    assert result["statistical_units"]["cohort"] == "participant"
    image = b.maps["effect_size"]
    import nibabel as nib

    flipped = replace(
        b, maps={**b.maps, "effect_size": nib.Nifti1Image(-image.get_fdata(), image.affine)}
    )
    reversed_result = session_reliability(a, flipped)
    assert reversed_result["sign_specific"]["positive"]["Dice"] < 0.1
    assert reversed_result["map_correlation"] < -0.8
    with pytest.raises(ValueError, match="scales"):
        session_reliability(
            a, replace(b, run=replace(other, provenance={"source": "missing scale"}))
        )
    with pytest.raises(ValueError, match="HRF"):
        session_reliability(a, replace(b, metadata={**b.metadata, "hrf_model": "glover"}))


def test_ROI_reliability_requires_actual_atlas_and_grid():
    from soma.fmri.reliability import regional_reliability
    from soma.fmri.spatial import SpatialMap
    from soma.imaging.volumes import Volume

    run, truth = simulate(14042)
    other, _ = simulate(14043, session="retest")
    cfg = ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    first = contrast(fit(run, cfg), Contrast("task", {"task": 1}))
    second = contrast(fit(other, cfg), first.contrast)
    labels = Volume(truth["positive"].astype(np.uint8), run.mask.affine_m, "labels")
    roi = SpatialMap(
        labels,
        run.subject,
        run.space,
        "analytic ROI",
        {
            "source": "synthetic analytic atlas",
            "atlas_name": "analytic",
            "atlas_version": "1",
            "hemisphere_convention": "known RAS origin",
            "label_mapping": {1: "positive region"},
        },
    )
    result = regional_reliability(first, second, roi)
    assert result["regions"][0]["common_mask_voxels"] == 27
    assert result["regions"][0]["session_mean_effects"][0] > 2.5
    with pytest.raises(ValueError, match="atlas"):
        regional_reliability(first, second, replace(roi, provenance={"source": "incomplete"}))
