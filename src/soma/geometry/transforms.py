"""Column-vector convention: destination = matrix @ source homogeneous point."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from soma.geometry.frames import Frame, Points


@dataclass(frozen=True)
class Transform:
    source: Frame
    destination: Frame
    matrix: NDArray[np.float64]
    rigid: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.source, Frame) or not isinstance(self.destination, Frame):
            raise ValueError("Explicit source and destination Frames are required")
        matrix = np.array(self.matrix, dtype=float, copy=True)
        if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
            raise ValueError("Transform must be finite 4 by 4")
        if not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-12, rtol=0):
            raise ValueError("Invalid homogeneous last row")
        rotation = matrix[:3, :3]
        determinant = np.linalg.det(rotation)
        if determinant <= 1e-12:
            raise ValueError("Transform must be nonsingular and preserve handedness")
        if self.rigid and (
            not np.allclose(rotation.T @ rotation, np.eye(3), atol=5e-7, rtol=0)
            or not np.isclose(determinant, 1, atol=5e-7, rtol=0)
        ):
            raise ValueError("Rigid transform requires an orthogonal proper rotation")
        if np.linalg.norm(matrix[:3, 3]) > 2:
            raise ValueError("Implausible translation; check units")
        matrix.flags.writeable = False
        object.__setattr__(self, "matrix", matrix)

    def apply(self, points: Points) -> Points:
        if points.frame != self.source:
            raise ValueError("Point and transform source frames differ")
        return Points(points.xyz @ self.matrix[:3, :3].T + self.matrix[:3, 3], self.destination)

    def inverse(self) -> "Transform":
        return Transform(
            self.destination,
            self.source,
            np.asarray(np.linalg.solve(self.matrix, np.eye(4)), dtype=np.float64),
            self.rigid,
        )

    def then(self, following: "Transform") -> "Transform":
        if self.destination != following.source:
            raise ValueError("Incompatible transformation composition")
        return Transform(
            self.source,
            following.destination,
            following.matrix @ self.matrix,
            self.rigid and following.rigid,
        )

    def to_mne(self) -> Any:
        """Template MRI is explicitly mapped to MNE's MRI constant at this boundary."""
        import mne

        names = {Frame.TEMPLATE_MRI: "mri", Frame.DEVICE: "meg"}
        return mne.transforms.Transform(
            names.get(self.source, self.source.value),
            names.get(self.destination, self.destination.value),
            self.matrix.copy(),
        )

    @classmethod
    def from_mne(cls, transform: Any, *, template: bool = False) -> "Transform":
        """Caller must state whether MRI coordinates belong to a template."""
        frames = {1: Frame.DEVICE, 4: Frame.HEAD, 5: Frame.TEMPLATE_MRI if template else Frame.MRI}
        try:
            return cls(
                frames[int(transform["from"])], frames[int(transform["to"])], transform["trans"]
            )
        except KeyError as exc:
            raise ValueError("Unsupported MNE coordinate frame") from exc
