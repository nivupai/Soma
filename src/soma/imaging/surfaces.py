"""Physical triangular surfaces extracted from voxel labels, independent of rendering."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from skimage.measure import marching_cubes

from soma.geometry import Frame, Points
from soma.imaging.segmentation import require_labels
from soma.imaging.volumes import Volume


@dataclass(frozen=True)
class Mesh:
    vertices: Points
    faces: np.ndarray[Any, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        faces = np.asarray(self.faces)
        if faces.ndim != 2 or faces.shape[1] != 3 or not np.issubdtype(faces.dtype, np.integer):
            raise ValueError("Triangle connectivity must be an integer n by 3 array")
        if not len(faces) or faces.min() < 0 or faces.max() >= len(self.vertices.xyz):
            raise ValueError("Invalid triangle vertex indices")
        faces = faces.copy()
        faces.flags.writeable = False
        object.__setattr__(self, "faces", faces)


def extract_surface(volume: Volume, *, label: int = 1) -> Mesh:
    mask = require_labels(volume) == label
    if not mask.any() or mask.all():
        raise ValueError("Label needs an interior and exterior")
    if any(np.take(mask, i, axis=axis).any() for axis in range(3) for i in (0, -1)):
        raise ValueError("Mask touches image boundary; surface may be clipped/open")
    vertices, faces, _, _ = marching_cubes(
        mask.astype(np.float32), level=0.5, gradient_direction="descent", allow_degenerate=False
    )
    xyz = volume.grid.to_world(vertices).xyz
    # Marching-cubes winding may be inward and affine reflections reverse it.
    # For this extracted closed boundary, orient total signed volume outward.
    triangles = xyz[faces]
    signed = (
        np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6
    )
    if signed < 0:
        faces = faces[:, [0, 2, 1]]
    return Mesh(
        Points(xyz, Frame.RAS),
        faces,
        {
            "source_grid": volume.geometry(),
            "source_metadata": volume.metadata,
            "label": label,
            "method": "skimage.marching_cubes_0.5",
            "orientation": "positive_total_signed_volume; component orientation checked separately",
            "units": "m",
        },
    )


def smooth(mesh: Mesh, *, iterations: int, step: float = 0.1) -> Mesh:
    if not 0 <= iterations <= 100 or not 0 < step <= 0.5:
        raise ValueError("Explicit bounded smoothing parameters required")
    from scipy.sparse import coo_matrix

    edges = np.vstack([mesh.faces[:, [0, 1]], mesh.faces[:, [1, 2]], mesh.faces[:, [2, 0]]])
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    n = len(mesh.vertices.xyz)
    adjacency = coo_matrix(
        (
            np.ones(2 * len(edges)),
            (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]]),
        ),
        shape=(n, n),
    ).tocsr()
    degrees = np.asarray(adjacency.sum(axis=1)).ravel()
    xyz = mesh.vertices.xyz.copy()
    for _ in range(iterations):
        xyz += step * (adjacency @ xyz / np.maximum(degrees[:, None], 1) - xyz)
    from soma.imaging.mesh_quality import mesh_quality

    result = Mesh(
        Points(xyz, mesh.vertices.frame),
        mesh.faces,
        {
            **mesh.metadata,
            "smoothing": {
                "iterations": iterations,
                "step": step,
                "max_vertex_change_m": float(
                    np.max(np.linalg.norm(xyz - mesh.vertices.xyz, axis=1))
                ),
                "connectivity_preserved": True,
            },
        },
    )
    before, after = (
        mesh_quality(mesh, self_intersections=False),
        mesh_quality(result, self_intersections=False),
    )
    result.metadata["smoothing"].update(
        {
            "area_change_m2": after["surface_area_m2"] - before["surface_area_m2"],
            "signed_volume_change_m3": after["signed_volume_m3"] - before["signed_volume_m3"],
            "euler_before": before["euler_characteristic"],
            "euler_after": after["euler_characteristic"],
        }
    )
    return result


def isosurface(volume: Volume, *, level: float) -> Mesh:
    """Scalar-field isosurface, with positive interior and negative exterior.

    Useful for analytic geometry benchmarks; a scalar intensity level alone is
    not an anatomical tissue segmentation or conductor boundary.
    """
    data = volume.array()
    if not np.isfinite(data).all() or not np.min(data) < level < np.max(data):
        raise ValueError("Finite scalar data crossing the requested level required")
    if any(np.take(data, i, axis=axis).max() >= level for axis in range(3) for i in (0, -1)):
        raise ValueError("Positive interior touches the image border")
    indices, faces, _, _ = marching_cubes(
        data.astype(np.float32), level=level, allow_degenerate=False
    )
    xyz = volume.grid.to_world(indices).xyz
    triangles = xyz[faces]
    signed = (
        np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6
    )
    if signed < 0:
        faces = faces[:, [0, 2, 1]]
    return Mesh(
        Points(xyz, Frame.RAS),
        faces,
        {
            "source_grid": volume.geometry(),
            "source_metadata": volume.metadata,
            "method": "scalar marching cubes",
            "level": level,
            "units": "m",
        },
    )
