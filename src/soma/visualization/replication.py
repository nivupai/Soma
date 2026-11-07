"""Replication/influence figures drawn from saved statistical and quality tables."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.visualization import spectral  # noqa: F401


def plot_influence(folder: Path) -> None:
    table = pd.read_csv(folder / "leave_one_subject_out.csv")
    if table.empty:
        return
    selected = table[(table.outcome == "log_absolute_power") & (table.band == "mu")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", squeeze=False)
    for ax, channel in zip(axes[0], ("C3", "C4"), strict=True):
        data = selected[selected.channel == channel].sort_values("excluded_subject")
        ax.scatter(data.excluded_subject, data.change, color="#3268a8", s=20)
        for row in data.nlargest(3, "absolute_change").to_dict("records"):
            ax.annotate(
                f"S{row['excluded_subject']}",
                (row["excluded_subject"], row["change"]),
                xytext=(3, 4),
                textcoords="offset points",
                fontsize=7,
            )
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set(
            title=f"{channel} mu: leave-one-subject change",
            xlabel="Excluded subject",
            ylabel="Change in equal-subject mean log contrast",
        )
    fig.savefig(folder / "subject_influence.png", dpi=180)
    plt.close(fig)


def plot_replication(folder: Path) -> None:
    subjects = pd.read_csv(folder / "subject_contrasts.csv")
    runs = pd.read_csv(folder / "run_contrasts.csv")
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12, max(5, len(subjects.subject.unique()) * 0.28)),
        layout="constrained",
        squeeze=False,
    )
    ids = sorted(subjects.subject.unique())
    for ax, channel in zip(axes[0], ("C3", "C4"), strict=True):
        chosen = (
            subjects[
                (subjects.channel == channel)
                & (subjects.band == "mu")
                & (subjects.outcome == "log_absolute_power")
            ]
            .set_index("subject")
            .reindex(ids)
        )
        for y, (_subject, subject_row) in enumerate(chosen.iterrows()):
            if np.isfinite(subject_row["contrast"]):
                value = float(subject_row["contrast"])
                spread = float(subject_row["run_sd"])
                ax.scatter(value, y, color="#3268a8", s=18)
                if np.isfinite(spread):
                    ax.plot(
                        [value - spread, value + spread], [y, y], color="#3268a8", linewidth=0.7
                    )
            else:
                ax.text(0, y, "excluded/unavailable", fontsize=6)
        ax.set(
            yticks=range(len(ids)),
            yticklabels=[f"S{s}" for s in ids],
            xlabel="Left − right mean log power",
            title=f"{channel} mu; bars = run SD, not CI",
        )
        ax.axvline(0, color="black", linewidth=0.6)
    fig.savefig(folder / "subject_forest.png", dpi=170)
    plt.close(fig)
    comparison = pd.read_csv(folder / "initial_comparison.csv")
    if len(comparison):
        fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout="constrained")
        for i, channel in enumerate(("C3", "C4")):
            for j, band in enumerate(("mu", "beta")):
                ax = axes[i, j]
                data = comparison[
                    (comparison.channel == channel)
                    & (comparison.band == band)
                    & (comparison.outcome == "log_absolute_power")
                    & (comparison.method == "t")
                ]
                labels = []
                for y, row in enumerate(data.to_dict("records")):
                    labels.append(f"{row['cohort']}, n={row['n_subjects']}")
                    if np.isfinite(row["estimate"]):
                        ax.scatter(row["estimate"], y, color="#3268a8")
                    if np.isfinite(row["ci_low"]) and np.isfinite(row["ci_high"]):
                        ax.plot([row["ci_low"], row["ci_high"]], [y, y], color="#3268a8")
                ax.axvline(0, color="black", linewidth=0.6)
                ax.set(
                    yticks=range(len(labels)),
                    yticklabels=labels,
                    title=f"{channel} {band}",
                    xlabel="Log-power contrast; bars = nominal 95% subject t intervals",
                )
        fig.savefig(folder / "initial_vs_replication.png", dpi=170)
        plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11, max(7, len(ids) * 0.27)), layout="constrained")
    bound = max(0.1, float(np.nanmax(np.abs(runs[runs.outcome == "log_absolute_power"].contrast))))
    for i, channel in enumerate(("C3", "C4")):
        for j, band in enumerate(("mu", "beta")):
            ax = axes[i, j]
            data = runs[
                (runs.channel == channel)
                & (runs.band == band)
                & (runs.outcome == "log_absolute_power")
            ]
            matrix = data.pivot(index="subject", columns="run", values="contrast").reindex(
                index=ids
            )
            image = ax.imshow(
                matrix.to_numpy(float), aspect="auto", cmap="RdBu_r", vmin=-bound, vmax=bound
            )
            ax.set(
                yticks=range(len(ids)),
                yticklabels=ids,
                xticks=range(len(matrix.columns)),
                xticklabels=matrix.columns,
                title=f"{channel} {band}",
                xlabel="Run",
                ylabel="Subject",
            )
            fig.colorbar(image, ax=ax, label="Paired left − right log power")
    fig.savefig(folder / "subject_run_effects.png", dpi=170)
    plt.close(fig)
    quality = pd.read_csv(folder / "quality_subject.csv")
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), layout="constrained")
    axes[0].bar(quality.subject, quality.complete_runs, color="#3268a8", label="complete")
    axes[0].bar(
        quality.subject,
        quality.failed_runs,
        bottom=quality.complete_runs,
        color="#bd5636",
        label="failed",
    )
    axes[0].set(ylabel="Run count", title="Every requested subject is retained in QC accounting")
    axes[0].legend()
    retention = quality.imagery_accepted / quality.imagery_proposed.where(
        quality.imagery_proposed > 0
    )
    axes[1].bar(quality.subject, retention, color="#3268a8")
    axes[1].axhline(
        0.7, color="black", linestyle="--", label="prespecified 70% retention criterion"
    )
    axes[1].set(ylabel="Accepted / proposed imagery", xlabel="Subject", ylim=(0, 1.05))
    axes[1].legend()
    fig.savefig(folder / "cohort_quality.png", dpi=170)
    plt.close(fig)
    plot_influence(folder)
    weights = pd.read_csv(folder / "weighting_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", squeeze=False)
    for ax, channel in zip(axes[0], ("C3", "C4"), strict=True):
        for band, color in (("mu", "#3268a8"), ("beta", "#c07832")):
            data = weights[(weights.channel == channel) & (weights.band == band)]
            ax.scatter(data.estimand, data.estimate, label=band, color=color)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.tick_params(axis="x", labelrotation=20)
        ax.set(
            title=f"{channel}: distinct weighting targets; no error bars",
            ylabel="Mean log contrast",
        )
        ax.legend()
    fig.savefig(folder / "weighting_diagnostics.png", dpi=170)
    plt.close(fig)


def plot_replication_sensitivity(folder: Path) -> None:
    table = pd.read_csv(folder / "sensitivity_effects.csv")
    data = table[
        (table.outcome == "log_absolute_power") & (table.band == "mu") & (table.method == "t")
    ]
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), layout="constrained", squeeze=False)
    for ax, channel in zip(axes[0], ("C3", "C4"), strict=True):
        selected = data[data.channel == channel]
        for y, row in enumerate(selected.to_dict("records")):
            ax.scatter(row["estimate"], y, color="#3268a8")
            ax.plot([row["ci_low"], row["ci_high"]], [y, y], color="#3268a8")
        ax.axvline(0, color="black", linewidth=0.6)
        ax.set(
            yticks=range(len(selected)),
            yticklabels=selected.variant,
            title=f"{channel} mu: all prespecified variants",
            xlabel="Left − right log power; nominal 95% subject t intervals",
        )
    fig.savefig(folder / "configuration_robustness.png", dpi=180)
    plt.close(fig)
