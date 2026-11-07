"""Identified image grids map dimensionless voxel indices to RAS+ metres.

Voxel maps permit reflections: left-handed array storage is not a reflected
physical anatomy. They deliberately do not weaken the rigid physical Transform.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from soma.geometry.frames import Frame, Points
from soma.geometry.transforms import Transform

Array = NDArray[np.float64]


def validate_affine(matrix: Array) -> Array:
    a = np.asarray(matrix, dtype=float)
    if a.shape != (4, 4) or not np.isfinite(a).all():
        raise ValueError("Affine must be finite 4 by 4")
    if not np.allclose(a[3], [0, 0, 0, 1], atol=1e-12, rtol=0):
        raise ValueError("Invalid homogeneous affine")
    singular = np.linalg.svd(a[:3, :3], compute_uv=False)
    if singular[-1] <= 0 or singular[-1] / singular[0] < 1e-8:
        raise ValueError("Singular or nearly singular spatial affine")
    return a


@dataclass(frozen=True)
class VoxelMap:
    affine_m: Array
    grid_id: str

    def __post_init__(self) -> None:
        if not self.grid_id:
            raise ValueError("An identified voxel grid is required")
        a = validate_affine(self.affine_m).copy()
        a.flags.writeable = False
        object.__setattr__(self, "affine_m", a)

    def to_world(self, indices: Array) -> Points:
        x = np.asarray(indices, dtype=float)
        if x.ndim != 2 or x.shape[1] != 3 or not np.isfinite(x).all():
            raise ValueError("Voxel indices must be finite n by 3")
        return Points(x @ self.affine_m[:3, :3].T + self.affine_m[:3, 3], Frame.RAS)

    def to_voxel(self, points: Points) -> Array:
        if points.frame != Frame.RAS:
            raise ValueError("Voxel map requires RAS+ physical points in metres")
        return np.asarray(
            np.linalg.solve(self.affine_m[:3, :3], (points.xyz - self.affine_m[:3, 3]).T).T
        )


def ras_lps() -> Transform:
    return Transform(Frame.RAS, Frame.LPS, np.diag([-1.0, -1, 1, 1]))


def transform_vectors(matrix: Array, vectors: Array, *, normals: bool = False) -> Array:
    a = validate_affine(matrix)[:3, :3]
    x = np.asarray(vectors, dtype=float)
    if x.ndim != 2 or x.shape[1] != 3 or not np.isfinite(x).all():
        raise ValueError("Vectors must be finite n by 3")
    result = np.linalg.solve(a.T, x.T).T if normals else x @ a.T
    if normals:
        lengths = np.linalg.norm(result, axis=1)
        if np.any(lengths == 0):
            raise ValueError("Zero normals cannot be normalized")
        result /= lengths[:, None]
    return np.asarray(result, dtype=float)
