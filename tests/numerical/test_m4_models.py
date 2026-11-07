from dataclasses import replace

import numpy as np
import pytest

from soma.simulations.hierarchical import SCENARIOS, SimulationConfig, simulate
from soma.statistics.inference import InferenceConfig, infer_mean


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_dgm_grouping_and_seed_reproducibility(scenario):
    cfg = SimulationConfig(scenario=scenario, n_subjects=20)
    a, b = simulate(cfg, 42), simulate(cfg, 42)
    for key in ("subject_effects", "run_effects", "left_counts", "right_counts"):
        np.testing.assert_array_equal(a[key], b[key])
    assert len(a["subject_effects"]) == 20
    assert a["structural_truth"] == 0.3
    if scenario == "preprocessing_shift":
        assert a["target_mean"] == pytest.approx(0.45)
    if scenario == "nonrandom_missing":
        assert a["target_mean"] > 0.3 and np.isnan(a["run_effects"]).any()


def test_perfect_trial_correlation_does_not_manufacture_more_subjects():
    cfg = SimulationConfig(n_subjects=30, correlation=1, min_trials=8, max_trials=8)
    x = simulate(cfg, 19)
    y = simulate(replace(cfg, min_trials=80, max_trials=80), 19)
    np.testing.assert_allclose(x["subject_effects"], y["subject_effects"], atol=1e-13)
    a = infer_mean(x["subject_effects"], methods=("t",))[0]
    b = infer_mean(y["subject_effects"], methods=("t",))[0]
    assert a["n_subjects"] == b["n_subjects"] == 30
    assert a["standard_error"] == pytest.approx(b["standard_error"], rel=1e-12)


def test_noiseless_paired_truth_cancels_arbitrary_subject_intercepts():
    cfg = SimulationConfig(n_subjects=50, subject_effect_sd=0, run_effect_sd=0, trial_sd=0)
    result = simulate(cfg, 7)
    np.testing.assert_allclose(result["subject_effects"], 0.3, atol=1e-13)
    assert np.std(result["subject_intercepts"]) > 0.5


def test_normal_t_coverage_has_monte_carlo_sampling_tolerance():
    covered = 0
    repetitions = 300
    for replicate in range(repetitions):
        x = simulate(SimulationConfig(scenario="normal", n_subjects=5), replicate)[
            "subject_effects"
        ]
        r = infer_mean(x, methods=("t",), cfg=InferenceConfig(n_resamples=100))[0]
        covered += r["ci_low"] <= 0.3 <= r["ci_high"]
    # Exact normal t intervals have .95 coverage; four binomial SE is ~.0504.
    assert 0.895 <= covered / repetitions <= 1


def test_heavy_tail_mean_and_mnar_target_known_over_independent_subjects():
    heavy = simulate(SimulationConfig(scenario="heavy_tail", n_subjects=20000), 71)
    assert abs(np.mean(heavy["subject_effects"]) - 0.3) < 0.04
    missing = simulate(SimulationConfig(scenario="nonrandom_missing", n_subjects=20000), 72)
    assert abs(np.nanmean(missing["subject_effects"]) - missing["target_mean"]) < 0.025
    assert missing["target_mean"] - 0.3 > 0.15
