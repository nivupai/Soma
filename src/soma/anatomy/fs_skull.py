"""FreeSurfer watershed BEM surfaces as a measured MRI skull model, on a scanner-RAS grid.

The surfaces come from ``mne.bem.make_watershed_bem`` (FreeSurfer ``mri_watershed``) on a
conformed, bias-corrected, intensity-normalised T1. This module only imports the result:
it converts FreeSurfer surface-RAS (tkr) coordinates to scanner RAS and voxelises each
closed surface onto a target grid so it can be scored by ``soma.benchmarks.ct_skull``.
"""

from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from nibabel.freesurfer.io import read_geometry

from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.imaging.volumes import Volume

WATERSHED_FILES = {
    "inner_skull": "{subject}_inner_skull_surface",
    "outer_skull": "{subject}_outer_skull_surface",
    "outer_scalp": "{subject}_outer_skin_surface",
}


def tkr_to_scanner(t1_mgz: Path) -> np.ndarray[Any, Any]:
    """4x4 map from FreeSurfer surface RAS (mm) to scanner RAS (mm) for this T1."""
    image: Any = nib.load(t1_mgz)
    vox2ras = image.header.get_vox2ras()
    vox2ras_tkr = image.header.get_vox2ras_tkr()
    return np.asarray(vox2ras @ np.linalg.inv(vox2ras_tkr), dtype=float)


def load_watershed(subject_dir: Path, subject: str) -> dict[str, Mesh]:
    """Watershed BEM surfaces in scanner RAS metres (Soma's Mesh convention)."""
    to_scanner = tkr_to_scanner(subject_dir / "mri" / "T1.mgz")
    meshes = {}
    for name, pattern in WATERSHED_FILES.items():
        path = subject_dir / "bem" / "watershed" / pattern.format(subject=subject)
        coords, faces = read_geometry(str(path))
        xyz = (np.c_[coords, np.ones(len(coords))] @ to_scanner.T)[:, :3] / 1000.0
        meshes[name] = Mesh(
            Points(xyz, Frame.RAS),
            faces.astype(np.int64),
            {"source": "FreeSurfer mri_watershed via mne.bem.make_watershed_bem", "name": name},
        )
    return meshes


def voxelize(mesh: Mesh, like: Volume) -> np.ndarray[Any, Any]:
    """Inside mask of a closed triangle mesh on ``like``'s grid (scanline parity, axis 2).

    For each voxel column (i, j) the ray along the third voxel axis is intersected with every
    triangle whose projection covers the column; voxels between successive crossings (even-odd
    rule) are inside. Exact for closed, non-self-intersecting meshes up to voxel sampling.
    """
    shape = like.shape
    world_to_voxel = np.linalg.inv(like.affine_m)
    v = (np.c_[mesh.vertices.xyz, np.ones(len(mesh.vertices.xyz))] @ world_to_voxel.T)[:, :3]
    tri = v[np.asarray(mesh.faces)]
    hits: dict[tuple[int, int], list[float]] = {}
    for a, b, c in tri:
        lo = np.ceil(np.minimum(np.minimum(a[:2], b[:2]), c[:2])).astype(int)
        hi = np.floor(np.maximum(np.maximum(a[:2], b[:2]), c[:2])).astype(int)
        lo = np.maximum(lo, 0)
        hi = np.minimum(hi, np.asarray(shape[:2]) - 1)
        if (hi < lo).any():
            continue
        ii, jj = np.meshgrid(
            np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1), indexing="ij"
        )
        # Tiny fixed jitter keeps columns off triangle edges/vertices (no double counting).
        p = np.c_[ii.ravel(), jj.ravel()].astype(float) + np.array([1.3e-6, 2.9e-6])
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        w1 = ((b[1] - c[1]) * (p[:, 0] - c[0]) + (c[0] - b[0]) * (p[:, 1] - c[1])) / d
        w2 = ((c[1] - a[1]) * (p[:, 0] - c[0]) + (a[0] - c[0]) * (p[:, 1] - c[1])) / d
        w3 = 1 - w1 - w2
        inside = (w1 > 0) & (w2 > 0) & (w3 > 0)
        z = w1 * a[2] + w2 * b[2] + w3 * c[2]
        for (i, j), zz in zip(np.rint(p[inside]).astype(int), z[inside], strict=True):
            hits.setdefault((int(i), int(j)), []).append(float(zz))
    out = np.zeros(shape, dtype=bool)
    k = np.arange(shape[2])
    for (i, j), zs in hits.items():
        zs_sorted = np.sort(zs)
        for start, stop in zip(zs_sorted[0::2], zs_sorted[1::2], strict=False):
            out[i, j, (k >= start) & (k <= stop)] = True
    return out


def offset_mesh(mesh: Mesh, offset_mm: float) -> Mesh:
    """Move every vertex along its outward normal by ``offset_mm`` (negative = inward).

    Used for a bias correction calibrated on development cases only. Winding is checked so
    "outward" is geometric, whatever the source file's convention.
    """
    from soma.anatomy.t1_skull import vertex_normals

    xyz = mesh.vertices.xyz
    normals = vertex_normals(mesh)
    if float(np.mean(np.sum(normals * (xyz - xyz.mean(axis=0)), axis=1))) < 0:
        normals = -normals
    moved = xyz + normals * (offset_mm / 1000.0)
    return Mesh(
        Points(moved, mesh.vertices.frame),
        np.asarray(mesh.faces),
        {**mesh.metadata, "normal_offset_mm": offset_mm},
    )


def crop_head_top(t1: Volume, height_mm: float = 220.0, margin_mm: float = 10.0) -> Volume:
    """Keep the superior ``height_mm`` of the T1 head (MRI-only rule; protocol v3.1).

    The top of the head is the most superior slice whose Otsu foreground covers at least 1% of
    the largest slice's foreground; nothing above it is removed. Slices more than
    ``height_mm`` below it (neck, shoulders) are dropped, and the in-plane extent is cut to the
    remaining foreground bounding box plus ``margin_mm``. World coordinates are preserved.
    """
    from skimage.filters import threshold_otsu

    from soma.benchmarks.ct_skull import superior_axis

    data = t1.array(np.float32)
    foreground = data > threshold_otsu(data)
    axis, direction = superior_axis(t1)
    area = np.moveaxis(foreground, axis, 0).sum(axis=(1, 2))
    present = np.flatnonzero(area >= 0.01 * float(np.max(area)))
    n_axis = data.shape[axis]
    keep = int(np.ceil(height_mm / float(t1.spacing_m[axis] * 1000)))
    if direction > 0:
        top = int(np.max(present))
        bounds = {axis: (max(top - keep + 1, 0), n_axis)}
    else:
        top = int(np.min(present))
        bounds = {axis: (0, min(top + keep, n_axis))}
    slab = [slice(None)] * 3
    slab[axis] = slice(*bounds[axis])
    kept = foreground[tuple(slab)]
    for other in (a for a in range(3) if a != axis):
        profile = np.flatnonzero(np.moveaxis(kept, other, 0).any(axis=(1, 2)))
        pad_voxels = int(np.ceil(margin_mm / float(t1.spacing_m[other] * 1000)))
        bounds[other] = (
            max(int(np.min(profile)) - pad_voxels, 0),
            min(int(np.max(profile)) + pad_voxels + 1, data.shape[other]),
        )
    index = tuple(slice(*bounds[a]) for a in range(3))
    affine = np.array(t1.affine_m, dtype=float)
    affine[:3, 3] = affine[:3, 3] + affine[:3, :3] @ np.array([bounds[a][0] for a in range(3)])
    return Volume(
        np.ascontiguousarray(t1.array()[index]),
        affine,
        t1.kind,
        {
            **t1.metadata,
            "crop_head_top": {
                "height_mm": height_mm,
                "margin_mm": margin_mm,
                "voxel_bounds": [list(bounds[a]) for a in range(3)],
            },
        },
    )
