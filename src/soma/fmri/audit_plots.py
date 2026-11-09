"""Private calibration and synthetic preprocessing diagnostics with source arrays."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soma.validation.plots import save


def calibration_figures(output: Path, summary: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), layout="constrained")
    names = []
    cover = []
    low = []
    high = []
    ratios = []
    rates = []
    for row in summary:
        names.append(row["scenario"] + " / " + row["model"])
        value = row["CI95_covers"]
        cover.append(value["estimate"])
        low.append(value["estimate"] - value["Wilson95"][0])
        high.append(value["Wilson95"][1] - value["estimate"])
        ratios.append(row["SE_to_empirical_SD"])
        rates.append(row["voxel_p05"]["estimate"])
    x = np.arange(len(names))
    axes[0].errorbar(cover, x, xerr=[low, high], fmt=".", capsize=2)
    axes[0].axvline(0.95, color="black")
    axes[0].set_yticks(x, names, fontsize=6)
    axes[0].set_title("95% CI coverage: seeded realizations")
    axes[1].scatter(ratios, x)
    axes[1].axvline(1, color="black")
    axes[1].set_title("Mean SE / empirical beta SD")
    axes[2].scatter(rates, x)
    axes[2].axvline(0.05, color="black")
    axes[2].set_title("Prespecified voxel p<.05: null or power")
    fig.suptitle("Synthetic calibration; Wilson Monte Carlo uncertainty, not human certification")
    save(
        output,
        "calibration-curves",
        fig,
        {
            "names": np.array(names),
            "coverage": cover,
            "coverage_lower_error": low,
            "coverage_upper_error": high,
            "SE_ratio": ratios,
            "voxel_p05": rates,
        },
    )


def preprocessing_figures(output: Path, run: Any, fitted: Any, t1: Any, qc: dict[str, Any]) -> None:
    mean = np.mean(run.image.get_fdata(), axis=3)
    anatomy = t1.array()
    mid = mean.shape[2] // 2
    motion = run.confounds[["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]].to_numpy()
    varying = np.std(motion, axis=0) > 1e-12
    corr = np.corrcoef(motion[:, varying].T)
    time = np.arange(run.n_scans) * run.tr
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), layout="constrained")
    axes[0, 0].plot(time, motion[:, :3])
    axes[0, 0].set(title="Synthetic measured translations", xlabel="seconds", ylabel="mm")
    axes[0, 1].plot(time, motion[:, 3:])
    axes[0, 1].set(title="Synthetic rotations", xlabel="seconds", ylabel="radians")
    fd = run.confounds.framewise_displacement.to_numpy()
    axes[0, 2].plot(time, fd)
    axes[0, 2].axhline(0.5, color="red")
    axes[0, 2].set(
        title="Provided FD; missing first remains visible", xlabel="seconds", ylabel="mm"
    )
    axes[1, 0].imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
    axes[1, 0].set_title("Varying motion-column correlations")
    axes[1, 1].imshow(mean[:, :, mid].T, origin="lower", cmap="gray")
    axes[1, 1].contour(anatomy[:, :, mid].T, levels=4, colors=["cyan"], linewidths=0.4)
    axes[1, 1].set_title("Identity fixture BOLD/T1: not human anatomy")
    axes[1, 2].imshow(fitted.design.to_numpy(), aspect="auto")
    axes[1, 2].set_title("Synthetic design; original acquisition rows")
    fig.suptitle(
        f"sub-{run.subject} / ses-{run.session}: synthetic fMRIPrep-shaped import, {qc['strategy']}"
    )
    save(
        output,
        "preprocessing-motion-design",
        fig,
        {
            "motion": motion,
            "motion_correlation": corr,
            "FD_finite_values": np.nan_to_num(fd),
            "FD_missing_mask": np.isnan(fd),
            "time_s": time,
            "mean_BOLD": mean,
            "T1": anatomy,
            "affine_RAS_m": run.mask.affine_m,
            "design": fitted.design.to_numpy(),
        },
    )
    native: list[list[float]] = []
    group_sizes = []
    white: list[list[float]] = []
    for result in fitted.model.results_[0].values():
        group_sizes.append(result.Y.shape[1])
        r = result.Y - fitted.design.to_numpy() @ result.theta
        w = result.whitened_residuals
        for residual, store in [(r, native), (w, white)]:
            store.append(
                [
                    float(
                        np.mean(
                            np.sum(residual[:-lag] * residual[lag:], axis=0)
                            / np.maximum(np.sum(residual**2, axis=0), 1e-20)
                        )
                    )
                    for lag in range(1, 9)
                ]
            )
    native_acf = np.average(native, axis=0, weights=group_sizes)
    white_acf = np.average(white, axis=0, weights=group_sizes)
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    ax.plot(range(1, 9), native_acf, label="native Y-X beta")
    ax.plot(range(1, 9), white_acf, label="whitened")
    ax.legend()
    ax.set(
        xlabel="acquisition lag",
        ylabel="residual ACF",
        title="Synthetic temporal diagnostic; no iid guarantee",
    )
    save(
        output,
        "residual-ACF",
        fig,
        {
            "lags": np.arange(1, 9),
            "native_ACF_voxel_average": native_acf,
            "whitened_ACF_voxel_average": white_acf,
        },
    )
