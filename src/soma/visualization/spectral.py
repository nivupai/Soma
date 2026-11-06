"""Headless plotting; plotting never changes analysis values."""

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/derived/.cache/matplotlib").resolve()))
os.environ.setdefault("XDG_CACHE_HOME", str(Path("data/derived/.cache").resolve()))

import matplotlib  # noqa: E402
import numpy as np  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from soma.core.signal import Signal  # noqa: E402
from soma.signal.spectral import Spectrum  # noqa: E402


def plot_spectra(spectra: dict[str, Spectrum], path: Path) -> None:
    units = {str(spec.metadata.get("units", "V^2/Hz")) for spec in spectra.values()}
    if not spectra or len(units) != 1:
        raise ValueError("Plot requires nonempty spectra with matching density units")
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    for label, spectrum in spectra.items():
        ax.semilogy(spectrum.frequencies, spectrum.density, label=label)
    peak = max(float(np.max(spec.density)) for spec in spectra.values())
    # Display six decades below the peak; floating-point residuals are not signal.
    if peak > 0:
        ax.set_ylim(peak * 1e-6, peak * 2)
    xmax = min(40.0, max(float(spec.frequencies[-1]) for spec in spectra.values()))
    ax.set(xlabel="Frequency (Hz)", ylabel=f"PSD ({next(iter(units))})", xlim=(0, xmax))
    ax.legend()
    ax.grid(alpha=0.2)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_segment(signals: list[Signal], path: Path, seconds: float = 5.0) -> None:
    fig, axes = plt.subplots(len(signals), 1, figsize=(10, 6), squeeze=False, layout="constrained")
    for ax, signal in zip(axes[:, 0], signals, strict=True):
        n = min(int(seconds * signal.fs), signal.values.size)
        scale, unit = (1e6, "µV") if signal.unit == "V" else (1.0, signal.unit)
        ax.plot(signal.times[:n], signal.values[:n] * scale, linewidth=0.6)
        ax.set(ylabel=f"{signal.channel} ({unit})")
    axes[-1, 0].set_xlabel("Time from recording start (s)")
    fig.savefig(path, dpi=150)
    plt.close(fig)
