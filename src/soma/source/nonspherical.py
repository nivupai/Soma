"""Bounded synthetic four-interface geometry and explicit physical contracts."""

import hashlib
import json
from importlib.resources import files
from typing import Any

import mne
import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation

from soma.anatomy.synthetic import discrete_sources, sphere_mesh
from soma.geometry import Frame, Points, Transform
from soma.imaging.mesh_quality import _point_triangle, contains, mesh_quality, surface_separation
from soma.imaging.surfaces import Mesh
from soma.protocol.model import SealedProtocol
from soma.results.contracts import canonical
from soma.source.noise import average_projector
from soma.source.uncertainty import SphereForward, fibonacci
from soma.workflow.model import digest

Array = NDArray[np.float64]
DESIGN_SHA = "a42e459d0938c53e6bba99fa0f59522c3fbf585f5bd157984933a5c0b8a78744"


def design() -> dict[str, Any]:
    raw = files("soma.resources").joinpath("nonspherical-v27-r2.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != DESIGN_SHA:
        raise ValueError("Frozen nonspherical design changed")
    return dict(json.loads(raw))


def protocol() -> SealedProtocol:
    raw = files("soma.resources").joinpath("nonspherical-protocol-v27.json").read_text()
    value = SealedProtocol(canonical(json.loads(raw)))
    if value.protocol.document()["optional_metadata"]["design_sha256"] != DESIGN_SHA:
        raise ValueError("Wrong active design/protocol")
    return value


def check_protocol(value: SealedProtocol) -> None:
    if value.protocol.fingerprint != protocol().protocol.fingerprint:
        raise ValueError("Unapproved nonspherical protocol drift")


def head_parameters(head: int) -> dict[str, Any]:
    c = design()
    if head not in c["head_ids"]:
        raise ValueError("Unknown frozen head")
    rng = np.random.default_rng(c["seed"] + head)
    family = c["families"][head]
    axes = np.asarray(c["axes"][family]) + rng.normal(0, c["axis_jitter_sd"], 3)
    centres = np.zeros((4, 3))
    centres[1] = rng.normal(0, c["csf_center_sd_mm"] / 1000, 3)
    centres[2] = rng.normal(0, c["skull_center_sd_mm"] / 1000, 3)
    bump = rng.normal(size=3)
    bump /= np.linalg.norm(bump)
    return {
        "head": head,
        "family": family,
        "seed": c["seed"] + head,
        "axes": axes.tolist(),
        "centres_m": centres.tolist(),
        "a": c["warp_xz"] * ((-1) ** head),
        "b": c["warp_y3"] * ((-1) ** head),
        "bump_direction": bump.tolist(),
    }


def cases() -> list[dict[str, Any]]:
    c = design()
    p = c["perturbations"]
    base = {
        "inner_mm": 0.0,
        "outer_mm": 0.0,
        "local_mm": 0.0,
        "electrode_mm": 0.0,
        "translation_mm": 0.0,
        "rotation_deg": 0.0,
        "skull": 0.004,
    }
    rows = [
        dict(base, id=f"mesh-{level}", family="mesh", level=level)
        for level in c["estimated_mesh_levels"]
    ]
    changes = [
        ("skull_shift", {"inner_mm": p["skull_shift_mm"], "outer_mm": p["skull_shift_mm"]}),
        ("skull_thickness", {"outer_mm": p["skull_thickness_mm"]}),
        ("csf_boundary", {"inner_mm": p["csf_boundary_mm"]}),
        ("local_skull", {"local_mm": p["local_skull_mm"]}),
        ("electrode", {"electrode_mm": p["electrode_tangent_mm"]}),
        (
            "registration",
            {
                "translation_mm": p["registration_translation_mm"],
                "rotation_deg": p["registration_rotation_deg"],
            },
        ),
        ("conductivity", {"skull": p["skull_conductivity_S_m"]}),
        (
            "interaction",
            {"outer_mm": p["skull_thickness_mm"], "skull": p["skull_conductivity_S_m"]},
        ),
    ]
    rows += [{**base, **change, "id": name, "family": name, "level": 2} for name, change in changes]
    return rows


def boundary_points(
    parameters: dict[str, Any], layer: int, directions: Array, case: dict[str, Any] | None = None
) -> Array:
    c = design()
    case = case or {}
    if layer not in range(4) or directions.ndim != 2 or directions.shape[1] != 3:
        raise ValueError("Invalid boundary/orientation array")
    if not np.isfinite(directions).all() or not np.allclose(
        np.linalg.norm(directions, axis=1), 1, atol=1e-12
    ):
        raise ValueError("Unit directions required")
    u = directions
    radius = c["radii_mm"][layer]
    radius += (
        case.get("inner_mm", 0) if layer == 1 else case.get("outer_mm", 0) if layer == 2 else 0
    )
    warp = np.exp(parameters["a"] * u[:, 0] * u[:, 2] + parameters["b"] * u[:, 1] ** 3)
    rr = radius * warp / 1000
    if layer == 2:
        distance = np.sum((u - np.asarray(parameters["bump_direction"])) ** 2, axis=1)
        rr += (
            (c["baseline_local_skull_bump_mm"] + case.get("local_mm", 0))
            / 1000
            * np.exp(-distance / (2 * c["bump_width"] ** 2))
        )
    return np.asarray(
        u * np.asarray(parameters["axes"]) * rr[:, None]
        + np.asarray(parameters["centres_m"])[layer],
        dtype=float,
    )


def meshes(
    parameters: dict[str, Any], level: int, case: dict[str, Any] | None = None
) -> list[Mesh]:
    if level not in (0, 1, 2, 3):
        raise ValueError("Unplanned mesh density")
    u, triangles = sphere_mesh(level, 1)
    return [
        Mesh(
            Points(boundary_points(parameters, j, u, case), Frame.MRI),
            triangles,
            {"synthetic": True, "head": parameters["head"], "layer": j, "level": level},
        )
        for j in range(4)
    ]


def mesh_fingerprint(boundaries: list[Mesh]) -> str:
    return digest(
        [
            {
                "xyz": m.vertices.xyz.tolist(),
                "faces": m.faces.tolist(),
                "frame": m.vertices.frame.value,
            }
            for m in boundaries
        ]
    )


def validate_meshes(boundaries: list[Mesh]) -> dict[str, Any]:
    c = design()
    if len(boundaries) != 4 or any(m.vertices.frame != Frame.MRI for m in boundaries):
        raise ValueError("Exactly four MRI/RAS metre boundaries required")
    quality = []
    for mesh in boundaries:
        q = mesh_quality(mesh)
        tri = mesh.vertices.xyz[mesh.faces]
        edges2 = np.sum((tri - np.roll(tri, 1, axis=1)) ** 2, axis=2)
        area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
        aspect = float(np.max(np.sqrt(3) * np.max(edges2, axis=1) / np.maximum(4 * area, 1e-30)))
        outward = np.einsum(
            "ij,ij->i",
            np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]),
            tri.mean(axis=1) - mesh.vertices.xyz.mean(axis=0),
        )
        if (
            not q["geometrically_valid_under_checks"]
            or not q["outward_global_winding"]
            or np.any(outward <= 0)
            or q["triangle_quality_min"] < c["min_triangle_quality"]
            or aspect > c["max_aspect_ratio"]
        ):
            raise ValueError(
                "Invalid geometry: mesh orientation, intersections, manifold or quality"
            )
        quality.append(
            {k: v for k, v in q.items() if k != "triangle_quality"} | {"aspect_ratio_max": aspect}
        )
    pairs = []
    for inner, outer in zip(boundaries[:-1], boundaries[1:], strict=True):
        pair = surface_separation(inner, outer)
        inside = bool(contains(outer, inner.vertices.xyz[:1]).all())
        if (
            not inside
            or pair["intersecting_or_touching_triangle_pairs"]
            or pair["minimum_triangle_distance_m"] * 1000 < c["min_thickness_mm"]
        ):
            raise ValueError("Invalid nested geometry or insufficient tissue thickness")
        pairs.append(pair)
    return {
        "quality": quality,
        "pairs": pairs,
        "minimum_thickness_mm": min(p["minimum_triangle_distance_m"] for p in pairs) * 1000,
        "fingerprint": mesh_fingerprint(boundaries),
        "anatomical_validation": False,
    }


def radial_projection(surface: Mesh, targets: Array) -> tuple[Array, Array]:
    """Explicit ray/triangle scalp discretization; never repair the mesh."""
    if (
        targets.ndim != 2
        or targets.shape[1] != 3
        or not np.isfinite(targets).all()
        or np.any(np.linalg.norm(targets, axis=1) < 1e-12)
    ):
        raise ValueError("Nonzero finite sensor targets required")
    tri = surface.vertices.xyz[surface.faces]
    a = tri[:, 0]
    e1 = tri[:, 1] - a
    e2 = tri[:, 2] - a
    out = []
    for point in targets:
        direction = point / np.linalg.norm(point)
        h = np.cross(np.broadcast_to(direction, e2.shape), e2)
        det = np.sum(e1 * h, axis=1)
        good = np.abs(det) > 1e-15
        inv = np.divide(1.0, det, out=np.zeros_like(det), where=good)
        s = -a
        u = inv * np.sum(s * h, axis=1)
        q = np.cross(s, e1)
        v = inv * (q @ direction)
        t = inv * np.sum(e2 * q, axis=1)
        valid = good & (u >= -1e-10) & (v >= -1e-10) & (u + v <= 1 + 1e-10) & (t > 0)
        if not valid.any():
            raise ValueError("Sensor ray does not intersect intended scalp")
        out.append(direction * np.min(t[valid]))
    positions = np.asarray(out)
    return positions, np.linalg.norm(positions - targets, axis=1) * 1000


def source_grid() -> Points:
    c = design()
    u = fibonacci(c["candidate_sources_per_shell"])
    return Points(np.vstack([u * r / 1000 for r in c["candidate_radii_mm"]]), Frame.MRI)


def check_sources(boundary: Mesh, points: Points) -> None:
    if points.frame != Frame.MRI or not len(points.xyz) or not contains(boundary, points.xyz).all():
        raise ValueError("Dipoles outside allowed MRI brain domain")
    tri = boundary.vertices.xyz[boundary.faces]
    if any(
        _point_triangle(np.broadcast_to(p, (len(tri), 3)), tri).min() * 1000
        < design()["dipole_boundary_margin_mm"]
        for p in points.xyz
    ):
        raise ValueError("Dipole boundary margin failed")


def sensor_targets(parameters: dict[str, Any], case: dict[str, Any] | None = None) -> Array:
    c = design()
    case = case or {}
    u = fibonacci(c["sensors"], -0.35)
    if case.get("electrode_mm", 0):
        delta = np.random.default_rng(c["seed"] + 20000 + parameters["head"]).normal(size=u.shape)
        delta -= np.sum(delta * u, axis=1)[:, None] * u
        delta *= case["electrode_mm"] / 1000 / 0.09 / np.sqrt(np.mean(np.sum(delta**2, axis=1)))
        u = u + delta
        u /= np.linalg.norm(u, axis=1)[:, None]
    xyz = boundary_points(parameters, 3, u)
    return xyz


def pose(case: dict[str, Any]) -> Transform:
    matrix = np.eye(4)
    matrix[:3, :3] = Rotation.from_euler("z", case.get("rotation_deg", 0), degrees=True).as_matrix()
    matrix[0, 3] = case.get("translation_mm", 0) / 1000
    return Transform(Frame.HEAD, Frame.MRI, matrix)


def convergence(errors: list[float]) -> dict[str, Any]:
    if len(errors) != 3 or not np.isfinite(errors).all() or any(x < 0 for x in errors):
        raise ValueError("Three finite ordered mesh errors required")
    c = design()
    ratios = [errors[i + 1] / max(errors[i], 1e-30) for i in range(2)]
    return {
        "status": "CONVERGED"
        if errors[-1] <= c["mesh_reference_rtol"]
        and all(r <= c["successive_error_ratio_max"] for r in ratios)
        else "NOT_CONVERGED",
        "errors": errors,
        "ratios": ratios,
        "rates_log2": [float(-np.log2(max(r, 1e-30))) for r in ratios],
    }


def native_forward(
    lead: Array, points: Points, electrodes: Array, transform: Transform
) -> SphereForward:
    """Only metadata adaptation: every physical lead-field entry is supplied by BEM."""
    from mne._fiff.constants import FIFF

    if (
        points.frame != Frame.MRI
        or lead.shape != (len(electrodes), len(points.xyz) * 3)
        or not np.isfinite(lead).all()
    ):
        raise ValueError("Incomplete/nonfinite forward matrix or source pairing")
    if transform.source != Frame.HEAD or transform.destination != Frame.MRI:
        raise ValueError("Explicit head-to-MRI transform required")
    n = len(electrodes)
    names = [f"E{i:02}" for i in range(n)]
    info = mne.create_info(names, 160, "eeg")
    info.set_montage(
        mne.channels.make_dig_montage(
            ch_pos=dict(zip(names, electrodes, strict=True)), coord_frame="head"
        )
    )
    raw = mne.io.RawArray(np.zeros((n, 2)), info, verbose=False)
    raw.set_eeg_reference(projection=True, verbose=False)
    info = raw.info
    src = discrete_sources(points.xyz)
    head_xyz = transform.inverse().apply(points).xyz
    for s in src:
        s["rr"] = head_xyz.copy()
        s["nn"] = np.tile([0.0, 0.0, 1.0], (len(head_xyz), 1))
        s["coord_frame"] = FIFF.FIFFV_COORD_HEAD
    cart = lead.reshape(n, -1, 3) @ transform.matrix[:3, :3]
    g = cart.reshape(n, -1)
    native = mne.Forward(
        sol=dict(data=g, nrow=n, ncol=g.shape[1], row_names=names, col_names=[]),
        sol_grad=None,
        _orig_sol=g.copy(),
        _orig_sol_grad=None,
        nchan=n,
        nsource=len(points.xyz),
        source_ori=FIFF.FIFFV_MNE_FREE_ORI,
        _orig_source_ori=FIFF.FIFFV_MNE_FREE_ORI,
        coord_frame=FIFF.FIFFV_COORD_HEAD,
        source_rr=head_xyz,
        source_nn=np.tile(np.eye(3), (len(points.xyz), 1)),
        surf_ori=False,
        mri_head_t=transform.inverse().to_mne(),
        src=src,
        info=info,
    )
    p = average_projector(n)
    return SphereForward(
        native,
        info,
        p @ g,
        p,
        points,
        transform,
        {"solver": "supplied nonspherical BEM; SphereForward reused only as metadata container"},
    )
