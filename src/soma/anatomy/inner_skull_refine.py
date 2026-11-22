"""Learned inner-skull refinement: per-vertex normal correction predicted from MRI only.

Starting from the calibrated watershed inner skull, each vertex gets features sampled from the
subject's own MRI (normalised T1 profile along the outward normal, and the signed distance to
SynthSeg's intracranial boundary along that profile). A regressor trained on development cases
predicts the signed distance from the vertex to the CT inner skull; the vertex is moved by minus
that prediction, after smoothing the corrections over the mesh. CT is used only as the training
target, never at inference.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import ndimage

from soma.anatomy.t1_skull import vertex_normals
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.imaging.volumes import Volume

PROFILE_MM = tuple(float(x) for x in np.arange(-10.0, 10.5, 1.0))


@dataclass(frozen=True)
class RefineParameters:
    profile_mm: tuple[float, ...] = PROFILE_MM
    smoothing_iterations: int = 10
    max_correction_mm: float = 6.0


def outward_normals(mesh: Mesh) -> np.ndarray[Any, Any]:
    xyz = mesh.vertices.xyz
    n = vertex_normals(mesh)
    if float(np.mean(np.sum(n * (xyz - xyz.mean(axis=0)), axis=1))) < 0:
        n = -n
    return np.asarray(n)


def signed_distance_mm(mask: np.ndarray[Any, Any], spacing_mm: np.ndarray[Any, Any]) -> Any:
    """Signed Euclidean distance to a mask boundary (mm): positive outside, negative inside."""
    inside = ndimage.distance_transform_edt(mask, sampling=spacing_mm)
    outside = ndimage.distance_transform_edt(~mask, sampling=spacing_mm)
    return outside - inside


def _sample(volume_data: Any, like: Volume, xyz_m: np.ndarray[Any, Any], order: int = 1) -> Any:
    voxel = like.grid.to_voxel(Points(xyz_m, Frame.RAS))
    return ndimage.map_coordinates(volume_data, voxel.T, order=order, mode="nearest")


def t1_scale(t1: Volume, synthseg_native: Volume) -> float:
    """Median T1 in cerebral white matter (SynthSeg 2/41): a per-subject intensity unit."""
    labels = synthseg_native.array()
    wm = np.isin(labels, [2, 41])
    value = float(np.median(t1.array(np.float64)[wm])) if wm.any() else 0.0
    return value if value > 0 else float(np.percentile(t1.array(np.float64), 99))


def features(
    mesh: Mesh,
    t1: Volume,
    synthseg_native: Volume,
    *,
    parameters: RefineParameters | None = None,
) -> np.ndarray[Any, Any]:
    """Per-vertex feature matrix (MRI only). ``synthseg_native`` must be on the T1 grid."""
    p = parameters or RefineParameters()
    if not synthseg_native.same_grid(t1):
        raise ValueError("SynthSeg labels must be on the T1 grid")
    xyz = mesh.vertices.xyz
    normals = outward_normals(mesh)
    t = np.asarray(p.profile_mm) / 1000.0
    samples = (xyz[:, None, :] + t[None, :, None] * normals[:, None, :]).reshape(-1, 3)
    scale = t1_scale(t1, synthseg_native)
    profile = _sample(t1.array(np.float32), t1, samples).reshape(len(xyz), len(t)) / scale
    icv = synthseg_native.array() > 0
    sd = signed_distance_mm(icv, t1.spacing_m * 1000).astype(np.float32)
    icv_profile = _sample(sd, t1, samples).reshape(len(xyz), len(t))
    gradient = np.diff(profile, axis=1)
    centre = xyz - xyz.mean(axis=0)
    direction = centre / np.maximum(np.linalg.norm(centre, axis=1, keepdims=True), 1e-9)
    return np.hstack([profile, gradient, icv_profile, direction, normals]).astype(np.float32)


def targets(mesh: Mesh, ct_cavity: Volume) -> np.ndarray[Any, Any]:
    """Signed distance (mm) from each vertex to the CT inner skull: + means vertex is outside."""
    mask = ct_cavity.array().astype(bool)
    sd = signed_distance_mm(mask, ct_cavity.spacing_m * 1000).astype(np.float32)
    return np.asarray(_sample(sd, ct_cavity, mesh.vertices.xyz))


def smooth_on_mesh(mesh: Mesh, values: np.ndarray[Any, Any], iterations: int) -> Any:
    faces = np.asarray(mesh.faces)
    n = len(mesh.vertices.xyz)
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.vstack([edges, edges[:, ::-1]])
    degree = np.bincount(edges[:, 0], minlength=n).astype(float)
    v = values.astype(float).copy()
    for _ in range(iterations):
        total = np.bincount(edges[:, 0], weights=v[edges[:, 1]], minlength=n)
        v = 0.5 * v + 0.5 * total / np.maximum(degree, 1)
    return v


def apply_correction(
    mesh: Mesh, predicted_mm: np.ndarray[Any, Any], parameters: RefineParameters | None = None
) -> Mesh:
    """Move each vertex inward by its smoothed, clipped predicted outside-distance."""
    p = parameters or RefineParameters()
    correction = np.clip(
        smooth_on_mesh(mesh, predicted_mm, p.smoothing_iterations),
        -p.max_correction_mm,
        p.max_correction_mm,
    )
    xyz = mesh.vertices.xyz - outward_normals(mesh) * (correction[:, None] / 1000.0)
    return Mesh(
        Points(xyz, mesh.vertices.frame),
        np.asarray(mesh.faces),
        {**mesh.metadata, "learned_inner_skull_refinement": True},
    )
