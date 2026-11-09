"""10 Hz, 4 µV sine: Welch peak 10 Hz, total band power 8e-12 V².

Burst detector consumes an already band-limited voltage signal; application
requires explicit filtering/edge guards and independent threshold calibration.
"""

import json

import numpy as np

from soma.sdk.eeg import Signal, WelchConfig, calibrated_detector, eeg_spectrum, intervals


def run():
    time = np.arange(1600) / 160
    signal = Signal(4e-6 * np.sin(2 * np.pi * 10 * time), 160, "synthetic", "V")
    spectrum = eeg_spectrum(signal, WelchConfig())
    mask = calibrated_detector(signal.values, signal.fs, 2e-6, 3e-6, 0.3)
    assert spectrum.peak_frequency == 10
    assert np.isclose(spectrum.band_power(8, 13), 8e-12, rtol=1e-10, atol=0)
    assert intervals(mask)
    return {
        "peak_hz": spectrum.peak_frequency,
        "mu_power_V2": spectrum.band_power(8, 13),
        "burst_intervals_half_open_samples": intervals(mask),
        "synthetic": True,
    }


if __name__ == "__main__":
    print(json.dumps(run(), allow_nan=False))
