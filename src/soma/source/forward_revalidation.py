"""Forward-model revalidation helpers: refinement, solver agreement and readiness tags.

Pure NumPy utilities used by ``scripts/run_forward_revalidation.py``. The refinement
metric is the M32 one (``scripts/run_mri_head_models.py``): the Frobenius norm of the
difference between two average-referenced lead fields divided by the Frobenius norm
of the finer (or reference) field. Matched numerical differences are not ground-truth
solver error and say nothing about anatomical accuracy.
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]
IntArray = NDArray[np.int64]

REFINEMENT_TARGET = 0.1
PERCENTILES = (5, 25, 50, 75, 95, 99)


def readiness_tag(anatomy_status: str, *, skull_ct_validated: bool) -> dict[str, Any]:
    """Label attached to every result; a numerical pass never upgrades the head."""
    if not anatomy_status:
        raise ValueError("Readiness label required")
    return {
        "head_readiness": anatomy_status,
        "skull_ct_validated": skull_ct_validated,
        "anatomical_accuracy_established": False,
        "statement": (
            f"Numerical forward-model evidence on a {anatomy_status} conductor; "
            + ("skull CT-validated" if skull_ct_validated else "skull not CT-validated")
            + "; not anatomical or source-accuracy validation"
        ),
    }


def subdivide_midpoint(vertices: Array, faces: IntArray) -> tuple[Array, IntArray]:
    """Split each triangle into four at edge midpoints, preserving the surface exactly.

    New vertices lie on the existing flat triangles, so the conductor geometry is
    unchanged and only the boundary-element discretization is refined. Winding is kept.
    """
    v = np.asarray(vertices, dtype=float)
    f = np.asarray(faces, dtype=np.int64)
    if v.ndim != 2 or v.shape[1] != 3 or f.ndim != 2 or f.shape[1] != 3:
        raise ValueError("Vertices n by 3 and faces m by 3 required")
    edges = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    unique, inverse = np.unique(edges, axis=0, return_inverse=True)
    mid = len(v) + inverse.reshape(3, len(f)).T  # midpoints of edges 01, 12, 20
    out_v = np.vstack([v, 0.5 * (v[unique[:, 0]] + v[unique[:, 1]])])
    a, b, c = f[:, 0], f[:, 1], f[:, 2]
    ab, bc, ca = mid[:, 0], mid[:, 1], mid[:, 2]
    out_f = np.concatenate(
        [
            np.stack([a, ab, ca], axis=1),
            np.stack([ab, b, bc], axis=1),
            np.stack([ca, bc, c], axis=1),
            np.stack([ab, bc, ca], axis=1),
        ]
    )
    return out_v, out_f.astype(np.int64)


def average_reference(lead: Array) -> Array:
    """Average-reference the sensor (row) dimension."""
    g = np.asarray(lead, dtype=float)
    if g.ndim != 2 or g.shape[0] < 2:
        raise ValueError("Lead field must be sensors by sources")
    return np.asarray(g - g.mean(axis=0, keepdims=True), dtype=float)


def fixed_orientation(free: Array, normals: Array, rotation: Array | None = None) -> Array:
    """Project a source-major XYZ free lead field onto unit source normals.

    ``rotation`` maps the coefficient frame of ``free`` to the frame of ``normals``
    (for MNE head-frame coefficients and MRI normals it is the head->MRI rotation).
    """
    g = np.asarray(free, dtype=float)
    n = np.asarray(normals, dtype=float)
    if n.ndim != 2 or n.shape[1] != 3 or g.ndim != 2 or g.shape[1] != 3 * len(n):
        raise ValueError("Free lead field must have 3 columns per source normal")
    if not np.allclose(np.linalg.norm(n, axis=1), 1.0, atol=1e-6):
        raise ValueError("Unit normals required")
    xyz = g.reshape(len(g), len(n), 3)
    if rotation is not None:
        r = np.asarray(rotation, dtype=float)
        if r.shape != (3, 3) or not np.allclose(r @ r.T, np.eye(3), atol=1e-6):
            raise ValueError("Rotation must be orthonormal 3 by 3")
        xyz = xyz @ r.T
    return np.asarray(np.einsum("esk,sk->es", xyz, n))


def relative_change(candidate: Array, reference: Array) -> float:
    """M32 metric: ||candidate - reference||_F / ||reference||_F."""
    a, b = np.asarray(candidate, dtype=float), np.asarray(reference, dtype=float)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Matched finite lead fields required")
    scale = float(np.linalg.norm(b))
    if scale == 0:
        raise ValueError("Reference field is zero")
    return float(np.linalg.norm(a - b) / scale)


def per_source(candidate: Array, reference: Array) -> dict[str, Array]:
    """Per-source (column) relative error, correlation and log magnitude ratio."""
    a, b = np.asarray(candidate, dtype=float), np.asarray(reference, dtype=float)
    if a.shape != b.shape or a.ndim != 2:
        raise ValueError("Matched sensors-by-sources lead fields required")
    nb, na = np.linalg.norm(b, axis=0), np.linalg.norm(a, axis=0)
    if np.any(nb == 0) or np.any(na == 0):
        raise ValueError("Zero source topography")
    ac, bc = a - a.mean(axis=0), b - b.mean(axis=0)
    corr = np.sum(ac * bc, axis=0) / (np.linalg.norm(ac, axis=0) * np.linalg.norm(bc, axis=0))
    return {
        "relative_error": np.linalg.norm(a - b, axis=0) / nb,
        "correlation": corr,
        "log_magnitude_ratio": np.log(na / nb),
    }


def summarize(values: Array) -> dict[str, float]:
    """Percentile summary of a finite 1-D array."""
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not len(x) or not np.isfinite(x).all():
        raise ValueError("Nonempty finite vector required")
    out = {f"p{p}": float(np.percentile(x, p)) for p in PERCENTILES}
    out.update(mean=float(x.mean()), min=float(x.min()), max=float(x.max()), count=len(x))
    return out


def margin_strata(
    candidate: Array, reference: Array, margin_m: Array, edges_mm: tuple[float, ...]
) -> list[dict[str, Any]]:
    """Relative change restricted to sources with inner-skull margin >= each edge."""
    m = np.asarray(margin_m, dtype=float)
    if m.shape != (np.asarray(reference).shape[1],):
        raise ValueError("One margin per source required")
    rows = []
    for edge in edges_mm:
        keep = m >= edge * 1e-3
        rows.append(
            {
                "minimum_margin_mm": edge,
                "sources": int(keep.sum()),
                "relative": (
                    relative_change(candidate[:, keep], reference[:, keep]) if keep.any() else None
                ),
            }
        )
    return rows


def minimum_mesh_level(
    changes: list[tuple[str, str, float]], target: float = REFINEMENT_TARGET
) -> str | None:
    """Coarsest level whose change to the next level and every finer change pass.

    ``changes`` are ``(coarse, fine, relative)`` in coarse-to-fine order, consecutive.
    Returns ``None`` when the change between the two finest levels fails the target.
    """
    if not changes or any(changes[i][1] != changes[i + 1][0] for i in range(len(changes) - 1)):
        raise ValueError("Consecutive coarse-to-fine refinement pairs required")
    chosen = None
    for coarse, _, rel in reversed(changes):
        if not np.isfinite(rel) or rel >= target:
            break
        chosen = coarse
    return chosen
