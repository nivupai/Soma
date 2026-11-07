"""Reference and artifact diagnostics with physical units and saved figure data."""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.visualization import spectral  # noqa: F401


def plot_covariance(
    folder: Path,
    channels: tuple[str, ...],
    original: np.ndarray[Any, Any],
    average: np.ndarray[Any, Any],
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), layout="constrained")
    ticks = [channels.index(ch) for ch in ("C3", "Cz", "C4", "Fz", "Pz") if ch in channels]
    for ax, matrix, title in zip(
        axes,
        (original, average),
        ("Acquisition reference, filtered", "Average reference, filtered"),
        strict=True,
    ):
        scale = np.sqrt(np.diag(matrix))
        denom = scale[:, None] * scale[None, :]
        corr = np.full(matrix.shape, np.nan)
        np.divide(matrix, denom, out=corr, where=denom > 0)
        image = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
        ax.set(
            title=title,
            xticks=ticks,
            yticks=ticks,
            xticklabels=[channels[i] for i in ticks],
            yticklabels=[channels[i] for i in ticks],
        )
        fig.colorbar(image, ax=ax, label="Channel correlation (all EEG channels)")
    fig.savefig(folder / "channel_correlation.png", dpi=160)
    plt.close(fig)


def plot_artifact_excerpt(
    folder: Path,
    times: np.ndarray[Any, Any],
    original: np.ndarray[Any, Any],
    referenced: dict[str, np.ndarray[Any, Any]],
    channels: tuple[str, ...],
) -> None:
    fig, axes = plt.subplots(
        len(channels), 2, figsize=(12, 2.6 * len(channels)), layout="constrained", squeeze=False
    )
    for c, channel in enumerate(channels):
        axes[c, 0].plot(times, original[c] * 1e6, label="raw acquisition", linewidth=0.6)
        axes[c, 0].plot(
            times, referenced["none"][c] * 1e6, label="filtered acquisition", linewidth=0.6
        )
        for name in ("average", "Fz_Pz"):
            axes[c, 1].plot(times, referenced[name][c] * 1e6, label=name, linewidth=0.7)
        for ax in axes[c]:
            ax.axvspan(
                1, 3, color="#bbbbbb", alpha=0.15, label="analysis window" if c == 0 else None
            )
            ax.set(
                title=f"{channel}: highest peak-to-peak proposal in run",
                xlabel="Time from cue (s)",
                ylabel="Voltage (µV)",
            )
            ax.legend(fontsize=7)
    fig.suptitle(
        "Review candidate, not a diagnosed artifact; raw voltage retains acquisition reference"
    )
    fig.savefig(folder / "artifact_review.png", dpi=150)
    plt.close(fig)


def plot_reference_audit(folder: Path) -> None:
    colors = {"average": "#3268a8", "none": "#d07928", "Fz_Pz": "#26856a"}
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), layout="constrained")
    for i, (filename, label) in enumerate(
        (
            ("retained_effects.csv", "Reference-specific retained trials"),
            ("common_trial_effects.csv", "Identical accepted trial intersection"),
        )
    ):
        table = pd.read_csv(folder / filename)
        for j, channel in enumerate(("C3", "C4")):
            ax = axes[i, j]
            for k, (reference, group) in enumerate(
                table[(table.channel == channel) & (table.band == "mu")].groupby("reference")
            ):
                ax.scatter(
                    group.subject + (k - 1) * 0.08,
                    group.contrast,
                    color=colors[str(reference)],
                    label=reference,
                    s=25,
                )
            ax.axhline(0, color="black", linewidth=0.6)
            ax.set(
                title=f"{channel} mu: {label}",
                xlabel="Subject",
                ylabel="Left − right log-power contrast",
                xticks=sorted(table.subject.unique()),
            )
            ax.legend(fontsize=7)
    fig.savefig(folder / "reference_sensitivity.png", dpi=170)
    plt.close(fig)
    table = pd.read_csv(folder / "common_mode.csv")
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    for run, group in table.groupby("run"):
        ax.scatter(group.subject, group.largest_pc_variance_fraction, label=f"Run {run}")
    ax.set(
        xlabel="Subject",
        ylabel="Largest covariance eigenvalue / trace",
        ylim=(0, 1),
        title="Common covariance structure before re-reference; no source interpretation",
        xticks=sorted(table.subject.unique()),
    )
    ax.legend()
    fig.savefig(folder / "common_mode.png", dpi=170)
    plt.close(fig)
    table = pd.read_csv(folder / "spectral_identity.csv")
    per_run = (
        table.groupby(["subject", "run", "channel", "band", "reference"])
        .mean(numeric_only=True)
        .reset_index()
    )
    per_subject = (
        per_run.groupby(["subject", "channel", "band", "reference"])
        .mean(numeric_only=True)
        .reset_index()
    )
    summary = (
        per_subject.groupby(["channel", "band", "reference"]).mean(numeric_only=True).reset_index()
    )
    summary.to_csv(folder / "spectral_components_figure_data.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", squeeze=False)
    for ax, channel in zip(axes[0], ("C3", "C4"), strict=True):
        row = summary[
            (summary.channel == channel) & (summary.band == "mu") & (summary.reference == "average")
        ].to_dict("records")[0]
        values = [
            row["acquisition_power_v2"],
            row["reference_power_v2"],
            -2 * row["cross_real_v2"],
            row["actual_referenced_power_v2"],
        ]
        ax.bar(
            ["Px", "Pr", "−2 Re Pxr", "P(x−r)"],
            np.asarray(values) * 1e12,
            color=["#3268a8", "#d07928", "#a84c58", "#26856a"],
        )
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set(
            title=f"{channel} mu: equal-run/subject PSD identity",
            ylabel="Band-power component (µV²)",
        )
    fig.savefig(folder / "spectral_reference_identity.png", dpi=170)
    plt.close(fig)
