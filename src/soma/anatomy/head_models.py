"""MRI frame-chain oracles and explicit conductor evidence levels."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np
from numpy.typing import NDArray

from soma.geometry import Frame, Transform
from soma.geometry.coordinates import validate_affine

Array = NDArray[np.float64]


@dataclass(frozen=True)
class MRIFrameChain:
    voxel_to_scanner_m: Array
    voxel_to_surface_m: Array
    head_to_surface_m: Array

    def __post_init__(self) -> None:
        for name in ["voxel_to_scanner_m", "voxel_to_surface_m", "head_to_surface_m"]:
            a = validate_affine(getattr(self, name)).copy()
            a.flags.writeable = False
            object.__setattr__(self, name, a)
        t = Transform(Frame.HEAD, Frame.MRI, self.head_to_surface_m)
        if not t.rigid:
            raise ValueError("Head/MRI mapping requires proper rigid transform, no reflection")
        for a in [self.voxel_to_scanner_m, self.voxel_to_surface_m]:
            spacing = np.linalg.norm(a[:3, :3], axis=0)
            if np.any(spacing < 1e-5) or np.any(spacing > 0.1):
                raise ValueError("MRI affine must be in metres")

    @classmethod
    def from_mgh(cls, image: Any, head_to_surface: Transform) -> "MRIFrameChain":
        if head_to_surface.source != Frame.HEAD or head_to_surface.destination != Frame.MRI:
            raise ValueError("Explicit head-to-MRI-surface transform direction required")
        scanner = np.asarray(image.affine, float).copy()
        scanner[:3] *= 0.001
        surface = np.asarray(image.header.get_vox2ras_tkr(), float).copy()
        surface[:3] *= 0.001
        return cls(scanner, surface, head_to_surface.matrix)

    def matrix(self, source: str, destination: str) -> Array:
        lps = np.diag([-1.0, -1.0, 1.0, 1.0])
        maps = {
            "voxel_centers": np.eye(4),
            "scanner_RAS_m": self.voxel_to_scanner_m,
            "scanner_LPS_m": lps @ self.voxel_to_scanner_m,
            "MRI_surface_RAS_m": self.voxel_to_surface_m,
            "head_m": np.linalg.inv(self.head_to_surface_m) @ self.voxel_to_surface_m,
        }
        if source not in maps or destination not in maps:
            raise ValueError("Unknown or ambiguous MRI frame")
        return np.asarray(maps[destination] @ np.linalg.inv(maps[source]), float)

    def apply(self, points: Array, source: str, destination: str) -> Array:
        p = np.asarray(points, float)
        if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all():
            raise ValueError("Finite Nx3 coordinates required")
        a = self.matrix(source, destination)
        return np.asarray(p @ a[:3, :3].T + a[:3, 3], float)


class AnatomicalLevel(StrEnum):
    VALIDATED_ANATOMY = "VALIDATED_ANATOMY"
    QC_ONLY_ANATOMY = "QC_ONLY_ANATOMY"
    NOT_READY_FOR_FORWARD_MODEL = "NOT_READY_FOR_FORWARD_MODEL"


COMPUTATIONAL_CHECKS = {
    "topology",
    "nesting",
    "self_intersections",
    "coordinates",
    "electrodes",
    "sources",
    "materials",
}


def classify_anatomy(
    checks: dict[str, bool | None],
    *,
    MRI_derived: bool,
    local_permission: bool,
    conductor_references: dict[str, dict[str, Any]] | None = None,
    independent_tissue_validation: bool = False,
) -> dict[str, Any]:
    if set(checks) != COMPUTATIONAL_CHECKS or any(
        v is not None and not isinstance(v, bool) for v in checks.values()
    ):
        raise ValueError("Complete explicit conductor evidence checks required")
    reason = []
    if not MRI_derived or not local_permission:
        reason.append("missing MRI origin or local-use authorization")
    if not all(v is True for v in checks.values()):
        reason.extend(k for k, v in checks.items() if v is not True)
    if reason:
        level = AnatomicalLevel.NOT_READY_FOR_FORWARD_MODEL
    elif conductor_references is None:
        level = AnatomicalLevel.QC_ONLY_ANATOMY
        reason = ["independent conductor-boundary ground truth unavailable"]
    else:
        valid = (
            set(conductor_references) == {"inner_skull", "outer_skull", "scalp"}
            and independent_tissue_validation
        )
        for r in conductor_references.values():
            valid = (
                valid
                and r.get("independent") is True
                and r.get("reference_role") == "conductor_boundary"
                and isinstance(r.get("provenance"), str)
                and bool(r["provenance"].strip())
            )
            valid = (
                valid
                and isinstance(r.get("Dice"), (int, float))
                and not isinstance(r["Dice"], bool)
                and np.isfinite(r["Dice"])
                and 0.8 <= r["Dice"] <= 1
            )
            valid = (
                valid
                and isinstance(r.get("HD95_mm"), (int, float))
                and not isinstance(r["HD95_mm"], bool)
                and np.isfinite(r["HD95_mm"])
                and 0 <= r["HD95_mm"] <= 5
            )
        level = (
            AnatomicalLevel.VALIDATED_ANATOMY
            if valid
            else AnatomicalLevel.NOT_READY_FOR_FORWARD_MODEL
        )
        if not valid:
            reason = [
                "independent anatomical validation incomplete or failed; "
                "cannot downgrade to successful QC"
            ]
    return {
        "status": str(level),
        "forward_allowed": level != AnatomicalLevel.NOT_READY_FOR_FORWARD_MODEL,
        "anatomical_accuracy_established": level == AnatomicalLevel.VALIDATED_ANATOMY,
        "checks": checks,
        "limitations": reason,
    }


def require_forward_ready(receipt: dict[str, Any]) -> None:
    if (
        receipt.get("status")
        not in [str(AnatomicalLevel.VALIDATED_ANATOMY), str(AnatomicalLevel.QC_ONLY_ANATOMY)]
        or receipt.get("forward_allowed") is not True
    ):
        raise ValueError("NOT_READY_FOR_FORWARD_MODEL: physical forward execution blocked")
