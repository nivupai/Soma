"""Three-dimensional MRI arrays with explicit RAS+ metre-valued grid geometry."""

import hashlib
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Literal, cast

import nibabel as nib
import numpy as np
from numpy.typing import NDArray

from soma.geometry.coordinates import VoxelMap, validate_affine


@dataclass(frozen=True)
class Volume:
    data: Any
    affine_m: NDArray[np.float64]
    kind: Literal["intensity", "labels"] = "intensity"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.data.shape) != 3 or any(int(n) < 1 for n in self.data.shape):
            raise ValueError("An anatomical Volume must be 3D; select an explicit 4D frame")
        if np.dtype(self.data.dtype).kind not in "buif":
            raise ValueError(
                "Volumes require real scalar numeric data, not complex/vector/object data"
            )
        if self.kind not in ("intensity", "labels"):
            raise ValueError("Unknown volume kind")
        a = validate_affine(self.affine_m).copy()
        spacing = np.linalg.norm(a[:3, :3], axis=0)
        if np.any(spacing < 1e-5) or np.any(spacing > 0.1):
            raise ValueError("Implausible voxel spacing in metres (allowed 0.01–100 mm)")
        a.flags.writeable = False
        object.__setattr__(self, "affine_m", a)

    @property
    def shape(self) -> tuple[int, int, int]:
        return tuple(int(n) for n in self.data.shape)  # type: ignore[return-value]

    @property
    def dtype(self) -> np.dtype[Any]:
        return cast("np.dtype[Any]", np.dtype(self.data.dtype))

    def array(self, dtype: Any = None) -> NDArray[Any]:
        """Materialize only when requested; preserve stored/scaled dtype by default."""
        return np.asanyarray(self.data, dtype=dtype)

    @property
    def spacing_m(self) -> NDArray[np.float64]:
        return np.linalg.norm(self.affine_m[:3, :3], axis=0)

    @property
    def grid_id(self) -> str:
        return hashlib.sha256(self.affine_m.tobytes() + str(self.shape).encode()).hexdigest()

    @property
    def grid(self) -> VoxelMap:
        return VoxelMap(self.affine_m, self.grid_id)

    def same_grid(self, other: "Volume", atol_m: float = 1e-9) -> bool:
        return self.shape == other.shape and bool(
            np.allclose(self.affine_m, other.affine_m, atol=atol_m, rtol=0)
        )

    def geometry(self) -> dict[str, Any]:
        corners = np.array(list(product(*[(-0.5, n - 0.5) for n in self.shape])))
        xyz = self.grid.to_world(corners).xyz
        return {
            "shape": self.shape,
            "stored_dtype": str(self.dtype),
            "voxel_to_RAS_m": self.affine_m.tolist(),
            "spacing_m": self.spacing_m.tolist(),
            "axis_codes": list(nib.aff2axcodes(self.affine_m)),
            "storage_determinant": float(np.linalg.det(self.affine_m[:3, :3])),
            "voxel_volume_m3": float(abs(np.linalg.det(self.affine_m[:3, :3]))),
            "physical_corner_bounds_m": [xyz.min(axis=0).tolist(), xyz.max(axis=0).tolist()],
            "grid_id": self.grid_id,
            "frame": "RAS+",
            "physical_units": "m",
            "kind": self.kind,
        }
