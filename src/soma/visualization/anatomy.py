"""Headless anatomical uncertainty figures with numeric companions and honest scope."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from soma.anatomy.surfaces import distance_to_surface
from soma.geometry import Frame, Points


def save_figure(fig: Any, output: Path, name: str, **arrays: Any) -> None:
    fig.savefig(output / f"{name}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    np.savez_compressed(output / f"{name}-figure-data.npz", **arrays)


def coreg_figures(output: Path, assets: Any, model: Any, comparison: dict[str, Any]) -> None:
    xyz = model.head_to_mri.apply(
        Points(np.array([c["loc"][:3] for c in model.info["chs"]]), Frame.HEAD)
    ).xyz
    scalp = model.surfaces.meshes[-1].vertices.xyz
    fig = plt.figure(figsize=(12, 5))
    ax = fig.add_subplot(121)
    ax3 = fig.add_subplot(122, projection="3d")
    image: Any = nib.load(assets.subject_dir / "mri/T1.mgz")
    data = np.asanyarray(image.dataobj)
    tkr = image.header.get_vox2ras_tkr()
    k = data.shape[2] // 2
    if np.allclose(tkr[:3, :3], np.array([[-1, 0, 0], [0, 0, 1], [0, -1, 0]])):
        view = data[:, :, k].T[::-1, ::-1]
        xmin = tkr[0, 3] - (data.shape[0] - 0.5)
        xmax = tkr[0, 3] + 0.5
        zmin = tkr[2, 3] - (data.shape[1] - 0.5)
        zmax = tkr[2, 3] + 0.5
        ax.imshow(view, origin="lower", cmap="gray", extent=(xmin, xmax, zmin, zmax))
        mask = np.abs(xyz[:, 1] - (tkr @ np.array([0, 0, k, 1]))[1] / 1000) < 0.025
        ax.scatter(xyz[mask, 0] * 1000, xyz[mask, 2] * 1000, c="red", s=12)
    else:
        ax.text(0.1, 0.5, "MRI orientation differs; use stored geometry")
    ax.set(
        title="Participant MRI; nearby EEG projected to coronal view",
        xlabel="MNE MRI x (mm)",
        ylabel="MNE MRI z (mm)",
    )
    ax3.scatter(*scalp.T * 1000, s=3, alpha=0.25, label="derived participant FLASH scalp")
    ax3.scatter(*xyz.T * 1000, c="red", s=14, label="digitized EEG, primary transform")
    ax3.set(xlabel="MRI x (mm)", ylabel="MRI y (mm)", zlabel="MRI z (mm)")
    ax3.legend(fontsize=8)
    fig.suptitle(
        f"{model.subject}: measured EEG / participant MRI; "
        "transform accuracy not independently known"
    )
    save_figure(
        fig,
        output,
        "MRI-head-electrode-alignment",
        electrode_MRI_m=xyz,
        scalp_MRI_m=scalp,
        head_to_MRI_m=model.head_to_mri.matrix,
        tkr_RAS_mm=tkr,
        MRI_coronal_slice=data[:, :, k],
        slice_index=k,
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    primary = np.array(comparison["primary_to_estimated_MRI_fiducials_residual_m"])
    fit = np.array(comparison["SVD_residuals_to_estimated_targets_m"])
    x = np.arange(3)
    ax.bar(x - 0.18, primary * 1000, 0.35, label="distributed transform")
    ax.bar(x + 0.18, fit * 1000, 0.35, label="fiducial-only refit")
    ax.set_xticks(x, ["LPA", "nasion", "RPA"])
    ax.set(
        ylabel="Residual to MNI-derived MRI targets (mm)",
        title=f"{model.subject}: derived targets, not anatomical fiducial truth",
    )
    ax.legend()
    save_figure(
        fig, output, "fiducial-residuals", primary_to_derived_m=primary, refit_to_derived_m=fit
    )
    distances = distance_to_surface(Points(xyz, Frame.MRI), model.surfaces.meshes[-1])
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(np.arange(len(distances)), distances * 1000)
    ax.set(
        xlabel="Retained measured EEG channel order",
        ylabel="Nearest triangle distance (mm)",
        title=f"{model.subject}: electrode/scalp discrepancies; MNE projects to scalp for EEG",
    )
    save_figure(
        fig,
        output,
        "electrode-scalp-distances",
        distances_m=distances,
        channels=np.array(model.info["ch_names"]),
    )


def surface_figures(output: Path, surfaces: Any, readiness: dict[str, Any]) -> None:
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(projection="3d")
    arrays = {}
    for index, (mesh, color, _label) in enumerate(
        zip(
            surfaces.meshes,
            ("red", "gold", "lightblue"),
            ("inner skull", "outer skull", "scalp"),
            strict=True,
        )
    ):
        artist = Poly3DCollection(
            mesh.vertices.xyz[mesh.faces] * 1000, facecolor=color, alpha=0.12, edgecolor="none"
        )
        ax.add_collection3d(artist)
        arrays[f"vertices_{index}_MRI_m"] = mesh.vertices.xyz
        arrays[f"faces_{index}"] = mesh.faces
    xyz = surfaces.meshes[-1].vertices.xyz * 1000
    ax.auto_scale_xyz(xyz[:, 0], xyz[:, 1], xyz[:, 2])
    ax.set(
        xlabel="MRI x (mm)",
        ylabel="MRI y (mm)",
        zlabel="MRI z (mm)",
        title=f"{surfaces.subject}: derived conductor surfaces; no clinical certification",
    )
    save_figure(fig, output, "three-conductor-surfaces", **arrays)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    values = []
    for label, quality in zip(
        ("inner skull", "outer skull", "scalp"), readiness["quality"], strict=True
    ):
        values.extend(quality["triangle_quality"])
        axes[0].hist(quality["triangle_quality"], bins=20, alpha=0.5, label=label)
    axes[0].set(xlabel="Triangle shape quality (1 = equilateral)", ylabel="Count")
    axes[0].legend()
    pairs = readiness["nesting"].get("pairs", [])
    gaps = np.array([p["minimum_triangle_distance_m"] for p in pairs])
    if len(gaps):
        axes[1].bar(np.arange(len(gaps)), gaps * 1000)
        axes[1].set_xticks(np.arange(len(gaps)), ["brain/skull", "skull/scalp"])
    axes[1].set(
        ylabel="Minimum triangle separation (mm)",
        title=f"Readiness {readiness['status']}\nAnatomical evidence is not clinical certification",
    )
    save_figure(
        fig,
        output,
        "mesh-quality-and-nesting",
        triangle_quality=np.array(values),
        separation_m=gaps,
    )


def individual_figures(output: Path, forward: Any) -> None:
    singular = np.linalg.svd(forward.matrix, compute_uv=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.semilogy(np.arange(1, len(singular) + 1), singular, "o-")
    ax.set(
        xlabel="Singular index",
        ylabel="V/(A m)",
        title=f"{forward.anatomy['subject']}: fixed-normal EEG spectrum; average reference",
    )
    save_figure(
        fig,
        output,
        "individual-leadfield-spectrum",
        singular_values=singular,
        lead_field=forward.matrix,
        source_head_m=forward.coordinates.points.xyz,
        lh_vertices=forward.vertices[0],
        rh_vertices=forward.vertices[1],
    )


def uncertainty_figures(
    output: Path, frame: pd.DataFrame, examples: dict[str, Any], xyz: Any, true_index: int
) -> None:
    successful = frame[frame.status == "computed"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for name in ("translation_x_m", "electrode_noise_m", "fiducial_noise_m", "headshape_noise_m"):
        part = successful[successful["case"] == name]
        if len(part):
            axes[0].plot(
                part.magnitude * 1000,
                part.relative_leadfield_change * 100,
                "o-",
                label=name.replace("_m", ""),
            )
    part = successful[successful["case"] == "rotation_z_deg"]
    axes[1].plot(part.magnitude, part.relative_leadfield_change * 100, "o-")
    axes[0].set(
        xlabel="Input displacement / per-coordinate SD (mm)",
        ylabel="Relative lead-field change (%)",
    )
    axes[0].legend(fontsize=7)
    axes[1].set(xlabel="Rotation about MRI z (degrees)", ylabel="Relative lead-field change (%)")
    fig.suptitle("sample: controlled perturbations; refits may include a separate method change")
    save_figure(
        fig,
        output,
        "coregistration-perturbation-effects",
        case=successful["case"].to_numpy(dtype=str),
        magnitude=successful.magnitude.to_numpy(),
        relative_change=successful.relative_leadfield_change.to_numpy(),
    )
    cond = successful[successful["case"].str.startswith("conductivity_")]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(np.arange(len(cond)), cond.relative_leadfield_change * 100)
    ax.set_xticks(np.arange(len(cond)), cond["case"].str.replace("conductivity_", ""), rotation=15)
    ax.set(
        ylabel="Relative EEG lead-field change (%)",
        title="sample: recomputed BEM conductivities; sensitivity, not measured tissue values",
    )
    save_figure(
        fig,
        output,
        "conductivity-sensitivity",
        case=cond["case"].to_numpy(dtype=str),
        relative_change=cond.relative_leadfield_change.to_numpy(),
    )
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for name in ("translation_x_m", "electrode_noise_m", "fiducial_noise_m", "headshape_noise_m"):
        part = successful[successful["case"] == name]
        if len(part):
            axes[0].plot(
                part.magnitude * 1000,
                part.peak_euclidean_m * 1000,
                "o-",
                label=name.replace("_m", ""),
            )
    part = successful[successful["case"] == "rotation_z_deg"]
    axes[1].plot(part.magnitude, part.peak_euclidean_m * 1000, "o-")
    axes[0].legend(fontsize=7)
    axes[0].set(
        xlabel="Input displacement / per-coordinate SD (mm)", ylabel="Peak Euclidean error (mm)"
    )
    axes[1].set(xlabel="Rotation (degrees)", ylabel="Peak Euclidean error (mm)")
    fig.suptitle(
        "Simulated source on participant geometry; not real generator localization accuracy"
    )
    save_figure(
        fig,
        output,
        "localization-versus-geometry",
        case=successful["case"].to_numpy(dtype=str),
        magnitude=successful.magnitude.to_numpy(),
        peak_error_m=successful.peak_euclidean_m.to_numpy(),
    )
    if examples:
        selected = list(examples)[:3]
        fig, axes = plt.subplots(1, len(selected), figsize=(5 * len(selected), 5))
        axes = np.atleast_1d(axes)
        for ax, name in zip(axes, selected, strict=True):
            artist = ax.scatter(xyz[:, 0] * 1000, xyz[:, 1] * 1000, c=examples[name], s=8)
            ax.scatter(
                xyz[true_index, 0] * 1000, xyz[true_index, 1] * 1000, marker="x", s=60, c="red"
            )
            ax.set(title=name, xlabel="MRI x (mm)", ylabel="MRI y (mm)")
            ax.set_aspect("equal")
            fig.colorbar(artist, ax=ax, label="Current RMS (A m)", shrink=0.7)
        fig.suptitle(
            "Synthetic truth mark / reconstructed sources on participant MRI; "
            "depth-overlapping projection"
        )
        save_figure(
            fig,
            output,
            "participant-synthetic-truth-recovery",
            source_MRI_m=xyz,
            true_index=true_index,
            **examples,
        )


def synthetic_figures(
    output: Path,
    surfaces: Any,
    alignment: list[dict[str, Any]],
    reference: Any,
    rows: Any,
    conductivity: Any,
    current: Any,
    reconstructions: Any,
    xyz: Any,
) -> None:
    readiness = surfaces.readiness(sensor_compatible=True, anatomical_evidence=True)
    surface_figures(output, surfaces, readiness)
    frame = pd.DataFrame(alignment)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(frame.measurement_std_m * 1000, frame.fit_RMS_m * 1000, "o-", label="fit residual")
    ax.plot(
        frame.measurement_std_m * 1000,
        frame.median_landmark_TRE_m * 1000,
        "o-",
        label="independent true-transform TRE",
    )
    ax.set(
        xlabel="Fiducial per-coordinate noise SD (mm)",
        ylabel="Error (mm)",
        title="Known synthetic rigid transform: fit is distinct from truth error",
    )
    ax.legend()
    save_figure(
        fig,
        output,
        "synthetic-coregistration-errors",
        noise_m=frame.measurement_std_m.to_numpy(),
        fit_RMS_m=frame.fit_RMS_m.to_numpy(),
        true_TRE_m=frame.median_landmark_TRE_m.to_numpy(),
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(
        [r["subdivisions"] for r in reference],
        [r["relative_BEM_vs_analytical_error"] * 100 for r in reference],
        "o-",
    )
    ax.set(
        xlabel="Icosphere subdivisions",
        ylabel="BEM vs analytical relative error (%)",
        title="Independent layered-sphere reference: discretization, not registration error",
    )
    save_figure(
        fig,
        output,
        "BEM-analytical-discretization",
        subdivisions=np.array([r["subdivisions"] for r in reference]),
        relative_error=np.array([r["relative_BEM_vs_analytical_error"] for r in reference]),
    )
    recovered = np.asarray(reconstructions["correct:0.0"]).reshape(-1, 3)
    truth = np.asarray(current).reshape(-1, 3)
    fig, ax = plt.subplots(figsize=(8, 4))
    ids = np.arange(len(truth))
    ax.bar(ids - 0.2, np.linalg.norm(truth, axis=1) * 1e9, 0.4, label="known truth")
    ax.bar(ids + 0.2, np.linalg.norm(recovered, axis=1) * 1e9, 0.4, label="regularized recovery")
    ax.set(
        xlabel="Known MRI source index",
        ylabel="Current vector amplitude (nA m)",
        title="Synthetic spherical geometry; nonlinear magnitude is not a linear resolution kernel",
    )
    ax.legend()
    save_figure(
        fig,
        output,
        "synthetic-truth-source-reconstruction",
        truth_Am=truth,
        recovered_Am=recovered,
        source_MRI_m=xyz,
    )
