"""Canonical physical contracts and unscaled independent BEM field diagnostics."""

import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np

from soma.anatomy.synthetic import sphere_mesh
from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import _point_triangle, contains, mesh_quality, surface_separation
from soma.imaging.surfaces import Mesh
from soma.protocol.model import SealedProtocol
from soma.results.contracts import canonical
from soma.source.noise import average_projector
from soma.source.nonspherical import boundary_points, head_parameters, meshes
from soma.workflow.model import digest

DESIGN_SHA = "70aa0942ed36ae6b2b75c1fc64fe13bfb5964d079c2d42811b37746923cbf596"


def design() -> dict[str, Any]:
    b = files("soma.resources").joinpath("bem-discrepancy-v28.json").read_bytes()
    if hashlib.sha256(b).hexdigest() != DESIGN_SHA:
        raise ValueError("Frozen diagnostic design drift")
    return dict(json.loads(b))


def protocol() -> SealedProtocol:
    s = SealedProtocol(
        canonical(
            json.loads(
                files("soma.resources").joinpath("bem-discrepancy-protocol-v28-r2.json").read_text()
            )
        )
    )
    if s.protocol.document()["optional_metadata"]["design_sha256"] != DESIGN_SHA:
        raise ValueError("Protocol design mismatch")
    return s


def geometry(head: int | None, levels: list[int]) -> list[Mesh]:
    if len(levels) != 3 or any(level not in (1, 2, 3) for level in levels):
        raise ValueError("Three frozen mesh levels required")
    if head is not None:
        p = head_parameters(head)
        return [meshes(p, level)[j + 1] for j, level in enumerate(levels)]
    out = []
    for radius, level in zip(design()["radii_mm"], levels, strict=True):
        v, f = sphere_mesh(level, radius / 1000)
        out.append(Mesh(Points(v, Frame.MRI), f, {"synthetic": True}))
    return out


def sensors(head: int | None) -> Any:
    u, _ = sphere_mesh(1, 1)
    return u[:32] * 0.09 if head is None else boundary_points(head_parameters(head), 3, u[:32])


def contract_hashes(raw: Any, points: Any, electrodes: Any, sigmas: Any) -> dict[str, str]:
    return dict(
        geometry=digest([dict(vertices=v.tolist(), faces=f.tolist()) for v, f in raw]),
        sources=digest(
            dict(
                xyz_m=points.tolist(),
                basis=np.eye(3).tolist(),
                order="source-major XYZ",
                unit="A*m",
            )
        ),
        sensors=digest(electrodes.tolist()),
        conductivity=digest(dict(values=list(sigmas), unit="S/m")),
        reference=digest(average_projector(len(electrodes)).tolist()),
        frame=digest("MRI RAS metres; identity head/MRI"),
    )


def validate(boundaries: list[Mesh], points: Any, electrodes: Any, sigmas: list[float]) -> None:
    if (
        len(boundaries) not in (1, 3, 4)
        or len(sigmas) != len(boundaries)
        or any(not np.isfinite(s) or not 0 < s <= 3 for s in sigmas)
    ):
        raise ValueError("Conductor topology/conductivity S/m mismatch")
    if any(
        m.vertices.frame != Frame.MRI or np.max(np.abs(m.vertices.xyz)) > 0.12 for m in boundaries
    ):
        raise ValueError("MRI metre scale required")
    for m in boundaries:
        q = mesh_quality(m)
        if not q["geometrically_valid_under_checks"] or not q["outward_global_winding"]:
            raise ValueError("Invalid winding, manifold or intersection")
    for a, b in zip(boundaries[:-1], boundaries[1:], strict=True):
        sep = surface_separation(a, b)
        if (
            sep["intersecting_or_touching_triangle_pairs"]
            or not contains(b, a.vertices.xyz[:1]).all()
        ):
            raise ValueError("Incorrect interface nesting")
    if (
        points.ndim != 2
        or points.shape[1] != 3
        or not 1 <= len(points) <= 80
        or not np.isfinite(points).all()
        or not contains(boundaries[0], points).all()
    ):
        raise ValueError("Invalid source positions or compartment")
    if electrodes.shape != (32, 3) or not np.isfinite(electrodes).all():
        raise ValueError("Canonical 32-sensor array required")
    tri = boundaries[-1].vertices.xyz[boundaries[-1].faces]
    if any(
        _point_triangle(np.broadcast_to(p, (len(tri), 3)), tri).min() > 1e-9 for p in electrodes
    ):
        raise ValueError("Hidden sensor projection: canonical sensors must lie on supplied scalp")


def match(a: dict[str, str], b: dict[str, str]) -> None:
    if a != b:
        raise ValueError("Unmatched geometry/source/sensor/conductivity/reference contracts")


def field_metrics(a: Any, b: Any) -> dict[str, Any]:
    """a is tested, b reference; scalar alignment never replaces physical error."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if (
        a.shape != b.shape
        or a.ndim != 2
        or a.shape[1] % 3
        or not np.isfinite(a).all()
        or not np.isfinite(b).all()
        or np.linalg.norm(b) == 0
        or np.linalg.norm(a) == 0
    ):
        raise ValueError("Incomplete or nonfinite paired lead fields")
    alpha = float(np.sum(a * b) / np.sum(a * a))
    norm = np.linalg.norm(b, axis=0)
    corr = np.sum(a * b, axis=0) / np.maximum(np.linalg.norm(a, axis=0) * norm, 1e-30)
    source_a = a.reshape(len(a), -1, 3)
    source_b = b.reshape(len(b), -1, 3)
    return dict(
        relative=float(np.linalg.norm(a - b) / np.linalg.norm(b)),
        rms_difference_uV=float(np.sqrt(np.mean(((a - b) * 1e-8) ** 2)) * 1e6),
        alignment_scalar=alpha,
        aligned_relative_diagnostic=float(np.linalg.norm(alpha * a - b) / np.linalg.norm(b)),
        column_relative=(np.linalg.norm(a - b, axis=0) / np.maximum(norm, 1e-30)).tolist(),
        column_correlation=corr.tolist(),
        source_relative=(
            np.linalg.norm(source_a - source_b, axis=(0, 2)) / np.linalg.norm(source_b, axis=(0, 2))
        ).tolist(),
        orientation_relative=[
            float(np.linalg.norm(a[:, j::3] - b[:, j::3]) / np.linalg.norm(b[:, j::3]))
            for j in range(3)
        ],
    )


def homogeneous_series(
    points: Any, electrodes: Any, *, sigma: float = 0.33, radius: float = 0.09, terms: int = 128
) -> Any:
    """Neumann sphere: differentiate regular solid harmonics in source coordinates.

    H0=1,H1=u.t,H(n+1)=((2n+1)(u.t)Hn-n(t.t)H(n-1))/(n+1).
    Surface dipole potential is sum((2n+1)/n grad_t Hn)/(4pi sigma R²).
    The n=0 gauge is omitted. t=source/R; all sensor positions lie at R.
    """
    points, electrodes = np.asarray(points, float), np.asarray(electrodes, float)
    if (
        points.ndim != 2
        or points.shape[1] != 3
        or not np.isfinite(points).all()
        or np.max(np.linalg.norm(points, axis=1)) >= 0.8 * radius
        or not np.allclose(np.linalg.norm(electrodes, axis=1), radius, atol=1e-12, rtol=0)
        or not 16 <= terms <= 256
        or not 0 < sigma <= 3
    ):
        raise ValueError("Analytical sphere domain/units/series contract")
    u = electrodes / radius
    blocks = []
    for p in points / radius:
        dot = u @ p
        r2 = p @ p
        h0 = np.ones(len(u))
        h1 = dot.copy()
        g0 = np.zeros_like(u)
        g1 = u.copy()
        total = 3 * g1
        for n in range(1, terms):
            h2 = ((2 * n + 1) * dot * h1 - n * r2 * h0) / (n + 1)
            g2 = (
                (2 * n + 1) * (u * h1[:, None] + dot[:, None] * g1)
                - n * (2 * p * h0[:, None] + r2 * g0)
            ) / (n + 1)
            total = total + (2 * n + 3) / (n + 1) * g2
            h0, h1, g0, g1 = h1, h2, g1, g2
        blocks.append(total / (4 * np.pi * sigma * radius**2))
    return np.concatenate(blocks, axis=1)


def solve(
    boundaries: list[Mesh],
    points: Any,
    electrodes: Any,
    sigmas: list[float],
    output: Path,
    *,
    solver: str,
    ip: bool = True,
    integrator: dict[str, Any] | None = None,
    conductivity_unit: str = "S/m",
) -> tuple[Any, dict[str, Any]]:
    import os
    import subprocess
    import sys

    if conductivity_unit != "S/m" or solver not in ("mne", "openmeeg"):
        raise ValueError("Solver/conductivity unit contract")
    validate(boundaries, points, electrodes, sigmas)
    output.mkdir(parents=True, exist_ok=False)
    arrays = {"points": points, "sensors": electrodes}
    for i, m in enumerate(boundaries):
        arrays.update({f"v{i}": m.vertices.xyz, f"f{i}": m.faces})
    packet = output / "input.npz"
    np.savez_compressed(packet, **arrays)
    request = dict(
        packet=str(packet.resolve()),
        packet_sha256=hashlib.sha256(packet.read_bytes()).hexdigest(),
        solver=solver,
        layers=len(boundaries),
        conductivities_S_m=sigmas,
        conductivity_unit="S/m",
        ip=ip,
        integrator=integrator or dict(order=3, adaptive_levels=0, tolerance=0.001),
    )
    p = output / "request.local.json"
    p.write_text(json.dumps(request))
    worker = Path(__file__).with_name("bem_worker.py")
    env = dict(
        os.environ,
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    env.pop("PYTHONPATH", None)
    try:
        r = subprocess.run(
            [sys.executable, "-I", str(worker), str(p), str(output / "result")],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=design()["budget"]["per_solver_seconds"],
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("Frozen solver time budget exceeded") from exc
    (output / "solver.log").write_text(r.stdout)
    if r.returncode:
        raise ValueError("Solver failed: " + r.stdout[-1500:])
    g = np.load(output / "result/lead.npy", allow_pickle=False)
    d = json.loads((output / "result/diagnostics.json").read_text())
    expected = contract_hashes(
        [(m.vertices.xyz, m.faces) for m in boundaries], points, electrodes, sigmas
    )
    match(d["contracts"], expected)
    if g.shape != (32, 3 * len(points)) or not np.isfinite(g).all():
        raise ValueError("Solver output ordering/shape invalid")
    d["worker_sha256"] = hashlib.sha256(worker.read_bytes()).hexdigest()
    d["packet_sha256"] = request["packet_sha256"]
    return g, d


def triangle_signature(triangles: Any) -> list[Any]:
    rows = []
    for tri in np.asarray(triangles):
        start = min(range(3), key=lambda i: tuple(tri[i]))
        rows.append(tuple(np.roll(tri, -start, axis=0).ravel()))
    return sorted(rows)
