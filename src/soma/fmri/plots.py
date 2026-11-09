"""Local scientific plots with source arrays; no medical images enter Git."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soma.fmri.glm import Estimate, Fit
from soma.validation.plots import save


def figures(
    root: Path, fitted: Fit, estimate: Estimate, truth: dict[str, Any] | None = None
) -> None:
    run = fitted.run
    mean = np.mean(np.asanyarray(run.image.dataobj), axis=3)
    effect = np.asarray(estimate.maps["effect_size"].dataobj)
    z = np.asarray(estimate.maps["z_score"].dataobj)
    selected = np.asarray(estimate.maps["fdr_reject"].dataobj)
    mid = mean.shape[2] // 2
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout="constrained")
    axes[0, 0].imshow(mean[:, :, mid].T, origin="lower", cmap="gray")
    axes[0, 0].set_title("Mean BOLD, native voxel slice")
    axes[0, 1].imshow(fitted.design.to_numpy(), aspect="auto", cmap="coolwarm")
    axes[0, 1].set_title("Design matrix; scan index × regressor")
    axes[0, 2].imshow(fitted.diagnostics["correlation"], vmin=-1, vmax=1, cmap="coolwarm")
    axes[0, 2].set_title("Varying-regressor correlations")
    axes[1, 0].imshow(effect[:, :, mid].T, origin="lower", cmap="coolwarm")
    axes[1, 0].set_title("Signed effect (native BOLD units)")
    axes[1, 1].imshow(z[:, :, mid].T, origin="lower", cmap="coolwarm")
    axes[1, 1].set_title("Signed z; descriptive unthresholded")
    axes[1, 2].imshow(mean[:, :, mid].T, origin="lower", cmap="gray")
    axes[1, 2].imshow(
        np.ma.masked_equal(selected[:, :, mid].T, 0), origin="lower", cmap="autumn", alpha=0.7
    )
    axes[1, 2].set_title("Two-sided BH FDR mask, q=" + str(fitted.config.q))
    fig.suptitle(run.preprocessing + ": first-level statistical demonstration; no clinical claim")
    save(
        root,
        "bold-design-contrast",
        fig,
        {
            "mean_bold": mean,
            "design": fitted.design.to_numpy(),
            "design_names": np.array(list(fitted.design)),
            "affine_mm": run.image.affine,
            "effect": effect,
            "z": z,
            "fdr_reject": selected,
            "correlations": np.asarray(fitted.diagnostics["correlation"]),
        },
    )
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
    for row in run.events.itertuples():
        axes[0].broken_barh([(row.onset, row.duration)], (0, 1))
    axes[0].set(title="Supplied events", xlabel="seconds", yticks=[])
    temporal = np.mean(np.asarray(run.image.dataobj)[run.mask.array().astype(bool)], axis=0)
    axes[1].plot(np.arange(run.n_scans) * run.tr, temporal)
    axes[1].set(title="Analysis-mask mean BOLD", xlabel="seconds", ylabel="native units")
    axes[2].imshow(mean[:, :, mid].T, origin="lower", cmap="gray")
    mask = run.mask.array()[:, :, mid].T
    if np.min(mask) != np.max(mask):
        axes[2].contour(mask, levels=[0.5], colors=["cyan"])
    axes[2].set_title("Mask/mean image: same-grid QC, not registration")
    save(
        root,
        "events-time-mask",
        fig,
        {
            "onset_s": run.events.onset.to_numpy(),
            "duration_s": run.events.duration.to_numpy(),
            "mean_timeseries": temporal,
            "mask": run.mask.array(),
            "time_s": np.arange(run.n_scans) * run.tr,
        },
    )
    if truth is not None:
        fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
        axes[0].imshow(truth["beta"][:, :, mid].T, origin="lower", cmap="coolwarm")
        axes[0].set_title("Simulated beta truth")
        axes[1].imshow(effect[:, :, mid].T, origin="lower", cmap="coolwarm")
        axes[1].set_title("Recovered effect")
        axes[2].scatter(truth["beta"].ravel(), effect.ravel(), s=3, alpha=0.2)
        axes[2].set(xlabel="True beta", ylabel="Recovered effect")
        save(
            root,
            "synthetic-recovery",
            fig,
            {"truth_beta": truth["beta"], "effect": effect, "response": truth["response"]},
        )
