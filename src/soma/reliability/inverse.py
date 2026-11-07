"""Unit-aware MNE linear kernels and selected resolution calibration."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mne
import numpy as np

from soma.anatomy.cache import cached_object
from soma.anatomy.contracts import validate_eeg_info
from soma.core.provenance import sha256
from soma.source.noise import NoiseModel
from soma.source.resolution import Resolution, spatial_metrics


def array_hash(array: Any) -> str:
    value = np.ascontiguousarray(array)
    return hashlib.sha256(
        str(value.shape).encode() + str(value.dtype).encode() + value.tobytes()
    ).hexdigest()


@dataclass(frozen=True)
class LinearEstimate:
    kernel: Any
    method: str
    loose: float
    lambda2: float
    units: str
    receipt: dict[str, Any]

    def amplitude_ratio(self, estimate: Any, truth: Any) -> float:
        if self.units != "A m":
            raise ValueError(
                "Physical amplitude comparison requires A m, not normalized statistics"
            )
        a, b = np.asarray(estimate), np.asarray(truth)
        if (
            a.shape != b.shape
            or not np.isfinite(a).all()
            or not np.isfinite(b).all()
            or np.linalg.norm(b) == 0
        ):
            raise ValueError("Corresponding finite nonzero current truth required")
        return float(np.linalg.norm(a) / np.linalg.norm(b))


def calibrated_inverse(
    forward: Any,
    covariance: Any,
    *,
    method: str = "MNE",
    loose: float = 0,
    depth: float = 0.8,
    lambda2: float = 1 / 9,
    cache_root: Path = Path("data/derived/reliability"),
) -> LinearEstimate:
    if method not in ("MNE", "dSPM", "sLORETA") or loose not in (0, 0.2, 1):
        raise ValueError("Prespecified MNE method and fixed/loose/free orientation required")
    if not np.isfinite(lambda2) or lambda2 <= 0 or depth not in (0, 0.8):
        raise ValueError("Positive lambda2 and prespecified depth required")
    projectors = validate_eeg_info(forward.info)
    if covariance.ch_names != forward.info.ch_names:
        raise ValueError("Inverse covariance/forward channel order mismatch")
    if len(covariance["projs"]) != len(forward.info["projs"]) or any(
        a["data"]["col_names"] != b["data"]["col_names"]
        or not np.array_equal(a["data"]["data"], b["data"]["data"])
        for a, b in zip(covariance["projs"], forward.info["projs"], strict=True)
    ):
        raise ValueError("Inverse covariance projector mismatch")
    if forward.anatomy.get("subject") != "sample" or any(
        s.get("subject_his_id") != "sample" for s in forward.native_free["src"]
    ):
        raise ValueError(
            "Reliability anatomical experiment requires matched sample source identity"
        )
    noise = NoiseModel(
        forward.projector @ covariance.data @ forward.projector,
        tuple(covariance.ch_names),
        forward.projector,
    )
    parameters = {
        "free_forward": array_hash(forward.native_free["sol"]["data"]),
        "covariance": array_hash(covariance.data),
        "projectors": projectors,
        "channels": forward.info.ch_names,
        "vertices": [v.tolist() for v in forward.vertices],
        "source_basis": array_hash(forward.native_free["source_nn"]),
        "source_positions": array_hash(forward.native_free["source_rr"]),
        "subject": forward.anatomy["subject"],
        "method": method,
        "loose": loose,
        "depth": depth,
        "lambda2": lambda2,
        "rank": noise.rank,
        "use_cps": False,
        "mne": mne.__version__,
        "numpy": np.__version__,
        "builder_sha256": sha256(Path(__file__)),
    }

    def build() -> Any:
        op = mne.minimum_norm.make_inverse_operator(
            forward.info,
            forward.native_free,
            covariance,
            loose=loose,
            fixed=loose == 0,
            depth=depth,
            rank={"eeg": noise.rank},
            use_cps=False,
            verbose=False,
        )
        stc = mne.minimum_norm.apply_inverse(
            mne.EvokedArray(np.eye(len(covariance.ch_names)), forward.info.copy(), nave=1),
            op,
            lambda2=lambda2,
            method=method,
            pick_ori=None if loose == 0 else "vector",
            use_cps=False,
            verbose=False,
        )
        forward.require_vertices(stc.vertices)
        if loose == 0:
            kernel = stc.data
        else:
            basis = forward.native_free["source_nn"].reshape(-1, 3, 3)
            kernel = np.einsum("nij,njk->nik", basis, stc.data).reshape(
                -1, len(covariance.ch_names)
            )
        return {
            "kernel": kernel,
            "singular": op["sing"],
            "singular_attenuation": op["sing"] ** 2 / (op["sing"] ** 2 + lambda2),
        }

    def read(path: Path) -> Any:
        with np.load(path, allow_pickle=False) as data:
            return {k: data[k] for k in data.files}

    def write(path: Path, data: Any) -> None:
        np.savez_compressed(path, **data)

    data, receipt = cached_object(cache_root, "inverse", parameters, ".npz", build, read, write)
    expected = (forward.matrix.shape[1] * (1 if loose == 0 else 3), len(covariance.ch_names))
    if data["kernel"].shape != expected or not np.isfinite(data["kernel"]).all():
        raise ValueError("Invalid cached linear kernel")
    return LinearEstimate(
        data["kernel"],
        method,
        loose,
        lambda2,
        "A m" if method == "MNE" else "dimensionless",
        {
            **receipt,
            "singular_values": data["singular"].tolist(),
            "singular_attenuation": data["singular_attenuation"].tolist(),
            "basis": "fixed signed normal"
            if loose == 0
            else "linear surface-local vector components",
        },
    )


def estimate_metrics(estimate: Any, truth: Any, xyz: Any, index: int) -> dict[str, Any]:
    """Pattern/energy metrics allow either physical currents or normalized statistics.

    Physical amplitude and sensor residual must be computed separately with units.
    Shape is sources × components × samples, including one signed fixed component.
    """
    a, b = np.asarray(estimate), np.asarray(truth)
    if (
        a.ndim != 3
        or a.shape != b.shape
        or a.shape[1] not in (1, 3)
        or not np.isfinite(a).all()
        or not np.isfinite(b).all()
        or np.linalg.norm(a) == 0
        or np.linalg.norm(b) == 0
    ):
        raise ValueError("Explicit corresponding signed/vector source representations required")
    strength = np.sqrt(np.sum(a * a, axis=(1, 2)))
    result = spatial_metrics(strength, index, np.asarray(xyz))
    result["normalized_pattern_cosine"] = float(
        np.sum(a * b) / (np.linalg.norm(a) * np.linalg.norm(b))
    )
    result["peak_source_norm"] = float(strength.max())
    return result


def selected_calibration(
    kernel: Any, lead: Any, indices: list[int], covariance: Any
) -> dict[str, Any]:
    resolution = Resolution(kernel, lead)
    psf, ctf = resolution.psf(indices), resolution.ctf(indices)
    return {
        "diagonal_gain": resolution.diagonal,
        "PSF": psf,
        "CTF": ctf,
        "noise_variance": np.einsum("ij,jk,ik->i", kernel, covariance, kernel),
        "noise_operator_norm": float(np.linalg.norm(kernel, 2)),
    }
