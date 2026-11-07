"""Calibration plots use saved estimates and explicit Monte Carlo uncertainty."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.visualization import spectral  # noqa: F401

COLORS = {
    "percentile": "#3268a8",
    "basic": "#d07928",
    "studentized": "#258568",
    "bca": "#945eb0",
    "t": "#333333",
}


def plot_calibration(folder: Path) -> None:
    table = pd.read_csv(folder / "calibration.csv")
    scenarios = table.scenario.unique().tolist()
    rows = int(np.ceil(len(scenarios) / 2))
    for metric, name, ylabel in (
        ("coverage", "coverage.png", "Coverage probability"),
        ("mean_width", "interval_width.png", "Mean successful interval width (log units)"),
        ("failure_rate", "interval_failures.png", "Failure fraction"),
    ):
        fig, axes = plt.subplots(
            rows, 2, figsize=(12, 3.4 * rows), layout="constrained", squeeze=False
        )
        for ax, scenario in zip(axes.flat, scenarios, strict=False):
            data = table[table.scenario == scenario]
            for method, group in data.groupby("method"):
                group = group.sort_values("n_requested")
                x = group.n_requested.to_numpy(float)
                y = group[metric].to_numpy(float)
                if metric == "coverage":
                    error = np.vstack(
                        (
                            y - group.coverage_mc_ci_low.to_numpy(float),
                            group.coverage_mc_ci_high.to_numpy(float) - y,
                        )
                    )
                    ax.errorbar(
                        x,
                        y,
                        yerr=error,
                        label=method,
                        color=COLORS[str(method)],
                        marker="o",
                        markersize=3,
                        linewidth=0.8,
                        capsize=2,
                    )
                else:
                    ax.plot(
                        x,
                        y,
                        "o-",
                        label=method,
                        color=COLORS[str(method)],
                        linewidth=0.8,
                        markersize=3,
                    )
            if metric == "coverage":
                ax.axhline(
                    float(data.nominal_confidence.iloc[0]),
                    color="black",
                    linestyle="--",
                    linewidth=0.7,
                )
                ax.set_ylim(0, 1.02)
            if metric == "failure_rate":
                ax.set_ylim(0, 1)
            ax.set(
                title=str(scenario),
                xlabel="Independent subjects",
                ylabel=ylabel,
                xticks=sorted(data.n_requested.unique()),
            )
            ax.legend(fontsize=7, ncol=2)
        for ax in list(axes.flat)[len(scenarios) :]:
            ax.set_visible(False)
        if metric == "coverage":
            fig.suptitle("All-replication coverage; bars: exact 95% Monte Carlo binomial intervals")
        fig.savefig(folder / name, dpi=170)
        plt.close(fig)
    fig, axes = plt.subplots(
        len(scenarios), 2, figsize=(11, 2.7 * len(scenarios)), layout="constrained", squeeze=False
    )
    for i, scenario in enumerate(scenarios):
        data = table[(table.scenario == scenario) & (table.method == "t")].sort_values(
            "n_requested"
        )
        if data.empty:
            data = (
                table[table.scenario == scenario]
                .drop_duplicates("n_requested")
                .sort_values("n_requested")
            )
        axes[i, 0].plot(data.n_requested, data.bias, "o-", label="bias vs observed-data target")
        axes[i, 0].plot(
            data.n_requested, data.structural_bias, "s--", label="bias vs structural truth"
        )
        axes[i, 0].axhline(0, color="black", linewidth=0.5)
        axes[i, 0].set(
            title=str(scenario), ylabel="Mean-estimator bias (log units)", xlabel="Subjects"
        )
        axes[i, 0].legend(fontsize=7)
        axes[i, 1].plot(data.n_requested, data.rmse, "o-", color="#3268a8")
        axes[i, 1].set(title=str(scenario), ylabel="RMSE vs target (log units)", xlabel="Subjects")
    fig.savefig(folder / "bias_rmse.png", dpi=150)
    plt.close(fig)
