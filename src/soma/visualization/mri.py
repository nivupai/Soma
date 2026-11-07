"""Headless MRI figures with numerical companions and explicit physical units."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soma.imaging.surfaces import Mesh
from soma.imaging.volumes import Volume


def _save(fig: Any, output: Path, name: str, **arrays: Any) -> None:
    fig.savefig(output / f"{name}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    np.savez_compressed(output / f"{name}-figure-data.npz", **arrays)


def _slice(volume: Volume, axis: int) -> Any:
    return np.take(volume.array(), volume.shape[axis] // 2, axis=axis).T


def _extent(volume: Volume, axis: int) -> tuple[float, float, float, float]:
    axes = [i for i in range(3) if i != axis]
    return (
        0,
        volume.shape[axes[0]] * volume.spacing_m[axes[0]] * 1000,
        0,
        volume.shape[axes[1]] * volume.spacing_m[axes[1]] * 1000,
    )


def registration_overlay(
    output: Path, fixed: Volume, moving: Volume, warped: Volume, name: str
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, volume, title in zip(
        axes, (moving, warped), ("Before alignment", "After estimated alignment"), strict=True
    ):
        a, b = _slice(fixed, 2), _slice(volume, 2)
        rgb = np.zeros((*a.shape, 3))
        rgb[..., 0] = a / max(float(a.max()), 1e-12)
        rgb[..., 1] = b / max(float(b.max()), 1e-12)
        ax.imshow(rgb, origin="lower", extent=_extent(fixed, 2))
        ax.set(title=title, xlabel="Grid-axis distance (mm)", ylabel="Grid-axis distance (mm)")
    fig.suptitle("Controlled transform: fixed red, moving green; yellow overlap")
    _save(
        fig,
        output,
        name,
        fixed=_slice(fixed, 2),
        moving=_slice(moving, 2),
        recovered=_slice(warped, 2),
        affine_RAS_m=fixed.affine_m,
    )


def synthetic_figures(
    output: Path,
    fixed: Volume,
    moving: Volume,
    warped: Volume,
    errors: Any,
    meshes: list[Mesh],
    nesting: dict[str, Any],
) -> None:
    registration_overlay(output, fixed, moving, warped, "synthetic-registration-overlay")
    fig, ax = plt.subplots(figsize=(7, 4))
    for mode, group in errors.groupby("mode"):
        ax.plot(group.perturbation_multiplier, group.median_landmark_TRE_m * 1000, "o-", label=mode)
    ax.set(
        xlabel="Known perturbation multiplier",
        ylabel="Median independent landmark TRE (mm)",
        title="Asymmetric phantom registration",
    )
    ax.legend()
    _save(
        fig,
        output,
        "registration-error-versus-perturbation",
        multiplier=errors.perturbation_multiplier.to_numpy(),
        TRE_m=errors.median_landmark_TRE_m.to_numpy(),
        mode=errors["mode"].to_numpy(dtype=str),
    )
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(projection="3d")
    for mesh, color, label in zip(
        meshes,
        ("red", "blue", "grey"),
        ("inner candidate", "middle candidate", "outer candidate"),
        strict=True,
    ):
        xyz = mesh.vertices.xyz
        ax.scatter(*xyz[::3].T * 1000, s=6, alpha=0.6, color=color, label=label)
    ax.set(
        xlabel="RAS x (mm)",
        ylabel="RAS y (mm)",
        zlabel="RAS z (mm)",
        title=(
            f"Synthetic nested shells: candidate={nesting['geometric_candidate']}\n"
            "Physiological conductor validation=False"
        ),
    )
    ax.legend()
    _save(
        fig,
        output,
        "nested-surface-readiness",
        **{f"vertices_{i}_m": m.vertices.xyz for i, m in enumerate(meshes)},
        **{f"faces_{i}": m.faces for i, m in enumerate(meshes)},
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    a = fixed.affine_m
    axes[0].imshow(a[:3, :3] * 1000, cmap="RdBu_r")
    axes[0].set(
        title="Voxel-index → RAS linear map (mm/voxel)", xlabel="Voxel axis", ylabel="RAS component"
    )
    ijk = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
    xyz = fixed.grid.to_world(ijk).xyz * 1000
    axes[1].scatter(xyz[:, 0], xyz[:, 1])
    axes[1].set(title="First voxel and adjacent centers", xlabel="RAS x (mm)", ylabel="RAS y (mm)")
    _save(fig, output, "voxel-grid-affine", voxel_indices=ijk, RAS_m=xyz / 1000, voxel_to_RAS_m=a)


def real_figures(
    output: Path,
    native: Volume,
    fixed: Volume,
    moving: Volume,
    warped: Volume,
    mask: Volume,
    mesh: Mesh,
    quality: dict[str, Any],
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    for axis, ax, name in zip(range(3), axes, ("Sagittal", "Coronal", "Axial"), strict=True):
        ax.imshow(_slice(native, axis), origin="lower", cmap="gray", extent=_extent(native, axis))
        ax.set(title=name, xlabel="Storage-axis distance (mm)", ylabel="Storage-axis distance (mm)")
    fig.suptitle(
        f"SPM auditory T1w; native storage {native.geometry()['axis_codes']} (array not reoriented)"
    )
    _save(
        fig,
        output,
        "MRI-orthogonal-slices",
        **{f"slice_{i}": _slice(native, i) for i in range(3)},
        affine_RAS_m=native.affine_m,
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    a = native.affine_m
    axes[0].imshow(a[:3, :3] * 1000, cmap="RdBu_r")
    axes[0].set(title="Native voxel → RAS (mm/voxel)", xlabel="Voxel i/j/k", ylabel="RAS x/y/z")
    axes[1].bar(["i", "j", "k"], native.spacing_m * 1000)
    axes[1].set(
        ylabel="Spacing (mm)",
        title=(
            f"Storage {native.geometry()['axis_codes']}; physical RAS+\n"
            "Storage determinant does not establish anatomical reversal"
        ),
    )
    _save(
        fig, output, "orientation-physical-diagnostics", affine_RAS_m=a, spacing_m=native.spacing_m
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, key in zip(axes, ("qform", "sform"), strict=True):
        matrix = native.metadata.get(key)
        ax.imshow(np.eye(4) if matrix is None else matrix, cmap="RdBu_r")
        ax.set(title=f"{key}, code={native.metadata[key + '_code']} (source mm)")
    _save(
        fig,
        output,
        "qform-sform-comparison",
        qform=np.array(native.metadata["qform"]),
        sform=np.array(native.metadata["sform"]),
    )
    registration_overlay(output, fixed, moving, warped, "real-controlled-registration")
    from soma.experiments.mri_geometry import target_grid
    from soma.imaging.resampling import resample

    background = resample(native, target_grid(native, mask.spacing_m[0]))
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(_slice(background, 2), origin="lower", cmap="gray", extent=_extent(mask, 2))
    ax.contour(_slice(mask, 2), levels=[0.5], colors="red", extent=_extent(mask, 2))
    ax.set(
        title="Estimated coarse foreground envelope\nOtsu + morphology; not brain/tissue truth",
        xlabel="Storage-axis distance (mm)",
        ylabel="Storage-axis distance (mm)",
    )
    _save(
        fig,
        output,
        "segmentation-foreground-overlay",
        intensity=_slice(background, 2),
        estimated_mask=_slice(mask, 2),
        affine_RAS_m=mask.affine_m,
    )
    fig = plt.figure(figsize=(7, 6))
    ax = fig.add_subplot(projection="3d")
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    polygons = Poly3DCollection(
        mesh.vertices.xyz[mesh.faces] * 1000,
        alpha=0.5,
        facecolor="lightsteelblue",
        edgecolor="none",
    )
    ax.add_collection3d(polygons)
    xyz = mesh.vertices.xyz * 1000
    ax.auto_scale_xyz(xyz[:, 0], xyz[:, 1], xyz[:, 2])
    ax.set(
        xlabel="RAS x (mm)",
        ylabel="RAS y (mm)",
        zlabel="RAS z (mm)",
        title="Coarse MRI foreground surface\nNot a validated cortical or BEM boundary",
    )
    _save(fig, output, "extracted-surface", vertices_RAS_m=mesh.vertices.xyz, faces=mesh.faces)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(quality["triangle_quality"], bins=30)
    ax.set(
        xlabel="4√3 area / sum(edge²), 1 = equilateral",
        ylabel="Triangle count",
        title=(
            f"Mesh quality; χ={quality['euler_characteristic']}, "
            f"boundary edges={quality['boundary_edges']}"
        ),
    )
    _save(
        fig,
        output,
        "mesh-quality-distribution",
        triangle_quality=np.array(quality["triangle_quality"]),
    )
