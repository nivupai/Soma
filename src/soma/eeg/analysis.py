"""Whole-record descriptive EEG experiment; no condition inference."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.core.provenance import manifest, output_directory, sha256, write_json
from soma.core.signal import Signal
from soma.datasets.eegbci import load_recording, recording_path
from soma.signal.spectral import BANDS, WelchConfig, welch
from soma.visualization.spectral import plot_segment, plot_spectra


def analyze_recording(root: Path, subject: int, run: int, output: Path) -> dict[str, Any]:
    raw, metadata = load_recording(root, subject, run)
    channels = [ch for ch in ("C3", "Cz", "C4") if ch in raw.ch_names]
    if not channels:
        raise ValueError("No motor-region channels C3, Cz, C4 found")
    signals = [Signal(raw.get_data(picks=[ch])[0], float(raw.info["sfreq"]), ch) for ch in channels]
    cfg = WelchConfig()
    spectra = {sig.channel: welch(sig, cfg) for sig in signals}
    output_directory(output)
    rows = [
        {
            "channel": ch,
            "band": band,
            "low_hz": lo,
            "high_hz": hi,
            "absolute_power_V2": spec.band_power(lo, hi),
        }
        for ch, spec in spectra.items()
        for band, (lo, hi) in BANDS.items()
    ]
    pd.DataFrame(rows).to_csv(output / "band_power.csv", index=False)
    np.savez(
        output / "spectra.npz",
        frequencies=next(iter(spectra.values())).frequencies,
        density=np.stack([spec.density for spec in spectra.values()]),
        channels=np.asarray(list(spectra)),
    )
    plot_segment(signals, output / "segment.png")
    plot_spectra(spectra, output / "psd.png")
    source = {**metadata, "sha256": sha256(recording_path(root, subject, run))}
    result = manifest(
        source,
        {
            "welch": asdict(cfg),
            "spectra": {ch: spec.metadata for ch, spec in spectra.items()},
            "selected_channels": channels,
            "bands_hz": BANDS,
            "segmentation": "whole recording; all task and rest periods",
            "preprocessing": "none beyond per-segment constant detrending in PSD",
        },
        {"data_root": str(root.resolve()), "output": str(output.resolve())},
    )
    write_json(output / "manifest.json", result)
    write_json(output / "recording.json", metadata)
    (output / "report.md").write_text(
        f"# EEGBCI S{subject:03d}R{run:02d}\n\n"
        f"Validated {metadata['n_eeg_channels']} EEG channels at {metadata['sfreq_hz']} Hz. "
        f"Samples: {metadata['n_samples']}. Selected channels: {', '.join(channels)}.\n\n"
        "Sensor names are standardized; measured sensor coordinates are unavailable. "
        "No filtering, rereferencing, artifact rejection or baseline correction was applied. "
        "Hann Welch: 320 samples, 160 overlap, mean averaging, constant segment detrending. "
        "Mu 8–13 Hz and beta 13–30 Hz powers are trapezoidal integrals in V².\n\n"
        "These are whole-record descriptive summaries mixing rest and imagery. "
        "They are not left/right comparisons, evidence of motor desynchronization, "
        "or statistically significant findings. Event-based analysis is deferred.\n\n"
        "See recording.json for run-specific event labels and manifest.json for provenance. "
        "Figures: segment.png and psd.png; arrays: spectra.npz; summaries: band_power.csv.\n"
    )
    raw.close()
    return result
