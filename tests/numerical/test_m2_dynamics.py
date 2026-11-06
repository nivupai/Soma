from dataclasses import replace

import numpy as np
import pytest
from scipy.signal import sosfreqz

from soma.eeg.epoching import EpochConfig, extract_trials
from soma.eeg.erd import PowerCoordinates, lateralization, power_change
from soma.eeg.events import parse_events
from soma.eeg.motor_imagery import MotorImageryConfig, analyze_run
from soma.eeg.preprocessing import PreprocessingConfig, design_filter, preprocess
from soma.eeg.timefrequency import MorletConfig, morlet_power, trial_spectra
from soma.signal.event_locked import event_locked_eeg


@pytest.mark.parametrize("amplitude", [0.2, 0.5, 0.8, 1.0, 1.5])
def test_analytic_power_scaling_and_sign(amplitude):
    coordinates = PowerCoordinates(("C3",), (10.0, 20.0))
    reference = np.array([[[5e-11, 1.8e-11]]])
    result = power_change(amplitude**2 * reference, reference, coordinates, coordinates)
    np.testing.assert_allclose(result.percent, 100 * (amplitude**2 - 1), atol=1e-12)
    np.testing.assert_allclose(result.log_ratio, 2 * np.log(amplitude), atol=1e-12)
    np.testing.assert_allclose(result.difference, (amplitude**2 - 1) * reference, atol=1e-25)
    assert result.valid.all()


def test_reference_masking_alignment_and_near_zero():
    coords = PowerCoordinates(("C3", "C4"), (10.0,))
    p = np.ones((2, 2, 1)) * 1e-11
    ref = np.array([[[0.0], [np.nan]], [[1e-30], [1e-11]]])
    result = power_change(p, ref, coords, coords, minimum_reference=1e-20)
    assert result.valid.sum() == 1
    assert np.isnan(result.percent[:1]).all()
    assert result.percent[1, 1, 0] == 0
    assert np.isnan(result.percent[1, 0, 0])
    with pytest.raises(ValueError, match="coordinates"):
        power_change(p, ref, coords, PowerCoordinates(("C4", "C3"), (10.0,)))
    with pytest.raises(ValueError):
        power_change(p, ref[:, :1], coords, coords)
    with pytest.raises(ValueError):
        power_change(-p, ref, coords, coords)
    zero = power_change(np.zeros_like(p), np.ones_like(p), coords, coords)
    assert np.all(zero.percent == -100)
    assert np.isnan(zero.log_ratio).all()


@pytest.mark.parametrize("fs", [100.0, 160.0, 256.0])
def test_event_locked_analytic_suppression_across_sampling_rates(fs):
    raw, truth = event_locked_eeg(fs=fs, noise_v=0)
    cfg = MotorImageryConfig(
        preprocessing=PreprocessingConfig(reference="none", highpass_hz=None, lowpass_hz=None),
        plots=False,
    )
    result = analyze_run(raw, 1, 4, "model", cfg)
    assert len(result["epochs"].trials) == 8
    summary = result["summary"]
    for code, condition in [("T1", "left hand imagery"), ("T2", "right hand imagery")]:
        rows = summary[summary.condition == condition]
        for c, channel in enumerate(("C3", "Cz", "C4")):
            power = rows[rows.channel == channel]
            expected = truth["expected_erd_percent"][code][c]
            np.testing.assert_allclose(power.mean_erd_percent, expected, atol=1e-8)
    li = result["lateralization"]
    assert (li[li.condition == "left hand imagery"].c4_minus_c3_over_sum < 0).all()
    assert (li[li.condition == "right hand imagery"].c4_minus_c3_over_sum > 0).all()
    tfr = result["tfr"]
    assert tfr.power.shape[:3] == (8, 3, 23)
    valid = tfr.valid
    assert np.isnan(tfr.power[..., ~valid]).all()
    changes = result["tfr_change"].percent
    for t, trial in enumerate(result["context"].trials):
        for c in range(3):
            # Two simultaneous tones produce instantaneous cross-term beating.
            # Compare temporal mean power, not every smoothed time sample.
            values = np.mean(changes[t, c][:, (tfr.times >= 1) & (tfr.times < 3)], axis=-1)
            np.testing.assert_allclose(
                values, truth["expected_erd_percent"][trial.event.code][c], atol=1e-6
            )


@pytest.mark.parametrize("baseline", ["condition_rest", "matched_rest", "none"])
def test_seeded_filtered_suppression_and_reference_strategies(baseline):
    raw, truth = event_locked_eeg()
    other, _ = event_locked_eeg()
    np.testing.assert_array_equal(raw.get_data(), other.get_data())
    cfg = MotorImageryConfig(
        preprocessing=PreprocessingConfig(reference="none"), baseline=baseline, plots=False
    )
    r = analyze_run(raw, 1, 4, "model", cfg)
    if baseline == "none":
        assert np.isnan(r["band_change"].percent).all()
        assert np.isfinite(r["features"].absolute_power_v2).all()
    else:
        for t, trial in enumerate(r["epochs"].trials):
            expected = np.asarray(truth["expected_erd_percent"][trial.event.code])[:, None]
            available = r["band_change"].valid[t]
            if available.any():
                # Three overlapping periodograms from 2 s at beta SNR ~25 dB:
                # allow 5 percentage points for noisy amplitude estimates, not a CI.
                np.testing.assert_allclose(
                    r["band_change"].percent[t][available],
                    np.broadcast_to(expected, (3, 2))[available],
                    atol=5.0,
                )
        if baseline == "matched_rest":
            assert np.isnan(r["band_change"].percent[0]).all()  # rest lies in filter edge guard


def test_filter_response_phase_and_amplitude_against_steady_tone():
    raw, _ = event_locked_eeg(noise_v=0)
    fs = 160
    t = np.arange(raw.n_times) / fs
    x = np.sin(2 * np.pi * 10 * t) * 1e-5 + np.sin(2 * np.pi * 60 * t) * 1e-5
    raw._data[:] = x
    cfg = PreprocessingConfig(reference="none")
    p = preprocess(raw, cfg)
    sos, report = design_filter(fs, cfg)
    f, h = sosfreqz(sos, worN=np.array([10.0, 60.0]), fs=fs)
    keep = (t >= 10) & (t < 60)
    recovered = []
    for frequency in f:
        sinusoid = np.sin(2 * np.pi * frequency * t[keep])
        cosine = np.cos(2 * np.pi * frequency * t[keep])
        recovered.append(2 * np.dot(p.data[0, keep], sinusoid) / len(sinusoid))
        assert abs(2 * np.dot(p.data[0, keep], cosine) / len(cosine)) < 1e-10
    np.testing.assert_allclose(recovered, 1e-5 * np.abs(h) ** 2, rtol=1e-5, atol=1e-12)
    assert recovered[1] < recovered[0] * 0.01
    assert report["edge_seconds"] > 1
    causal = preprocess(raw, replace(cfg, phase="causal"))
    assert not np.allclose(causal.data, p.data, atol=1e-8)


def test_morlet_support_and_trial_psd():
    raw, _ = event_locked_eeg(noise_v=0)
    p = preprocess(raw, PreprocessingConfig(reference="none", highpass_hz=None, lowpass_hz=None))
    events = parse_events(raw, 1, 4, "model")
    epochs = extract_trials(p, events)
    spec = trial_spectra(epochs)
    assert spec.density.shape == (8, 3, 81)
    tfr = morlet_power(epochs)
    for f, half in enumerate(tfr.half_support_s):
        mask = tfr.valid[f]
        assert not mask[0] and not mask[-1]
        assert np.all(tfr.times[mask] >= epochs.times[0] + half)
        assert np.isfinite(tfr.power[:, :, f, mask]).all()
    tiny = extract_trials(p, events, EpochConfig(1, 1.1))
    with pytest.raises(ValueError, match="Wavelet exceeds"):
        morlet_power(tiny)
    for cfg in (MorletConfig((10.0, 80.0)), MorletConfig((20.0, 10.0)), MorletConfig(n_cycles=0)):
        with pytest.raises(ValueError):
            morlet_power(epochs, cfg)


def test_lateralization_no_epsilon_and_no_negative_power():
    assert np.isnan(lateralization(np.zeros(1), np.zeros(1))[0])
    assert lateralization(np.array([1.0]), np.array([3.0]))[0] == 0.5
    with pytest.raises(ValueError):
        lateralization(np.array([-1.0]), np.array([3.0]))


def test_highpass_suppresses_known_slow_drift():
    raw, _ = event_locked_eeg(noise_v=0)
    t = np.arange(raw.n_times) / 160
    drift = 100e-6 * np.sin(2 * np.pi * 0.2 * t)
    carrier = 10e-6 * np.sin(2 * np.pi * 10 * t)
    raw._data[:] = drift + carrier
    p = preprocess(raw, PreprocessingConfig(reference="none"))
    keep = (t >= 10) & (t < 60)
    drift_amplitude = 2 * np.dot(p.data[0, keep], np.sin(2 * np.pi * 0.2 * t[keep])) / keep.sum()
    tone_amplitude = 2 * np.dot(p.data[0, keep], np.sin(2 * np.pi * 10 * t[keep])) / keep.sum()
    assert abs(drift_amplitude) < 1e-8
    assert tone_amplitude == pytest.approx(10e-6, rel=0.001)
