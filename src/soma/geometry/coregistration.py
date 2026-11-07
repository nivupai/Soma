"""Weighted proper rigid alignment and explicitly labeled head-shape ICP."""

from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from soma.geometry import Points, Transform


@dataclass(frozen=True)
class Alignment:
    transform: Transform
    residuals_m: np.ndarray[Any, Any]
    inliers: np.ndarray[Any, Any]
    diagnostics: dict[str, Any]


def rigid_align(
    source: Points,
    target: Points,
    *,
    weights: Any = None,
    robust_cutoff_m: float | None = None,
    seed: int = 42,
) -> Alignment:
    """Minimize sum w ||R source+t-target||², with det(R)=+1.

    Full-rank mirrored correspondences are rejected. Three noncollinear planar
    points identify a proper rigid map but cannot independently certify chirality.
    Robust mode is deterministic RANSAC followed by weighted SVD, not a claim that
    outlier removal establishes the correctness of landmark correspondence.
    """
    x, y = source.xyz, target.xyz
    if x.shape != y.shape or len(x) < 3:
        raise ValueError("At least three corresponding 3D points are required")
    w = np.ones(len(x)) if weights is None else np.asarray(weights, dtype=float)
    if w.shape != (len(x),) or not np.isfinite(w).all() or np.any(w < 0) or np.sum(w > 0) < 3:
        raise ValueError("Finite nonnegative weights with at least three positive values required")
    if robust_cutoff_m is not None:
        if not np.isfinite(robust_cutoff_m) or robust_cutoff_m <= 0:
            raise ValueError("Positive finite robust cutoff in metres required")
        choices = (
            list(combinations(range(len(x)), 3))
            if len(x) <= 12
            else [
                tuple(np.random.default_rng(seed + i).choice(len(x), 3, replace=False))
                for i in range(128)
            ]
        )
        best = None
        best_score = (-1, float("-inf"))
        for indices in choices:
            ids = np.array(indices)
            try:
                candidate = rigid_align(
                    Points(x[ids], source.frame), Points(y[ids], target.frame), weights=w[ids]
                )
            except ValueError:
                continue
            distances = np.linalg.norm(candidate.transform.apply(source).xyz - y, axis=1)
            keep = (distances <= robust_cutoff_m) & (w > 0)
            score = (int(keep.sum()), -float(np.sum(w[keep] * distances[keep] ** 2)))
            if score > best_score:
                best, best_score = keep, score
        if best is None or best.sum() < 3:
            raise ValueError("No nondegenerate robust correspondence set")
        fit = rigid_align(source, target, weights=w * best)
        distances = np.linalg.norm(fit.transform.apply(source).xyz - y, axis=1)
        return Alignment(
            fit.transform,
            distances,
            best,
            {
                **fit.diagnostics,
                "method": "RANSAC_weighted_SVD",
                "cutoff_m": robust_cutoff_m,
                "seed": seed,
                "outliers": int((~best).sum()),
            },
        )
    w = w / w.sum()
    a, b = np.sum(w[:, None] * x, axis=0), np.sum(w[:, None] * y, axis=0)
    xc, yc = x - a, y - b
    singular_x = np.linalg.svd(xc * np.sqrt(w[:, None]), compute_uv=False)
    singular_y = np.linalg.svd(yc * np.sqrt(w[:, None]), compute_uv=False)
    if singular_x[1] <= singular_x[0] * 1e-6 or singular_y[1] <= singular_y[0] * 1e-6:
        raise ValueError("Collinear/coincident or numerically degenerate correspondences")
    u, s, vt = np.linalg.svd((xc * w[:, None]).T @ yc)
    raw = vt.T @ u.T
    full_rank = singular_x[-1] > singular_x[0] * 1e-6 and singular_y[-1] > singular_y[0] * 1e-6
    if full_rank and np.linalg.det(raw) < 0:
        raise ValueError(
            "Mirrored full-rank correspondences require a reflection, not a rigid rotation"
        )
    correction = np.eye(3)
    correction[-1, -1] = np.linalg.det(raw)
    rotation = vt.T @ correction @ u.T
    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = b - rotation @ a
    transform = Transform(source.frame, target.frame, matrix)
    residuals = np.linalg.norm(transform.apply(source).xyz - y, axis=1)
    return Alignment(
        transform,
        residuals,
        w > 0,
        {
            "method": "weighted_SVD_Procrustes",
            "weighted_RMS_m": float(np.sqrt(w @ residuals**2)),
            "max_residual_m": float(np.max(residuals)),
            "singular_values": s.tolist(),
            "rank": int(np.sum(s > s[0] * 1e-6)),
            "reflection_identifiable": bool(full_rank),
            "determinant": float(np.linalg.det(rotation)),
            "source_frame": source.frame.value,
            "destination_frame": target.frame.value,
            "units": "m",
        },
    )


def align_fiducials(
    source: Points,
    source_names: tuple[str, ...],
    target: Points,
    target_names: tuple[str, ...],
    *,
    maximum_residual_m: float | None = None,
) -> Alignment:
    expected = {"LPA", "nasion", "RPA"}
    if (
        set(source_names) != expected
        or set(target_names) != expected
        or len(source_names) != 3
        or len(target_names) != 3
    ):
        raise ValueError("Require unique named LPA/nasion/RPA fiducial correspondences")
    ordered = Points(target.xyz[[target_names.index(n) for n in source_names]], target.frame)
    fit = rigid_align(source, ordered)
    if maximum_residual_m is not None and fit.residuals_m.max() > maximum_residual_m:
        raise ValueError("Fiducial mismatch: residual exceeds the explicit tolerance")
    return fit


def icp_align(
    headshape: Points,
    scalp_vertices: Points,
    initial: Transform,
    *,
    measurement_kind: str,
    iterations: int = 30,
    trim_fraction: float = 0.9,
    max_distance_m: float = 0.03,
    tolerance_m: float = 1e-7,
) -> Alignment:
    if measurement_kind not in ("digitized_headshape", "synthetic_headshape"):
        raise ValueError(
            "ICP requires explicit head-shape points; electrodes/HPI are not head shape"
        )
    if (
        len(headshape.xyz) < 10
        or len(scalp_vertices.xyz) < 10
        or iterations < 1
        or not 0.5 <= trim_fraction <= 1
    ):
        raise ValueError("Insufficient headshape/scalp coverage or invalid ICP settings")
    if initial.source != headshape.frame or initial.destination != scalp_vertices.frame:
        raise ValueError("ICP initial transform has incompatible coordinate frames")
    if max_distance_m <= 0 or tolerance_m <= 0:
        raise ValueError("Positive distance tolerances in metres required")
    tree = cKDTree(scalp_vertices.xyz)
    transform = initial
    previous = float("inf")
    trace = []
    keep = np.ones(len(headshape.xyz), dtype=bool)
    for _ in range(iterations):
        moved = transform.apply(headshape)
        distances, nearest = tree.query(moved.xyz)
        cutoff = min(float(np.quantile(distances, trim_fraction)), max_distance_m)
        keep = distances <= cutoff
        if keep.sum() < 3:
            raise ValueError("Insufficient overlapping ICP correspondences")
        update = rigid_align(
            Points(moved.xyz[keep], moved.frame),
            Points(scalp_vertices.xyz[nearest[keep]], scalp_vertices.frame),
        )
        transform = transform.then(update.transform)
        rms = float(np.sqrt(np.mean(distances[keep] ** 2)))
        trace.append(rms)
        if abs(previous - rms) < tolerance_m:
            break
        previous = rms
    final = np.asarray(tree.query(transform.apply(headshape).xyz)[0], dtype=float)
    return Alignment(
        transform,
        final,
        keep,
        {
            "method": "trimmed_nearest_vertex_ICP",
            "distance_kind": "nearest_scalp_vertex_not_exact_triangle_distance",
            "trace_RMS_m": trace,
            "iterations": len(trace),
            "trim_fraction": trim_fraction,
            "measurement_kind": measurement_kind,
            "fit_RMS_m": float(np.sqrt(np.mean(final[keep] ** 2))),
            "anatomical_ground_truth_claim": False,
        },
    )
