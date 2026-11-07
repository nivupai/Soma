"""Selected linear PSFs/CTFs, never a dense full cortical resolution matrix."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

Array = NDArray[np.float64]


@dataclass(frozen=True)
class Resolution:
    kernel: Array
    forward: Array
    linear: bool = True
    max_selected: int = 128

    def __post_init__(self) -> None:
        if not self.linear:
            raise ValueError("A nonlinear vector magnitude has no fixed linear resolution kernel")
        if (
            self.kernel.ndim != 2
            or self.forward.ndim != 2
            or self.kernel.shape[::-1] != self.forward.shape
        ):
            raise ValueError("Kernel and forward dimensions differ")
        if not np.isfinite(self.kernel).all() or not np.isfinite(self.forward).all():
            raise ValueError("Resolution operators must be finite")

    def _indices(self, indices: list[int]) -> None:
        if not indices or len(indices) > self.max_selected:
            raise ValueError("Select a bounded nonempty source subset")
        if min(indices) < 0 or max(indices) >= self.forward.shape[1]:
            raise ValueError("Source index outside forward")

    def psf(self, indices: list[int]) -> Array:
        self._indices(indices)
        return self.kernel @ self.forward[:, indices]

    def ctf(self, indices: list[int]) -> Array:
        self._indices(indices)
        return self.kernel[indices] @ self.forward

    def apply(self, source: Array) -> Array:
        return np.asarray(self.kernel @ (self.forward @ source), dtype=float)

    @property
    def diagonal(self) -> Array:
        return np.asarray(np.einsum("ij,ji->i", self.kernel, self.forward), dtype=float)


def spatial_metrics(
    psf: Array, truth_index: int, coordinates: Array, geodesic_m: Array | None = None
) -> dict[str, Any]:
    if psf.ndim != 1 or coordinates.shape != (len(psf), 3) or not np.isfinite(psf).all():
        raise ValueError("Expected one signed PSF and matching coordinates")
    energy = psf * psf
    if energy.sum() == 0:
        raise ValueError("A zero PSF has no localization peak")
    peak = int(np.argmax(np.abs(psf)))
    distance = np.linalg.norm(coordinates - coordinates[truth_index], axis=1)
    result: dict[str, Any] = {
        "truth_index": truth_index,
        "peak_index": peak,
        "peak_euclidean_m": float(distance[peak]),
        "dispersion_euclidean_m": float(np.sqrt(energy @ (distance * distance) / energy.sum())),
        "off_target_energy_fraction": float(1 - energy[truth_index] / energy.sum()),
        "energy_outside_20mm_fraction": float(energy[distance > 0.02].sum() / energy.sum()),
    }
    if geodesic_m is not None:
        if geodesic_m.shape != psf.shape:
            raise ValueError("Geodesic distances must match sources")
        finite = np.isfinite(geodesic_m)
        result["peak_geodesic_m"] = float(geodesic_m[peak]) if finite[peak] else None
        result["within_hemisphere_geodesic_dispersion_m"] = float(
            np.sqrt(energy[finite] @ geodesic_m[finite] ** 2 / energy[finite].sum())
        )
        result["other_hemisphere_energy_fraction"] = float(energy[~finite].sum() / energy.sum())
    return result


def cortical_distances(src: Any, indices: list[int]) -> Array:
    """White mesh edge shortest paths in metres, infinity across hemispheres.

    Edge paths approximate a surface geodesic; not straight-line head distance.
    Only requested seeds are evaluated, with at most one hemisphere graph alive.
    """
    counts = [len(s["vertno"]) for s in src]
    out = np.full((len(indices), sum(counts)), np.inf)
    offset = 0
    for hemi, count in enumerate(counts):
        seeds = [
            (row, index - offset)
            for row, index in enumerate(indices)
            if offset <= index < offset + count
        ]
        if seeds:
            surface = src[hemi]
            edges = np.vstack(
                [surface["tris"][:, [0, 1]], surface["tris"][:, [1, 2]], surface["tris"][:, [2, 0]]]
            )
            edges = np.unique(np.sort(edges, axis=1), axis=0)
            length = np.linalg.norm(surface["rr"][edges[:, 0]] - surface["rr"][edges[:, 1]], axis=1)
            graph = coo_matrix(
                (
                    np.r_[length, length],
                    (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]]),
                ),
                shape=(len(surface["rr"]),) * 2,
            ).tocsr()
            for row, local in seeds:
                distances = dijkstra(graph, directed=False, indices=int(surface["vertno"][local]))
                out[row, offset : offset + count] = distances[surface["vertno"]]
        offset += count
    return out
