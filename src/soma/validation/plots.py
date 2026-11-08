"""Evidence-labelled scientific figures with pickle-free numerical companions."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def save(output: Path, name: str, fig: Any, arrays: dict[str, Any]) -> None:
    fig.savefig(output / (name + ".png"), dpi=150, bbox_inches="tight")
    np.savez_compressed(output / (name + ".npz"), **dict(arrays))
    plt.close(fig)


def cohort_plots(output: Path, summary: dict[str, Any], arrays: dict[str, Any]) -> None:
    rows = summary["subjects"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    data = {}
    if rows:
        dice = np.array(
            [
                [r["Dice"] if r["Dice"] is not None else np.nan for r in row["labels"]]
                for row in rows
            ]
        )
        distance = np.array(
            [
                [r["ASSD_mm"] if r["ASSD_mm"] is not None else np.nan for r in row["labels"]]
                for row in rows
            ]
        )
        for i, row in enumerate(rows):
            axes[0].plot([1, 2, 3], dice[i], marker="o", label=row["subject"])
            axes[1].plot([1, 2, 3], distance[i], marker="o", label=row["subject"])
        axes[0].set(ylabel="Dice", ylim=(0, 1))
        axes[1].set(ylabel="ASSD (mm)")
        axes[0].legend()
        data = {"dice": dice, "ASSD_mm": distance}
        for ax in axes:
            ax.set_xticks([1, 2, 3], ["CSF", "GM", "WM"])
    else:
        for ax, title in zip(
            axes, ["Tissue Dice: unavailable", "Subject variability: unavailable"], strict=True
        ):
            ax.text(
                0.5,
                0.5,
                "No authorized human tissue files\nNo scores or population inference",
                ha="center",
                va="center",
            )
            ax.set(title=title)
            ax.set_axis_off()
        data = {
            "requested_subject_count": np.array(len(summary["requested_subjects"])),
            "available_subject_count": np.array(0),
            "failed_subject_count": np.array(len(summary["failures"])),
        }
    fig.suptitle(
        "Human manual tissue references | "
        + summary["split"]
        + " split; subject is statistical unit"
    )
    save(output, "tissue-subject-variability", fig, data)
    for row in rows:
        sid = row["subject"]
        fig, axes = plt.subplots(1, 3, figsize=(10, 4), layout="constrained")
        for ax, key, title in zip(
            axes,
            ["image_slice", "reference_slice", "prediction_slice"],
            ["T1", "Manual tissue reference", "Independent baseline"],
            strict=True,
        ):
            x = arrays[sid + "__" + key]
            ax.imshow(
                x.T,
                origin="lower",
                cmap="gray" if key == "image_slice" else "tab10",
                vmin=None if key == "image_slice" else 0,
                vmax=None if key == "image_slice" else 9,
            )
            ax.set_title(title)
        fig.suptitle(sid + " | native aligned voxel index; no automatic registration")
        save(
            output,
            sid + "-overlay",
            fig,
            {k: v for k, v in arrays.items() if k.startswith(sid + "__")},
        )


def conductor_plots(output: Path, summary: dict[str, Any], arrays: dict[str, Any]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for ax, key, title in zip(
        axes,
        ["native_T1_slice", "native_segmentation_slice"],
        ["SCI T1 native index", "SCI external computational labels"],
        strict=True,
    ):
        if key in arrays:
            ax.imshow(arrays[key].T, origin="lower", cmap="gray" if "T1" in key else "tab10")
        ax.set(title=title, xlabel="native voxel index", ylabel="native voxel index")
    fig.suptitle(
        "SCI computational reference: separate native views; label anatomical frame unverified"
    )
    save(
        output, "SCI-reference-native-views", fig, {k: v for k, v in arrays.items() if "slice" in k}
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    rows = summary["external_label_connectivity"]
    codes = np.array([r["label_ID"] for r in rows])
    components = np.array([r["components_6connected"] for r in rows])
    axes[0].bar(codes, components)
    axes[0].set(xlabel="Unverified native label ID", ylabel="6-connected components", yscale="log")
    axes[1].text(
        0.5,
        0.5,
        (
            "External BEM: INDETERMINATE\nFEM ≠ three-layer "
            "BEM\nFrame, units, ontology and interfaces unresolved"
        ),
        ha="center",
        va="center",
    )
    axes[1].set_axis_off()
    fig.suptitle("SCI external computational labels: connectivity is not anatomical validation")
    save(output, "SCI-mesh-evidence", fig, {"label_ID": codes, "components": components})
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    xyz = arrays["source_grid_MRI_m"]
    depth = (0.08 - np.linalg.norm(xyz, axis=1)) * 1000
    names = ["boundary_1mm", "skull_half"]
    for name in names:
        axes[0].scatter(depth, arrays[name + "_relative_per_source"], s=4, alpha=0.3, label=name)
    axes[0].set(xlabel="Depth below 80 mm brain sphere (mm)", ylabel="Relative lead-block change")
    axes[0].legend()
    axes[1].bar(
        names, [summary["synthetic_sensitivity"][n]["relative_lead_Frobenius"] for n in names]
    )
    axes[1].set(ylabel="Relative full lead Frobenius change")
    fig.suptitle(
        "Analytically known sphere BEM: physical recomputation, not human anatomical variation"
    )
    save(
        output,
        "synthetic-leadfield-perturbations",
        fig,
        {"depth_mm": depth, **{n: arrays[n + "_relative_per_source"] for n in names}},
    )
    fig, ax = plt.subplots(figsize=(6, 4), layout="constrained")
    theta = np.linspace(0, 2 * np.pi, 200)
    for radius, label in zip([80, 85, 90], ["brain", "skull outer", "scalp"], strict=True):
        ax.plot(radius * np.cos(theta), radius * np.sin(theta), label=label)
    ax.plot(81 * np.cos(theta), 81 * np.sin(theta), "--", label="brain +1 mm")
    ax.set(xlabel="MRI x (mm)", ylabel="MRI y (mm)", aspect="equal")
    ax.legend()
    ax.set_title("Analytic conductor control; external correspondence unavailable")
    save(
        output,
        "controlled-boundary-difference",
        fig,
        {"theta": theta, "baseline_radii_mm": [80, 85, 90], "perturbed_brain_radius_mm": 81},
    )


def prior_plots(
    output: Path, rows: list[dict[str, Any]], records: dict[str, Any], arrays: dict[str, Any]
) -> None:
    selected = [
        r
        for r in rows
        if r["source"] == 0
        and r["angle_deg"] == 0
        and r["model"] == "analytical"
        and r["representation"] == "free"
        and r["fitted_noise"] == "matched"
        and r["lambda2"] == 1 / 9
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
    plotdata = {}
    for policy in ["uniform", "depth", "area", "orientation", "depth_area"]:
        for norm in ["none", "sensor_trace"]:
            rr = sorted(
                [r for r in selected if r["prior"] == policy and r["normalization"] == norm],
                key=lambda r: r["spacing_m"],
            )
            x = np.array([r["spacing_m"] * 1000 for r in rr])
            label = policy + (" normalized" if norm == "sensor_trace" else " raw")
            for ax, key in zip(
                axes,
                ["peak_error_mm", "nearest_vertex_amplitude_ratio", "dispersion_mm"],
                strict=True,
            ):
                y = np.array([r["noisefree"][key] for r in rr])
                ax.plot(x, y, marker="o", ls="--" if norm == "sensor_trace" else "-", label=label)
                plotdata[label + "_" + key] = y
            plotdata[label + "_spacing_mm"] = x
    for ax, title in zip(
        axes, ["Peak error (mm)", "Nearest moment / true moment", "Dispersion (mm)"], strict=True
    ):
        ax.set(xlabel="Grid spacing (mm)", ylabel=title)
    axes[0].legend(fontsize=6, ncol=2)
    fig.suptitle(
        "Continuous analytic truth: fixed alpha across priors/grids; no grid-invariance guarantee"
    )
    save(output, "grid-prior-reconstruction", fig, plotdata)
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    data = {}
    xyz = arrays["0.01_free__positions_MRI_m"]
    depth = (0.08 - np.linalg.norm(xyz, axis=1)) * 1000
    for policy in ["uniform", "depth", "area", "orientation", "depth_area"]:
        block = arrays["0.01_free_analytical_matched_" + policy + "__raw_prior_blocks"]
        weights = np.trace(block, axis1=1, axis2=2)
        ax.scatter(depth, weights, s=3, alpha=0.3, label=policy)
        data[policy] = weights
    ax.set(xlabel="Depth below 80 mm sphere (mm)", ylabel="Raw block covariance trace")
    ax.legend(fontsize=7)
    ax.set_title("Synthetic volumetric grid: area is a declared quadrature, not cortical anatomy")
    data["depth_mm"] = depth
    save(output, "prior-weights-depth", fig, data)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    data = {}
    for norm in ["none", "sensor_trace"]:
        rr = [r for r in selected if r["spacing_m"] == 0.01 and r["normalization"] == norm]
        x = np.arange(len(rr))
        gain = np.array([r["nearest_resolution_gain"] for r in rr])
        complexity = np.array([records[r["operator"]]["effective_complexity"] for r in rr])
        for ax, y in zip(axes, [gain, complexity], strict=True):
            ax.plot(x, y, "o-", label=norm)
        data[norm + "_gain"] = gain
        data[norm + "_complexity"] = complexity
        for ax in axes:
            ax.set_xticks(x, [r["prior"] for r in rr], rotation=20)
            ax.legend()
    axes[0].set_ylabel("Nearest block resolution gain")
    axes[1].set_ylabel("Effective complexity tr(KL)")
    fig.suptitle("Synthetic 10 mm free source grid: prior-induced regularization tradeoffs")
    save(output, "resolution-prior-gain", fig, data)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    data = {}
    names = ["analytical", "BEM", "boundary_1mm", "skull_half"]
    for model in names:
        rr = sorted(
            [
                r
                for r in rows
                if r["source"] == 0
                and r["angle_deg"] == 0
                and r["model"] == model
                and r["representation"] == "free"
                and r["fitted_noise"] == "matched"
                and r["lambda2"] == 1 / 9
                and r["prior"] == "uniform"
                and r["normalization"] == "none"
            ],
            key=lambda r: r["spacing_m"],
        )
        if not rr:
            continue
        x = np.array([r["spacing_m"] * 1000 for r in rr])
        y = np.array([r["noisefree"]["peak_error_mm"] for r in rr])
        amp = np.array([r["noisefree"]["nearest_vertex_amplitude_ratio"] for r in rr])
        axes[0].plot(x, y, "o-", label=model)
        axes[1].plot(x, amp, "o-", label=model)
        data[model + "_spacing_mm"] = x
        data[model + "_peak_mm"] = y
        data[model + "_moment_ratio"] = amp
    for ax in axes:
        ax.set_xlabel("Grid spacing (mm)")
        ax.legend(fontsize=7)
    axes[0].set_ylabel("Peak localization error (mm)")
    axes[1].set_ylabel("Nearest moment ratio")
    fig.suptitle("Analytic continuous truth / recomputed synthetic conductor mismatch")
    save(output, "conductor-prior-sensitivity", fig, data)
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    data = {}
    for norm in ["none", "sensor_trace"]:
        rr = [r for r in selected if r["prior"] == "uniform" and r["normalization"] == norm]
        count = np.array([records[r["operator"]]["inverse_fit_wall_s"] * 1000 for r in rr])
        error = np.array([r["noisefree"]["peak_error_mm"] for r in rr])
        ax.plot(count, error, "o-", label=norm)
        data[norm + "_fit_wall_ms"] = count
        data[norm + "_error_mm"] = error
    ax.set(
        xlabel="Measured inverse fit wall time (ms; one local fit/operator)",
        ylabel="Peak error (mm)",
    )
    ax.legend()
    ax.set_title("Synthetic off-grid accuracy vs measured fit cost; cache/environment in manifest")
    save(output, "accuracy-dimension", fig, data)
