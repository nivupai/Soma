"""Explicit cell-moment priors and retained-subspace inverse calibration.

Coefficients are integrated XYZ dipole moments (A m), never pointwise current
 densities. Generalized spatial-white intensity q (A²/m) integrates to q*volume.
"""

import hashlib
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree
from scipy.stats import qmc

from soma.source.noise import NoiseModel

Array = NDArray[np.float64]
PriorKind = Literal["unweighted", "cell_volume", "total_variance"]
Method = Literal["Tikhonov", "MNE", "dSPM"]


def positions(value: Array) -> Array:
    p = np.asarray(value, dtype=float)
    if (
        p.ndim != 2
        or p.shape[1] != 3
        or not len(p)
        or not np.isfinite(p).all()
        or np.any(np.linalg.norm(p, axis=1) > 0.065 + 1e-12)
        or len(np.unique(p, axis=0)) != len(p)
    ):
        raise ValueError("Unique finite MRI RAS metre candidates inside 65 mm required")
    return p


def grid_hash(grid: Array) -> str:
    return hashlib.sha256(np.ascontiguousarray(positions(grid), dtype="<f8").tobytes()).hexdigest()


def cell_volumes(grid: Array, probes: int = 65536) -> Array:
    """Deterministic approximate Voronoi quadrature over a common 65 mm ball."""
    p = positions(grid)
    if probes < 1024 or probes & (probes - 1):
        raise ValueError("Power-of-two quadrature count at least 1024 required")
    u = qmc.Sobol(3, scramble=False).random_base2(int(np.log2(probes)))
    z = 2 * u[:, 0] - 1
    r = 0.065 * np.cbrt(u[:, 2])
    a = 2 * np.pi * u[:, 1]
    xyz = (
        np.column_stack([np.sqrt(1 - z * z) * np.cos(a), np.sqrt(1 - z * z) * np.sin(a), z])
        * r[:, None]
    )
    index = cKDTree(p).query(xyz)[1]
    volumes = (
        np.bincount(index, minlength=len(p)).astype(float) / probes * (4 * np.pi * 0.065**3 / 3)
    )
    if np.any(volumes <= 0):
        raise ValueError("Unresolved source cell: quadrature gives zero mass")
    return volumes


@dataclass(frozen=True)
class SourcePrior:
    grid_fingerprint: str
    diagonal: Array
    volumes_m3: Array
    kind: PriorKind
    moment_scale_Am: float = 1e-8
    coefficient_unit: str = "A*m"
    orientation_order: str = "source-major XYZ"

    def __post_init__(self) -> None:
        d, v = np.asarray(self.diagonal, float), np.asarray(self.volumes_m3, float)
        domain = 4 * np.pi * 0.065**3 / 3
        if (
            v.ndim != 1
            or not len(v)
            or d.shape != (3 * len(v),)
            or not np.isfinite(d).all()
            or np.any(d <= 0)
            or not np.isfinite(v).all()
            or np.any(v <= 0)
            or not np.isclose(v.sum(), domain, rtol=1e-12, atol=0)
            or self.kind not in ("unweighted", "cell_volume", "total_variance")
            or self.coefficient_unit != "A*m"
            or self.orientation_order != "source-major XYZ"
            or not np.isfinite(self.moment_scale_Am)
            or self.moment_scale_Am <= 0
            or len(self.grid_fingerprint) != 64
        ):
            raise ValueError("Invalid positive source covariance, volume, units or ordering")
        expected = {
            "unweighted": np.ones(len(v)),
            "cell_volume": 12 * v / domain,
            "total_variance": np.full(len(v), 12 / len(v)),
        }[self.kind]
        if not np.allclose(d, np.repeat(expected, 3), rtol=1e-12, atol=0):
            raise ValueError("Prior covariance inconsistent with declared discretization")
        for name, value in [("diagonal", d), ("volumes_m3", v)]:
            value = value.copy()
            value.flags.writeable = False
            object.__setattr__(self, name, value)

    @classmethod
    def create(cls, grid: Array, kind: PriorKind, volumes: Array | None = None) -> "SourcePrior":
        p = positions(grid)
        v = cell_volumes(p) if volumes is None else np.asarray(volumes, float)
        if kind == "unweighted":
            d = np.ones(len(p))
        elif kind == "cell_volume":
            d = 12 * v / (4 * np.pi * 0.065**3 / 3)
        elif kind == "total_variance":
            d = np.full(len(p), 12 / len(p))
        else:
            raise ValueError("Unsupported source prior")
        if v.shape != (len(p),):
            raise ValueError("Cell/grid dimension mismatch")
        return cls(grid_hash(p), np.repeat(d, 3), v, kind)

    @property
    def trace_Am2(self) -> float:
        return float(self.diagonal.sum() * self.moment_scale_Am**2)


@dataclass(frozen=True)
class PriorInverse:
    """Independent moment-space Gaussian inverse, with MNE trace normalization.

    dSPM uses three-component block noise normalization of the moment kernel.
    Its sensor predictions always use the underlying physical moment kernel.
    """

    lead: Array
    grid: Array
    prior: SourcePrior
    noise: NoiseModel
    method: Method

    def __post_init__(self) -> None:
        g = np.asarray(self.lead, float)
        if (
            grid_hash(self.grid) != self.prior.grid_fingerprint
            or g.shape != (len(self.noise.channels), len(self.prior.diagonal))
            or not np.isfinite(g).all()
            or not np.any(g)
            or self.method not in ("Tikhonov", "MNE", "dSPM")
            or not np.allclose(self.noise.projector @ g, g, rtol=1e-10, atol=1e-12)
        ):
            raise ValueError("Forward/prior grid order, reference or dimensions disagree")
        for name, value in [("lead", g), ("grid", positions(self.grid))]:
            value = value.copy()
            value.flags.writeable = False
            object.__setattr__(self, name, value)

    def components(self) -> tuple[Array, Array, Array]:
        a = self.noise.whitener @ self.lead * self.prior.moment_scale_Am
        r = self.prior.diagonal.copy()
        if self.method != "Tikhonov":
            r *= self.noise.rank / float(np.sum((a * a) * r))
        b = (a * r) @ a.T
        return a, r, b

    def kernel(self, alpha: float, *, physical: bool = False) -> Array:
        if not np.isfinite(alpha) or alpha <= 0:
            raise ValueError("Positive finite alpha required")
        a, r, b = self.components()
        k = (
            self.prior.moment_scale_Am
            * (r[:, None] * a.T)
            @ np.linalg.solve(b + alpha * np.eye(len(b)), self.noise.whitener)
        )
        if self.method == "dSPM" and not physical:
            norm = np.sqrt(
                np.einsum("ij,jk,ik->i", k, self.noise.covariance, k).reshape(-1, 3).sum(axis=1)
            )
            if np.any(norm <= 0):
                raise ValueError("Degenerate dSPM noise normalization")
            k = k / np.repeat(norm, 3)[:, None]
        return np.asarray(k, float)

    def alpha(
        self,
        policy: str,
        historical_scale: float,
        sweep: Array,
        calibration_a: Array,
        calibration_b: Array,
    ) -> tuple[float, bool, list[float]]:
        """Independent-repeat sensor prediction; accepts no source-localization targets."""
        if not np.isfinite(historical_scale) or historical_scale <= 0:
            raise ValueError("Invalid scale")
        base = (
            0.001 * (historical_scale * self.prior.moment_scale_Am / 5e-8) ** 2
            if self.method == "Tikhonov"
            else 1 / 9
        )
        if policy == "historical":
            return float(base), False, []
        if policy == "spectral":
            top = np.linalg.eigvalsh(self.components()[2])[-1]
            return float((0.001 if self.method == "Tikhonov" else 1 / 9) * top), False, []
        if policy != "prediction":
            raise ValueError("Unsupported regularization policy")
        x, y = np.asarray(calibration_a), np.asarray(calibration_b)
        if (
            x.ndim != 2
            or x.shape != y.shape
            or x.shape[0] != len(self.lead)
            or not x.shape[1]
            or not np.isfinite(x).all()
            or not np.isfinite(y).all()
        ):
            raise ValueError("Paired finite calibration measurements required")
        if (
            sweep.ndim != 1
            or len(sweep) < 3
            or np.any(np.diff(sweep) <= 0)
            or not np.isfinite(sweep).all()
        ):
            raise ValueError("Ordered prespecified log sweep required")
        alphas = base * 10.0**sweep
        losses = [
            float(
                np.mean(
                    (
                        self.noise.whitener
                        @ (self.lead @ self.kernel(float(t), physical=True) @ x - y)
                    )
                    ** 2
                )
            )
            for t in alphas
        ]
        index = int(np.argmin(losses))
        return float(alphas[index]), index in (0, len(alphas) - 1), losses

    def diagnostics(self, alpha: float) -> dict[str, float]:
        _, r, b = self.components()
        eigen = np.maximum(np.linalg.eigvalsh(b), 0)
        return {
            "prior_trace_Am2": self.prior.trace_Am2,
            "effective_prior_trace_Am2": float(r.sum() * self.prior.moment_scale_Am**2),
            "whitened_prior_trace": float(np.trace(b)),
            "top_eigenvalue": float(eigen[-1]),
            "alpha": float(alpha),
            "alpha_over_top": float(alpha / eigen[-1]),
            "EDF": float(np.sum(eigen / (eigen + alpha))),
            "condition_regularized": float((eigen[-1] + alpha) / (eigen[0] + alpha)),
        }


def source_split(calibration: list[int], test: list[int], count: int) -> None:
    if (
        len(set(calibration)) != len(calibration)
        or len(set(test)) != len(test)
        or set(calibration) & set(test)
        or set(calibration) | set(test) != set(range(count))
    ):
        raise ValueError("Source-level split leaks or omits sources")


def amplitude_unit(method: Method, physical: bool = False) -> str:
    if method == "dSPM" and physical:
        raise ValueError("dSPM amplitude is not physical current")
    return "dimensionless" if method == "dSPM" else "A*m"


def conditional_interval(values: Array, seed: int = 310422) -> tuple[float, float, float]:
    """Only complete head/source matrices after averaging repeats, never row IID."""
    a = np.asarray(values, float)
    if a.ndim != 2 or a.shape[0] != 6 or a.shape[1] < 2 or not np.isfinite(a).all():
        raise ValueError("Six head clusters and source-averaged complete paired values required")
    rng = np.random.default_rng(seed)
    h = np.concatenate([rng.integers(i, i + 2, (999, 2)) for i in (0, 2, 4)], axis=1)
    s = rng.integers(0, a.shape[1], (999, 6, a.shape[1]))
    means = a[h[:, :, None], s].mean(axis=(1, 2))
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(a.mean()), float(lo), float(hi)


EXAMPLE_SHA256 = "7fa45a960ceca3cb83eb668aacb067c83cbd32fcb571b67036be33d002a7d050"


def validate_example(raw: bytes) -> dict[str, object]:
    import json

    if hashlib.sha256(raw).hexdigest() != EXAMPLE_SHA256:
        raise ValueError("Corrupt inverse-calibration result fingerprint")
    value = json.loads(raw)
    if (
        value.get("schema") != "soma.inverse-calibration.explorer/1"
        or value.get("synthetic_only") is not True
        or value.get("human_subjects") != 0
        or value.get("design_sha256")
        != "abb24125e39c51438197e4e7301b3f7079bdb4820bdd6257069348594d6468bc"
        or len(value.get("failures", [])) != value["receipt"]["failed_configurations"]
    ):
        raise ValueError("Unsupported inverse evidence or unreported scientific failures")
    return dict(value)
