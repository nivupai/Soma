"""Sensor-space decoding figures from saved predictions and fit diagnostics."""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import mne
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from soma.decoding.features import FeatureBank
from soma.visualization import spectral  # noqa: F401


def plot_evaluation(folder: Path, bank: FeatureBank) -> None:
    summary = pd.read_csv(folder / "summary.csv")
    scores = pd.read_csv(folder / "metrics_subject.csv")
    runs = pd.read_csv(folder / "metrics_run.csv")
    predictions = pd.read_csv(folder / "predictions.csv")
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    for series, (count, group) in enumerate(summary.groupby("calibration_trials")):
        color = plt.get_cmap("tab10")(series)
        offset = 0.12 * (series - (summary.calibration_trials.nunique() - 1) / 2)
        for i, row in enumerate(group.to_dict("records")):
            if np.isfinite(row["estimate"]):
                ax.scatter(
                    i + offset,
                    row["estimate"],
                    s=25,
                    color=color,
                    label=f"k={count}" if i == 0 else None,
                )
            if np.isfinite(row["ci_low"]) and np.isfinite(row["ci_high"]):
                ax.plot(
                    [i + offset, i + offset],
                    [row["ci_low"], row["ci_high"]],
                    color=color,
                    linewidth=1,
                )
        ax.set(xticks=range(len(group)), xticklabels=group.model)
    ax.axhline(0.5, color="black", linestyle="--", linewidth=0.7, label="chance balanced accuracy")
    ax.tick_params(axis="x", labelrotation=30)
    ax.set(
        ylabel="Equal-subject mean balanced accuracy",
        title="Nominal subject t intervals; CV training sets may overlap",
    )
    ax.legend(fontsize=8)
    fig.savefig(folder / "model_comparison.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    groups = list(scores.groupby("model"))
    for i, (_model, frame) in enumerate(groups):
        ax.scatter(np.full(len(frame), i), frame.balanced_accuracy, s=12, alpha=0.6)
    ax.set(
        xticks=range(len(groups)),
        xticklabels=[g[0] for g in groups],
        ylabel="Subject balanced accuracy",
        title="Subject distributions; each dot is a subject/count cell",
    )
    ax.tick_params(axis="x", labelrotation=30)
    ax.axhline(0.5, color="black", linewidth=0.6)
    fig.savefig(folder / "subject_distribution.png", dpi=160)
    plt.close(fig)
    models = list(predictions.model.unique())
    fig, axes = plt.subplots(
        (len(models) + 2) // 3,
        3,
        figsize=(12, 3 * ((len(models) + 2) // 3)),
        layout="constrained",
        squeeze=False,
    )
    for ax in axes.flat:
        ax.axis("off")
    for ax, model in zip(axes.flat, models, strict=False):
        frame = predictions[
            (predictions.model == model)
            & (predictions.calibration_trials == predictions.calibration_trials.min())
        ]
        matrix = np.asarray(
            [[np.sum((frame.label == a) & (frame.prediction == b)) for b in (0, 1)] for a in (0, 1)]
        )
        ax.axis("on")
        ax.imshow(matrix, cmap="Blues")
        for (a, b), value in np.ndenumerate(matrix):
            ax.text(
                b,
                a,
                str(value),
                ha="center",
                va="center",
                color="black",
                bbox={"facecolor": "white", "alpha": 0.6, "edgecolor": "none"},
            )
        ax.set(
            xticks=[0, 1],
            xticklabels=["left", "right"],
            yticks=[0, 1],
            yticklabels=["left", "right"],
            xlabel="Predicted",
            ylabel="True",
            title=f"{model}; n={int(matrix.sum())}",
        )
    fig.savefig(folder / "confusion_matrices.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12, max(5, scores.subject.nunique() * 0.22)),
        layout="constrained",
        squeeze=False,
    )
    for ax, model in zip(axes[0], ("multiband_lr", "tangent_lr"), strict=True):
        chosen = runs[
            (runs.model == model) & (runs.calibration_trials == runs.calibration_trials.min())
        ]
        for y, (_subject, group) in enumerate(chosen.groupby("subject")):
            ax.plot(
                [group.balanced_accuracy.min(), group.balanced_accuracy.max()],
                [y, y],
                color="#3268a8",
                linewidth=0.7,
            )
            ax.scatter(group.balanced_accuracy.mean(), y, s=18)
        ids = sorted(chosen.subject.unique())
        ax.set(
            yticks=range(len(ids)),
            yticklabels=ids,
            xlabel="Balanced accuracy",
            title=f"{model}: bars = observed run range, not CI",
            ylabel="Subject",
        )
        ax.axvline(0.5, color="black", linewidth=0.6)
    fig.savefig(folder / "subject_forest.png", dpi=160)
    plt.close(fig)
    if scores.calibration_trials.nunique() > 1:
        fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
        for model, frame in summary.groupby("model"):
            frame = frame.sort_values("calibration_trials")
            ax.plot(frame.calibration_trials, frame.estimate, marker="o", label=model)
            ax.fill_between(frame.calibration_trials, frame.ci_low, frame.ci_high, alpha=0.15)
        ax.set(
            xlabel="Labeled run-4 calibration trials",
            ylabel="Balanced accuracy on runs 8/12",
            title="Pooling adaptation; shading = nominal subject t intervals",
        )
        ax.legend()
        fig.savefig(folder / "adaptation_curve.png", dpi=160)
        plt.close(fig)
    patterns = pd.read_csv(folder / "csp_patterns.csv")
    if len(patterns):
        first = patterns[patterns.fold == patterns.fold.iloc[0]]
        info = mne.create_info(list(bank.dataset.channels), bank.dataset.fs, "eeg")
        name = (
            "colin27_1005"
            if "colin27_1005" in mne.channels.get_builtin_montages()
            else "standard_1005"
        )
        info.set_montage(name)
        components = sorted(first.component.unique())
        fig, axes = plt.subplots(
            1,
            len(components),
            figsize=(3 * len(components), 3.5),
            layout="constrained",
            squeeze=False,
        )
        for ax, component in zip(axes[0], components, strict=True):
            values = (
                first[first.component == component]
                .set_index("channel")
                .reindex(bank.dataset.channels)
                .pattern.to_numpy(float)
            )
            image, _ = mne.viz.plot_topomap(values, info, axes=ax, show=False, contours=0)
            fig.colorbar(image, ax=ax, shrink=0.65, label="Pattern weight (arbitrary units)")
            ax.set_title(f"Training CSP component {component + 1}")
        fig.suptitle(
            "One training fit; template sensors, arbitrary sign; not anatomical sources", fontsize=9
        )
        fig.savefig(folder / "csp_sensor_patterns.png", dpi=160)
        plt.close(fig)
        stability: list[dict[str, Any]] = []
        reference = (
            first.pivot(index="component", columns="channel", values="pattern")
            .reindex(columns=bank.dataset.channels)
            .to_numpy(float)
        )
        for fold, frame in patterns.groupby("fold"):
            candidate = (
                frame.pivot(index="component", columns="channel", values="pattern")
                .reindex(columns=bank.dataset.channels)
                .to_numpy(float)
            )
            similarities = np.abs(reference @ candidate.T) / np.maximum(
                np.linalg.norm(reference, axis=1)[:, None]
                * np.linalg.norm(candidate, axis=1)[None],
                1e-30,
            )
            a, b = linear_sum_assignment(-similarities)
            stability.extend(
                {
                    "fold": fold,
                    "reference_component": int(i),
                    "matched_component": int(j),
                    "absolute_cosine": float(similarities[i, j]),
                    "interpretation": "sign/permutation aligned; reference is first training fold",
                }
                for i, j in zip(a, b, strict=True)
            )
        pd.DataFrame(stability).to_csv(folder / "csp_pattern_stability.csv", index=False)
    states = json.loads((folder / "fitted_states.json").read_text())
    diagnostic = [
        {"model": state["model"], "fold": state["fold"], **row}
        for state in states
        for row in state.get("test_trial_covariance_diagnostics", [])
    ]
    if diagnostic:
        table = pd.DataFrame(diagnostic)
        table.to_csv(folder / "covariance_diagnostics.csv", index=False)
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
        axes[0].hist(np.log10(table.minimum_eigenvalue), bins=35)
        axes[1].hist(np.log10(table.condition_number), bins=35)
        axes[0].set(xlabel="log10 minimum eigenvalue (µV²)", ylabel="Trial/fit count")
        axes[1].set(xlabel="log10 spectral condition number", ylabel="Trial/fit count")
        fig.suptitle(
            "Explicit OAS/floor covariance diagnostics; repeated folds are not independent trials"
        )
        fig.savefig(folder / "covariance_conditioning.png", dpi=160)
        plt.close(fig)
    _probability_plot(folder)
    _tangent_plot(folder)


def _probability_plot(folder: Path) -> None:
    try:
        table = pd.read_csv(folder / "reliability.csv")
    except pd.errors.EmptyDataError:
        return
    if table.empty:
        return
    fig, ax = plt.subplots(figsize=(7, 5), layout="constrained")
    for (model, count), group in table.groupby(["model", "calibration_trials"]):
        if model in ("multiband_lr", "tangent_lr", "dummy"):
            ax.plot(
                group.mean_probability,
                group.fraction_right,
                marker="o",
                label=f"{model}; k={count}",
            )
    ax.plot([0, 1], [0, 1], color="black", linewidth=0.6)
    ax.set(
        xlabel="Mean predicted P(right)",
        ylabel="Observed fraction right",
        title="Descriptive reliability bins; correlated trials, no binomial CI",
    )
    ax.legend()
    fig.savefig(folder / "reliability.png", dpi=160)
    plt.close(fig)


def _tangent_plot(folder: Path) -> None:
    path = folder / "tangent_projection.csv"
    if not path.exists():
        return
    table = pd.read_csv(path)
    if table.empty:
        return
    first = table[table.fold == table.fold.iloc[0]]
    fig, ax = plt.subplots(figsize=(6, 5), layout="constrained")
    for label, group in first.groupby("label"):
        ax.scatter(
            group.coordinate_0,
            group.coordinate_1,
            s=14,
            alpha=0.6,
            label="right" if label else "left",
        )
    ax.set(
        xlabel="Tangent coordinate 0",
        ylabel="Tangent coordinate 1",
        title="First outer test fold; training reference; descriptive 2D slice",
    )
    ax.legend()
    fig.savefig(folder / "tangent_projection.png", dpi=160)
    plt.close(fig)
