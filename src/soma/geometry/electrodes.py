"""Dataset-independent sensor identities and conservative geometric diagnostics."""

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.distance import pdist

from soma.geometry.frames import Frame, Points


@dataclass(frozen=True)
class Electrodes:
    names: tuple[str, ...]
    points: Points

    def __post_init__(self) -> None:
        if len(self.names) != len(self.points.xyz) or len(set(self.names)) != len(self.names):
            raise ValueError("Unique names must match electrode coordinates")
        radii = np.linalg.norm(self.points.xyz, axis=1)
        if len(radii) < 2 or np.any(radii < 0.01) or np.any(radii > 0.3):
            raise ValueError("Implausible sensor geometry in metres")
        if np.min(pdist(self.points.xyz)) < 1e-5:
            raise ValueError("Coincident electrodes")

    def scalp_diagnostics(self, scalp: Points) -> dict[str, float | str]:
        if scalp.frame != self.points.frame:
            raise ValueError("Scalp and electrodes must share a coordinate frame")
        distances, _ = cKDTree(scalp.xyz).query(self.points.xyz)
        return {
            "distance_kind": "nearest_scalp_vertex_not_exact_surface_distance",
            "median_distance_m": float(np.median(distances)),
            "max_distance_m": float(np.max(distances)),
            "minimum_interelectrode_distance_m": float(np.min(pdist(self.points.xyz))),
        }

    def require_head(self) -> None:
        if self.points.frame != Frame.HEAD:
            raise ValueError("MNE EEG input requires head coordinates")
