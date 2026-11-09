"""Analytical and adversarial first-level tests; entirely offline synthetic inputs."""

from dataclasses import replace

import nibabel as nib
import numpy as np
import pandas as pd
import pytest
from scipy.stats import t

from soma.experiments.fmri_simulation import canonical_response, simulate
from soma.fmri.design import (
    Contrast,
    ModelConfig,
    build_design,
    diagnostics,
    nuisance,
    validate_events,
)
from soma.fmri.glm import analytical_ols, contrast, fit, fixed_effects
from soma.fmri.retest import retest
from soma.imaging.volumes import Volume


@pytest.fixture
def run():
    return simulate()[0]


@pytest.fixture
def config():
    return ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))


@pytest.mark.parametrize("tr", [1.0, 2.0, 3.0])
def test_independent_hrf_quadrature_matches_nilearn(tr):
    r, truth = simulate(tr=tr, n_scans=100, noise=0)
    design, report = build_design(r, ModelConfig(drift_model=None))
    # Different sampling implementations: bound discretization error, not exact equality.
    np.testing.assert_allclose(design.task, truth["response"], atol=0.012, rtol=0.025)
    assert report["rank"] == design.shape[1]
    assert list(design.index) == list(np.arange(100) * tr)
    assert np.max(design.task) > 0.5


def test_causal_hrf_event_timing():
    times = np.arange(80.0)
    events = pd.DataFrame({"onset": [20.0], "duration": [2.0], "trial_type": ["task"]})
    response = canonical_response(times, events)
    assert np.max(np.abs(response[times < 20])) < 1e-12
    assert 24 <= times[np.argmax(response)] <= 28


def test_noisy_beta_signs_and_independent_QR_variance(run, config):
    f = fit(run, config)
    definition = Contrast("task", {"task": 1})
    e = contrast(f, definition)
    data = run.image.get_fdata()[1, 3, 3]
    oracle = analytical_ols(f.design.to_numpy(), data[:, None], definition.vector(f.design))
    np.testing.assert_allclose(
        e.maps["effect_size"].get_fdata()[1, 3, 3], oracle["effect"][0], atol=1e-9
    )
    np.testing.assert_allclose(
        e.maps["effect_variance"].get_fdata()[1, 3, 3], oracle["variance"][0], atol=1e-10
    )
    expected_t = oracle["effect"][0] / np.sqrt(oracle["variance"][0])
    assert e.maps["stat"].get_fdata()[1, 3, 3] == pytest.approx(expected_t)
    assert e.maps["p_two_sided"].get_fdata()[1, 3, 3] == pytest.approx(
        2 * t.sf(abs(expected_t), oracle["dof"]), abs=1e-8
    )
    assert 2.5 < e.maps["effect_size"].get_fdata()[1, 3, 3] < 3.5
    assert e.maps["effect_size"].get_fdata()[5, 3, 3] < -2.5
    assert "p_value" not in e.maps
    assert e.metadata["family_voxels"] == 343
    assert e.metadata["correction"] == "Benjamini-Hochberg FDR"


def test_analytic_noiseless_ols():
    x = np.c_[np.ones(20), np.arange(20.0)]
    y = x @ np.array([[3.0, 2.0], [-0.5, 0.7]])
    result = analytical_ols(x, y, np.array([0.0, 1.0]))
    np.testing.assert_allclose(result["effect"], [-0.5, 0.7], atol=1e-12)
    assert np.max(result["variance"]) < 1e-25


@pytest.mark.parametrize("seed", [1, 42, 13142])
def test_simulation_determinism(seed):
    a, t1 = simulate(seed, ar=0.6, spatial_sigma=0.5)
    b, t2 = simulate(seed, ar=0.6, spatial_sigma=0.5)
    np.testing.assert_array_equal(a.image.dataobj, b.image.dataobj)
    np.testing.assert_array_equal(t1["beta"], t2["beta"])
    c, _ = simulate(seed + 1)
    assert not np.array_equal(a.image.dataobj, c.image.dataobj)


@pytest.mark.parametrize(
    "changes",
    [
        {"hrf_model": "unknown"},
        {"noise_model": "ar9"},
        {"drift_model": "unknown"},
        {"high_pass": float("nan")},
        {"slice_time_ref": 2.0},
        {"smoothing_fwhm": -1},
        {"q": 0},
        {"fd_threshold": -1},
        {"initial_spikes": -1},
    ],
)
def test_bad_model_config(changes):
    with pytest.raises(ValueError):
        ModelConfig(**changes)


@pytest.mark.parametrize(
    "column,value",
    [
        ("onset", -1),
        ("duration", -1),
        ("onset", 1e5),
        ("duration", 1e5),
        ("onset", np.nan),
        ("trial_type", None),
    ],
)
def test_event_coverage_and_values(run, column, value):
    events = run.events.copy()
    events.loc[0, column] = value
    with pytest.raises(ValueError):
        validate_events(events, run.n_scans, run.tr)


@pytest.mark.parametrize("weights", [{"absent": 1}, {"task": 0}, (1.0,), (np.nan, 0.0, 0.0, 0.0)])
def test_contrast_rejects_missing_zero_or_wrong_vectors(run, config, weights):
    design, _ = build_design(run, config)
    with pytest.raises(ValueError):
        Contrast("invalid", weights).vector(design)


def test_rank_collinearity_and_nonestimable_contrast(run, config):
    broken = run.confounds.copy()
    broken["duplicate"] = broken.motion
    r = replace(run, confounds=broken)
    with pytest.raises(ValueError, match="Rank|condition"):
        build_design(r, replace(config, confound_columns=("motion", "duplicate")))
    x = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="estimable"):
        Contrast("difference", {"a": 1.0, "b": -1.0}).vector(x)
    with pytest.raises(ValueError):
        diagnostics(pd.DataFrame(np.eye(3)))


def test_spikes_keep_timing_and_derivatives(run, config):
    c = run.confounds.copy()
    c["framewise_displacement"] = 0.0
    c.loc[0, "framewise_displacement"] = np.nan
    c.loc[17, "framewise_displacement"] = 0.9
    r = replace(run, confounds=c)
    cfg = replace(
        config,
        confound_columns=("motion",),
        fd_threshold=0.5,
        motion_derivatives=True,
        initial_spikes=1,
    )
    design, report = build_design(r, cfg)
    assert design.spike_0017.iloc[17] == 1 and design.spike_0017.sum() == 1
    assert design.spike_0000.sum() == 1 and len(design) == run.n_scans
    assert design.motion_derivative.iloc[0] == 0
    assert report["deleted_volumes"] == 0
    assert design.index[17] == 34


def test_missing_and_nonfinite_confounds(run, config):
    with pytest.raises(ValueError, match="Missing"):
        build_design(run, replace(config, confound_columns=("absent",)))
    with pytest.raises(ValueError, match="FD"):
        nuisance(run, replace(config, fd_threshold=0.5))
    c = run.confounds.copy()
    c.loc[12, "motion"] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        build_design(replace(run, confounds=c), config)
    with pytest.raises(ValueError, match="Spike"):
        nuisance(run, replace(config, initial_spikes=101))


@pytest.mark.parametrize(
    "fault",
    ["tr", "count", "mask-grid", "empty-mask", "nonfinite", "units", "subject", "preprocessing"],
)
def test_functional_contract(run, fault):
    with pytest.raises(ValueError):
        if fault == "tr":
            replace(run, tr=1.0)
        elif fault == "count":
            replace(run, confounds=run.confounds.iloc[:-1])
        elif fault == "mask-grid":
            replace(
                run,
                mask=Volume(
                    run.mask.array(), run.mask.affine_m + np.diag([0.001, 0, 0, 0]), "labels"
                ),
            )
        elif fault == "empty-mask":
            replace(run, mask=Volume(np.zeros(run.mask.shape), run.mask.affine_m, "labels"))
        elif fault == "nonfinite":
            data = run.image.get_fdata().copy()
            data[0, 0, 0, 0] = np.nan
            replace(run, image=nib.Nifti1Image(data, run.image.affine, run.image.header))
        elif fault == "units":
            img = nib.Nifti1Image(run.image.dataobj, run.image.affine, run.image.header.copy())
            img.header.set_xyzt_units("mm", "msec")
            replace(run, image=img)
        elif fault == "subject":
            replace(run, provenance={"source": "test", "subject": "wrong"})
        else:
            replace(run, preprocessing="raw")


def test_raw_model_guard(run, config):
    raw = replace(run, preprocessing="unvalidated-educational")
    with pytest.raises(ValueError, match="Raw"):
        fit(raw, config)
    e = contrast(fit(raw, config, allow_unvalidated_demo=True), Contrast("task", {"task": 1}))
    assert e.metadata["exploratory"] is True


def test_ar1_and_fixed_effects_and_retest(run, config):
    definition = Contrast("task", {"task": 1})
    a = contrast(fit(run, config), definition)
    r, _ = simulate(13043, ar=0.6, session="retest")
    b = contrast(fit(r, replace(config, noise_model="ar1")), definition)
    maps, receipt = fixed_effects([a, b])
    assert receipt["population_random_effects"] is False
    variance = maps["effect_variance"].get_fdata()
    assert np.all(
        variance
        <= np.maximum(a.maps["effect_variance"].get_fdata(), b.maps["effect_variance"].get_fdata())
    )
    with pytest.raises(ValueError, match="HRF"):
        fixed_effects([a, replace(b, metadata={**b.metadata, "hrf_model": "glover"})])
    with pytest.raises(ValueError, match="scale"):
        fixed_effects([a, replace(b, run=replace(b.run, provenance={"source": "missing scale"}))])
    result = retest(a, b)
    assert result["map_correlation"] > 0.85 and result["population_generalization"] is False
    wrong = replace(b, run=replace(b.run, subject="other"))
    with pytest.raises(ValueError, match="subject"):
        retest(a, wrong)
    with pytest.raises(ValueError):
        fixed_effects([a, wrong])
    with pytest.raises(ValueError, match="alignment"):
        retest(a, replace(b, run=replace(b.run, provenance={"source": "test"})))


def test_AR1_whitened_residual_diagnostic(config):
    run, _ = simulate(13142, ar=0.6)
    f = fit(run, replace(config, noise_model="ar1"))
    assert 0.35 < f.diagnostics["mean_native_residual_lag1"] < 0.7
    assert abs(f.diagnostics["mean_whitened_residual_lag1"]) < 0.15
    assert f.diagnostics["nilearn_residual_dof"] == 96


def test_independent_null_behavior_and_FDR_subset(config):
    fractions = []
    for seed in range(13142, 13152):
        run, _ = simulate(seed, beta=0)
        e = contrast(fit(run, config), Contrast("null", {"task": 1}))
        p = e.maps["p_two_sided"].get_fdata()
        rejected = e.maps["fdr_reject"].get_fdata().astype(bool)
        assert np.all(p[rejected] <= config.q)
        fractions.append(np.mean(p < 0.05))
    assert 0.025 < float(np.mean(fractions)) < 0.075


def test_difference_contrast_matches_independent_oracle(run, config):
    events = run.events.copy()
    events.loc[events.index[::2], "trial_type"] = "control"
    r = replace(run, events=events)
    fitted = fit(r, config)
    definition = Contrast("task-minus-control", {"task": 1.0, "control": -1.0})
    e = contrast(fitted, definition)
    oracle = analytical_ols(
        fitted.design.to_numpy(),
        run.image.get_fdata()[1, 3, 3][:, None],
        definition.vector(fitted.design),
    )
    assert e.maps["effect_size"].get_fdata()[1, 3, 3] == pytest.approx(
        oracle["effect"][0], abs=1e-9
    )


def test_confound_name_collision_is_not_overwritten(run, config):
    c = run.confounds.copy()
    c["spike_0000"] = np.arange(run.n_scans)
    with pytest.raises(ValueError, match="collision"):
        nuisance(
            replace(run, confounds=c),
            replace(config, confound_columns=("motion", "spike_0000"), initial_spikes=1),
        )


def test_unsafe_contrast_name_and_invalid_spike_type(run, config):
    design, _ = build_design(run, config)
    with pytest.raises(ValueError):
        Contrast("../escape", {"task": 1}).vector(design)
    with pytest.raises(ValueError):
        ModelConfig(initial_spikes=0.5)
