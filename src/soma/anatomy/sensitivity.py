"""Finite differences, correspondence-safe comparisons and local covariance propagation."""

from collections.abc import Callable
from typing import Any

import numpy as np


def forward_difference(reference: Any, alternative: Any) -> dict[str, Any]:
    a, b = np.asarray(reference, dtype=float), np.asarray(alternative, dtype=float)
    if a.shape != b.shape or a.ndim != 2 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Finite corresponding forward arrays required")
    base = np.linalg.norm(a)
    if base == 0:
        raise ValueError("Zero reference operator")
    s, t = np.linalg.svd(a, compute_uv=False), np.linalg.svd(b, compute_uv=False)
    return {
        "relative_frobenius": float(np.linalg.norm(b - a) / base),
        "relative_per_channel": (
            np.linalg.norm(b - a, axis=1) / np.maximum(np.linalg.norm(a, axis=1), 1e-300)
        ).tolist(),
        "singular_values_reference": s.tolist(),
        "singular_values_alternative": t.tolist(),
        "relative_spectrum_change": float(np.linalg.norm(t - s) / np.linalg.norm(s)),
    }


def central_differences(
    evaluate: Callable[[float], Any], steps: list[float]
) -> tuple[list[Any], list[dict[str, float | None]]]:
    if not steps or any(not np.isfinite(h) or h <= 0 for h in steps):
        raise ValueError("Positive finite derivative steps required")
    derivatives: list[Any] = []
    records = []
    for h in steps:
        plus, minus = np.asarray(evaluate(h), dtype=float), np.asarray(evaluate(-h), dtype=float)
        if plus.shape != minus.shape or not np.isfinite(plus).all() or not np.isfinite(minus).all():
            raise ValueError("Derivative evaluations do not correspond")
        derivative = (plus - minus) / (2 * h)
        change = (
            None
            if not derivatives
            else float(
                np.linalg.norm(derivative - derivatives[-1])
                / max(np.linalg.norm(derivative), 1e-300)
            )
        )
        derivatives.append(derivative)
        records.append(
            {
                "step": h,
                "derivative_norm": float(np.linalg.norm(derivative)),
                "relative_change_from_previous": change,
            }
        )
    return derivatives, records


def local_covariance(jacobian: Any, parameter_covariance: Any) -> np.ndarray[Any, Any]:
    j, c = np.asarray(jacobian, dtype=float), np.asarray(parameter_covariance, dtype=float)
    if (
        j.ndim != 2
        or c.shape != (j.shape[1],) * 2
        or not np.isfinite(j).all()
        or not np.isfinite(c).all()
        or not np.allclose(c, c.T)
        or np.min(np.linalg.eigvalsh(c)) < -1e-15
    ):
        raise ValueError("Jacobian and PSD parameter covariance must correspond")
    return np.asarray(j @ c @ j.T, dtype=float)
