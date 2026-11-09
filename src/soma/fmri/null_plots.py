"""Null diagnostics with Monte Carlo units and saved plotting arrays."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soma.validation.plots import save


def null_figures(root: Path, summaries: list[dict[str, Any]], p_values: dict[str, Any]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), layout="constrained")
    arrays = {}
    for model in ["ols", "ar1", "ar2", "known-GLS", "estimated-stationary-AR1"]:
        key = "single-ar1-n100-" + model
        values = np.asarray(p_values[key])
        ordered = np.sort(values)
        axes[0].plot((np.arange(len(values)) + 0.5) / len(values), ordered, label=model)
        axes[1].hist(values, bins=np.linspace(0, 1, 11), histtype="step", label=model)
        arrays[model + "_p"] = values
    axes[0].plot([0, 1], [0, 1], color="black", ls="--")
    axes[0].set(
        xlabel="Uniform quantile", ylabel="Observed p quantile", title="AR(.6), one voxel, n100"
    )
    axes[1].set(
        xlabel="Nominal two-sided p",
        ylabel="independent realizations",
        title="Marginal p histogram",
    )
    axes[1].legend(fontsize=7)
    spatial = [r for r in summaries if r["case"] == "spatial-ar1-independent-m343"]
    x = np.arange(len(spatial))
    for i, method in enumerate(["bh", "by", "bonferroni"]):
        values = np.array([r[method]["any_rejection"] for r in spatial])
        axes[2].bar(x + (i - 1) * 0.22, values, 0.22, label=method)
        arrays[method + "_family_rate"] = values
    axes[2].axhline(0.05, color="black")
    axes[2].set_xticks(x, [r["model"] for r in spatial], rotation=20)
    axes[2].set(
        ylabel="Any rejection probability", title="Global null,343 voxels; not marginal error"
    )
    axes[2].legend()
    fig.suptitle("Synthetic diagnostic only; conservative correction does not validate p-values")
    save(root, "null-marginal-family", fig, arrays)
    selected = [r for r in summaries if r["case"].startswith("single-")]
    fig, axes = plt.subplots(1, 2, figsize=(13, 8), layout="constrained")
    names = [r["case"] + "/" + r["model"] for r in selected]
    y = np.arange(len(selected))
    coverage = np.array([r["coverage"] for r in selected])
    bounds = np.array([r["coverage_Wilson95"] for r in selected])
    axes[0].errorbar(
        coverage, y, xerr=[coverage - bounds[:, 0], bounds[:, 1] - coverage], fmt=".", capsize=2
    )
    axes[0].axvline(0.95, color="black")
    axes[0].set_yticks(y, names, fontsize=6)
    axes[0].set_title("95% interval coverage with Wilson uncertainty")
    ratio = np.array([r["mean_SE"] / r["empirical_SD"] for r in selected])
    axes[1].scatter(ratio, y)
    axes[1].axvline(1, color="black")
    axes[1].set_title("Mean estimated SE / empirical SD")
    save(
        root,
        "null-coverage-SE",
        fig,
        {
            "names": np.array(names, dtype=str),
            "coverage": coverage,
            "coverage_bounds": bounds,
            "SE_ratio": ratio,
        },
    )
    spatial = [r for r in summaries if r["case"].startswith("spatial-")]
    fig, axes = plt.subplots(1, 2, figsize=(14, 8), layout="constrained")
    names = [r["case"] + "/" + r["model"] for r in spatial]
    rates = np.array([r["bh"]["any_rejection"] for r in spatial])
    fdp = np.array([r["bh"]["empirical_FDR"] for r in spatial])
    axes[0].barh(np.arange(len(names)), rates)
    axes[0].axvline(0.05, color="black")
    axes[0].set_yticks(np.arange(len(names)), names, fontsize=6)
    axes[0].set_title("BH any rejection (power mixed with error under alternatives)")
    axes[1].barh(np.arange(len(names)), fdp)
    axes[1].axvline(0.05, color="black")
    axes[1].set_title("Mean FDP; equals any-rejection only under global null")
    save(
        root,
        "null-spatial-FDR",
        fig,
        {"names": np.array(names, dtype=str), "BH_any": rates, "empirical_FDR": fdp},
    )
