"""Seeded repeated-measures simulations with individual effects and burst truth."""

from typing import Any

import mne
import numpy as np

from soma.signal.event_locked import event_locked_eeg


def cohort_recording(
    subject: int, run: int, seed: int = 42, *, missing: bool = False, artifacts: bool = False
) -> tuple[Any, dict[str, Any]]:
    """Known individual log power ratios, run/trial random amplitude variation.

    Seven sensor signals allow average/pair reference sensitivity. Independent
    phases/noise prevent the three coherent-channel reference degeneracy of M2.
    The analytical reference=none benchmark disables preprocessing and noise in
    separate tests; this noisy model is not an exact post-reference effect model.
    """
    if subject < 1 or run not in (4, 8, 12):
        raise ValueError("Synthetic cohort requires positive subject and imagery run 4/8/12")
    rng_subject = np.random.default_rng(np.random.SeedSequence([seed, subject, 0]))
    rng = np.random.default_rng(np.random.SeedSequence([seed, subject, run]))
    raw, _ = event_locked_eeg(seed=seed)
    fs, n = float(raw.info["sfreq"]), int(raw.n_times)
    t = np.arange(n) / fs
    channels = ["C3", "Cz", "C4", "Fz", "Pz", "O1", "O2"]
    baseline = float(np.exp(rng_subject.normal(0, 0.15)))
    suppression = float(np.clip(0.5 + rng_subject.normal(0, 0.05), 0.3, 0.7))
    data = rng.normal(0, 0.5e-6, (len(channels), n))
    truth_intervals = []
    for c, channel in enumerate(channels):
        phase = rng_subject.uniform(0, 2 * np.pi)
        run_variation = float(np.exp(rng.normal(0, 0.02)))
        for i, ann in enumerate(raw.annotations):
            a, b = int(round(ann["onset"] * fs)), int(round((ann["onset"] + ann["duration"]) * fs))
            code = str(ann["description"])
            contra = (channel == "C4" and code == "T1") or (channel == "C3" and code == "T2")
            factor = suppression if contra else (0.8 if code != "T0" and c < 3 else 1.0)
            trial_variation = float(np.exp(rng.normal(0, 0.04)))
            carrier = 10e-6 * np.sin(2 * np.pi * 10 * t[a:b] + phase) + 6e-6 * np.sin(
                2 * np.pi * 20 * t[a:b] + phase
            )
            # Baseline oscillatory floor + two known high-amplitude bouts in every interval.
            envelope = np.full(b - a, 0.35)
            for lo, hi in ((0.6, 1.4), (2.0, 3.2)):
                x, y = int(round(lo * fs)), int(round(hi * fs))
                envelope[x:y] = 1.4
                truth_intervals.append(
                    {
                        "channel": channel,
                        "annotation_index": i,
                        "condition_code": code,
                        "onset_s": a / fs + lo,
                        "offset_s": a / fs + hi,
                        "amplitude_factor": baseline * factor * trial_variation * run_variation,
                    }
                )
            data[c, a:b] += baseline * factor * trial_variation * run_variation * envelope * carrier
    if artifacts and (subject + run) % 2:
        data[0, int(5.5 * fs) : int(5.6 * fs)] += 1e-3
    annotations = raw.annotations.copy()
    omitted = []
    if missing and subject % 2 == 0:
        omitted = [3]
        annotations.delete(omitted)
    result = mne.io.RawArray(data, mne.create_info(channels, fs, "eeg"), verbose=False)
    result.set_annotations(annotations)
    return result, {
        "seed": seed,
        "subject": subject,
        "run": run,
        "individual_baseline_factor": baseline,
        "contralateral_amplitude_factor": suppression,
        "ipsilateral_amplitude_factor": 0.8,
        "unreferenced_population_target_c3_left_minus_right_log_power": float(
            2 * np.log(0.8 / suppression)
        ),
        "noise_sd_v": 0.5e-6,
        "trial_log_amplitude_sd": 0.04,
        "run_log_amplitude_sd": 0.02,
        "omitted_annotation_indices": omitted,
        "artifacts": artifacts,
        "burst_intervals": truth_intervals,
        "caveat": (
            "Ground truth factors precede referencing/filtering; estimated "
            "effects need not equal them exactly"
        ),
    }


def burst_benchmark(
    kind: str, fs: float = 160.0, noise_v: float = 0.1e-6, seed: int = 42
) -> tuple[np.ndarray[Any, Any], list[tuple[float, float]]]:
    """Controlled pulse trains for amplitude/duration/count/noise interventions."""
    if (
        kind not in {"baseline", "amplitude", "shorter", "fewer", "noise"}
        or fs <= 60
        or noise_v < 0
    ):
        raise ValueError("Invalid burst benchmark manipulation or sampling/noise parameters")
    t = np.arange(int(30 * fs)) / fs
    intervals = [(5.0, 7.0), (12.0, 14.0), (20.0, 22.0)]
    if kind == "shorter":
        intervals = [(a, a + 1) for a, _ in intervals]
    if kind == "fewer":
        intervals = intervals[:1]
    amplitude = 10e-6 * (0.6 if kind == "amplitude" else 1.0)
    envelope = np.full(len(t), 0.1e-6)
    for a, b in intervals:
        envelope[(t >= a) & (t < b)] = amplitude
    noise = noise_v * (10 if kind == "noise" else 1)
    return envelope * np.sin(2 * np.pi * 10 * t) + np.random.default_rng(seed).normal(
        0, noise, len(t)
    ), intervals
