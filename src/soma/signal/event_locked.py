"""Known event-locked power suppression; no claim of a biophysical EEG model."""

from typing import Any

import mne
import numpy as np


def event_locked_eeg(
    seed: int = 42, fs: float = 160.0, noise_v: float = 0.5e-6, artifacts: bool = False
) -> tuple[Any, dict[str, Any]]:
    if not np.isfinite([fs, noise_v]).all() or fs <= 40 or noise_v < 0:
        raise ValueError("fs must exceed 40 Hz; noise standard deviation must be nonnegative")
    # Alternating rest/imagery, four repetitions of each hand, then final rest.
    codes = [code for hand in ("T1", "T2") * 4 for code in ("T0", hand)] + ["T0"]
    duration = 4.0
    n = int(round(len(codes) * duration * fs))
    t = np.arange(n) / fs
    rng = np.random.default_rng(seed)
    data = np.empty((3, n))
    factors = {"T0": [1.0, 1.0, 1.0], "T1": [0.8, 0.7, 0.5], "T2": [0.5, 0.7, 0.8]}
    for c in range(3):
        envelope = np.ones(n)
        for i, code in enumerate(codes):
            envelope[int(round(i * duration * fs)) : int(round((i + 1) * duration * fs))] = factors[
                code
            ][c]
        carrier = 10e-6 * np.sin(2 * np.pi * 10 * t) + 6e-6 * np.sin(2 * np.pi * 20 * t)
        data[c] = envelope * carrier + rng.normal(0, noise_v, n)
    if artifacts:
        data[0, int(5.5 * fs) : int(5.6 * fs)] += 1e-3
    raw = mne.io.RawArray(data, mne.create_info(["C3", "Cz", "C4"], fs, "eeg"), verbose=False)
    raw.set_annotations(
        mne.Annotations(np.arange(len(codes)) * duration, np.full(len(codes), duration), codes)
    )
    truth = {
        "seed": seed,
        "fs_hz": fs,
        "noise_std_v": noise_v,
        "artifacts": artifacts,
        "duration_s": len(codes) * duration,
        "annotation_duration_s": duration,
        "amplitudes_v": {"10_hz": 10e-6, "20_hz": 6e-6},
        "channels": ["C3", "Cz", "C4"],
        "amplitude_factors": factors,
        "expected_erd_percent": {
            code: [100 * (a * a - 1) for a in values] for code, values in factors.items()
        },
        "reference": "none: three coherent model channels; average reference changes ground truth",
    }
    return raw, truth
