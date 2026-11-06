"""Optional plotting for run-preserving motor imagery artifacts."""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

# Reuse the existing headless plotting setup and configured cache locations.
from soma.visualization import spectral  # noqa: F401

COLORS = {"T0": "#9a9a9a", "T1": "#3268b2", "T2": "#dc7b32"}
CONDITIONS = ("left hand imagery", "right hand imagery")


def _average(data: Any) -> Any:
    count = np.sum(np.isfinite(data), axis=0)
    result = np.full(count.shape, np.nan)
    np.divide(np.nansum(data, axis=0), count, out=result, where=count > 0)
    return result


def plot_motor_imagery(results: dict[int, dict[str, Any]], output: Path) -> None:
    fig, axes = plt.subplots(
        len(results), 1, figsize=(12, 2.5 * len(results)), squeeze=False, layout="constrained"
    )
    for ax, (run, r) in zip(axes[:, 0], results.items(), strict=True):
        for ev in r["events"].itertuples():
            ax.broken_barh([(ev.onset_s, ev.duration_s)], (0, 1), facecolors=COLORS[ev.code])
        ax.set(xlabel="Recording time (s)", ylabel=f"Run {run}", yticks=[])
        for code, label in (("T0", "rest"), ("T1", "left imagery"), ("T2", "right imagery")):
            ax.plot([], [], color=COLORS[code], linewidth=6, label=label)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.28), ncol=3)
    fig.savefig(output / "event_timeline.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(
        1, len(results), figsize=(6 * len(results), 6), squeeze=False, layout="constrained"
    )
    for ax, (run, r) in zip(axes[0], results.items(), strict=True):
        for ch, xyz in r["geometry"]["positions"].items():
            selected = ch in r["epochs"].channels
            ax.scatter(xyz[0], xyz[1], color="#bd5329" if selected else "#91a9b4", s=24)
            ax.annotate(ch, (xyz[0], xyz[1]), fontsize=7, xytext=(2, 2), textcoords="offset points")
        ax.set(
            title=f"Run {run}: template positions, not digitization",
            xlabel="Head x (m), right →",
            ylabel="Head y (m), anterior →",
            aspect="equal",
        )
    fig.savefig(output / "sensor_montage.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(
        len(results),
        max(len(r["epochs"].channels) for r in results.values()),
        figsize=(13, 3.7 * len(results)),
        squeeze=False,
        layout="constrained",
    )
    for row, (run, r) in enumerate(results.items()):
        epochs, spec, rest, rest_spec = r["epochs"], r["spectra"], r["rest"], r["rest_spectra"]
        for c, ch in enumerate(epochs.channels):
            ax = axes[row, c]
            if len(rest.trials):
                ax.semilogy(
                    rest_spec.frequencies,
                    np.mean(rest_spec.density[:, c], axis=0),
                    color=COLORS["T0"],
                    label=f"rest n={len(rest.trials)}",
                )
            for label, code in zip(CONDITIONS, ("T1", "T2"), strict=True):
                mask = np.array([t.event.label == label for t in epochs.trials], dtype=bool)
                if mask.any():
                    ax.semilogy(
                        spec.frequencies,
                        np.mean(spec.density[mask, c], axis=0),
                        label=f"{label}, n={mask.sum()}",
                        color=COLORS[code],
                    )
            ax.set(
                title=f"Run {run} {ch}", xlabel="Frequency (Hz)", ylabel="PSD (V²/Hz)", xlim=(5, 35)
            )
            visible = (spec.frequencies >= 5) & (spec.frequencies <= 35)
            densities = [line.get_ydata()[visible] for line in ax.lines]
            if densities:
                positive = np.concatenate(densities)
                positive = positive[positive > 0]
                if positive.size:
                    ax.set_ylim(float(np.min(positive)) / 2, float(np.max(positive)) * 2)
                ax.legend(fontsize=7)
    fig.savefig(output / "psd_comparison.png", dpi=150)
    plt.close(fig)
    rows = sum(2 * len(r["context"].channels) for r in results.values())
    fig, axes = plt.subplots(rows, 1, figsize=(10, 2.4 * rows), squeeze=False, layout="constrained")
    i = 0
    for run, r in results.items():
        tfr, context = r["tfr"], r["context"]
        for label in CONDITIONS:
            mask = np.array([t.event.label == label for t in context.trials], dtype=bool)
            for c, channel in enumerate(context.channels):
                ax = axes[i, 0]
                i += 1
                if mask.any():
                    average = _average(tfr.power[mask, c])
                    view = np.full_like(average, np.nan)
                    np.log10(average, out=view, where=average > 0)
                    mesh = ax.pcolormesh(
                        tfr.times,
                        tfr.frequencies,
                        view,
                        shading="auto",
                        cmap="viridis",
                        vmin=-12,
                        vmax=-8,
                    )
                    fig.colorbar(mesh, ax=ax, label="log10 wavelet power (V²)")
                else:
                    ax.text(
                        0.5, 0.5, "No accepted context trials", ha="center", transform=ax.transAxes
                    )
                ax.set(
                    title=f"Run {run} {channel}, {label}, n={mask.sum()}; edges masked",
                    xlabel="Time from cue (s)",
                    ylabel="Hz",
                )
    fig.savefig(output / "timefrequency.png", dpi=130)
    plt.close(fig)
    if not any(np.isfinite(r["tfr_change"].percent).any() for r in results.values()):
        return
    fig, axes = plt.subplots(
        len(results) * 2, 2, figsize=(12, 5 * len(results)), squeeze=False, layout="constrained"
    )
    for row, (run, r) in enumerate(results.items()):
        tfr, context = r["tfr"], r["context"]
        for condition, label in enumerate(CONDITIONS):
            mask = np.array([t.event.label == label for t in context.trials], dtype=bool)
            for b, (band, limits) in enumerate((("mu", (8, 13)), ("beta", (13, 30)))):
                ax = axes[row * 2 + condition, b]
                freq_mask = (tfr.frequencies >= limits[0]) & (tfr.frequencies <= limits[1])
                if mask.any():
                    average = _average(r["tfr_change"].percent[mask])
                    for c, ch in enumerate(context.channels):
                        band_average = _average(average[c, freq_mask])
                        ax.plot(tfr.times, band_average, label=ch)
                ax.axhline(0, color="black", linewidth=0.6)
                ax.set(
                    title=f"Run {run} {label}: {band}",
                    xlabel="Time from cue (s)",
                    ylabel="Wavelet ERD/ERS (%)",
                )
                if len(ax.lines) > 1:
                    ax.legend(fontsize=8)
    fig.savefig(output / "erd_ers.png", dpi=150)
    plt.close(fig)
