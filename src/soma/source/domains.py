"""Explicit MRI voxel-measure domains for M31 moment priors; never a ball substitution."""

import hashlib
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from soma.geometry.coordinates import validate_affine

Array = NDArray[np.float64]


@dataclass(frozen=True)
class SourceDomain:
    mask: NDArray[np.bool_]
    voxel_to_mri_m: Array
    frame: str = "MRI_surface_RAS_m"

    def __post_init__(self) -> None:
        mask = np.asarray(self.mask)
        a = validate_affine(self.voxel_to_mri_m).copy()
        spacing = np.linalg.norm(a[:3, :3], axis=0)
        if (
            mask.ndim != 3
            or mask.dtype != np.dtype(bool)
            or not mask.any()
            or self.frame != "MRI_surface_RAS_m"
            or np.any(spacing < 1e-5)
            or np.any(spacing > 0.1)
        ):
            raise ValueError(
                "Explicit binary MRI domain, surface-RAS frame and metre affine required"
            )
        mask = mask.copy()
        mask.flags.writeable = False
        a.flags.writeable = False
        object.__setattr__(self, "mask", mask)
        object.__setattr__(self, "voxel_to_mri_m", a)

    @property
    def volume_m3(self) -> float:
        return float(self.mask.sum() * abs(np.linalg.det(self.voxel_to_mri_m[:3, :3])))

    @property
    def identity(self) -> str:
        # MRI-derived fingerprint: private provenance only, never public exports.
        return hashlib.sha256(
            str(self.mask.shape).encode()
            + self.frame.encode()
            + self.mask.tobytes()
            + self.voxel_to_mri_m.astype("<f8").tobytes()
        ).hexdigest()

    def centers(self) -> Array:
        ijk = np.argwhere(self.mask)
        return np.asarray(ijk @ self.voxel_to_mri_m[:3, :3].T + self.voxel_to_mri_m[:3, 3], float)

    def positions(self, grid: Array) -> Array:
        p = np.asarray(grid, float)
        if (
            p.ndim != 2
            or p.shape[1] != 3
            or not len(p)
            or not np.isfinite(p).all()
            or np.any(np.linalg.norm(p, axis=1) > 2)
            or len(np.unique(p, axis=0)) != len(p)
        ):
            raise ValueError("Unique finite MRI surface-RAS metre source coordinates required")
        inv = np.linalg.inv(self.voxel_to_mri_m)
        ijk = np.rint(p @ inv[:3, :3].T + inv[:3, 3]).astype(int)
        if (
            np.any(ijk < 0)
            or np.any(ijk >= np.array(self.mask.shape))
            or not self.mask[tuple(ijk.T)].all()
        ):
            raise ValueError("Source outside declared MRI voxel domain")
        return p

    def weights(self, grid: Array) -> Array:
        p = self.positions(grid)
        nearest = cKDTree(p).query(self.centers())[1]
        v = np.bincount(nearest, minlength=len(p)).astype(float) * abs(
            np.linalg.det(self.voxel_to_mri_m[:3, :3])
        )
        if np.any(v <= 0) or not np.isclose(v.sum(), self.volume_m3, rtol=1e-12, atol=0):
            raise ValueError("Invalid anatomical quadrature mass")
        return np.asarray(v, dtype=float)
