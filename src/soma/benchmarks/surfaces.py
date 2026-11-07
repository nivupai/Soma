"""Analytic area/volume references and sampled boundary/repair experiments."""

from typing import Any

import numpy as np
from scipy import ndimage
from scipy.spatial.transform import Rotation

from soma.anatomy.synthetic import sphere_mesh
from soma.benchmarks.topology import topology
from soma.geometry import Frame, Points
from soma.imaging.phantoms import coordinates, grid
from soma.imaging.resampling import resample
from soma.imaging.surfaces import Mesh
from soma.imaging.volumes import Volume


def radial_radius(normals: Any, name: str) -> Any:
    if name.startswith("shell"):
        return np.full(len(normals), float(name[5:]) / 1000)
    if name == "sphere":
        return np.full(len(normals), 0.03)
    if name == "asymmetric":
        return 0.03 * (1 + 0.12 * normals[:, 0] * normals[:, 1] + 0.08 * normals[:, 2] ** 3)
    if name == "ellipsoid":
        rotation = Rotation.from_euler("xyz", [13, -17, 24], degrees=True).as_matrix()
        n = normals @ rotation
        return 1 / np.sqrt(np.sum((n / [0.035, 0.025, 0.018]) ** 2, axis=1))
    raise ValueError("Unknown analytic geometry")


def field(name: str, spacing_mm: float) -> Volume:
    reference = grid((spacing_mm / 1000,) * 3, extent_m=0.1)
    xyz = coordinates(reference)
    flat = xyz.reshape(-1, 3)
    length = np.linalg.norm(flat, axis=1)
    normals = flat / np.maximum(length[:, None], 1e-30)
    normals[length == 0] = [1, 0, 0]
    values = radial_radius(normals, name) - length
    return Volume(
        values.reshape(reference.shape).astype(np.float32),
        reference.affine_m,
        metadata={"reference": "analytic radial surface", "shape": name, "spacing_mm": spacing_mm},
    )


def analytic_values(name: str, order: int = 128) -> dict[str, float]:
    if name == "sphere" or name.startswith("shell"):
        r = 0.03 if name == "sphere" else float(name[5:]) / 1000
        return {
            "area_m2": 4 * np.pi * r * r,
            "volume_m3": 4 * np.pi * r**3 / 3,
            "quadrature_order": 0,
        }
    z, weights = np.polynomial.legendre.leggauss(order)
    phi = np.arange(order * 2) * np.pi / order
    zz, pp = np.meshgrid(z, phi, indexing="ij")
    w = np.broadcast_to(weights[:, None], zz.shape) * np.pi / order
    n = np.stack(
        [np.sqrt(1 - zz * zz) * np.cos(pp), np.sqrt(1 - zz * zz) * np.sin(pp), zz], axis=-1
    )
    if name == "ellipsoid":
        axes = np.array([0.035, 0.025, 0.018])
        area = float(np.sum(np.prod(axes) * np.linalg.norm(n / axes, axis=-1) * w))
        volume = float(4 * np.pi * np.prod(axes) / 3)
    elif name == "asymmetric":
        f = 1 + 0.12 * n[..., 0] * n[..., 1] + 0.08 * n[..., 2] ** 3
        grad = np.stack([0.12 * n[..., 1], 0.12 * n[..., 0], 0.24 * n[..., 2] ** 2], axis=-1)
        tangent = grad - n * np.sum(grad * n, axis=-1)[..., None]
        area = float(np.sum(0.03**2 * f * np.sqrt(f * f + np.sum(tangent * tangent, axis=-1)) * w))
        volume = float(np.sum(0.03**3 * f**3 * w) / 3)
    else:
        raise ValueError("Unknown analytic surface")
    return {"area_m2": area, "volume_m3": volume, "quadrature_order": order}


def convergence_record(
    mesh: Mesh, name: str, spacing_mm: float, method: str, max_faces: int
) -> dict[str, Any]:
    q = topology(mesh, check_intersections=len(mesh.faces) <= max_faces)
    ref = analytic_values(name)
    xyz = mesh.vertices.xyz
    r = np.linalg.norm(xyz, axis=1)
    residual = radial_radius(xyz / r[:, None], name) - r
    return {
        "shape": name,
        "spacing_mm": spacing_mm,
        "method": method,
        "reference": ref,
        "area_relative_error": (q["surface_area_m2"] - ref["area_m2"]) / ref["area_m2"],
        "algebraic_volume_relative_error": (q["signed_volume_m3"] - ref["volume_m3"])
        / ref["volume_m3"],
        "radial_vertex_RMS_mm": float(np.sqrt(np.mean(residual**2)) * 1000),
        "radial_vertex_max_mm": float(np.max(np.abs(residual)) * 1000),
        "topology": q,
        "distance_definition": (
            "radial residual; exact nearest-sphere distance only for spherical references"
        ),
    }


def mask_perturbations(seed: int = 42) -> tuple[Volume, dict[str, Volume]]:
    scalar = field("sphere", 1)
    binary = scalar.array() >= 0
    reference = Volume(
        binary.astype(np.uint8),
        scalar.affine_m,
        "labels",
        {
            "reference": "analytic sphere center sampling",
            "subject": "analytic-sphere",
            "space": "analytic-RAS",
        },
    )
    inside = ndimage.distance_transform_edt(binary, sampling=0.001)
    outside = ndimage.distance_transform_edt(~binary, sampling=0.001)
    masks = {
        "dilation_1mm": outside <= 0.001,
        "erosion_1mm": inside > 0.001,
        "radial_shift_1mm": scalar.array() >= -0.001,
    }
    hole = binary.copy()
    hole[79:83, 49:52, 49:52] = False
    masks["localized_hole"] = hole
    island = binary.copy()
    island[89:91, 49:51, 49:51] = True
    masks["disconnected_island"] = island
    noise = ndimage.gaussian_filter(np.random.default_rng(seed).normal(size=binary.shape), sigma=3)
    noise *= 0.001 / noise[np.abs(scalar.array()) < 0.002].std()
    masks["boundary_noise_1mm"] = scalar.array() + noise >= 0
    index = coordinates(scalar)
    partial = np.zeros(binary.shape)
    for dx in (-0.00025, 0.00025):
        for dy in (-0.00025, 0.00025):
            for dz in (-0.00025, 0.00025):
                partial += np.linalg.norm(index + [dx, dy, dz], axis=-1) <= 0.03
    masks["partial_volume_eight_samples"] = partial / 8 >= 0.5
    result = {
        name: Volume(
            mask.astype(np.uint8),
            reference.affine_m,
            "labels",
            {
                "method": name,
                "scale_m": 0.001,
                "reference": (
                    "controlled analytic perturbation, not independent segmentation method"
                ),
            },
        )
        for name, mask in masks.items()
    }
    for name, volume in result.items():
        volume.metadata["physical_perturbation"] = {
            "dilation_1mm": {"radius_m": 0.001},
            "erosion_1mm": {"radius_m": 0.001},
            "radial_shift_1mm": {"radial_displacement_m": 0.001},
            "localized_hole": {"removed_box_extent_m": [0.004, 0.003, 0.003]},
            "disconnected_island": {"added_box_extent_m": [0.002, 0.002, 0.002]},
            "boundary_noise_1mm": {
                "boundary_field_SD_m": 0.001,
                "Gaussian_smoothing_sigma_m": 0.003,
                "seed": seed,
            },
            "partial_volume_eight_samples": {
                "subvoxel_axis_offsets_m": [-0.00025, 0.00025],
                "samples": 8,
                "threshold": 0.5,
            },
        }[name]
    for name, spacing in [
        ("resampling_4mm", (0.004,) * 3),
        ("anisotropic_2x2x4mm", (0.002, 0.002, 0.004)),
    ]:
        target = grid(spacing, extent_m=0.1)
        coarse = resample(reference, target, order=0)
        result[name] = resample(coarse, reference, order=0, allow_repeated=True)
    return reference, result


def repair_cases() -> dict[str, Mesh]:
    rr, faces = sphere_mesh(3, 0.03)
    base = Mesh(Points(rr, Frame.RAS), faces, {"reference": "known analytic sphere tessellation"})
    duplicate = faces.copy()
    duplicate[0, 0] = len(rr)
    mixed = faces.copy()
    mixed[::3] = mixed[::3][:, [0, 2, 1]]
    distorted = rr.copy()
    distorted[0] = -rr[0] * 1.2
    return {
        "reference": base,
        "duplicate_vertex": Mesh(Points(np.vstack([rr, rr[faces[0, 0]]]), Frame.RAS), duplicate),
        "duplicate_face": Mesh(base.vertices, np.vstack([faces, faces[0]])),
        "degenerate_face": Mesh(base.vertices, np.vstack([faces, [0, 0, 1]])),
        "small_hole": Mesh(base.vertices, faces[1:]),
        "large_hole": Mesh(base.vertices, faces[5:]),
        "mixed_orientation": Mesh(base.vertices, mixed),
        "self_intersection": Mesh(Points(distorted, Frame.RAS), faces),
    }
