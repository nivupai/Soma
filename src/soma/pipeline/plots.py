"""Optional local QC figures with arrays; custom outputs are not BIDS suffixes."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soma.validation.plots import save


def pipeline_figures(output: Path, a: dict[str, Any], stages: list[dict[str, Any]]) -> None:
    native = a["native"]
    image = a["processed"]
    axis = 2
    before = np.take(native.array(), native.shape[axis] // 2, axis=axis)
    after = np.take(image.array(), image.shape[axis] // 2, axis=axis)
    labels = np.take(a["labels"].array(), image.shape[axis] // 2, axis=axis)
    mask = (
        np.ones_like(after)
        if a["mask"] is None
        else np.take(a["mask"].array(), image.shape[axis] // 2, axis=axis)
    )
    fig, axes = plt.subplots(1, 4, figsize=(13, 4), layout="constrained")
    limits = (
        min(float(before.min()), float(after.min())),
        max(float(before.max()), float(after.max())),
    )
    axes[0].imshow(before.T, origin="lower", cmap="gray", vmin=limits[0], vmax=limits[1])
    axes[1].imshow(after.T, origin="lower", cmap="gray", vmin=limits[0], vmax=limits[1])
    axes[2].imshow(after.T, origin="lower", cmap="gray", vmin=limits[0], vmax=limits[1])
    if a["mask"] is not None:
        axes[2].contour(mask.T, levels=[0.5], colors=["cyan"], linewidths=0.7)
    axes[3].imshow(after.T, origin="lower", cmap="gray", vmin=limits[0], vmax=limits[1])
    axes[3].imshow(
        np.ma.masked_equal(labels.T, 0), origin="lower", cmap="tab10", vmin=0, vmax=9, alpha=0.55
    )
    for ax, title in zip(
        axes,
        [
            "Native T1",
            "After preprocessing",
            "Mask overlay" if a["mask"] is not None else "Mask disabled",
            "Tissue overlay",
        ],
        strict=True,
    ):
        ax.set(title=title, xlabel="Panel native/output voxel grid")
    fig.suptitle("Research QC; automatic tissue labels, no anatomical certification")
    save(
        output,
        "preprocess-mask-segmentation",
        fig,
        {
            "before": before,
            "after": after,
            "mask": mask,
            "labels": labels,
            "native_affine_RAS_m": native.affine_m,
            "output_affine_RAS_m": image.affine_m,
        },
    )
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    for volume, title in [(native, "before"), (image, "after")]:
        x = volume.array()
        x = x[x > 0]
        axes[0].hist(x.ravel()[:: max(1, len(x) // 100000)], bins=64, alpha=0.5, label=title)
    axes[0].legend()
    axes[0].set(title="Native intensity scale", xlabel="MRI arbitrary units")
    names = [s["name"] for s in stages]
    times = [s["cache"]["wall_s"] for s in stages]
    hits = [s["cache"]["hit"] for s in stages]
    axes[1].barh(names, times)
    axes[1].set(xlabel="Stage cache/build wall seconds")
    axes[2].bar(names, hits)
    axes[2].tick_params(axis="x", rotation=90)
    axes[2].set(ylabel="Cache hit", title="Numerical PASS; anatomical INDETERMINATE")
    save(
        output,
        "intensity-time-cache",
        fig,
        {
            "histogram_counts": np.array(a["intensity_qc"]["histogram"]),
            "histogram_edges": np.array(a["intensity_qc"]["histogram_edges"]),
            "wall_s": times,
            "cache_hit": hits,
        },
    )
    fig, ax = plt.subplots(figsize=(13, 2.5), layout="constrained")
    x = np.arange(len(names))
    ax.scatter(x, np.zeros(len(x)))
    for i, name in enumerate(names):
        ax.text(i, 0.06, name, rotation=45, ha="left", va="bottom")
        if i:
            ax.annotate("", xy=(i, 0), xytext=(i - 1, 0), arrowprops={"arrowstyle": "->"})
    ax.set(
        xlim=(-0.5, len(x) + 0.8),
        ylim=(-0.2, 1),
        title="Declared stage DAG; dependencies checked before execution",
    )
    ax.axis("off")
    save(output, "pipeline-graph", fig, {"stage_order": np.array(names), "units": "RAS metres"})

    spatial_qc_figures(output, a)


def benchmark_figures(output: Path, results: dict[str, Any], timing: dict[str, Any]) -> None:
    names = list(results)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    dice = [results[n]["macro_Dice"]["mean"] for n in names]
    first = [timing[n]["initial_wall_s"] for n in names]
    resume = [timing[n]["verified_resume_wall_s"] for n in names]
    axes[0].bar(names, dice)
    axes[0].set(ylabel="Subject mean macro Dice", ylim=(0, 1))
    x = np.arange(len(names))
    axes[1].bar(x - 0.15, first, 0.3, label="first")
    axes[1].bar(x + 0.15, resume, 0.3, label="verified resume")
    axes[1].set_xticks(x, names)
    axes[1].set_ylabel("Wall seconds")
    axes[1].legend()
    axes[2].bar(names, [results[n]["completed"] for n in names])
    axes[2].set_ylabel("Completed subjects")
    fig.suptitle("Known human tissue references; unchanged baseline; no conductor certification")
    save(
        output,
        "cohort-cache-performance",
        fig,
        {"macro_Dice": dice, "initial_wall_s": first, "resume_wall_s": resume},
    )


def spatial_qc_figures(output: Path, a: dict[str, Any]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    axes[0].imshow(a["native"].affine_m, aspect="auto")
    axes[0].set(
        title="Native voxel to RAS metres",
        xlabel="homogeneous voxel coordinate",
        ylabel="world matrix row",
    )
    for (i, j), value in np.ndenumerate(a["native"].affine_m):
        axes[0].text(j, i, f"{value:.4g}", ha="center", va="center", color="white", fontsize=8)
    axes[1].imshow(a["processed"].affine_m, aspect="auto")
    axes[1].set(title="Processed voxel to RAS metres", xlabel="homogeneous voxel coordinate")
    save(
        output,
        "orientation-affines",
        fig,
        {"native_affine_m": a["native"].affine_m, "output_affine_m": a["processed"].affine_m},
    )
    rows = a["mesh_qc"]["surfaces"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    volumes = a["label_qc"]["volumes_mm3"]
    codes = sorted(volumes, key=int)
    axes[0].bar(codes, [volumes[c] for c in codes])
    axes[0].set(
        xlabel="Canonical tissue label",
        ylabel="Volume (mm³)",
        title="Numerical label QC; no anatomical certification",
    )
    data = {}
    if rows:
        data = {
            "euler": np.array([r["euler_used_vertices"] for r in rows]),
            "boundary_edges": np.array([r["boundary_edges"] for r in rows]),
            "intersection_assessed": np.array([r["intersection_assessed"] for r in rows]),
        }
        axes[1].bar(np.arange(len(rows)), data["boundary_edges"])
        axes[1].set(title="Requested surface topology", ylabel="Boundary edges")
    else:
        axes[1].text(
            0.5,
            0.5,
            "Surfaces not requested\nMesh anatomy: INDETERMINATE",
            ha="center",
            va="center",
        )
        axes[1].set_axis_off()
    save(
        output,
        "label-surface-qc",
        fig,
        {
            "label_codes": np.array(codes),
            "volumes_mm3": np.array([volumes[c] for c in codes]),
            **data,
        },
    )
