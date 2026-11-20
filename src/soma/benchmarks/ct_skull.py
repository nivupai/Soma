"""CT bone truth, evaluation region, exclusion flags and boundary metrics for skull surfaces.

CT is the independent reference: nothing here reads an estimator output to build truth or the
evaluation region. All thresholds are explicit parameters recorded in provenance; the frozen
values live in docs/MILESTONE33_SKULL_PROTOCOL.md. World coordinates are RAS+ metres (Soma's
Volume convention) regardless of the voxel storage order (SynthRAD2023 stores LPS voxel axes).
"""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage.filters import threshold_otsu

from soma.anatomy.t1_skull import boundary_mesh, mask_volume, pad, vertex_normals
from soma.benchmarks.segmentation import _quantile
from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import _point_triangle, contains
from soma.imaging.surfaces import Mesh
from soma.imaging.volumes import Volume

BOUNDARIES = ("inner_skull", "outer_skull", "outer_scalp")
PRIMARY_BONE_HU = 300.0
SENSITIVITY_BONE_HU = (200.0, 400.0)


@dataclass(frozen=True)
class CTSkullParameters:
    bone_hu: float = PRIMARY_BONE_HU
    tissue_hu: float = -200.0
    bone_closing_voxels: int = 2
    max_bone_hole_mm3: float = 5000.0  # diploe / partial-volume holes filled inside bone
    enclosure_closing_voxels: int = 5  # bridges foramina/sutures to enclose the cavity only
    scalp_closing_voxels: int = 3
    padding_voxels: int = 8
    smoothing_iterations: int = 10
    smoothing_step: float = 0.1

    def __post_init__(self) -> None:
        widest = max(
            self.bone_closing_voxels, self.enclosure_closing_voxels, self.scalp_closing_voxels
        )
        if min(self.bone_closing_voxels, self.scalp_closing_voxels) < 0 or widest < 0:
            raise ValueError("Nonnegative morphology required")
        if self.padding_voxels <= widest:
            raise ValueError("Padding must exceed every closing radius")


@dataclass(frozen=True)
class RegionRule:
    """Evaluation region fitted on the CT cranial cavity, applied identically to every surface.

    Superior axis is world +z (RAS). The intracranial extent runs from the lowest axial level
    whose cavity cross-section reaches ``extent_area_fraction`` of the maximum (this ignores
    the spinal canal) to the top of the cavity. Points below ``inferior_fraction`` of that
    extent are excluded, as is an anterior-inferior face/orbit/defacing box.
    """

    inferior_fraction: float = 0.4
    extent_area_fraction: float = 0.25
    orbit_box_anterior_fraction: float = 0.6  # box starts here along the posterior→anterior span
    orbit_box_superior_fraction: float = 0.65  # box ends here along the intracranial height
    bin_mm: float = 1.0

    def fit(self, cavity: Volume) -> "FittedRegion":
        mask = cavity.array().astype(bool)
        if not mask.any():
            raise ValueError("Empty cranial cavity; region undefined")
        xyz: Any = cavity.grid.to_world(np.argwhere(mask).astype(float)).xyz * 1000
        z, y = xyz[:, 2], xyz[:, 1]
        bins = np.floor((z - z.min()) / self.bin_mm).astype(int)
        area: Any = np.bincount(bins) * float(np.prod(cavity.spacing_m * 1000)) / self.bin_mm
        low = int(np.argmax(area >= self.extent_area_fraction * area.max()))
        z_lo, z_hi = float(z.min() + low * self.bin_mm), float(z.max())
        y_lo, y_hi = float(y.min()), float(y.max())
        return FittedRegion(
            self,
            plane_z_mm=z_lo + self.inferior_fraction * (z_hi - z_lo),
            box_y_min_mm=y_lo + self.orbit_box_anterior_fraction * (y_hi - y_lo),
            box_z_max_mm=z_lo + self.orbit_box_superior_fraction * (z_hi - z_lo),
            extent_mm=(z_lo, z_hi, y_lo, y_hi),
        )


@dataclass(frozen=True)
class FittedRegion:
    rule: RegionRule
    plane_z_mm: float
    box_y_min_mm: float
    box_z_max_mm: float
    extent_mm: tuple[float, float, float, float]

    def contains_mm(self, xyz_mm: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        x = np.asarray(xyz_mm, dtype=float)
        box = (x[:, 1] >= self.box_y_min_mm) & (x[:, 2] <= self.box_z_max_mm)
        return np.asarray((x[:, 2] >= self.plane_z_mm) & ~box)

    def points(self, points: Points) -> np.ndarray[Any, Any]:
        return self.contains_mm(points.xyz * 1000)

    def voxel_mask(self, like: Volume) -> np.ndarray[Any, Any]:
        index = np.indices(like.shape).reshape(3, -1).T.astype(float)
        inside = self.contains_mm(like.grid.to_world(index).xyz * 1000)
        return inside.reshape(like.shape)

    def provenance(self) -> dict[str, Any]:
        z_lo, z_hi, y_lo, y_hi = self.extent_mm
        return {
            "rule": asdict(self.rule),
            "frame": "RAS+ world, mm; superior=+z, anterior=+y",
            "intracranial_z_mm": [z_lo, z_hi],
            "intracranial_y_mm": [y_lo, y_hi],
            "superior_of_plane_z_mm": self.plane_z_mm,
            "excluded_box": {"y_min_mm": self.box_y_min_mm, "z_max_mm": self.box_z_max_mm},
            "fitted_on": "CT cranial cavity only",
        }


def superior_axis(volume: Volume) -> tuple[int, int]:
    """Voxel axis closest to world +z and the index direction (+1/-1) that moves superior."""
    column = volume.affine_m[2, :3]
    axis = int(np.argmax(np.abs(column)))
    return axis, 1 if column[axis] > 0 else -1


def _largest(mask: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    labelled, count = ndimage.label(mask)
    if count <= 1:
        return np.asarray(mask, dtype=bool)
    return np.asarray(labelled == np.argmax(np.bincount(labelled.ravel())[1:]) + 1)


def _fill_small_holes(mask: np.ndarray[Any, Any], max_voxels: int) -> np.ndarray[Any, Any]:
    """Fill enclosed background components of at most ``max_voxels`` (6-connected)."""
    holes = np.asarray(ndimage.binary_fill_holes(mask)) & ~mask
    labelled, count = ndimage.label(holes)
    if not count:
        return np.asarray(mask, dtype=bool)
    small = np.bincount(labelled.ravel()) <= max_voxels
    small[0] = False
    return np.asarray(mask | small[labelled])


def _slice_fill(mask: np.ndarray[Any, Any], axis: int) -> np.ndarray[Any, Any]:
    out = np.moveaxis(np.asarray(mask, dtype=bool).copy(), axis, 0)
    for i in range(out.shape[0]):
        out[i] = ndimage.binary_fill_holes(out[i])
    return np.moveaxis(out, 0, axis)


@dataclass(frozen=True)
class CTSkullTruth:
    masks: dict[str, Volume]  # bone, inner_skull (cavity), outer_skull, outer_scalp; padded
    meshes: dict[str, Mesh]
    provenance: dict[str, Any]


def ct_truth(
    ct: Volume, head_mask: Volume, *, parameters: CTSkullParameters | None = None
) -> CTSkullTruth:
    p = parameters or CTSkullParameters()
    if not ct.same_grid(head_mask):
        raise ValueError("CT and its head mask must share a grid")
    n = p.padding_voxels
    hu = pad(ct, n).array(np.float64)
    hu[pad(head_mask, n).array() == 0] = -1024.0
    like = pad(head_mask, n)
    within = like.array() > 0
    voxel_mm3 = float(np.prod(like.spacing_m * 1000))
    axis, _ = superior_axis(like)

    bone = (hu > p.bone_hu) & within
    if p.bone_closing_voxels:
        bone = ndimage.binary_closing(bone, iterations=p.bone_closing_voxels)
    bone = _largest(bone)
    bone = _fill_small_holes(bone, max(1, int(p.max_bone_hole_mm3 / voxel_mm3)))
    enclosure = (
        ndimage.binary_closing(bone, iterations=p.enclosure_closing_voxels)
        if p.enclosure_closing_voxels
        else bone
    )
    cavity = _largest(np.asarray(ndimage.binary_fill_holes(_slice_fill(enclosure, axis) & ~bone)))
    if not cavity.any():
        raise ValueError("No bone-enclosed cranial cavity at this HU threshold")
    outer = _largest(np.asarray(ndimage.binary_fill_holes(_slice_fill(bone | cavity, axis))))
    tissue = (hu > p.tissue_hu) & within
    if p.scalp_closing_voxels:
        tissue = ndimage.binary_closing(tissue, iterations=p.scalp_closing_voxels)
    scalp = _largest(np.asarray(ndimage.binary_fill_holes(tissue)) | outer)
    masks = {
        "bone": mask_volume(bone, like, boundary="bone", bone_hu=p.bone_hu),
        "inner_skull": mask_volume(cavity, like, boundary="inner_skull", bone_hu=p.bone_hu),
        "outer_skull": mask_volume(outer, like, boundary="outer_skull", bone_hu=p.bone_hu),
        "outer_scalp": mask_volume(scalp, like, boundary="outer_scalp", tissue_hu=p.tissue_hu),
    }
    meshes = {
        name: boundary_mesh(masks[name], iterations=p.smoothing_iterations, step=p.smoothing_step)
        for name in BOUNDARIES
    }
    return CTSkullTruth(
        masks,
        meshes,
        {
            "truth": "CT bone (HU) within the dataset head mask",
            "parameters": asdict(p),
            "ct_sha256": ct.metadata.get("source_sha256"),
            "mask_sha256": head_mask.metadata.get("source_sha256"),
            "superior_voxel_axis": axis,
            "definitions": {
                "bone": "HU > bone_hu in mask; closing; largest component; small holes filled",
                "inner_skull": (
                    "axial-slice fill of the enclosure-closed bone, minus bone; "
                    "3D hole fill; largest component"
                ),
                "outer_skull": "outer boundary of filled bone ∪ cavity",
                "outer_scalp": "HU > tissue_hu in mask; closing; filled; largest component",
            },
            "volumes_mm3": {k: float(v.array().sum() * voxel_mm3) for k, v in masks.items()},
        },
    )


@dataclass(frozen=True)
class FlagThresholds:
    metal_hu: float = 3000.0
    metal_region_voxels: int = 10
    truncation_slices: int = 3
    defect_search_voxels: int = 3
    defect_area_mm2: float = 200.0
    minimum_cavity_ml: float = 900.0
    dark_fraction_of_otsu: float = 0.5
    minimum_bone_dark_fraction: float = 0.5


def exclusion_flags(
    ct: Volume,
    head_mask: Volume,
    truth: CTSkullTruth,
    region: FittedRegion,
    *,
    t1: Volume | None = None,
    thresholds: FlagThresholds | None = None,
) -> dict[str, Any]:
    """Automatic exclusion flags; reported per case, never applied silently."""
    f = thresholds or FlagThresholds()
    hu = ct.array(np.float64)
    within = head_mask.array() > 0
    n = int(truth.provenance["parameters"]["padding_voxels"])
    like = truth.masks["bone"]
    region_padded = region.voxel_mask(like)
    region_native = region_padded[n:-n, n:-n, n:-n] if n else region_padded
    flags: dict[str, Any] = {}

    metal = (hu >= f.metal_hu) & within
    metal_region = int(np.sum(metal & region_native))
    flags["metal"] = {
        "flag": metal_region > f.metal_region_voxels,
        "voxels_total": int(metal.sum()),
        "voxels_in_region": metal_region,
        "threshold": {"hu": f.metal_hu, "region_voxels": f.metal_region_voxels},
    }

    axis, direction = superior_axis(ct)
    top = np.moveaxis(hu, axis, 0)
    top_mask = np.moveaxis(within, axis, 0)
    slab = slice(-f.truncation_slices, None) if direction > 0 else slice(0, f.truncation_slices)
    tissue_top = int(
        np.sum((top[slab] > truth.provenance["parameters"]["tissue_hu"]) & top_mask[slab])
    )
    bone_top = int(np.sum((top[slab] > truth.provenance["parameters"]["bone_hu"]) & top_mask[slab]))
    flags["vertex_truncation"] = {
        "flag": tissue_top > 0 or bone_top > 0,
        "tissue_voxels_top_slices": tissue_top,
        "bone_voxels_top_slices": bone_top,
        "superior_voxel_axis": axis,
        "superior_index_direction": direction,
        "slices": f.truncation_slices,
    }

    cavity = truth.masks["inner_skull"].array().astype(bool)
    bone = truth.masks["bone"].array().astype(bool)
    voxel_mm3 = float(np.prod(like.spacing_m * 1000))
    face_mm2 = voxel_mm3 ** (2 / 3)
    boundary = cavity & ~ndimage.binary_erosion(cavity) & region_padded
    near_bone = ndimage.binary_dilation(bone, iterations=f.defect_search_voxels)
    uncovered = boundary & ~near_bone
    labelled, count = ndimage.label(uncovered, structure=np.ones((3, 3, 3)))
    sizes: Any = np.bincount(labelled.ravel())[1:]
    largest_mm2 = float(sizes.max() * face_mm2) if count else 0.0
    cavity_ml = float(cavity.sum() * voxel_mm3 / 1000)
    flags["skull_defect"] = {
        "flag": largest_mm2 >= f.defect_area_mm2 or cavity_ml < f.minimum_cavity_ml,
        "largest_uncovered_patch_mm2": largest_mm2,
        "uncovered_fraction": float(uncovered.sum() / max(boundary.sum(), 1)),
        "cavity_ml": cavity_ml,
        "threshold": {
            "area_mm2": f.defect_area_mm2,
            "minimum_cavity_ml": f.minimum_cavity_ml,
            "search_voxels": f.defect_search_voxels,
        },
    }

    if t1 is None:
        flags["mr_ct_consistency"] = {"flag": None, "reason": "no T1 supplied"}
    else:
        if not t1.same_grid(ct):
            raise ValueError("MR/CT consistency check requires the paired identical grid")
        mr = t1.array(np.float64)
        dark = mr < f.dark_fraction_of_otsu * float(threshold_otsu(mr[within]))
        bone_native = bone[n:-n, n:-n, n:-n] if n else bone
        core = ndimage.binary_erosion(bone_native) & region_native
        fraction = float(np.sum(dark & core) / max(int(core.sum()), 1))
        flags["mr_ct_consistency"] = {
            "flag": fraction < f.minimum_bone_dark_fraction,
            "ct_bone_dark_in_mr_fraction": fraction,
            "bone_core_voxels": int(core.sum()),
            "threshold": {
                "dark_fraction_of_otsu": f.dark_fraction_of_otsu,
                "minimum_bone_dark_fraction": f.minimum_bone_dark_fraction,
            },
        }
    flags["any"] = any(v.get("flag") is True for v in flags.values() if isinstance(v, dict))
    flags["thresholds"] = asdict(f)
    return flags


def _surface_samples(mesh: Mesh) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    tri = mesh.vertices.xyz[mesh.faces] * 1000
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
    return tri.mean(axis=1), area


def _nearest_distance(
    points_mm: np.ndarray[Any, Any], mesh: Mesh, *, k: int
) -> np.ndarray[Any, Any]:
    """Point-to-triangle distance (mm) over the k nearest triangles by centroid."""
    tri = mesh.vertices.xyz[mesh.faces] * 1000
    k = min(k, len(tri))
    _, index = cKDTree(tri.mean(axis=1)).query(points_mm, k=k)
    index = np.asarray(index).reshape(len(points_mm), k)
    best = np.full(len(points_mm), np.inf)
    for j in range(k):
        best = np.minimum(best, _point_triangle(points_mm, tri[index[:, j]]))
    return best


def _inside(
    points_mm: np.ndarray[Any, Any], truth_mask: Volume | None, mesh: Mesh, budget: float
) -> tuple[np.ndarray[Any, Any], str]:
    if truth_mask is None or len(points_mm) * len(mesh.faces) <= budget:
        return contains(mesh, points_mm / 1000), "contains (generalized winding number)"
    voxel = truth_mask.grid.to_voxel(Points(points_mm / 1000, mesh.vertices.frame))
    level = ndimage.map_coordinates(
        truth_mask.array(np.float32), voxel.T, order=1, mode="constant", cval=0.0
    )
    return level > 0.5, "trilinear truth mask at level 0.5 (contains audited on a subsample)"


def boundary_metrics(
    estimate: Mesh,
    truth: Mesh,
    region: FittedRegion,
    *,
    truth_mask: Volume | None = None,
    k: int = 16,
    contains_budget: float = 2e8,
    audit_points: int = 256,
    seed: int = 11042,
) -> dict[str, Any]:
    """Signed mean (estimate→truth; + is outside truth), symmetric mean |d| and HD95, in mm.

    Distances are area-weighted over triangle centroids inside the evaluation region, as in
    ``soma.benchmarks.segmentation`` (``_quantile``). The sign comes from ``contains`` on the
    truth mesh; for large meshes, the trilinear truth mask is used and ``contains`` is audited
    on a seeded subsample whose agreement is reported.
    """
    pe, we = _surface_samples(estimate)
    pt, wt = _surface_samples(truth)
    me, mt = region.contains_mm(pe), region.contains_mm(pt)
    if not me.any() or not mt.any():
        raise ValueError("No surface inside the evaluation region")
    pe, we, pt, wt = pe[me], we[me], pt[mt], wt[mt]
    d_et = _nearest_distance(pe, truth, k=k)
    d_te = _nearest_distance(pt, estimate, k=k)
    inside, sign_method = _inside(pe, truth_mask, truth, contains_budget)
    signed = np.where(inside, -d_et, d_et)
    audit = None
    if sign_method.startswith("trilinear") and audit_points:
        rng = np.random.default_rng(seed)
        far = np.flatnonzero(d_et > 0.5)
        pick = rng.choice(far, size=min(audit_points, len(far)), replace=False) if len(far) else far
        if len(pick):
            exact = contains(truth, pe[pick] / 1000)
            audit = {"points": len(pick), "agreement": float(np.mean(exact == inside[pick]))}
    both_d, both_w = np.r_[d_et, d_te], np.r_[we, wt]
    return {
        "signed_mean_mm": float(np.average(signed, weights=we)),
        "mean_abs_mm": float(np.average(both_d, weights=both_w)),
        "HD95_mm": max(_quantile(d_et, we, 0.95), _quantile(d_te, wt, 0.95)),
        "directed_HD95_mm": {
            "estimate_to_truth": _quantile(d_et, we, 0.95),
            "truth_to_estimate": _quantile(d_te, wt, 0.95),
        },
        "evaluated_area_mm2": {"estimate": float(we.sum()), "truth": float(wt.sum())},
        "sign_convention": "positive = estimate outside the CT boundary",
        "sign_method": sign_method,
        "contains_audit": audit,
        "k_nearest_triangles": k,
    }


def _shell_length(
    mask_inner: Volume,
    mask_outer: Volume,
    origins_mm: np.ndarray[Any, Any],
    normals: np.ndarray[Any, Any],
    t_mm: np.ndarray[Any, Any],
) -> np.ndarray[Any, Any]:
    shell = (mask_outer.array().astype(bool) & ~mask_inner.array().astype(bool)).astype(np.uint8)
    samples = origins_mm[:, None, :] + t_mm[None, :, None] * normals[:, None, :]
    flat = samples.reshape(-1, 3) / 1000
    voxel = mask_outer.grid.to_voxel(Points(flat, Frame.RAS))
    values = ndimage.map_coordinates(shell, voxel.T, order=0, mode="constant", cval=0)
    step = float(t_mm[1] - t_mm[0])
    return np.asarray(values.reshape(len(origins_mm), len(t_mm)).sum(axis=1) * step)


def thickness_error(
    estimate_masks: dict[str, Volume],
    truth: CTSkullTruth,
    region: FittedRegion,
    *,
    window_mm: tuple[float, float] = (-10.0, 25.0),
    step_mm: float = 0.25,
) -> dict[str, Any]:
    """Skull thickness along outward CT inner-skull normals: shell length on the same ray.

    Thickness is the ray length inside (outer skull minus inner skull), within a fixed window
    around each CT inner-skull vertex; the estimate is measured on the identical ray.
    """
    mesh = truth.meshes["inner_skull"]
    origins = mesh.vertices.xyz * 1000
    keep = region.contains_mm(origins)
    if not keep.any():
        raise ValueError("No inner-skull vertices inside the evaluation region")
    normals = vertex_normals(mesh)[keep]
    origins = origins[keep]
    tri = mesh.vertices.xyz[mesh.faces]
    face_area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
    weights = np.zeros(len(mesh.vertices.xyz))
    for i in range(3):
        np.add.at(weights, mesh.faces[:, i], face_area / 3)
    weights = weights[keep]
    t = np.arange(window_mm[0], window_mm[1] + step_mm / 2, step_mm)
    ct = _shell_length(truth.masks["inner_skull"], truth.masks["outer_skull"], origins, normals, t)
    est = _shell_length(
        estimate_masks["inner_skull"], estimate_masks["outer_skull"], origins, normals, t
    )
    error = est - ct
    return {
        "mean_error_mm": float(np.average(error, weights=weights)),
        "mean_abs_error_mm": float(np.average(np.abs(error), weights=weights)),
        "ct_mean_thickness_mm": float(np.average(ct, weights=weights)),
        "estimate_mean_thickness_mm": float(np.average(est, weights=weights)),
        "rays": int(len(origins)),
        "window_mm": list(window_mm),
        "step_mm": step_mm,
        "sign_convention": "positive = estimate thicker than CT",
    }


def score_case(
    estimate_meshes: dict[str, Mesh],
    estimate_masks: dict[str, Volume],
    truth: CTSkullTruth,
    region: FittedRegion,
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "boundaries": {
            name: boundary_metrics(
                estimate_meshes[name],
                truth.meshes[name],
                region,
                truth_mask=truth.masks[name],
                **kwargs,
            )
            for name in BOUNDARIES
        },
        "thickness": thickness_error(estimate_masks, truth, region),
        "region": region.provenance(),
    }
