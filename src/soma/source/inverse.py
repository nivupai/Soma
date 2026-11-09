"""Independent small-matrix SVD reference and MNE's anatomical inverse adapter."""

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from soma.source.noise import NoiseModel

Array = NDArray[np.float64]


@dataclass(frozen=True)
class Tikhonov:
    """Solve ||Q(Lj-y)||² + lambda2 ||j||²; toy coordinates have caller-defined units."""

    forward: Array
    lambda2: float
    noise: NoiseModel | None = None

    def __post_init__(self) -> None:
        lead = np.asarray(self.forward, dtype=float)
        if lead.ndim != 2 or not min(lead.shape) or not np.isfinite(lead).all():
            raise ValueError("Forward matrix must be finite and nonempty")
        if not np.isfinite(self.lambda2) or self.lambda2 < 0:
            raise ValueError("lambda2 must be finite and nonnegative")
        if self.noise is not None and self.noise.covariance.shape[0] != lead.shape[0]:
            raise ValueError("Noise and forward sensor dimensions differ")

    @property
    def kernel(self) -> Array:
        lead = self.forward
        q = np.eye(lead.shape[0]) if self.noise is None else self.noise.whitener
        u, s, vt = np.linalg.svd(q @ lead, full_matrices=False)
        if self.lambda2 == 0:
            factors = np.zeros_like(s)
            keep = s > np.max(s) * max(lead.shape) * np.finfo(float).eps
            factors[keep] = 1 / s[keep]
        else:
            factors = s / (s * s + self.lambda2)
        return np.asarray((vt.T * factors) @ u.T @ q, dtype=np.float64)

    def solve(self, measurements: Array) -> Array:
        y = np.asarray(measurements, dtype=float)
        if y.ndim not in (1, 2) or y.shape[0] != self.forward.shape[0] or not np.isfinite(y).all():
            raise ValueError("Invalid sensor observations")
        return np.asarray(self.kernel @ y, dtype=float)

    def diagnostics(self, measurements: Array, truth: Array | None = None) -> dict[str, float]:
        estimate = self.solve(measurements)
        residual = self.forward @ estimate - measurements
        result = {
            "residual_norm": float(np.linalg.norm(residual)),
            "penalty_norm": float(np.linalg.norm(estimate)),
            "noise_amplification": float(np.linalg.norm(self.kernel, 2)),
            "forward_consistency_relative": float(
                np.linalg.norm(residual) / max(float(np.linalg.norm(measurements)), 1e-300)
            ),
        }
        if truth is not None:
            result["relative_source_error"] = float(
                np.linalg.norm(estimate - truth) / max(float(np.linalg.norm(truth)), 1e-300)
            )
        return result


class CorticalInverse:
    """MNE/dSPM with fixed signed normals or an explicit free surface basis.

    A free vector STC is in Cartesian head coordinates. ``kernel`` converts it
    back to the forward's surface basis before constructing linear resolution.
    Vector magnitudes are nonlinear and are deliberately not exposed as kernels.
    """

    def __init__(
        self,
        forward: Any,
        covariance: Any,
        *,
        lambda2: float = 1 / 9,
        method: Literal["MNE", "dSPM"] = "MNE",
        depth: float | None = 0.8,
        orientation: Literal["fixed", "free"] = "fixed",
    ) -> None:
        import mne

        if method not in ("MNE", "dSPM") or orientation not in ("fixed", "free"):
            raise ValueError("Unsupported inverse method or orientation")
        if not np.isfinite(lambda2) or lambda2 <= 0:
            raise ValueError("Anatomical inverse requires positive finite lambda2")
        channels = tuple(forward.info["ch_names"])
        if tuple(covariance.ch_names) != channels:
            raise ValueError("Covariance and forward channel ordering differ")
        expected_projs = forward.info["projs"]
        if len(covariance["projs"]) != len(expected_projs) or any(
            a["data"]["col_names"] != b["data"]["col_names"]
            or not np.allclose(a["data"]["data"], b["data"]["data"])
            for a, b in zip(covariance["projs"], expected_projs, strict=True)
        ):
            raise ValueError("Covariance and forward projector definitions differ")
        projected_covariance = forward.projector @ covariance.data @ forward.projector
        noise = NoiseModel(projected_covariance, channels, forward.projector)
        self.forward = forward
        self.lambda2 = lambda2
        self.method = method
        self.orientation = orientation
        self.units = "A m" if method == "MNE" else "dimensionless"
        self.operator = mne.minimum_norm.make_inverse_operator(
            forward.info,
            forward.native_free,
            covariance,
            loose=0 if orientation == "fixed" else 1,
            fixed=orientation == "fixed",
            depth=depth,
            rank={"eeg": noise.rank},
            use_cps=False,
            verbose=False,
        )
        self._kernel: Array | None = None

    def apply(self, evoked: Any) -> Any:
        import mne

        if tuple(evoked.ch_names) != tuple(self.forward.info["ch_names"]):
            raise ValueError("Evoked channel order differs from forward")
        if evoked.nave != 1:
            raise ValueError("Use nave=1 for a fixed trial/evoked comparison kernel")
        return mne.minimum_norm.apply_inverse(
            evoked,
            self.operator,
            self.lambda2,
            self.method,
            pick_ori=None if self.orientation == "fixed" else "vector",
            use_cps=False,
            verbose=False,
        )

    @property
    def kernel(self) -> Array:
        import mne

        if self._kernel is None:
            stc = self.apply(
                mne.EvokedArray(
                    np.eye(len(self.forward.info["ch_names"])), self.forward.info.copy(), nave=1
                )
            )
            self.forward.require_vertices(stc.vertices)
            if self.orientation == "fixed":
                self._kernel = np.asarray(stc.data, dtype=float)
            else:
                basis = self.forward.native_free["source_nn"].reshape(-1, 3, 3)
                self._kernel = np.einsum("nij,njk->nik", basis, stc.data).reshape(
                    -1, stc.data.shape[-1]
                )
        return self._kernel

    def epochs(self, epochs: Any) -> Any:
        import mne

        if tuple(epochs.ch_names) != tuple(self.forward.info["ch_names"]):
            raise ValueError("Epoch channel order differs from forward")
        return mne.minimum_norm.apply_inverse_epochs(
            epochs,
            self.operator,
            self.lambda2,
            self.method,
            nave=1,
            pick_ori=None if self.orientation == "fixed" else "vector",
            return_generator=True,
            use_cps=False,
            verbose=False,
        )
