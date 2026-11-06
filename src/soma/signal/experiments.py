"""Reproducible synthetic experiment orchestration, separate from algorithms."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.core.provenance import manifest, output_directory, write_json
from soma.signal.spectral import BANDS, WelchConfig, welch
from soma.signal.synthetic import KINDS, synthetic
from soma.visualization.spectral import plot_segment, plot_spectra


def synthetic_spectrum(output: Path, seed: int = 42) -> dict[str, Any]:
    cfg = WelchConfig()
    signals = {kind: synthetic(kind, seed=seed) for kind in KINDS}
    spectra = {kind: welch(sig, cfg) for kind, sig in signals.items()}
    output_directory(output)
    rows = [
        {
            "signal": kind,
            "peak_hz": spec.peak_frequency,
            "time_mean_square_V2": float(np.mean(signals[kind].values ** 2)),
            "integrated_psd_V2": spec.band_power(0, signals[kind].fs / 2),
            **{f"{band}_power_V2": spec.band_power(*bounds) for band, bounds in BANDS.items()},
        }
        for kind, spec in spectra.items()
    ]
    pd.DataFrame(rows).to_csv(output / "summary.csv", index=False)
    np.savez(
        output / "spectra.npz",
        frequencies=next(iter(spectra.values())).frequencies,
        density=np.stack([spec.density for spec in spectra.values()]),
        channels=np.asarray(list(spectra)),
    )
    plot_spectra(spectra, output / "psd.png")
    plot_segment(list(signals.values()), output / "signals.png", seconds=20)
    result = manifest(
        {
            "dataset": "synthetic",
            "file_identifier": "soma-six-signal-laboratory-v1",
            "subject": None,
            "run": None,
        },
        {
            "fs_hz": 160,
            "duration_s": 20,
            "selected_channels": list(KINDS),
            "amplitude_V": 1e-5,
            "noise_std_V": 3e-6,
            "modulation_hz": 0.5,
            "modulation_depth": 0.5,
            "burst_fraction": [0.4, 0.6],
            "welch": asdict(cfg),
            "bands_hz": BANDS,
            "spectra": {kind: spec.metadata for kind, spec in spectra.items()},
        },
        {"output": str(output.resolve())},
        seed,
    )
    write_json(output / "manifest.json", result)
    (output / "report.md").write_text(
        "# Synthetic spectrum laboratory\n\nSix seeded 20-second signals at 160 Hz; "
        "10 µV sinusoid amplitude and 3 µV Gaussian noise SD. See manifest.json for "
        "parameters, versions and seed. summary.csv contains peaks, mean-square signal "
        "and integrated PSD powers (V²). Hann Welch segments are two seconds, with "
        "50% overlap. Spectral bins are 0.5 Hz apart.\n\n"
        "For stationary, bin-centered pure tones, integrated density equals A²/2 "
        "(5e-11 V² per tone). Nonstationary burst/modulated signals need not agree "
        "exactly with full-record mean square because Welch weights overlapping windows "
        "and detrends segments. Figures are psd.png and signals.png.\n"
    )
    return result
