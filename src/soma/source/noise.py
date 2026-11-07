"""Rank-aware covariance and whitening on an explicitly retained sensor subspace."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


def average_projector(n_channels: int) -> Array:
    if n_channels < 2:
        raise ValueError("Average reference requires at least two channels")
    return np.eye(n_channels) - np.ones((n_channels, n_channels)) / n_channels


def validate_projector(projector: Array, n: int) -> Array:
    p = np.asarray(projector, dtype=float)
    if p.shape != (n, n) or not np.isfinite(p).all():
        raise ValueError("Invalid projector shape or values")
    if not np.allclose(p, p.T, atol=1e-10) or not np.allclose(p @ p, p, atol=1e-10):
        raise ValueError("Projector must be symmetric and idempotent")
    return p


@dataclass(frozen=True)
class NoiseModel:
    covariance: Array
    channels: tuple[str, ...]
    projector: Array
    kind: str = "unspecified_background"
    rtol: float = 1e-10

    def __post_init__(self) -> None:
        c = np.asarray(self.covariance, dtype=float)
        n = len(self.channels)
        if len(set(self.channels)) != n or c.shape != (n, n) or not np.isfinite(c).all():
            raise ValueError("Invalid covariance or channel identities")
        p = validate_projector(self.projector, n)
        scale = max(float(np.max(np.abs(c))), np.finfo(float).tiny)
        if not np.allclose(c, c.T, atol=scale * 1e-10, rtol=1e-10):
            raise ValueError("Covariance must be symmetric")
        if not np.allclose(p @ c @ p, c, atol=scale * 1e-9, rtol=1e-9):
            raise ValueError("Covariance is inconsistent with the reference/projector")
        if not 0 < self.rtol < 1:
            raise ValueError("Invalid rank tolerance")
        eigenvalues = np.linalg.eigvalsh(c)
        if eigenvalues[-1] <= 0 or eigenvalues[0] < -scale * 1e-9:
            raise ValueError("Covariance must be nonzero positive semidefinite")
        for name, array in (("covariance", c), ("projector", p)):
            frozen = array.copy()
            frozen.flags.writeable = False
            object.__setattr__(self, name, frozen)

    def require(self, channels: tuple[str, ...], projector: Array) -> None:
        if channels != self.channels or not np.allclose(projector, self.projector, atol=1e-10):
            raise ValueError("Covariance channel order or reference differs")

    @property
    def eigenvalues(self) -> Array:
        return np.linalg.eigvalsh(self.covariance)

    @property
    def whitener(self) -> Array:
        values, vectors = np.linalg.eigh(self.covariance)
        keep = values > values[-1] * self.rtol
        return np.asarray((vectors[:, keep] / np.sqrt(values[keep])).T, dtype=float)

    @property
    def rank(self) -> int:
        return int(self.whitener.shape[0])

    def diagnostics(self) -> dict[str, object]:
        values = self.eigenvalues
        retained = values[values > values[-1] * self.rtol]
        q = self.whitener
        return {
            "kind": self.kind,
            "rank": self.rank,
            "eigenvalues": values.tolist(),
            "retained_condition": float(retained[-1] / retained[0]),
            "whitening_identity_error": float(
                np.linalg.norm(q @ self.covariance @ q.T - np.eye(self.rank))
            ),
            "reference_nullity": len(values) - int(np.linalg.matrix_rank(self.projector)),
        }

    @classmethod
    def estimate(
        cls,
        samples: Array,
        channels: tuple[str, ...],
        projector: Array,
        *,
        shrinkage: float = 0.1,
        kind: str = "independent_synthetic_noise",
    ) -> "NoiseModel":
        x = np.asarray(samples, dtype=float)
        if x.ndim != 2 or x.shape[0] != len(channels) or x.shape[1] < 2:
            raise ValueError(
                "Samples must be channels by observations with at least two observations"
            )
        if not np.isfinite(x).all() or not 0 <= shrinkage <= 1:
            raise ValueError("Invalid samples or shrinkage")
        p = validate_projector(projector, len(channels))
        rank = int(np.linalg.matrix_rank(p))
        if rank == 0:
            raise ValueError("Projector removes all channels")
        empirical = np.cov(p @ x)
        target = np.trace(empirical) / rank * p
        return cls((1 - shrinkage) * empirical + shrinkage * target, channels, p, kind)
