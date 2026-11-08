"""Explicit block source covariance, physical quadrature and sensor calibration.

Coefficients are vertex dipole moments (A m). Covariance blocks have (A m)^2
units times a declared scale; surface-density and moment models are distinct.
No dense source-by-source covariance or resolution matrix is constructed.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from soma.reliability.inverse import array_hash
from soma.source.noise import NoiseModel


@dataclass(frozen=True)
class SourcePrior:
    blocks: Any
    source_ids: tuple[str, ...]
    frame: str
    policy: str
    metadata: dict[str, Any]
    units: str = "A2 m2"

    def __post_init__(self) -> None:
        b = np.asarray(self.blocks, dtype=float)
        if (
            b.ndim != 3
            or b.shape[0] != len(self.source_ids)
            or b.shape[1] != b.shape[2]
            or b.shape[1] not in (1, 3)
            or not len(b)
            or not np.isfinite(b).all()
            or len(set(self.source_ids)) != len(b)
            or any(not x for x in self.source_ids)
            or self.frame not in ("MRI", "HEAD")
            or self.units != "A2 m2"
        ):
            raise ValueError(
                "Explicit unique source order, frame and moment covariance blocks required"
            )
        scale = max(float(np.max(np.abs(b))), np.finfo(float).tiny)
        if not np.allclose(b, b.transpose(0, 2, 1), rtol=1e-12, atol=scale * 1e-12):
            raise ValueError("Source covariance must be symmetric")
        if (
            np.min(np.linalg.eigvalsh(b)) < -scale * 1e-12
            or np.trace(b, axis1=1, axis2=2).sum() <= 0
        ):
            raise ValueError("Source covariance must be nonzero positive semidefinite")
        b = b.copy()
        b.flags.writeable = False
        object.__setattr__(self, "blocks", b)

    @property
    def dimensions(self) -> int:
        return int(self.blocks.shape[0] * self.blocks.shape[1])

    @property
    def trace(self) -> float:
        return float(np.trace(self.blocks, axis1=1, axis2=2).sum())

    def require(self, source_ids: tuple[str, ...], frame: str, columns: int) -> None:
        if source_ids != self.source_ids or frame != self.frame or columns != self.dimensions:
            raise ValueError("Source order, basis frame or orientation dimensions differ")

    def right(self, matrix: Any) -> Any:
        """Return matrix @ Q without allocating Q."""
        x = np.asarray(matrix, dtype=float)
        if x.ndim != 2 or x.shape[1] != self.dimensions or not np.isfinite(x).all():
            raise ValueError("Matrix columns do not match finite source covariance")
        return np.einsum(
            "cni,nij->cnj", x.reshape(len(x), *self.blocks.shape[:2]), self.blocks
        ).reshape(x.shape)

    def receipt(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "units": self.units,
            "frame": self.frame,
            "source_order_sha256": array_hash(np.array(self.source_ids)),
            "blocks_sha256": array_hash(self.blocks),
            "dimensions": self.dimensions,
            "total_prior_variance": self.trace,
            **self.metadata,
        }


def vertex_areas(vertices_m: Any, faces: Any, *, units: str = "m") -> Any:
    """Barycentric dual patch area; exactly one third of incident triangle area."""
    v, f = np.asarray(vertices_m, dtype=float), np.asarray(faces)
    if (
        units != "m"
        or v.ndim != 2
        or v.shape[1] != 3
        or not np.isfinite(v).all()
        or f.ndim != 2
        or f.shape[1] != 3
        or f.dtype.kind not in "iu"
        or not len(f)
        or f.min() < 0
        or f.max() >= len(v)
    ):
        raise ValueError("Metre-valued vertices and integer triangular faces required")
    a = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1) / 2
    if np.any(a <= 0):
        raise ValueError("Degenerate patches have no positive area")
    result = np.zeros(len(v))
    np.add.at(result, f.ravel(), np.repeat(a / 3, 3))
    if np.any(result <= 0):
        raise ValueError("Every source vertex must have positive incident patch area")
    return result


def make_prior(
    lead: Any,
    source_ids: tuple[str, ...],
    *,
    orientation: str = "free",
    frame: str = "MRI",
    policy: str = "uniform",
    normals: Any = None,
    areas_m2: Any = None,
    area_units: str = "m2",
    depth_exponent: float = 0.8,
    depth_cap: float = 10.0,
    loose: float = 0.2,
) -> SourcePrior:
    matrix = np.asarray(lead, dtype=float)
    n, k = len(source_ids), 1 if orientation == "fixed" else 3
    if (
        orientation not in ("fixed", "free")
        or matrix.ndim != 2
        or matrix.shape[1] != n * k
        or not np.isfinite(matrix).all()
        or not n
        or policy not in ("uniform", "depth", "area", "orientation", "depth_area")
        or not np.isfinite(depth_exponent)
        or not 0 <= depth_exponent <= 1
        or not np.isfinite(depth_cap)
        or depth_cap < 1
        or not 0 <= loose <= 1
    ):
        raise ValueError("Invalid lead representation or explicit prior policy")
    weights = np.ones(n)
    if policy in ("depth", "depth_area"):
        norm = np.linalg.norm(matrix.reshape(len(matrix), n, k), axis=(0, 2))
        if np.max(norm) <= 0:
            raise ValueError("Zero forward cannot define depth sensitivity")
        weights *= np.minimum(
            (np.max(norm) / np.maximum(norm, np.max(norm) * 1e-15)) ** (2 * depth_exponent),
            depth_cap,
        )
    if policy in ("area", "depth_area"):
        area = np.asarray(areas_m2, dtype=float)
        if (
            area_units != "m2"
            or area.shape != (n,)
            or not np.isfinite(area).all()
            or np.any(area <= 0)
        ):
            raise ValueError("Positive source quadrature areas explicitly in m2 required")
        weights *= area / 0.001  # fixed 10 cm² reference measure; never changes with grid
    blocks = weights[:, None, None] * np.broadcast_to(np.eye(k), (n, k, k)).copy()
    if policy == "orientation" and k == 3:
        normal = np.asarray(normals, dtype=float)
        if (
            normal.shape != (n, 3)
            or not np.isfinite(normal).all()
            or not np.allclose(np.linalg.norm(normal, axis=1), 1, atol=1e-10)
        ):
            raise ValueError("Unit normals in the same source basis required")
        blocks = loose * np.eye(3)[None] + (1 - loose) * np.einsum("ni,nj->nij", normal, normal)
    return SourcePrior(
        blocks,
        source_ids,
        frame,
        policy,
        {
            "depth_exponent": depth_exponent,
            "depth_variance_cap": depth_cap,
            "loose_tangential_variance": loose,
            "area_reference_m2": 0.001,
            "area_model": (
                "independent density-white-noise integrated over patches; Q proportional area"
            ),
            "normalization": "none",
        },
    )


def normalize_prior(
    prior: SourcePrior, lead: Any, noise: NoiseModel, *, target: float = 1.0
) -> SourcePrior:
    matrix = np.asarray(lead, dtype=float)
    if not np.isfinite(target) or target <= 0:
        raise ValueError("Positive finite sensor-trace target required")
    lw = noise.whitener @ matrix
    trace = float(np.sum(prior.right(lw) * lw))
    if not np.isfinite(trace) or trace <= 0:
        raise ValueError("Unobservable prior cannot be normalized")
    return SourcePrior(
        prior.blocks * (target / trace),
        prior.source_ids,
        prior.frame,
        prior.policy,
        {
            **prior.metadata,
            "normalization": "sensor_trace",
            "raw_sensor_trace": trace,
            "target_sensor_trace": target,
            "scalar": target / trace,
        },
    )


@dataclass(frozen=True)
class PriorInverse:
    kernel: Any
    diagnostics: dict[str, Any]

    def apply(self, observations: Any) -> Any:
        y = np.asarray(observations, dtype=float)
        if y.ndim not in (1, 2) or y.shape[0] != self.kernel.shape[1] or not np.isfinite(y).all():
            raise ValueError("Finite observations in matching sensor order required")
        return self.kernel @ y


def fit_prior(
    lead: Any,
    prior: SourcePrior,
    noise: NoiseModel,
    *,
    alpha: float,
    source_ids: tuple[str, ...],
    frame: str = "MRI",
) -> PriorInverse:
    matrix = np.asarray(lead, dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all() or not np.isfinite(alpha) or alpha < 0:
        raise ValueError("Finite lead and nonnegative physical regularization required")
    prior.require(source_ids, frame, matrix.shape[1])
    w = noise.whitener
    lw = w @ matrix
    qlt = prior.right(lw).T
    sensor = lw @ qlt
    sensor = (sensor + sensor.T) / 2
    eig, u = np.linalg.eigh(sensor)
    if eig[-1] <= 0:
        raise ValueError("Prior has no observable sensor variance")
    if alpha == 0:
        factors = np.zeros_like(eig)
        keep = eig > eig[-1] * max(sensor.shape) * np.finfo(float).eps
        factors[keep] = 1 / eig[keep]
    else:
        factors = 1 / (np.maximum(eig, 0) + alpha)
    kernel = (qlt @ (u * factors)) @ u.T @ w
    gain = np.einsum("sc,cs->s", kernel, matrix)
    return PriorInverse(
        kernel,
        {
            "units": "A m",
            "alpha": alpha,
            "noise_rank": noise.rank,
            "sensor_prior_trace": float(np.trace(sensor)),
            "total_prior_variance": prior.trace,
            "sensor_prior_eigenvalues": eig.tolist(),
            "effective_complexity": float(np.sum(gain)),
            "resolution_diagonal": gain.tolist(),
            "noise_amplification_Am_per_V": float(np.linalg.norm(kernel, 2)),
            "source_order_sha256": prior.receipt()["source_order_sha256"],
            "prior": prior.receipt(),
        },
    )
