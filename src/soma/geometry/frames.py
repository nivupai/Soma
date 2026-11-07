"""Explicit right-handed coordinate frames; internal length unit is always metres."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray


class Frame(StrEnum):
    VOXEL = "voxel"
    RAS = "ras"
    LPS = "lps"
    HEAD = "head"
    MRI = "mri"
    DEVICE = "device"
    TEMPLATE_MRI = "template_mri"


@dataclass(frozen=True)
class Points:
    xyz: NDArray[np.float64]
    frame: Frame
    unit: str = "m"

    def __post_init__(self) -> None:
        xyz = np.array(self.xyz, dtype=float, copy=True)
        if self.frame == Frame.VOXEL:
            raise ValueError("Voxel indices are dimensionless; use VoxelMap")
        if self.unit != "m":
            raise ValueError("Internal geometry must use metres; convert explicitly")
        if xyz.ndim != 2 or xyz.shape[1] != 3 or not np.isfinite(xyz).all():
            raise ValueError("Points must be finite (n, 3) coordinates")
        if not isinstance(self.frame, Frame):
            raise ValueError("An explicit Frame is required")
        if np.any(np.linalg.norm(xyz, axis=1) > 2):
            raise ValueError("Implausible head geometry: check millimetres versus metres")
        xyz.flags.writeable = False
        object.__setattr__(self, "xyz", xyz)

    @classmethod
    def from_mm(cls, xyz: NDArray[np.float64], frame: Frame) -> "Points":
        return cls(np.asarray(xyz, dtype=float) / 1000, frame)


@dataclass(frozen=True)
class SourceCoordinates:
    points: Points
    identifiers: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if len(self.identifiers) != len(self.points.xyz):
            raise ValueError("Source identifiers must correspond one to one with coordinates")
        if len(set(self.identifiers)) != len(self.identifiers):
            raise ValueError("Source identifiers must be unique")
