"""Frozen physical four-shell experiments; no anatomy or EEG downloads."""

import hashlib
import io
import itertools
import json
import logging
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Literal

import mne
import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation

from soma.geometry import Frame, Points, Transform
from soma.protocol.binding import example_protocol
from soma.protocol.model import Protocol, SealedProtocol, anatomy, methods, seal
from soma.source.inverse import CorticalInverse, Tikhonov
from soma.source.noise import average_projector

Array = NDArray[np.float64]
DESIGN_SHA256 = "42a9608377c35577001ca4c216c82aaf40836f03eca869232ab8f5f461e37a8a"


def design() -> dict[str, Any]:
    raw = files("soma.resources").joinpath("source-uncertainty-v26.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != DESIGN_SHA256:
        raise ValueError("Frozen simulation design changed; explicit protocol revision required")
    return dict(json.loads(raw))


def protocol() -> SealedProtocol:
    c = design()
    d = example_protocol("source").document()
    d.update(id="source-uncertainty-v26", name="Physical anatomical uncertainty", version="1.0.0")
    for name, stage in d["requirements"]["stages"].items():
        stage.update(implementation="source.uncertainty." + name, algorithm_version="26.1")
        stage["parameters"] = {"design_sha256": DESIGN_SHA256, "stage": name}
    for a in d["requirements"]["artifacts"].values():
        a["metadata"]["spatial_reference"] = {
            "frame": "mri",
            "space": "synthetic-sphere-native",
            "unit": "m",
        }
        a["metadata"]["units"] = {"values": "explicit mixed SI; dSPM dimensionless"}
    s = d["scientific"]
    s.update(
        question="How do anatomical and acquisition errors affect known source recovery?",
        objective="Paired controlled physical simulation, no human anatomical validation",
        estimand="Generator-averaged localization/spread/amplitude under fixed idealized anatomy",
        conditions=["49 frozen models; shared independently generated measurements"],
        primary_outcomes=["peak localization mm", "spatial dispersion mm", "amplitude bias"],
        analysis_methods=methods(d["requirements"]),
        anatomical_conventions=anatomy(d["requirements"]),
        preprocessing={n: v["parameters"] for n, v in d["requirements"]["stages"].items()},
        source_conductivity={
            "model": "MNE four-shell sphere",
            "sigmas_S_m": c["conductivities_S_m"],
        },
        limitations=[
            "idealized isotropic shells; not BEM/MRI segmentation validation",
            "conditional Monte Carlo intervals, no human population inference",
            "shared MNE forward code; off-grid truth avoids exact inverse crime only",
        ],
    )
    s["population"].update(
        dataset_namespace="synthetic-source-v26",
        scope=DESIGN_SHA256,
        inclusion=["all 12 independent generator draws"],
        exclusion=["retain all planned failures; no outcome selection"],
    )
    d["optional_metadata"] = {"design": c, "design_sha256": DESIGN_SHA256}
    return seal(Protocol.from_dict(d))


def check_protocol(value: SealedProtocol) -> None:
    if value.protocol.fingerprint != protocol().protocol.fingerprint:
        raise ValueError("Unapproved simulation protocol drift")


def fibonacci(n: int, lower_z: float = -1) -> Array:
    z = lower_z + (1 - lower_z) * (np.arange(n) + 0.5) / n
    phi = np.arange(n) * np.pi * (3 - np.sqrt(5))
    return np.column_stack([np.sqrt(1 - z * z) * np.cos(phi), np.sqrt(1 - z * z) * np.sin(phi), z])


def candidate_grid(multiplier: int = 1) -> Points:
    c = design()
    if multiplier not in (1, 2):
        raise ValueError("Only the two frozen convergence grids are allowed")
    directions = fibonacci(c["candidate_sources_per_shell"] * multiplier)
    return Points(np.vstack([directions * r / 1000 for r in c["candidate_radii_mm"]]), Frame.MRI)


def scenarios() -> list[dict[str, Any]]:
    c = design()
    base = {
        "family": "baseline",
        "magnitude": 0.0,
        "inner_mm": 0.0,
        "outer_mm": 0.0,
        "skull": 0.004,
        "electrode_mm": 0.0,
        "pattern": 0,
        "translation_mm": 0.0,
        "rotation_deg": 0.0,
    }
    rows = [dict(base, id="baseline")]
    for family, key, values in [
        ("inner_boundary", "inner_mm", c["inner_skull_delta_mm"]),
        ("outer_boundary", "outer_mm", c["outer_skull_delta_mm"]),
        ("conductivity", "skull", c["skull_S_m"]),
        ("translation", "translation_mm", c["translation_x_mm"]),
        ("rotation", "rotation_deg", c["rotation_z_deg"]),
    ]:
        for value in values:
            rows.append(
                dict(base, id=f"{family}-{value}", family=family, magnitude=value, **{key: value})
            )
    for value, pattern in itertools.product(c["electrode_rms_mm"], c["electrode_patterns"]):
        rows.append(
            dict(
                base,
                id=f"electrode-{value}-{pattern}",
                family="electrode",
                magnitude=value,
                electrode_mm=value,
                pattern=pattern,
            )
        )
    for bits in itertools.product([0, 1], repeat=4):
        if not any(bits):
            continue
        rows.append(
            dict(
                base,
                id="interaction-" + "".join(map(str, bits)),
                family="interaction",
                magnitude=sum(bits),
                outer_mm=2.0 * bits[0],
                skull=0.01 if bits[1] else 0.004,
                electrode_mm=5.0 * bits[2],
                translation_mm=5.0 * bits[3],
            )
        )
    return rows


def transform(translation_mm: float = 0, rotation_deg: float = 0) -> Transform:
    if not np.isfinite([translation_mm, rotation_deg]).all():
        raise ValueError("Finite declared registration perturbation required")
    matrix = np.eye(4)
    matrix[:3, :3] = Rotation.from_euler("z", rotation_deg, degrees=True).as_matrix()
    matrix[0, 3] = translation_mm / 1000
    return Transform(Frame.HEAD, Frame.MRI, matrix)


def electrode_positions(rms_mm: float = 0, pattern: int = 0) -> Points:
    if not np.isfinite(rms_mm) or not 0 <= rms_mm <= 10 or pattern not in (0, 1, 2):
        raise ValueError("Invalid frozen electrode perturbation")
    c = design()
    xyz = fibonacci(c["sensors"], -0.35) * 0.09
    delta = np.random.default_rng(c["seed"] + 100 + pattern).normal(size=xyz.shape)
    delta *= rms_mm / 1000 / np.sqrt(np.mean(np.sum(delta**2, axis=1)))
    return Points(xyz + delta, Frame.HEAD)


@dataclass
class SphereForward:
    """Discrete free Cartesian source adapter for the existing CorticalInverse."""

    native_free: Any
    info: Any
    matrix: Array
    projector: Array
    positions: Points
    head_to_mri: Transform
    diagnostics: dict[str, Any]

    def require_vertices(self, vertices: list[Array]) -> None:
        expected = [s["vertno"] for s in self.native_free["src"]]
        if len(vertices) != len(expected) or any(
            not np.array_equal(a, b) for a, b in zip(vertices, expected, strict=True)
        ):
            raise ValueError("Inverse/forward source identity mismatch")


def physical_forward(
    points: Points,
    electrodes: Points,
    head_to_mri: Transform,
    radii_mm: list[float] | None = None,
    sigmas: list[float] | None = None,
) -> SphereForward:
    c = design()
    radii = np.asarray(c["shell_radii_mm"] if radii_mm is None else radii_mm, dtype=float)
    conduct = np.asarray(c["conductivities_S_m"] if sigmas is None else sigmas, dtype=float)
    if (
        points.frame != Frame.MRI
        or electrodes.frame != Frame.HEAD
        or head_to_mri.source != Frame.HEAD
        or head_to_mri.destination != Frame.MRI
    ):
        raise ValueError("Explicit MRI sources, head electrodes and head-to-MRI transform required")
    if (
        radii.shape != (4,)
        or conduct.shape != (4,)
        or not np.isfinite(radii).all()
        or not np.isfinite(conduct).all()
        or np.any(np.diff(radii) <= 0)
        or not 70 < radii[0] < radii[-1] < 110
        or np.any(conduct <= 0)
        or np.any(conduct > 3)
        or len(points.xyz) < 1
        or np.any(np.linalg.norm(points.xyz, axis=1) >= radii[0] / 1000 - 0.001)
    ):
        raise ValueError("Degenerate geometry or nonphysical tissue parameters")
    mri_to_head = head_to_mri.inverse()
    center = mri_to_head.apply(Points(np.zeros((1, 3)), Frame.MRI)).xyz[0]
    electrode_radius = np.linalg.norm(electrodes.xyz - center, axis=1)
    if len(electrodes.xyz) < 4 or np.min(electrode_radius) <= radii[0] / 1000:
        raise ValueError("Electrodes enter innermost shell")
    names = [f"E{i:02}" for i in range(len(electrodes.xyz))]
    info = mne.create_info(names, 160, "eeg")
    info.set_montage(
        mne.channels.make_dig_montage(
            ch_pos=dict(zip(names, electrodes.xyz, strict=True)), coord_frame="head"
        )
    )
    raw = mne.io.RawArray(np.zeros((len(names), 2)), info, verbose=False)
    raw.set_eeg_reference(projection=True, verbose=False)
    info = raw.info
    src = mne.setup_volume_source_space(
        pos={"rr": points.xyz, "nn": np.tile([0.0, 0.0, 1.0], (len(points.xyz), 1))},
        sphere=(0, 0, 0, radii[0] / 1000),
        add_interpolator=False,
        verbose=False,
    )
    log = io.StringIO()
    handler = logging.StreamHandler(log)
    logger = logging.getLogger("mne")
    logger.addHandler(handler)
    try:
        sphere = mne.make_sphere_model(
            r0=tuple(center),
            head_radius=radii[-1] / 1000,
            relative_radii=tuple(radii / radii[-1]),
            sigmas=tuple(conduct),
            verbose="INFO",
        )
    finally:
        logger.removeHandler(handler)
    match = re.search(r"RV = ([0-9.eE+-]+)", log.getvalue())
    if match is None:
        raise ValueError("MNE approximation residual unavailable")
    native = mne.make_forward_solution(
        info,
        trans=mri_to_head.to_mne(),
        src=src,
        bem=sphere,
        meg=False,
        eeg=True,
        mindist=0,
        n_jobs=1,
        verbose=False,
    )
    projector = average_projector(len(names))
    lead = projector @ native["sol"]["data"]
    if lead.shape != (len(names), 3 * len(points.xyz)) or not np.isfinite(lead).all():
        raise ValueError("Forward source pairing changed or nonfinite solution")
    if not np.allclose(native["source_rr"], mri_to_head.apply(points).xyz, atol=1e-7, rtol=0):
        raise ValueError("MNE transform/source ordering mismatch")
    s = np.linalg.svd(lead, compute_uv=False)
    keep = s > s[0] * max(lead.shape) * np.finfo(float).eps
    rv = float(match.group(1)) / 100
    if (
        rv > c["sphere_fit_max_rv"]
        or np.linalg.norm(lead.sum(axis=0)) / np.linalg.norm(lead) > c["reference_rtol"]
    ):
        raise ValueError(f"Sphere approximation or average reference tolerance failed: RV={rv:.9g}")
    return SphereForward(
        native,
        info,
        lead,
        projector,
        points,
        head_to_mri,
        {
            "sphere_fit_rv": rv,
            "rank": int(keep.sum()),
            "condition_retained": float(s[0] / s[keep][-1]),
            "scalp_fit_rms_mm": float(
                np.sqrt(np.mean((electrode_radius - radii[-1] / 1000) ** 2)) * 1000
            ),
            "units": "V/(A m)",
            "frame": "head",
            "orientation": "free Cartesian",
        },
    )


def kernels(forward: SphereForward, scale: float) -> tuple[dict[str, Array], dict[str, Any]]:
    c = design()
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Fixed positive baseline spectral scale required")
    a = forward.matrix / scale
    kernel = Tikhonov(a, c["tikhonov_lambda2"]).kernel / scale
    from scipy.linalg import solve

    reference = solve(a @ a.T + c["tikhonov_lambda2"] * np.eye(len(a)), a, assume_a="pos").T / scale
    error = float(np.linalg.norm(kernel - reference) / np.linalg.norm(reference))
    residual = float(
        np.linalg.norm((a @ a.T + c["tikhonov_lambda2"] * np.eye(len(a))) @ (kernel * scale).T - a)
        / np.linalg.norm(a)
    )
    if max(error, residual) > c["normal_equation_rtol"]:
        raise ValueError("Independent inverse solve tolerance failed")
    covariance = mne.Covariance(
        (5e-8) ** 2 * forward.projector,
        forward.info["ch_names"],
        [],
        forward.info["projs"],
        nfree=1000,
    )
    operators = {"Tikhonov": kernel}
    inverse_methods: tuple[Literal["MNE", "dSPM"], ...] = ("MNE", "dSPM")
    for method in inverse_methods:
        inv = CorticalInverse(
            forward,
            covariance,
            lambda2=c["mne_lambda2"],
            method=method,
            depth=None,
            orientation="free",
        )
        operators[method] = inv.kernel
    return operators, {
        "svd_vs_independent_solve_relative": error,
        "normal_equation_residual_relative": residual,
    }
