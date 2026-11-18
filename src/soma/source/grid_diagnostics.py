"""Explicitly compatible resolution comparisons and synthetic evidence guards."""

from typing import Any

import numpy as np


def resolution_difference(
    a: Any, b: Any, grid_a: Any, grid_b: Any, unit_a: str, unit_b: str
) -> float:
    a, b, ga, gb = map(np.asarray, [a, b, grid_a, grid_b])
    if (
        ga.shape != gb.shape
        or ga.ndim != 2
        or ga.shape[1] != 3
        or not np.array_equal(ga, gb)
        or a.shape != b.shape
        or a.shape != (3 * len(ga), 3 * len(ga))
        or not np.isfinite(a).all()
        or not np.isfinite(b).all()
        or unit_a != unit_b
        or unit_a not in ("1", "1/(A*m)")
        or np.linalg.norm(b) == 0
    ):
        raise ValueError(
            "Resolution operators require identical ordered grids and compatible units"
        )
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def validate_evidence(value: dict[str, Any]) -> None:
    from soma.experiments.mesh_grid import protocol

    if (
        value.get("schema") != "soma.mesh-grid.explorer/1"
        or value.get("synthetic_only") is not True
        or value.get("human_subjects") != 0
        or value.get("threshold") != 0.1
        or value.get("mesher") != "Gmsh4.15.2"
        or value.get("protocol") != protocol().protocol.fingerprint
    ):
        raise ValueError("Unsupported independent mesh evidence or modified threshold")

    rows = value.get("configurations", [])
    receipt = value.get("receipt", {})
    if receipt.get("computed_fields") != sum(
        r.get("status") == "computed" for r in rows
    ) or receipt.get("failed_fields") != sum(r.get("status") != "computed" for r in rows):
        raise ValueError("Unreported configuration failure")
