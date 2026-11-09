"""Independent arithmetic, null assumptions and policy enforcement; offline only."""

from dataclasses import replace

import numpy as np
import pytest
from scipy.linalg import cholesky
from scipy.stats import t

from soma.experiments.fmri_simulation import simulate
from soma.fmri.calibration import stationary_covariance
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import contrast, fit
from soma.fmri.inference import InferencePolicy, adjust_probabilities
from soma.fmri.null_audit import (
    fixed_design,
    generator,
    matrix_fit,
    probability_summary,
    reference_fit,
)


@pytest.mark.parametrize("model", ["ols", "ar1", "ar2"])
def test_low_level_numerics_match_independent_whitened_QR(model):
    d = generator(1401000, 1, 0, 0, "ar1", 100, 3)
    x, y, c = d["X"], d["Y"], d["c"]
    actual = matrix_fit(y, x, c, model)
    for voxel in [0, 4, 15]:
        w = np.eye(100)
        for lag, rho in enumerate(actual["rho"][voxel], 1):
            w[lag:] -= rho * np.eye(100)[:-lag]
        wx = w @ x
        wy = w @ y[:, voxel]
        q, r = np.linalg.qr(wx)
        beta = np.linalg.solve(r, q.T @ wy)
        residual = wy - wx @ beta
        variance = (residual @ residual) / 96 * np.sum(np.linalg.solve(r.T, c) ** 2)
        effect = c @ beta
        stat = effect / np.sqrt(variance)
        assert actual["effect"][voxel] == pytest.approx(effect, abs=1e-9)
        assert actual["SE"][voxel] == pytest.approx(np.sqrt(variance), abs=1e-10)
        assert actual["p"][voxel] == pytest.approx(2 * t.sf(abs(stat), 96), abs=1e-10)
    assert actual["max_z_to_t_p_error"] < 1e-12


@pytest.mark.parametrize("noise", ["iid", "ar1", "ar2"])
def test_global_null_mean_is_in_nuisance_span(noise):
    d = generator(1401000, 1, 0, 0, noise, 100, 3)
    beta = np.linalg.lstsq(d["X"], d["mean"], rcond=None)[0]
    np.testing.assert_allclose(d["X"] @ beta, d["mean"], atol=1e-11)
    np.testing.assert_allclose(d["c"] @ beta, 0, atol=1e-11)
    assert not np.any(d["beta"])


def test_mixture_mean_has_exact_prespecified_effects():
    d = generator(1401000, 2, 0, 0, "ar1", 100, 7, "mixture")
    beta = np.linalg.lstsq(d["X"], d["mean"], rcond=None)[0]
    np.testing.assert_allclose(d["c"] @ beta, d["beta"], atol=1e-11)
    assert np.any(d["beta"] == 0) and np.any(d["beta"] > 0) and np.any(d["beta"] < 0)


def test_independent_stage_case_and_replicate_streams():
    a = generator(1401000, 1, 0, 0, "iid", 100, 3)
    b = generator(1401000, 1, 0, 0, "iid", 100, 3)
    np.testing.assert_array_equal(a["Y"], b["Y"])
    for stage, case, rep in [(2, 0, 0), (1, 1, 0), (1, 0, 1)]:
        c = generator(1401000, stage, case, rep, "iid", 100, 3)
        assert not np.array_equal(a["Y"], c["Y"])
        assert (
            abs(np.corrcoef((a["Y"] - a["mean"]).ravel(), (c["Y"] - c["mean"]).ravel())[0, 1])
            < 0.15
        )


@pytest.mark.parametrize("spatial", ["independent", "correlated", "smoothed"])
def test_declared_spatial_operator_and_covariance(spatial):
    d = generator(1401000, 2, 0, 0, "ar1", 100, 3, spatial)
    np.testing.assert_allclose(d["spatial_C"], d["G"] @ d["G"].T)
    np.testing.assert_allclose(d["G"].sum(axis=1), 1, atol=1e-12)
    assert d["Y"].shape == (100, 27)
    np.linalg.cholesky(d["C"])


def test_known_covariance_null_probabilities_broad_uniformity():
    x, c = fixed_design(100)
    cov = stationary_covariance(100, (0.6,))
    rng = np.random.default_rng(1401000)
    y = x @ np.array([[0.0], [0.3], [2.0], [100.0]]) + cholesky(cov, lower=True) @ rng.normal(
        size=(100, 128)
    )
    actual = reference_fit(y, x, c, cov)
    assert probability_summary(actual["p"])["KS_D"] < 0.2
    assert np.mean(actual["p"] < 0.05) < 0.15
    np.testing.assert_allclose(
        reference_fit(y, x, c, np.eye(100))["effect"],
        matrix_fit(y, x, c, "ols")["effect"],
        atol=1e-10,
    )


@pytest.mark.parametrize("fault", ["rank", "samples", "voxels", "model"])
def test_matrix_diagnostic_bounds_and_rank(fault):
    x, c = fixed_design(100)
    y = np.ones((100, 2))
    if fault == "rank":
        x[:, 1] = x[:, 2]
    if fault == "samples":
        y = y[:-1]
    if fault == "voxels":
        y = np.ones((100, 1001))
    with pytest.raises(ValueError):
        matrix_fit(y, x, c, "bad" if fault == "model" else "ols")


def test_multiple_testing_independent_hand_values():
    p = np.array([0.001, 0.01, 0.04, 0.3])
    expected = np.array([0.004, 0.02, 0.04 * 4 / 3, 0.3])
    np.testing.assert_allclose(adjust_probabilities(p, "bh"), expected)
    np.testing.assert_allclose(
        adjust_probabilities(p, "by"), np.minimum(1, expected * np.sum(1 / np.arange(1, 5)))
    )
    np.testing.assert_allclose(adjust_probabilities(p, "bonferroni"), [0.004, 0.04, 0.16, 1])
    permutation = np.array([2, 0, 3, 1])
    np.testing.assert_allclose(adjust_probabilities(p[permutation]), expected[permutation])


@pytest.mark.parametrize("values", [[np.nan], [1.1], [-0.1], [], [[0.2, 0.1]]])
def test_invalid_probabilities_rejected(values):
    with pytest.raises(ValueError):
        adjust_probabilities(np.array(values))


@pytest.fixture
def fitted():
    run, _ = simulate(1401000)
    run = replace(
        run,
        provenance={
            **run.provenance,
            "calibration_contract": {"family": "iid-Gaussian-fixed-X-independent-voxels"},
        },
    )
    return fit(
        run, ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    )


def test_default_preserves_descriptive_maps_and_restricts_claims(fitted):
    e = contrast(fitted, Contrast("task", {"task": 1}))
    assert e.metadata["confirmatory_claim_allowed"] is False
    assert "effect_size" in e.maps and "fdr_reject" in e.maps
    mask = fitted.run.mask.array().astype(bool)
    for method, name, rejected in [
        ("by", "q_by", "fdr_reject"),
        ("bonferroni", "p_bonferroni", "fwe_reject"),
    ]:
        alternative = contrast(fitted, e.contrast, policy=InferencePolicy(correction=method))
        assert name in alternative.maps and rejected in alternative.maps
        assert "q_bh" not in alternative.maps
        np.testing.assert_allclose(
            alternative.maps[name].get_fdata()[mask],
            adjust_probabilities(e.maps["p_two_sided"].get_fdata()[mask], method),
            atol=1e-7,
        )
    approved = contrast(fitted, e.contrast, policy=InferencePolicy("confirmatory"))
    assert approved.metadata["confirmatory_claim_allowed"] is True
    np.testing.assert_array_equal(
        approved.maps["effect_size"].get_fdata(), e.maps["effect_size"].get_fdata()
    )


@pytest.mark.parametrize(
    "fault", ["ar1", "ar2", "human", "undeclared", "smoothing", "q", "correction"]
)
def test_unsupported_confirmation_cannot_be_silently_approved(fitted, fault):
    config = fitted.config
    run = fitted.run
    policy = InferencePolicy("confirmatory")
    if fault in ["ar1", "ar2"]:
        config = replace(config, noise_model=fault)
    elif fault == "human":
        run = replace(
            run,
            preprocessing="validated",
            provenance={**run.provenance, "preprocessing_evidence": "mock external"},
        )
    elif fault == "undeclared":
        run = replace(run, provenance={"source": "undeclared"})
    elif fault == "smoothing":
        config = replace(config, smoothing_fwhm=3.0)
    elif fault == "q":
        config = replace(config, q=0.01)
    else:
        policy = InferencePolicy("confirmatory", "by")
    with pytest.raises(ValueError, match="Unsupported confirmatory"):
        contrast(
            replace(fitted, run=run, config=config), Contrast("task", {"task": 1}), policy=policy
        )


@pytest.mark.parametrize("model", ["ols", "ar1", "ar2"])
def test_full_image_pipeline_equals_matrix_diagnostic(model):
    import nibabel as nib

    base, _ = simulate(1401000, beta=0, n_scans=100)
    d = generator(1401000, 2, 0, 0, "ar1", 100, 7)
    image = nib.Nifti1Image(d["Y"].T.reshape(7, 7, 7, 100), base.image.affine, base.image.header)
    run = replace(base, image=image)
    f = fit(
        run, ModelConfig(noise_model=model, drift_model=None, confound_columns=("motion", "trend"))
    )
    e = contrast(f, Contrast("task", {"task": 1}))
    matrix = matrix_fit(d["Y"], d["X"], d["c"], model)
    np.testing.assert_allclose(
        e.maps["effect_size"].get_fdata().ravel(), matrix["effect"], atol=1e-10
    )
    np.testing.assert_allclose(
        e.maps["effect_variance"].get_fdata().ravel(), matrix["SE"] ** 2, atol=1e-10
    )
    np.testing.assert_allclose(e.maps["p_two_sided"].get_fdata().ravel(), matrix["p"], atol=3e-8)
