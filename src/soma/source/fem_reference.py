"""Independent P1 Galerkin full-subtraction EEG reference (optional scikit-fem)."""

import importlib
import time
from typing import Any

import numpy as np
from scipy.sparse.linalg import splu

from soma.geometry import Frame
from soma.source.noise import average_projector
from soma.workflow.model import digest


def tetra_quality(vertices: Any, tetrahedra: Any, labels: Any) -> dict[str, Any]:
    v, t, labels = np.asarray(vertices), np.asarray(tetrahedra), np.asarray(labels)
    if (
        v.ndim != 2
        or v.shape[1] != 3
        or t.ndim != 2
        or t.shape[1] != 4
        or labels.shape != (len(t),)
        or not np.issubdtype(t.dtype, np.integer)
        or not np.issubdtype(labels.dtype, np.integer)
        or not np.isfinite(v).all()
        or np.max(np.abs(v)) > 0.15
        or t.min() < 0
        or t.max() >= len(v)
        or not np.isin(labels, [0, 1, 2, 3]).all()
    ):
        raise ValueError("Invalid metre mesh/tissue labels")
    x = v[t]
    det = np.linalg.det(np.stack([x[:, j] - x[:, 0] for j in (1, 2, 3)], axis=2))
    if np.any(det <= 1e-18):
        raise ValueError("Inverted or degenerate tetrahedra")
    edges = sum(np.sum((x[:, j] - x[:, k]) ** 2, axis=1) for j in range(4) for k in range(j))
    quality = 12 * (3 * det / 6) ** (2 / 3) / edges
    return dict(
        nodes=len(v),
        elements=len(t),
        min_volume_m3=float(det.min() / 6),
        min_mean_ratio=float(quality.min()),
        max_mean_ratio=float(quality.max()),
        tissue_counts=[int(np.sum(labels == i)) for i in range(4)],
        mesh_hash=digest(dict(v=v.tolist(), t=t.tolist(), labels=labels.tolist())),
    )


def radial_mesh(boundaries: list[Any], radial_steps: int) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Conforming ordered-triangle prism split; all four boundary facets are retained."""
    if len(boundaries) != 4 or radial_steps not in (1, 2, 3, 4):
        raise ValueError("Four interfaces and bounded radial schedule required")
    faces = np.asarray(boundaries[0].faces)
    if any(not np.array_equal(b.faces, faces) for b in boundaries):
        raise ValueError("Shared angular topology required")
    surfaces = [np.asarray(b.vertices.xyz) for b in boundaries]
    for mesh in boundaries:
        xyz = mesh.vertices.xyz
        tri = xyz[mesh.faces]
        normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        if (
            mesh.vertices.frame != Frame.MRI
            or not np.isfinite(xyz).all()
            or np.any(np.sum(normals * tri.mean(axis=1), axis=1) <= 0)
        ):
            raise ValueError("Outward star-shaped MRI metre boundaries required")
        edges = np.sort(
            np.concatenate([mesh.faces[:, [0, 1]], mesh.faces[:, [1, 2]], mesh.faces[:, [2, 0]]]),
            axis=1,
        )
        if not np.all(np.unique(edges, axis=0, return_counts=True)[1] == 2):
            raise ValueError("Closed manifold interface required")
    if any(
        np.any(np.linalg.norm(outer, axis=1) <= np.linalg.norm(inner, axis=1))
        for inner, outer in zip(surfaces[:-1], surfaces[1:], strict=True)
    ):
        raise ValueError("Positive nested radial tissue thickness required")
    n = len(surfaces[0])
    shells = []
    shell_labels: Any = []
    previous = np.zeros_like(surfaces[0])
    for tissue, surface in enumerate(surfaces):
        steps = (4 if tissue == 0 else 1) * radial_steps
        for k in range(1, steps + 1):
            shells.append(previous + (surface - previous) * k / steps)
            shell_labels.append(tissue)
        previous = surface
    v = np.concatenate([np.zeros((1, 3)), *shells])
    t: Any = []
    labels: Any = []
    for layer, tissue in enumerate(shell_labels):
        lower = 1 + (layer - 1) * n
        upper = 1 + layer * n
        for a, b, c in np.sort(faces, axis=1):
            if layer == 0:
                t.append([0, upper + a, upper + b, upper + c])
                labels.append(tissue)
            else:
                t.extend(
                    [
                        [lower + a, lower + b, lower + c, upper + c],
                        [lower + a, lower + b, upper + b, upper + c],
                        [lower + a, upper + a, upper + b, upper + c],
                    ]
                )
                labels.extend([tissue] * 3)
    t = np.asarray(t, dtype=np.int64)
    labels = np.asarray(labels, dtype=np.int64)
    x = v[t]
    determinants = np.linalg.det(np.stack([x[:, j] - x[:, 0] for j in (1, 2, 3)], axis=2))
    # Explicitly orient each element; zero-volume elements are still rejected.
    inverted = determinants < 0
    t[inverted, :2] = t[inverted, 1::-1]
    q = tetra_quality(v, t, labels)
    # Independently enumerate element facets and check interface correspondence.
    fs = np.sort(
        np.concatenate(
            [t[:, [0, 1, 2]], t[:, [0, 1, 3]], t[:, [0, 2, 3]], t[:, [1, 2, 3]]], axis=0
        ),
        axis=1,
    )
    labs = np.tile(labels, 4)
    order = np.lexsort(fs.T[::-1])
    fs = fs[order]
    labs = labs[order]
    unique, starts, counts = np.unique(fs, axis=0, return_index=True, return_counts=True)
    if np.any(counts > 2):
        raise ValueError("Nonmanifold volumetric mesh")
    actual_outer = {tuple(row) for row in unique[counts == 1]}
    wanted_outer = {tuple(row) for row in np.sort(faces + 1 + (len(shells) - 1) * n, axis=1)}
    if actual_outer != wanted_outer:
        raise ValueError("Outer boundary mismatch")
    cursor = 0
    for tissue in range(3):
        cursor += (4 if tissue == 0 else 1) * radial_steps
        wanted = {tuple(row) for row in np.sort(faces + 1 + (cursor - 1) * n, axis=1)}
        got = {
            tuple(unique[i])
            for i in np.flatnonzero(counts == 2)
            if set(labs[starts[i] : starts[i] + 2]) == {tissue, tissue + 1}
        }
        if got != wanted:
            raise ValueError("Tissue interface mismatch")
    q.update(
        exact_surface_facets=True,
        boundary_hash=digest([dict(v=s.tolist(), f=faces.tolist()) for s in surfaces]),
    )
    return v, t, labels, q


def full_subtraction(
    vertices: Any,
    tetrahedra: Any,
    labels: Any,
    sources: Any,
    sensors: Any,
    sigmas: list[float],
    *,
    quadrature: int = 4,
    conductivity_unit: str = "S/m",
    frame: str = "MRI_RAS_m",
    boundary: str = "insulating",
    max_residual: float = 1e-8,
) -> tuple[Any, dict[str, Any]]:
    """A(u_c,v)=-∫(σ-σ0)∇u∞·∇v-∮σ0 ∂n u∞ v; φ=u∞+u_c.

    u∞=p·(x-x0)/(4πσ0|x-x0|³). No discrete nodal dipole is inserted.
    Node zero fixes only the correction gauge; sensor average reference is common.
    """
    started = time.perf_counter()
    q = tetra_quality(vertices, tetrahedra, labels)
    if (
        conductivity_unit != "S/m"
        or frame != "MRI_RAS_m"
        or boundary != "insulating"
        or len(sigmas) != 4
        or not all(np.isfinite(s) and 0 < s <= 3 for s in sigmas)
        or quadrature not in (4, 6, 8)
        or not 0 < max_residual <= 1e-6
    ):
        raise ValueError("Unsupported physical units/frame/boundary/quadrature")
    sk = importlib.import_module("skfem")
    helpers = importlib.import_module("skfem.helpers")
    mesh = sk.MeshTet(np.asarray(vertices).T, np.asarray(tetrahedra).T, sort_t=False)
    basis = sk.Basis(mesh, sk.ElementTetP1(), intorder=quadrature)
    fb = sk.FacetBasis(mesh, sk.ElementTetP1(), intorder=quadrature + 2)
    sources = np.asarray(sources, float)
    sensors = np.asarray(sensors, float)
    if (
        sources.ndim != 2
        or sources.shape[1] != 3
        or not 1 <= len(sources) <= 80
        or not np.isfinite(sources).all()
        or sensors.ndim != 2
        or sensors.shape[1] != 3
        or not np.isfinite(sensors).all()
    ):
        raise ValueError("Invalid source/sensor coordinates")
    elements = mesh.element_finder()(*sources.T)
    if np.any(np.asarray(labels)[elements] != 0):
        raise ValueError("Source outside brain compartment")
    # Sensors must be supplied boundary vertices; no projection or interpolation ambiguity.
    ix = np.argmin(np.linalg.norm(np.asarray(vertices)[:, None] - sensors[None], axis=2), axis=0)
    if (
        np.max(np.linalg.norm(np.asarray(vertices)[ix] - sensors, axis=1)) > 1e-12
        or not np.isin(ix, mesh.boundary_nodes()).all()
    ):
        raise ValueError("Sensor coordinates are not exact scalp nodes")
    sigma = np.asarray(sigmas)[labels][:, None]

    def stiffness(u: Any, v: Any, w: Any) -> Any:
        return w.sigma * helpers.dot(helpers.grad(u), helpers.grad(v))

    a = sk.asm(sk.BilinearForm(stiffness), basis, sigma=sigma)
    lu = splu(a[1:, 1:].tocsc())
    cols = []
    residual = []
    balance = []
    sigma0 = sigmas[0]
    for p in sources:
        for moment in np.eye(3):

            def gradient(x: Any, p: Any = p, moment: Any = moment) -> Any:
                d = x - p[:, None, None]
                r = np.sqrt(np.sum(d * d, axis=0))
                return (
                    moment[:, None, None] / r**3
                    - 3 * d * np.sum(d * moment[:, None, None], axis=0) / r**5
                ) / (4 * np.pi * sigma0)

            def volume(v: Any, w: Any) -> Any:
                # Evaluate only outside brain: singular field is never sampled near source.
                return -(w.sigma - sigma0) * helpers.dot(gradient(w.x), helpers.grad(v))

            def flux(v: Any, w: Any) -> Any:
                return -sigma0 * helpers.dot(gradient(w.x), w.n) * v

            outside = np.flatnonzero(np.asarray(labels) != 0)
            b = sk.asm(sk.LinearForm(flux), fb)
            if len(outside):
                ob = basis.with_elements(outside)
                b += sk.asm(
                    sk.LinearForm(volume),
                    ob,
                    sigma=np.asarray(sigmas)[np.asarray(labels)[outside]][:, None],
                )
            imbalance = float(abs(b.sum()) / max(np.linalg.norm(b), 1e-30))
            balance.append(imbalance)
            if imbalance > 1e-3:
                raise ValueError(f"Current conservation/quadrature failed: {imbalance}")
            b -= b.mean()
            u = np.r_[0.0, lu.solve(b[1:])]
            residual.append(float(np.linalg.norm(a @ u - b) / np.linalg.norm(b)))
            d = sensors - p
            cols.append(u[ix] + d @ moment / (4 * np.pi * sigma0 * np.linalg.norm(d, axis=1) ** 3))
    if max(residual) > max_residual:
        raise ValueError("Linear solver nonconvergence")
    lead = average_projector(len(sensors)) @ np.array(cols).T
    return lead, dict(
        **q,
        solver="scikit-fem P1 full subtraction",
        solver_version=sk.__version__,
        independent_of_OpenMEEG=True,
        units="V/(A*m)",
        frame=frame,
        source_order="source-major XYZ",
        quadrature=quadrature,
        relative_residual=max(residual),
        preprojection_current_imbalance=max(balance),
        compatibility_correction="subtract algebraic RHS mean; reported before correction",
        seconds=time.perf_counter() - started,
        reference="sensor average",
    )


def layered_sphere_series(
    sources: Any, sensors: Any, radii: list[float], sigmas: list[float], terms: int = 96
) -> tuple[Any, dict[str, Any]]:
    """Independent concentric transmission solve for each solid-harmonic degree.

    Each shell has a*r^n+b*r^(-n-1), b0=1 fixes the dipole singular field.
    Match potential/current and zero outer flux; no MNE/OpenMEEG coefficients.
    """
    p = np.asarray(sources, float)
    e = np.asarray(sensors, float)
    rs = np.asarray(radii, float)
    if (
        rs.shape != (4,)
        or np.any(np.diff(rs) <= 0)
        or not 0 < rs[0] < rs[-1] <= 0.12
        or len(sigmas) != 4
        or not all(0 < s <= 3 for s in sigmas)
        or not 16 <= terms <= 128
        or p.ndim != 2
        or p.shape[1] != 3
        or np.max(np.linalg.norm(p, axis=1)) >= 0.8 * rs[0]
        or not np.isfinite(p).all()
        or not np.allclose(np.linalg.norm(e, axis=1), rs[-1], rtol=0, atol=1e-12)
    ):
        raise ValueError("Layered analytical sphere domain/units")
    gains = []
    residuals = []
    for n in range(1, terms + 1):
        a = np.zeros((7, 7))
        b = np.zeros(7)

        def coefficients(layer: int, x: float, flux: bool, n: int = n) -> tuple[Any, float]:
            row = np.zeros(7)
            aa = n * x ** (n - 1) if flux else x**n
            bb = -(n + 1) * x ** (-n - 2) if flux else x ** (-n - 1)
            factor = sigmas[layer] if flux else 1.0
            row[0 if layer == 0 else 2 * layer - 1] = factor * aa
            if layer:
                row[2 * layer] = factor * bb
            return row, factor * bb if layer == 0 else 0.0

        for i in range(3):
            for j, flux in enumerate([False, True]):
                left, known = coefficients(i, rs[i] / rs[-1], flux)
                right, _ = coefficients(i + 1, rs[i] / rs[-1], flux)
                a[2 * i + j] = left - right
                b[2 * i + j] = -known
        a[-1], _ = coefficients(3, 1.0, True)
        solution = np.linalg.solve(a, b)
        gains.append(solution[-2] + solution[-1])
        residuals.append(float(np.linalg.norm(a @ solution - b) / np.linalg.norm(b)))
    blocks = []
    u = e / rs[-1]
    for point in p / rs[-1]:
        dot = u @ point
        r2 = point @ point
        h0 = np.ones(len(e))
        h1 = dot.copy()
        g0 = np.zeros_like(u)
        g1 = u.copy()
        total = gains[0] * g1
        for n in range(1, terms):
            h2 = ((2 * n + 1) * dot * h1 - n * r2 * h0) / (n + 1)
            g2 = (
                (2 * n + 1) * (u * h1[:, None] + dot[:, None] * g1)
                - n * (2 * point * h0[:, None] + r2 * g0)
            ) / (n + 1)
            total += gains[n] * g2
            h0, h1, g0, g1 = h1, h2, g1, g2
        blocks.append(total / (4 * np.pi * sigmas[0] * rs[-1] ** 2))
    return average_projector(len(e)) @ np.concatenate(blocks, axis=1), dict(
        terms=terms,
        max_transmission_residual=max(residuals),
        reference="independent concentric harmonic transmission series; insulating exterior",
        units="V/(A*m)",
    )
