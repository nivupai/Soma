"""Headless reliability figures with explicit definitions and numeric companions."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from soma.visualization.anatomy import save_figure


def coreg_plots(
    output: Path,
    comparisons: dict[str, Any],
    registration: dict[str, Any],
    geometry: dict[str, Any],
) -> None:
    fig = plt.figure(figsize=(14, 4))
    for position, name in enumerate(["distributed", "MNE_fiducials", "MNE_ICP_headshape_only"]):
        ax = fig.add_subplot(1, 3, position + 1, projection="3d")
        ax.scatter(
            *(geometry["scalp_MRI_m"].T * 1000), s=2, alpha=0.15, label="Derived FLASH scalp"
        )
        ax.scatter(
            *(geometry[name + "_headshape_MRI_m"].T * 1000), s=6, c="red", label="Measured EXTRA"
        )
        ax.scatter(
            *(geometry["proxy_fiducials_MRI_m"].T * 1000),
            s=40,
            marker="*",
            c="black",
            label="Derived fiducials",
        )
        ax.set(xlabel="MRI x (mm)", ylabel="MRI y (mm)", zlabel="MRI z (mm)", title=name)
        if position == 0:
            ax.legend(fontsize=7)
    fig.suptitle(
        "sample: 78 measured headshape points / derived scalp and "
        "fiducials; no anatomical ground truth"
    )
    fig.tight_layout()
    save_figure(fig, output, "spatial-headshape-alignment", **geometry)
    names = list(comparisons)
    fid = np.array([comparisons[n]["proxy_fiducial_discrepancy_mm"] for n in names])
    hsp = np.array([comparisons[n]["common_ico3_headshape_triangle_distances_mm"] for n in names])
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for i, label in enumerate(["LPA", "nasion", "RPA"]):
        axes[0].plot(np.arange(len(names)), fid[:, i], "o-", label=label)
    axes[0].set_xticks(np.arange(len(names)), names, rotation=20, ha="right")
    axes[0].legend()
    axes[0].set(
        ylabel="Proxy fiducial discrepancy (mm)",
        title="3 measured HEAD / derived MRI pairs; no anatomical truth",
    )
    axes[1].boxplot(hsp.T, tick_labels=names, showfliers=False)
    axes[1].tick_params(axis="x", labelrotation=20)
    axes[1].set(
        ylabel="EXTRA→common ico3 triangle distance (mm)",
        title="78 headshape points; reference is not truth",
    )
    fig.suptitle("sample: alignment audit; MNE/Soma fits use different scalp objectives")
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "fiducial-headshape-audit",
        names=np.array(names),
        proxy_residual_mm=fid,
        headshape_distance_mm=hsp,
    )
    frame = pd.DataFrame(registration["records"])
    cases = frame["case"].unique()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, field, label in zip(
        axes,
        ["fit_RMS_mm", "heldout_TRE_RMS_mm"],
        ["Training residual RMS (mm)", "Independent held-out TRE RMS (mm)"],
        strict=True,
    ):
        ax.boxplot(
            [frame[frame["case"] == c][field] for c in cases], tick_labels=cases, showfliers=False
        )
        ax.tick_params(axis="x", labelrotation=35)
        ax.set_ylabel(label)
    fig.suptitle(
        f"Asymmetric phantom: known transform, "
        f"{registration['repetitions_per_scenario']} trials/scenario; empirical distributions"
    )
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "registration-residual-distributions",
        case=frame["case"].to_numpy(dtype=str),
        fit_mm=frame.fit_RMS_mm.to_numpy(),
        heldout_TRE_mm=frame.heldout_TRE_RMS_mm.to_numpy(),
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    part = frame[frame["case"].isin(["independent", "correlated", "anisotropic"])]
    truth = np.array(registration["truth_head_to_MRI_m"])
    values = [
        part.estimated_translation_x_mm.to_numpy(),
        part.estimated_rotation_angle_deg.to_numpy(),
    ]
    targets = [truth[0, 3] * 1000, Rotation.from_matrix(truth[:3, :3]).magnitude() * 180 / np.pi]
    for ax, values0, target, label in zip(
        axes,
        values,
        targets,
        ["Estimated translation x (mm)", "Estimated rotation angle (degrees)"],
        strict=True,
    ):
        ax.hist(values0, bins=25, alpha=0.7, label="Estimated")
        ax.axvline(target, c="black", label="Known truth")
        ax.set(xlabel=label, ylabel="Trials")
        ax.legend()
    fig.suptitle(
        "Asymmetric phantom: SVD, three Gaussian models; 300 trials at default N=100/model"
    )
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "estimated-known-transform",
        estimated_x_mm=values[0],
        estimated_rotation_deg=values[1],
        truth_x_mm=targets[0],
        truth_rotation_deg=targets[1],
    )


def inverse_plots(
    output: Path,
    frame: pd.DataFrame,
    selected: dict[str, Any],
    historical: dict[str, Any],
    forward: Any,
    indices: list[int],
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    part = frame[
        (frame.method == "MNE") & (frame.depth_weight == 0.8) & (frame["index"] == indices[0])
    ]
    for loose, values in part.groupby("loose"):
        ax.semilogx(
            values.lambda2,
            values.amplitude_norm_ratio_at_true_source,
            "o-",
            label=f"loose={loose:g}",
        )
    ax.set_ylim(0, float(part.amplitude_norm_ratio_at_true_source.max()) * 1.25)
    ax.text(0.02, 0.95, "Ideal ratio 1 is outside this zoom", transform=ax.transAxes, va="top")
    ax.set(
        xlabel="lambda² (dimensionless)",
        ylabel="True-source current norm / generating current",
        title="sample geometry, known 10-nA m normal source; MNE, noiseless, N=1/source",
    )
    ax.legend()
    save_figure(
        fig,
        output,
        "amplitude-transfer-regularization",
        lambda2=part.lambda2.to_numpy(),
        loose=part.loose.to_numpy(),
        current_ratio=part.amplitude_norm_ratio_at_true_source.to_numpy(),
    )
    fig, ax = plt.subplots(figsize=(8, 4))
    singular = np.linalg.svd(forward.matrix, compute_uv=False)
    ax.semilogy(np.arange(1, len(singular) + 1), singular, "o-")
    ax.set(
        xlabel="Singular index",
        ylabel="V / (A m)",
        title="sample: 59 EEG × 1239 fixed-normal sources; rank 58, no real source truth",
    )
    save_figure(fig, output, "leadfield-spectrum", singular_values=singular)
    prefix = next(key[:-3] for key in selected if ":loose0.0:" in key and key.endswith("PSF"))
    psf = selected[prefix + "PSF"]
    ctf = selected[prefix + "CTF"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for col, index in enumerate(indices):
        axes[0].plot(psf[:, col], label=str(index))
        axes[1].plot(ctf[col], label=str(index))
    for ax, label in zip(
        axes, ["PSF: one generating source", "CTF: one reconstructed source"], strict=True
    ):
        ax.set(
            xlabel="Ordered cortical source index",
            ylabel="Signed current transfer (dimensionless)",
            title=label,
        )
        ax.legend(title="Source index")
    fig.suptitle(
        "sample geometry: MNE, fixed, depth .8, lambda² 1/9; three selected kernels, no full K"
    )
    fig.tight_layout()
    save_figure(fig, output, "pointspread-crosstalk", PSF=psf, CTF=ctf, indices=np.array(indices))
    methods = list(frame.method.unique())
    fig, axes = plt.subplots(1, len(methods), figsize=(4.5 * len(methods), 4))
    for ax, method in zip(np.atleast_1d(axes), methods, strict=True):
        part = frame[(frame.method == method) & (frame.depth_weight == 0.8) & (frame.loose == 0)]
        if len(part):
            for source_key, values in part.groupby("index"):
                ax.semilogx(
                    values.lambda2, values.peak_euclidean_m * 1000, "o-", label=str(source_key)
                )
            ax.legend(title="Source index")
        ax.set(xlabel="lambda²", ylabel="Peak error (mm)", title=method)
    fig.suptitle(
        "sample geometry: noise-free simulated normals, N=3 selected "
        "sources; no universal method ranking"
    )
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "method-localization",
        method=frame.method.to_numpy(dtype=str),
        lambda2=frame.lambda2.to_numpy(),
        peak_m=frame.peak_euclidean_m.to_numpy(),
        loose=frame.loose.to_numpy(),
        depth_weight=frame.depth_weight.to_numpy(),
        source_index=frame["index"].to_numpy(),
    )


def evidence_plots(output: Path, evidence: dict[str, Any]) -> None:
    records = evidence["records"]
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.axis("off")
    table = ax.table(
        cellText=[[r["property"], r["category"], r["status"]] for r in records],
        colLabels=["Property (sample MRI/FLASH)", "Evidence category", "Explicit check"],
        loc="center",
        cellLoc="left",
        colWidths=[0.31, 0.43, 0.26],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    ax.set_title(
        "sample anatomical evidence: INDETERMINATE; no independent "
        "tissue/landmark truth\nCategorical records, no aggregate "
        "score or clinical certification"
    )
    save_figure(
        fig,
        output,
        "anatomical-evidence-report",
        property=np.array([r["property"] for r in records]),
        category=np.array([r["category"] for r in records]),
        status=np.array([r["status"] for r in records]),
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    arrays = {}
    for name, values in evidence["derivative_checks"].items():
        distance = np.array(values["surface_to_boundary_voxel_center_distance_m"]) * 1000
        axes[0].hist(distance, bins=30, alpha=0.5, label=name)
        arrays[name + "_boundary_distance_mm"] = distance
    for i, gap in enumerate(evidence["inner_vertex_to_outer_triangle_separations_m"]):
        axes[1].hist(
            np.array(gap) * 1000, bins=30, alpha=0.5, label=["brain/skull", "skull/scalp"][i]
        )
        arrays["gap_" + str(i) + "_mm"] = np.array(gap) * 1000
    axes[0].set(
        xlabel="Surface→derivative boundary voxel-center distance (mm)",
        ylabel="Vertices (N=642/boundary)",
    )
    axes[0].legend()
    axes[1].set(
        xlabel="Inner vertex→outer triangle separation (mm)", ylabel="Vertices (N=642/boundary)"
    )
    axes[1].legend()
    fig.suptitle(
        "sample: geometric and same-pipeline derivative evidence; no independent anatomical truth"
    )
    fig.tight_layout()
    save_figure(fig, output, "surface-volume-consistency", **arrays)


def attribution_plots(
    output: Path, rows: list[dict[str, Any]], interactions: dict[str, Any], arrays: dict[str, Any]
) -> None:
    part = [r for r in rows if r["case"].startswith("noise_SNR_")]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.errorbar(
        [r["snr_db"] for r in part],
        [r["peak_error_mm"]["mean"] for r in part],
        yerr=[
            [r["peak_error_mm"]["mean"] - r["peak_error_mm"]["low95"] for r in part],
            [r["peak_error_mm"]["high95"] - r["peak_error_mm"]["mean"] for r in part],
        ],
        fmt="o-",
    )
    ax.set(
        xlabel="Expected sensor SNR (dB)",
        ylabel="Peak source error (mm)",
        title=(
            "sample geometry, simulated 10-nA m normal; MNE λ²=1/9\n40 "
            "paired Gaussian draws/setting; approximate 95% t interval of"
            " mean"
        ),
    )
    save_figure(
        fig,
        output,
        "localization-SNR",
        snr_db=np.array([r["snr_db"] for r in part]),
        mean_mm=np.array([r["peak_error_mm"]["mean"] for r in part]),
        interval_mm=np.array(
            [[r["peak_error_mm"]["low95"], r["peak_error_mm"]["high95"]] for r in part]
        ),
    )
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    part = [r for r in rows if not r["case"].startswith(("factorial", "noise_"))]
    for ax, field, label in zip(
        axes,
        ["total", "change"],
        ["Relative source-current error", "Paired change from correct model"],
        strict=True,
    ):
        vals = [r if field == "total" else r["baseline_change"] for r in part]
        ax.errorbar(
            np.arange(len(part)),
            [v["mean"] for v in vals],
            yerr=[[v["mean"] - v["low95"] for v in vals], [v["high95"] - v["mean"] for v in vals]],
            fmt="o",
        )
        ax.set_xticks(np.arange(len(part)), [r["case"] for r in part], rotation=25, ha="right")
        ax.set_ylabel(label)
        ax.axhline(0, c="gray", ls="--")
    fig.suptitle(
        "sample simulated current: MNE fixed; 40 common-noise draws, "
        "95% t intervals; no additive attribution"
    )
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "error-attribution",
        cases=np.array([r["case"] for r in part]),
        relative_error=np.array([r["mean"] for r in part]),
        paired_change=np.array([r["baseline_change"]["mean"] for r in part]),
        interval_relative=np.array([[r["low95"], r["high95"]] for r in part]),
        change_interval=np.array(
            [[r["baseline_change"]["low95"], r["baseline_change"]["high95"]] for r in part]
        ),
    )
    fig, ax = plt.subplots(figsize=(9, 4))
    names = list(interactions)
    vals = list(interactions.values())
    if names:
        ax.errorbar(
            np.arange(len(names)),
            [v["mean"] for v in vals],
            yerr=[[v["mean"] - v["low95"] for v in vals], [v["high95"] - v["mean"] for v in vals]],
            fmt="o",
        )
        ax.set_xticks(np.arange(len(names)), names)
    ax.axhline(0, c="gray", ls="--")
    ax.set(
        xlabel="Interacting factor indices (0 registration, 1 skull, 2 λ²)",
        ylabel="Difference of differences in relative error",
        title=(
            "sample simulated current: 2³ factorial, 40 paired noise "
            "draws\n95% t simulation intervals; not biological variance "
            "components"
        ),
    )
    save_figure(
        fig,
        output,
        "factor-interactions",
        factors=np.array(names),
        interaction_mean=np.array([v["mean"] for v in vals]),
        interval=np.array([[v["low95"], v["high95"]] for v in vals]),
    )
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    xyz = arrays["source_MRI_m"] * 1000
    index = int(np.argmax(np.abs(arrays["truth_Am"])))
    names = ["correct", "registration", "conductivity"]
    estimates = [
        np.mean(np.abs(arrays[name + ":estimated_current_Am"]), axis=1) * 1e9 for name in names
    ]
    upper = float(np.max(estimates))
    for ax, name, value in zip(axes, names, estimates, strict=True):
        artist = ax.scatter(xyz[:, 0], xyz[:, 1], c=value, s=5, vmin=0, vmax=upper)
        ax.scatter(*xyz[index, :2], marker="x", c="red", label="Known truth")
        ax.set(xlabel="MRI x (mm)", ylabel="MRI y (mm)", title=name)
        fig.colorbar(artist, ax=ax, label="Mean |current| (nA m)")
    fig.suptitle(
        "sample geometry / simulated normal: MNE, 40 draws; depth-"
        "overlapping projection, no real source truth"
    )
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "correct-mismatched-reconstruction",
        source_MRI_m=xyz / 1000,
        estimated_mean_absolute_nAm=np.stack(estimates),
        truth_index=index,
    )
