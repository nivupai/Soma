import numpy as np
import pandas as pd
import pytest

from soma.eeg.preprocessing import PreprocessingConfig, ProcessedRecording
from soma.experiments.benchmark import uncertainty_validation
from soma.signal.bursts import BurstConfig, analyze_bursts, calibrated_detector, intervals
from soma.signal.cohort_synthetic import burst_benchmark, cohort_recording
from soma.statistics.hierarchical import ResamplingConfig, subject_bootstrap


@pytest.mark.parametrize(
    "kind,expected_count,expected_occupancy",
    [("baseline", 3, 0.2), ("amplitude", 3, 0.2), ("shorter", 3, 0.1), ("fewer", 1, 2 / 30)],
)
def test_known_burst_duration_and_occupancy(kind, expected_count, expected_occupancy):
    fs = 160
    values, truth = burst_benchmark(kind, noise_v=0)
    detected = calibrated_detector(values, fs, 2e-6, 4e-6, 0.3)
    bouts = intervals(detected)
    assert len(bouts) == expected_count
    assert detected.mean() == pytest.approx(expected_occupancy, abs=2 * 0.1 * expected_count / 30)
    for (a, b), (start, stop) in zip(bouts, truth, strict=True):
        assert a / fs == pytest.approx(start, abs=0.1)
        assert b / fs == pytest.approx(stop, abs=0.1)


def test_amplitude_vs_power_scaling_independent_of_threshold_occupancy():
    base, _ = burst_benchmark("baseline", noise_v=0)
    reduced, _ = burst_benchmark("amplitude", noise_v=0)
    # Within known interior bouts, amplitudes scale 0.6 and powers 0.36.
    inside = np.zeros(len(base), dtype=bool)
    for a, b in ((5.2, 6.8), (12.2, 13.8), (20.2, 21.8)):
        inside[int(a * 160) : int(b * 160)] = True
    assert np.mean(reduced[inside] ** 2) / np.mean(base[inside] ** 2) == pytest.approx(
        0.36, rel=0.001
    )
    baseline_mask = calibrated_detector(base, 160, 2e-6, 4e-6, 0.3)
    reduced_mask = calibrated_detector(reduced, 160, 2e-6, 4e-6, 0.3)
    assert len(intervals(baseline_mask)) == len(intervals(reduced_mask)) == 3
    # Fixed amplitude thresholds need not preserve identical boundary samples.
    assert np.sum(baseline_mask & reduced_mask) / np.sum(baseline_mask | reduced_mask) > 0.9


@pytest.mark.parametrize("fs", [100.0, 160.0, 256.0])
def test_continuous_fir_detector_edge_guards_and_noise(fs):
    values, _ = burst_benchmark("baseline", fs, noise_v=0.1e-6)
    processed = ProcessedRecording(values[None], ("C3",), fs, 0, {})
    windows = pd.DataFrame(
        [
            dict(
                stage="rest",
                accepted=True,
                index=0,
                label="rest",
                code="T0",
                onset_s=0,
                start_sample=0,
                stop_sample_exclusive=int(4 * fs),
            ),
            dict(
                stage="analysis",
                accepted=True,
                index=1,
                label="left hand imagery",
                code="T1",
                onset_s=4,
                start_sample=int(4 * fs),
                stop_sample_exclusive=int(25 * fs),
            ),
        ]
    )
    cfg = BurstConfig(strategies=("fixed",), fixed_low_v=2e-6, fixed_high_v=4e-6, min_cycles=2)
    result = analyze_bursts(processed, windows, 1, 4, "model", cfg)
    mu = result["features"].query("band=='mu' and trial_index==1").iloc[0]
    # Seven-cycle FIR envelope broadening is bounded by one 8 Hz period per edge.
    assert mu.occupancy == pytest.approx(6 / 21, abs=6 * 0.125 / 21)
    assert mu.onset_count == 3
    assert mu.mean_complete_duration_s == pytest.approx(2, abs=0.25)
    for calibration in result["calibration"]:
        assert calibration["edge_samples"] >= int(2 * fs)


def test_noise_intervention_changes_detector_behavior_without_changing_bout_truth():
    quiet, truth = burst_benchmark("baseline", noise_v=0.3e-6)
    noisy, same_truth = burst_benchmark("noise", noise_v=0.3e-6)
    assert truth == same_truth
    quiet_mask = calibrated_detector(quiet, 160, 2e-6, 4e-6, 0.3)
    noisy_mask = calibrated_detector(noisy, 160, 2e-6, 4e-6, 0.3)
    assert not np.array_equal(quiet_mask, noisy_mask)
    assert np.var(noisy - quiet) > np.var(quiet) * 0.05


def test_cohort_simulation_individual_run_and_missing_event_determinism():
    a, truth = cohort_recording(2, 4, 42, missing=True, artifacts=True)
    b, same = cohort_recording(2, 4, 42, missing=True, artifacts=True)
    np.testing.assert_array_equal(a.get_data(), b.get_data())
    assert truth == same
    assert len(a.annotations) == 16
    other, individual = cohort_recording(3, 4, 42)
    assert truth["individual_baseline_factor"] != individual["individual_baseline_factor"]
    run, run_truth = cohort_recording(2, 8, 42)
    assert truth["individual_baseline_factor"] == run_truth["individual_baseline_factor"]
    assert not np.array_equal(run.get_data(), a.get_data())
    assert truth["burst_intervals"]


def test_subject_population_recovery_and_repeated_coverage(tmp_path):
    # Independent repeated subject simulations, not one favorable seeded interval.
    result = uncertainty_validation(
        tmp_path / "coverage", seed=2026, repetitions=100, n_subjects=40, n_bootstrap=500
    )
    # Nominal .95 with binomial SE .022: allow >4 SE plus small-sample percentile bias.
    assert 0.85 <= result["observed_coverage"] <= 1
    assert (
        result["coverage_binomial_ci"][0]
        <= result["observed_coverage"]
        <= result["coverage_binomial_ci"][1]
    )
    values = np.random.default_rng(12).normal(0.5, 0.1, 200)
    estimate = subject_bootstrap(values, ResamplingConfig(n_bootstrap=1000))
    assert estimate["estimate"] == pytest.approx(0.5, abs=0.03)
    assert estimate["ci_low"] < 0.5 < estimate["ci_high"]


def test_controlled_manipulations_separate_power_from_duration_and_rate():
    results = {}
    for kind in ("baseline", "amplitude", "shorter", "fewer"):
        signal, truth = burst_benchmark(kind, noise_v=0)
        mask = calibrated_detector(signal, 160, 2e-6, 4e-6, 0.3)
        results[kind] = (float(np.mean(signal**2)), mask.mean(), len(intervals(mask)))
    assert results["amplitude"][0] / results["baseline"][0] == pytest.approx(0.36, abs=0.001)
    assert results["shorter"][0] / results["baseline"][0] == pytest.approx(0.5, abs=0.001)
    assert results["fewer"][0] / results["baseline"][0] == pytest.approx(1 / 3, abs=0.001)
    assert results["amplitude"][2] == results["shorter"][2] == results["baseline"][2] == 3
    assert results["fewer"][2] == 1
    assert results["shorter"][1] < results["baseline"][1] * 0.6


def test_eeg_simulated_population_effect_with_individual_ground_truth():
    from soma.eeg.motor_imagery import MotorImageryConfig, analyze_run
    from soma.statistics.hierarchical import subject_contrasts

    frames = []
    targets = {}
    for subject in (1, 2, 3):
        for run in (4, 8):
            raw, truth = cohort_recording(subject, run, seed=43)
            cfg = MotorImageryConfig(
                preprocessing=PreprocessingConfig(reference="none"), plots=False
            )
            result = analyze_run(raw, subject, run, f"S{subject}R{run}", cfg)
            frames.append(result["features"])
            targets[subject] = truth["unreferenced_population_target_c3_left_minus_right_log_power"]
    _, subjects = subject_contrasts(pd.concat(frames, ignore_index=True))
    selected = subjects[
        (subjects.channel == "C3")
        & (subjects.band == "mu")
        & (subjects.outcome == "log_absolute_power")
    ]
    for row in selected.itertuples():
        # Trial log-amplitude SD .04, four trials/condition and two runs;
        # .2 log units conservatively exceeds four standard errors plus spectral noise.
        assert abs(row.contrast - targets[row.subject]) < 0.2
    assert abs(selected.contrast.mean() - np.mean(list(targets.values()))) < 0.1
