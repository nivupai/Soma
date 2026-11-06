"""Auditable scientific figures drawn from saved CSVs, with explicit statistical units."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from soma.visualization import spectral  # noqa: F401

COLORS = {"C3": "#2864a6", "Cz": "#6b6b6b", "C4": "#c36b24"}


def _save(fig: Figure, path: Path) -> None:
    # Figure typing is supplied by Matplotlib where available.
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_cohort(folder: Path) -> None:
    subjects = pd.read_csv(folder / "subject_contrasts.csv")
    subjects = subjects[subjects.outcome == "log_absolute_power"]
    if subjects.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", squeeze=False)
    for ax, band in zip(axes[0], ("mu", "beta"), strict=True):
        for channel, color in COLORS.items():
            data = subjects[(subjects.band == band) & (subjects.channel == channel)]
            ax.scatter(data.subject, data.contrast, label=channel, color=color, s=35)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set(
            title=f"{band}: one point per subject/channel",
            xlabel="Subject",
            ylabel="Left − right log power (natural log ratio)",
        )
        ax.legend()
        ax.set_xticks(sorted(subjects.subject.unique()))
    _save(fig, folder / "subject_effects.png")
    runs = pd.read_csv(folder / "run_contrasts.csv")
    runs = runs[runs.outcome == "log_absolute_power"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), layout="constrained")
    for b, band in enumerate(("mu", "beta")):
        for c, channel in enumerate(COLORS):
            ax = axes[b, c]
            selected = runs[(runs.band == band) & (runs.channel == channel)]
            for subject, data in selected.groupby("subject"):
                data = data.sort_values("run")
                ax.plot(
                    data.run, data.contrast, "o-", label=f"S{subject}", linewidth=0.8, markersize=4
                )
            ax.axhline(0, color="black", linewidth=0.6)
            ax.set(
                title=f"{channel} {band}: paired run contrasts",
                xlabel="Run",
                ylabel="Left − right log power",
            )
            ax.set_xticks(sorted(runs.run.unique()))
            if c == 2:
                ax.legend(fontsize=7, ncol=2)
    _save(fig, folder / "run_consistency.png")
    population = pd.read_csv(folder / "population.csv")
    population = population[population.outcome == "log_absolute_power"].sort_values(
        ["band", "channel"]
    )
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    for y, row in enumerate(population.to_dict("records")):
        if np.isfinite(row["estimate"]):
            ax.scatter(row["estimate"], y, color=COLORS.get(row["channel"], "black"))
        if np.isfinite(row["ci_low"]) and np.isfinite(row["ci_high"]):
            ax.plot(
                [row["ci_low"], row["ci_high"]], [y, y], color=COLORS.get(row["channel"], "black")
            )
    labels = [
        f"{row['channel']} {row['band']}, n={row['n_subjects']} subjects"
        for row in population.to_dict("records")
    ]
    ax.set(
        yticks=range(len(labels)),
        yticklabels=labels,
        xlabel="Mean left − right log power (natural log ratio)",
        title=(
            f"Equal-subject mean; nominal {population.confidence.iloc[0] * 100:g}% "
            "pointwise percentile subject-bootstrap intervals"
        ),
    )
    ax.axvline(0, color="black", linewidth=0.6)
    _save(fig, folder / "effect_forest.png")
    lateral = pd.read_csv(folder / "lateralization_subject.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", squeeze=False)
    for ax, band in zip(axes[0], ("mu", "beta"), strict=True):
        for metric, color, label in (
            ("left_log_contra_over_ipsi", "#2864a6", "left: C4/C3"),
            ("right_log_contra_over_ipsi", "#c36b24", "right: C3/C4"),
        ):
            selected = lateral[(lateral.band == band) & (lateral.outcome == metric)]
            ax.scatter(selected.subject, selected.contrast, label=label, color=color, s=30)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set(
            title=f"{band}: sensor convention; subject means",
            xlabel="Subject",
            ylabel="Log contra/ipsi power",
        )
        ax.legend(fontsize=8)
        ax.set_xticks(sorted(lateral.subject.unique()))
    _save(fig, folder / "lateralization.png")
    bursts = pd.read_csv(folder / "burst_condition_summary.csv")
    fig, axes = plt.subplots(3, 2, figsize=(11, 10), layout="constrained")
    conditions = ("rest", "left hand imagery", "right hand imagery")
    for c, channel in enumerate(COLORS):
        for b, band in enumerate(("mu", "beta")):
            ax = axes[c, b]
            chosen = bursts[(bursts.channel == channel) & (bursts.band == band)]
            for j, (strategy, data) in enumerate(chosen.groupby("strategy")):
                for subject, group in data.groupby("subject"):
                    means = group.groupby("condition").occupancy.mean()
                    points = [means.get(label, np.nan) * 100 for label in conditions]
                    ax.plot(
                        np.arange(3) + (j - 0.5) * 0.08,
                        points,
                        "o-",
                        alpha=0.55,
                        linewidth=0.7,
                        color=["#2864a6", "#c36b24"][j % 2],
                        markersize=3,
                        label=strategy if subject == data.subject.min() else None,
                    )
            ax.set(
                title=f"{channel} {band}: points are subject means",
                xticks=range(3),
                xticklabels=("rest", "left", "right"),
                ylabel="Valid-time burst occupancy (%)",
                ylim=(0, 100),
            )
            if ax.lines:
                ax.legend(fontsize=7)
    _save(fig, folder / "burst_occupancy.png")
    events = pd.read_csv(folder / "burst_events.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", squeeze=False)
    for ax, band in zip(axes[0], ("mu", "beta"), strict=True):
        for strategy, group in events[(events.band == band) & events.complete].groupby("strategy"):
            ax.hist(
                group.observed_duration_s,
                bins=np.linspace(0, max(2.0, float(events.observed_duration_s.max())), 25),
                histtype="step",
                label=strategy,
            )
        ax.set(
            title=f"{band}: complete fragments pooled descriptively",
            xlabel="Duration (s)",
            ylabel="Count (not independent subjects)",
        )
        if ax.patches:
            ax.legend(fontsize=8)
    _save(fig, folder / "burst_durations.png")
    retention = pd.read_csv(folder / "retention.csv")
    accepted = retention[retention.stage == "analysis"].pivot(
        index="subject", columns="run", values="accepted"
    )
    proposed = retention[retention.stage == "analysis"].pivot(
        index="subject", columns="run", values="proposed"
    )
    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
    coverage = pd.read_csv(folder / "coverage.csv")
    requested_subjects, requested_runs = (
        sorted(coverage.subject.unique()),
        sorted(coverage.run.unique()),
    )
    accepted = accepted.reindex(index=requested_subjects, columns=requested_runs)
    proposed = proposed.reindex(index=requested_subjects, columns=requested_runs)
    matrix = accepted / proposed.where(proposed > 0)
    image = ax.imshow(matrix.to_numpy(), vmin=0, vmax=1, cmap="Blues", aspect="auto")
    for i in range(len(matrix)):
        for j in range(len(matrix.columns)):
            value = accepted.to_numpy(dtype=float)[i, j]
            ax.text(
                j,
                i,
                f"{int(value)}/{int(proposed.to_numpy(dtype=float)[i, j])}"
                if np.isfinite(value)
                else "missing",
                ha="center",
                va="center",
                color="white" if matrix.to_numpy(dtype=float)[i, j] > 0.6 else "#111111",
            )
    ax.set(
        xticks=range(len(matrix.columns)),
        xticklabels=matrix.columns,
        yticks=range(len(matrix)),
        yticklabels=matrix.index,
        xlabel="Run",
        ylabel="Subject",
        title="Accepted / proposed imagery windows; incomplete records in coverage.csv",
    )
    fig.colorbar(image, ax=ax, label="Trial retention fraction")
    _save(fig, folder / "trial_retention.png")


def plot_sensitivity(folder: Path) -> None:
    frame = pd.read_csv(folder / "sensitivity_effects.csv")
    frame = frame[(frame.outcome == "log_absolute_power") & frame.channel.isin(["C3", "C4"])].copy()
    frame["outcome_label"] = frame.channel + " " + frame.band
    matrix = frame.pivot(index="variant", columns="outcome_label", values="effect_change")
    bound = max(float(np.nanmax(np.abs(matrix.to_numpy()))), 0.01)
    fig, ax = plt.subplots(figsize=(10, 7), layout="constrained")
    mesh = ax.imshow(matrix.to_numpy(), cmap="RdBu_r", vmin=-bound, vmax=bound, aspect="auto")
    for i in range(len(matrix)):
        for j in range(len(matrix.columns)):
            value = matrix.to_numpy(dtype=float)[i, j]
            ax.text(
                j,
                i,
                f"{value:+.3f}" if np.isfinite(value) else "unavailable",
                ha="center",
                va="center",
                fontsize=8,
            )
    ax.set(
        xticks=range(len(matrix.columns)),
        xticklabels=matrix.columns,
        yticks=range(len(matrix)),
        yticklabels=matrix.index,
        title="Prespecified sensitivity: change in left − right log power vs primary",
    )
    fig.colorbar(mesh, ax=ax, label="Change in natural log ratio (equal-subject estimate)")
    _save(fig, folder / "sensitivity_heatmap.png")
    missing = pd.read_csv(folder / "sensitivity_missingness.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    axes[0].barh(missing.variant, missing.subjects_retained, color="#2864a6")
    axes[0].set(xlabel="Subjects with any accepted imagery", title="Subject retention")
    axes[1].barh(missing.variant, missing.missing_reference_fraction * 100, color="#c36b24")
    axes[1].set(
        xlabel="Unavailable normalized feature cells (%)",
        title="Reference missingness; absolute power retained",
        xlim=(0, 100),
    )
    _save(fig, folder / "sensitivity_retention.png")
