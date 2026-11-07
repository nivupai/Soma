"""Continuous dipoles with independently evaluated forwards and explicit grid separation."""

from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import mne
import numpy as np
from scipy.spatial import cKDTree

from soma.anatomy.cache import cached_object
from soma.anatomy.surfaces import ConductorSurfaces
from soma.anatomy.synthetic import discrete_sources, sphere_mesh, synthetic_info
from soma.core.provenance import sha256
from soma.geometry import Frame, Points, Transform
from soma.reliability.inverse import array_hash
from soma.source.inverse import Tikhonov
from soma.source.noise import average_projector


@dataclass(frozen=True)
class ContinuousDipole:
    position: Points
    orientation: Any
    moment_Am: float
    subject: str = "synthetic-sphere"

    def __post_init__(self) -> None:
        direction = np.asarray(self.orientation, dtype=float)
        if (
            self.position.frame != Frame.MRI
            or self.position.xyz.shape != (1, 3)
            or not self.subject
        ):
            raise ValueError("One explicitly identified continuous MRI-frame location required")
        if (
            direction.shape != (3,)
            or not np.isfinite(direction).all()
            or not np.isclose(np.linalg.norm(direction), 1, atol=1e-10)
        ):
            raise ValueError(
                "Dipole orientation must be an explicit unit vector in MRI coordinates"
            )
        if not np.isfinite(self.moment_Am) or self.moment_Am <= 0:
            raise ValueError("Positive finite dipole moment in A m required")
        direction = direction.copy()
        direction.flags.writeable = False
        object.__setattr__(self, "orientation", direction)

    def receipt(self) -> dict[str, Any]:
        return {
            "position_MRI_m": self.position.xyz[0].tolist(),
            "orientation_MRI_unit": self.orientation.tolist(),
            "moment_Am": self.moment_Am,
            "subject": self.subject,
            "location_definition": "continuous, not chosen from reconstruction vertices",
        }


def offgrid(
    dipole: ContinuousDipole,
    grid: Points,
    *,
    subject: str = "synthetic-sphere",
    tolerance_m: float = 0.0005,
) -> tuple[float, int]:
    if (
        grid.frame != dipole.position.frame
        or subject != dipole.subject
        or tolerance_m <= 0
        or not np.isfinite(tolerance_m)
    ):
        raise ValueError("Source/grid identity, frame or physical tolerance mismatch")
    distance, index = cKDTree(grid.xyz).query(dipole.position.xyz[0])
    if distance <= tolerance_m:
        raise ValueError("Source coincides with reconstruction grid within off-grid tolerance")
    return float(distance), int(index)


def source_grid(spacing_m: float) -> Points:
    if not np.isfinite(spacing_m) or not 0.005 <= spacing_m <= 0.03:
        raise ValueError("Bounded physical source spacing required")
    axis = np.arange(-0.06, 0.0600001, spacing_m)
    xyz = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1).reshape(-1, 3)
    radius = np.linalg.norm(xyz, axis=1)
    return Points(xyz[(radius > 0.005) & (radius <= 0.065)], Frame.MRI)


def direction(position: Any, angle_deg: float = 0) -> Any:
    normal = np.asarray(position, dtype=float)
    normal = normal / np.linalg.norm(normal)
    tangent = np.cross(normal, [1.0, 0, 0])
    if np.linalg.norm(tangent) < 1e-10:
        tangent = np.cross(normal, [0, 1.0, 0])
    tangent /= np.linalg.norm(tangent)
    return normal * np.cos(np.deg2rad(angle_deg)) + tangent * np.sin(np.deg2rad(angle_deg))


def _bem(radii: tuple[float, float, float], sigmas: tuple[float, float, float], level: int) -> Any:
    surfaces = []
    for identity, radius, sigma in zip((4, 3, 1), reversed(radii), sigmas, strict=True):
        rr, tris = sphere_mesh(level, radius)
        surfaces.append(
            mne.surface.complete_surface_info(
                {
                    "id": identity,
                    "sigma": sigma,
                    "coord_frame": 5,
                    "rr": rr,
                    "tris": tris,
                    "np": len(rr),
                    "ntri": len(tris),
                },
                copy=True,
                verbose=False,
            )
        )
    conductor = ConductorSurfaces.from_mne(
        "synthetic-sphere",
        surfaces,
        {"source": "analytic nested spheres", "radii_inner_to_outer_m": radii},
    )
    if conductor.readiness(sensor_compatible=True, anatomical_evidence=True)["status"] != "PASS":
        raise ValueError("Synthetic BEM geometry failed validation")
    return mne.make_bem_solution(surfaces, verbose=False)


def evaluate_forward(
    points: Points,
    *,
    kind: str = "analytical",
    radii: tuple[float, float, float] = (0.08, 0.085, 0.09),
    sigmas: tuple[float, float, float] = (0.3, 0.006, 0.3),
    level: int = 2,
    transform: Transform | None = None,
) -> tuple[Any, dict[str, Any]]:
    if (
        points.frame != Frame.MRI
        or np.any(np.linalg.norm(points.xyz, axis=1) >= radii[0])
        or kind not in ("analytical", "BEM")
    ):
        raise ValueError("Explicit intracranial MRI sources and supported conductor required")
    if not 0 < radii[0] < radii[1] < radii[2] or any(s <= 0 or not np.isfinite(s) for s in sigmas):
        raise ValueError("Nested radii and positive S/m conductivities required")
    t = transform or Transform(Frame.HEAD, Frame.MRI, np.eye(4))
    if t.source != Frame.HEAD or t.destination != Frame.MRI or not t.rigid:
        raise ValueError("HEAD→MRI rigid mapping required")
    if kind == "analytical" and not np.allclose(t.matrix, np.eye(4), atol=1e-15, rtol=0):
        raise ValueError("Analytical reference requires coincident known synthetic frames")
    info = synthetic_info()
    physical = {
        "kind": kind,
        "radii_inner_to_outer_m": list(radii),
        "conductivities_scalp_skull_brain_S_m": list(sigmas),
        "subdivisions": level,
        "mne": mne.__version__,
        "numpy": np.__version__,
        "scipy": version("scipy"),
        "builder_sha256": sha256(Path(__file__)),
    }
    conductor_receipt: dict[str, Any] = {}
    if kind == "analytical":
        conductor = mne.make_sphere_model(
            r0=(0, 0, 0),
            head_radius=radii[2],
            relative_radii=tuple(r / radii[2] for r in radii),
            sigmas=tuple(reversed(sigmas)),
            verbose=False,
        )
    else:
        conductor, conductor_receipt = cached_object(
            Path("data/derived/offgrid"),
            "conductor",
            physical,
            "-bem-sol.fif",
            lambda: _bem(radii, sigmas, level),
            lambda p: mne.read_bem_solution(p, verbose=False),
            lambda p, x: mne.write_bem_solution(p, x, overwrite=False, verbose=False),
        )
    params = {
        **physical,
        "positions_sha256": array_hash(points.xyz),
        "positions_m": points.xyz.tolist(),
        "channels": info.ch_names,
        "sensor_HEAD_m": [c["loc"][:6].tolist() for c in info["chs"]],
        "head_to_MRI_m": t.matrix.tolist(),
        "orientation": "Cartesian MRI x/y/z, A m",
        "reference": "average",
    }

    def build() -> Any:
        native = mne.make_forward_solution(
            info,
            trans=t.to_mne(),
            src=discrete_sources(points.xyz),
            bem=conductor,
            eeg=True,
            meg=False,
            mindist=0,
            n_jobs=1,
            verbose=False,
        )
        returned = native["source_rr"] @ t.matrix[:3, :3].T + t.matrix[:3, 3]
        if returned.shape != points.xyz.shape or not np.allclose(
            returned, points.xyz, atol=1e-9, rtol=0
        ):
            raise ValueError("Forward source order/frame correspondence changed")
        cart = native["sol"]["data"].reshape(len(info.ch_names), -1, 3)
        mri = np.einsum("cni,ij->cnj", cart, np.linalg.inv(t.matrix[:3, :3]))
        return {"lead": average_projector(len(info.ch_names)) @ mri.reshape(len(info.ch_names), -1)}

    def read(path: Path) -> Any:
        with np.load(path, allow_pickle=False) as x:
            return {k: x[k] for k in x.files}

    def write(path: Path, x: Any) -> None:
        np.savez_compressed(path, **x)

    data, receipt = cached_object(
        Path("data/derived/offgrid"), "forward", params, ".npz", build, read, write
    )
    lead = data["lead"]
    if lead.shape != (24, 3 * len(points.xyz)) or not np.isfinite(lead).all():
        raise ValueError("Invalid forward dimensions/numerics")
    return lead, {
        "forward": receipt,
        "conductor": conductor_receipt,
        "shared_assumptions": (
            "piecewise homogeneous isotropic concentric spheres; MNE "
            "analytical approximation or BEM"
        ),
        "source_count": len(points.xyz),
    }


def reconstruction_operator(
    lead: Any, grid: Points, *, orientation: str = "free", lambda2: float = 1 / 9
) -> tuple[Any, Any, dict[str, Any]]:
    cart = np.asarray(lead, dtype=float)
    if cart.shape != (24, 3 * len(grid.xyz)) or orientation not in ("fixed", "free"):
        raise ValueError("Explicit grid and fixed-radial/free-Cartesian representation required")
    if orientation == "fixed":
        normals = grid.xyz / np.linalg.norm(grid.xyz, axis=1)[:, None]
        matrix = np.einsum("cni,ni->cn", cart.reshape(24, -1, 3), normals)
    else:
        matrix = cart
    singular = np.linalg.svd(matrix, compute_uv=False)
    keep = singular > singular[0] * max(matrix.shape) * np.finfo(float).eps
    rank = int(keep.sum())
    scale = float(np.linalg.norm(matrix) / np.sqrt(rank))
    kernel = Tikhonov(matrix / scale, lambda2).kernel / scale
    return (
        kernel,
        matrix,
        {
            "orientation": "fixed radial" if orientation == "fixed" else "free Cartesian MRI",
            "units": "A m",
            "rank": rank,
            "retained_condition": float(singular[0] / singular[keep][-1]),
            "scale_V_per_Am": scale,
            "lambda2": lambda2,
            "physical_ridge_alpha": lambda2 * scale**2,
            "noise_operator_norm_Am_per_V": float(np.linalg.norm(kernel, 2)),
        },
    )


def reconstruction_metrics(
    estimate: Any, lead: Any, observed: Any, dipole: ContinuousDipole, grid: Points, nearest: int
) -> dict[str, Any]:
    array = np.asarray(estimate)
    if array.ndim != 2 or array.shape[0] not in (len(grid.xyz), 3 * len(grid.xyz)):
        raise ValueError("Explicit fixed/vector source dimensions required")
    strength = np.linalg.norm(array.reshape(len(grid.xyz), -1, array.shape[1]), axis=1)
    peak = np.argmax(strength, axis=0)
    distance = np.linalg.norm(grid.xyz - dipole.position.xyz[0], axis=1)
    energy = strength**2
    total = energy.sum(axis=0)
    if np.any(total == 0):
        raise ValueError("Zero estimate has no localization peak")
    return {
        "peak_error_mm": distance[peak] * 1000,
        "nearest_grid_mm": float(distance[nearest] * 1000),
        "dispersion_mm": np.sqrt(np.sum(energy * distance[:, None] ** 2, axis=0) / total) * 1000,
        "nearest_vertex_amplitude_ratio": strength[nearest] / dipole.moment_Am,
        "off_nearest_energy_fraction": 1 - energy[nearest] / total,
        "sensor_residual_relative": np.linalg.norm(lead @ array - observed, axis=0)
        / np.linalg.norm(observed, axis=0),
        "peak_index": peak,
        "peak_current_norm_Am": strength[peak, np.arange(array.shape[1])],
    }
