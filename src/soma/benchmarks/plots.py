"""Scientific benchmark figures and their exact numeric inputs."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.visualization.anatomy import save_figure


def segmentation_plots(
    output: Path, results: dict[str, Any], images: dict[str, Any], controlled: list[dict[str, Any]]
) -> None:
    for name, data in images.items():
        fig, axes = plt.subplots(1, 3, figsize=(12, 4))
        label_ids = np.unique(np.r_[data["reference"].ravel(), data["prediction"].ravel()])
        display = {
            key: np.searchsorted(label_ids, data[key]) for key in ("reference", "prediction")
        }
        palette = plt.get_cmap("turbo", len(label_ids))
        for ax, key in zip(axes, ["T1", "reference", "prediction"], strict=True):
            ax.imshow(data["T1"].T, cmap="gray", origin="lower")
            if key != "T1":
                ax.imshow(
                    np.ma.masked_where(data[key].T == 0, display[key].T),
                    origin="lower",
                    alpha=0.6,
                    cmap=palette,
                    vmin=0,
                    vmax=max(1, len(label_ids) - 1),
                    interpolation="nearest",
                )
            ax.set(title=key, xlabel="Voxel index (aligned grid)", ylabel="Voxel index")
        kind = "simulated tissue" if name == "BrainWeb" else "manual cortical"
        fig.suptitle(
            f"{results[name]['subject']}: {kind} reference vs independent prediction; "
            "no registration"
        )
        fig.text(
            0.5, 0.015, "Shared categorical colors; original label IDs retained in NPZ", ha="center"
        )
        fig.tight_layout(rect=(0, 0.04, 1, 0.96))
        save_figure(
            fig,
            output,
            name + "-overlay",
            **data,
            label_ids=label_ids,
            reference_display_indices=display["reference"],
            prediction_display_indices=display["prediction"],
        )
        rows = results[name]["labels"]
        labels = np.array([r["label"] for r in rows])
        dice = np.array([np.nan if r["Dice"] is None else r["Dice"] for r in rows])
        assd = np.array([np.nan if r["ASSD_mm"] is None else r["ASSD_mm"] for r in rows])
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        axes[0].bar(np.arange(len(rows)), dice)
        axes[0].set(xlabel="Declared label index", ylabel="Dice", ylim=(0, 1))
        axes[1].bar(np.arange(len(rows)), assd)
        axes[1].set(
            xlabel="Declared label index", ylabel="Area-weighted symmetric surfel distance (mm)"
        )
        fig.suptitle(
            f"{results[name]['subject']}: {kind} reference; "
            f"N={len(rows)} labels, not independent subjects"
        )
        fig.tight_layout()
        save_figure(fig, output, name + "-label-metrics", label_ids=labels, Dice=dice, ASSD_mm=assd)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    names = [r["case"] for r in controlled]
    values = np.array([r["metrics"]["Dice"] for r in controlled])
    volume = np.array([r["metrics"]["signed_relative_volume_error"] for r in controlled])
    axes[0].bar(np.arange(len(names)), values)
    axes[0].set(ylabel="Dice against analytic center-sampled sphere", ylim=(0, 1))
    axes[1].bar(np.arange(len(names)), volume * 100)
    axes[1].set_ylabel("Signed volume change (%)")
    for ax in axes:
        ax.set_xticks(np.arange(len(names)), names, rotation=35, ha="right")
    fig.suptitle("Analytic sphere: controlled mask defects/resampling, not segmentation validation")
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "mask-boundary-perturbations",
        cases=np.array(names),
        Dice=values,
        signed_relative_volume_error=volume,
    )


def surface_plots(output: Path, rows: list[dict[str, Any]], examples: dict[str, Any]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for name in ["sphere", "ellipsoid", "asymmetric"]:
        for method in ["binary", "scalar"]:
            part = [r for r in rows if r["shape"] == name and r["method"] == method]
            for ax, key in zip(
                axes,
                ["area_relative_error", "algebraic_volume_relative_error", "radial_vertex_RMS_mm"],
                strict=True,
            ):
                ax.plot(
                    [r["spacing_mm"] for r in part],
                    [abs(r[key]) for r in part],
                    "o-",
                    label=name + " " + method,
                )
    for ax, label in zip(
        axes,
        [
            "Absolute relative area error",
            "Absolute relative algebraic volume error",
            "Radial vertex RMS (mm)",
        ],
        strict=True,
    ):
        ax.set(xlabel="Voxel spacing (mm)", ylabel=label)
    axes[0].legend(fontsize=6)
    fig.suptitle(
        "Analytic geometry / independent formulas or quadrature; scalar "
        "vs binary sampling, no monotonicity guarantee"
    )
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "surface-convergence",
        shape=np.array([r["shape"] for r in rows]),
        method=np.array([r["method"] for r in rows]),
        spacing_mm=np.array([r["spacing_mm"] for r in rows]),
        relative_area_error=np.array([r["area_relative_error"] for r in rows]),
        relative_volume_error=np.array([r["algebraic_volume_relative_error"] for r in rows]),
        radial_RMS_mm=np.array([r["radial_vertex_RMS_mm"] for r in rows]),
    )
    fig = plt.figure(figsize=(7, 5))
    ax = fig.add_subplot(projection="3d")
    xyz = examples["xyz_m"] * 1000
    artist = ax.scatter(*xyz.T, c=examples["radial_error_mm"], s=2, cmap="coolwarm")
    fig.colorbar(artist, ax=ax, label="Radial boundary error (mm)")
    ax.set(
        xlabel="RAS x (mm)",
        ylabel="RAS y (mm)",
        zlabel="RAS z (mm)",
        title="Analytic sphere / scalar isosurface, finest voxel sampling",
    )
    save_figure(fig, output, "boundary-displacement-map", **examples)
    fig, ax = plt.subplots(figsize=(7, 4))
    cost = np.array([r["extraction_wall_s"] + r["validation_wall_s"] for r in rows])
    error = np.array([r["radial_vertex_RMS_mm"] for r in rows])
    assessed = np.array([r["topology"]["intersection_assessed"] for r in rows])
    for state, label in [
        (True, "Full allowed intersection checks"),
        (False, "Full intersections unassessed (face cap)"),
    ]:
        ax.scatter(cost[assessed == state], error[assessed == state], label=label)
    ax.legend(fontsize=7)
    ax.set(
        xlabel="Extraction + scoped validation wall time (s)",
        ylabel="Radial RMS error (mm)",
        title=(
            "Analytic surfaces: geometric accuracy vs mesh size; "
            "cache/environment specified in manifest"
        ),
    )
    save_figure(
        fig,
        output,
        "accuracy-cost",
        wall_s=cost,
        radial_error_mm=error,
        intersection_assessed=assessed,
    )


def repair_plots(output: Path, results: dict[str, Any], examples: dict[str, Any]) -> None:
    fig = plt.figure(figsize=(12, 7))
    arrays = {}
    for row, (name, pair) in enumerate(examples.items()):
        for column, mesh in enumerate(pair):
            ax = fig.add_subplot(len(examples), 2, row * 2 + column + 1, projection="3d")
            xyz = mesh.vertices.xyz * 1000
            ax.plot_trisurf(
                *xyz.T, triangles=mesh.faces, color="lightsteelblue", linewidth=0.02, alpha=0.8
            )
            ax.set(
                xlabel="x (mm)",
                ylabel="y (mm)",
                zlabel="z (mm)",
                title=name
                + (
                    " before"
                    if column == 0
                    else " returned; accepted=" + str(results[name]["accepted"])
                ),
            )
            arrays[f"{name}_{column}_vertices_m"] = mesh.vertices.xyz
            arrays[f"{name}_{column}_faces"] = mesh.faces
    fig.suptitle(
        "Known analytic sphere tessellation: conservative repair; no anatomical certification"
    )
    fig.tight_layout()
    save_figure(fig, output, "mesh-repair-before-after", **arrays)


def source_plots(
    output: Path,
    rows: list[dict[str, Any]],
    grids: dict[float, Any],
    truth: Any,
    interactions: list[dict[str, Any]],
) -> None:
    frame = pd.DataFrame(
        [
            {
                "spacing_mm": r["spacing_m"] * 1000,
                "source": r["source"],
                "angle": r["angle_deg"],
                "conductor": r["conductor"],
                "representation": r["representation"],
                "lambda2": r["lambda2"],
                "variant": r["variant"],
                "noise": r["noise"],
                **{k: v["mean"] for k, v in r["metrics"].items()},
            }
            for r in rows
        ]
    )
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(projection="3d")
    coarse = grids[max(grids)].xyz * 1000
    ax.scatter(*coarse.T, s=10, alpha=0.3, label="Reconstruction vertices")
    ax.scatter(*(truth.T * 1000), marker="*", s=100, c="red", label="Continuous dipole truth")
    ax.set(
        xlabel="MRI x (mm)",
        ylabel="MRI y (mm)",
        zlabel="MRI z (mm)",
        title="Known synthetic sphere: continuous sources separate from cubic grid",
    )
    ax.legend()
    save_figure(
        fig,
        output,
        "offgrid-truth-vertices",
        reconstruction_MRI_m=coarse / 1000,
        continuous_truth_MRI_m=truth,
    )
    part = frame[
        (frame.angle == 0)
        & (frame.variant == "baseline")
        & (frame.noise == "noiseless")
        & np.isclose(frame.lambda2, 1 / 9)
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for (kind, representation, source), values in part.groupby(
        ["conductor", "representation", "source"]
    ):
        values = values.sort_values("spacing_mm")
        label = f"{kind}/{representation}/source{source}"
        axes[0].plot(values.spacing_mm, values.peak_error_mm, "o-", label=label)
        axes[1].plot(values.spacing_mm, values.nearest_vertex_amplitude_ratio, "o-", label=label)
    axes[0].set(xlabel="Grid spacing (mm)", ylabel="Peak error to continuous truth (mm)")
    axes[1].set(
        xlabel="Grid spacing (mm)", ylabel="Nearest-vertex current norm / true dipole moment"
    )
    axes[0].legend(fontsize=5)
    fig.suptitle(
        "Synthetic continuous dipoles: analytical truth, separate grid "
        "forwards; no monotone/bias-free guarantee"
    )
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "grid-localization-amplitude",
        spacing_mm=part.spacing_mm.to_numpy(),
        peak_error_mm=part.peak_error_mm.to_numpy(),
        nearest_ratio=part.nearest_vertex_amplitude_ratio.to_numpy(),
        nearest_grid_mm=part.nearest_grid_mm.to_numpy(),
        conductor=part.conductor.to_numpy(dtype=str),
        representation=part.representation.to_numpy(dtype=str),
        source=part.source.to_numpy(),
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    subset = frame[
        (frame.source == 0)
        & (frame.angle == 0)
        & (frame.conductor == "BEM")
        & (frame.representation == "fixed")
        & (frame.noise == "SNR10")
        & np.isclose(frame.lambda2, 1 / 9)
    ]
    subset = subset.drop_duplicates(["spacing_mm", "variant"])
    for variant, values in subset.groupby("variant"):
        axes[0].plot(values.spacing_mm, values.peak_error_mm, "o-", label=variant)
    axes[0].set(xlabel="Grid spacing (mm)", ylabel="Mean peak error (mm)")
    axes[0].legend(fontsize=7)
    if interactions:
        mean = np.array([r["paired_difference_of_differences"]["mean"] for r in interactions])
        limits = np.array(
            [
                [
                    r["paired_difference_of_differences"]["low95"],
                    r["paired_difference_of_differences"]["high95"],
                ]
                for r in interactions
            ]
        )
        axes[1].errorbar(
            [r["spacing_m"] * 1000 for r in interactions],
            mean,
            yerr=[mean - limits[:, 0], limits[:, 1] - mean],
            fmt="o-",
        )
    axes[1].set(xlabel="Grid spacing (mm)", ylabel="Boundary×registration interaction (mm)")
    if not interactions:
        axes[1].axis("off")
        axes[1].text(
            0.5, 0.5, "Boundary×registration not evaluated\nin the grid-only command", ha="center"
        )
    fig.suptitle(
        (
            "Known spherical geometry: 1-mm assigned perturbations, 20 paired"
            " noise draws; 95% t intervals"
        )
        if interactions
        else ("Known spherical geometry: baseline grid comparison, 20 paired noise draws")
    )
    fig.tight_layout()
    save_figure(
        fig,
        output,
        "anatomical-perturbation-sensitivity",
        spacing_mm=subset.spacing_mm.to_numpy(),
        variant=subset.variant.to_numpy(dtype=str),
        peak_mm=subset.peak_error_mm.to_numpy(),
        interaction_spacing_m=np.array([r["spacing_m"] for r in interactions]),
        interaction_interval_mm=np.array(
            [
                [
                    r["paired_difference_of_differences"]["low95"],
                    r["paired_difference_of_differences"]["high95"],
                ]
                for r in interactions
            ]
        ),
        interaction_mean=np.array(
            [r["paired_difference_of_differences"]["mean"] for r in interactions]
        ),
    )
