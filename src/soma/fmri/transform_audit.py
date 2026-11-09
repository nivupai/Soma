"""ITK transform receipts retain nonlinear representations and explicit point direction."""

import re
from pathlib import Path
from typing import Any

import numpy as np
import SimpleITK as sitk

from soma.core.provenance import sha256
from soma.geometry import Points
from soma.geometry.coordinates import ras_lps, validate_affine
from soma.imaging.nifti import load_nifti


def audit_transform(spec: dict[str, Any], *, subject: str) -> dict[str, Any]:
    required = {
        "path",
        "subject",
        "from_space",
        "to_space",
        "point_direction",
        "kind",
        "reference",
        "source_image",
    }
    if not required.issubset(spec) or spec["subject"] != subject:
        raise ValueError("Transform subject or explicit spatial provenance missing/mismatched")
    if spec["point_direction"] not in {"source_to_target", "target_to_source"}:
        raise ValueError("Explicit physical point transform direction required")
    if spec["kind"] not in {"affine", "nonlinear"}:
        raise ValueError("Transform kind must preserve affine/nonlinear semantics")
    path = Path(spec["path"])
    for key in ["path", "reference", "source_image"]:
        labels = re.findall(r"(?:^|[/_])sub-([A-Za-z0-9]+)", str(spec[key]))
        if any(label != subject for label in labels):
            raise ValueError("Transform asset subject identity mismatch")
    for token in [f"from-{spec['from_space']}", f"to-{spec['to_space']}"]:
        if token not in path.name:
            raise ValueError("Transform filename and declared direction disagree")
    reference = load_nifti(Path(spec["reference"]))
    source = load_nifti(Path(spec["source_image"]))
    transform = sitk.ReadTransform(str(path))
    if transform.GetDimension() != 3:
        raise ValueError("Only explicitly three-dimensional ITK transforms supported")
    linear = bool(transform.IsLinear())
    if spec["kind"] == "affine" and not linear:
        raise ValueError("Nonlinear transform cannot be declared affine")
    if spec["kind"] == "affine":
        offset = np.asarray(transform.TransformPoint((0.0, 0.0, 0.0)))
        columns = [np.asarray(transform.TransformPoint(tuple(v))) - offset for v in np.eye(3)]
        matrix = np.eye(4)
        matrix[:3, :3] = np.column_stack(columns)
        try:
            validate_affine(matrix)
        except ValueError as exc:
            raise ValueError("Singular affine transform has no stable inverse") from exc
    inverse_available = True
    try:
        transform.GetInverse()
    except RuntimeError:
        inverse_available = False
    if spec["kind"] == "affine" and not inverse_available:
        raise ValueError("Singular affine transform has no valid inverse")
    result = {
        "status": "PASS",
        "kind": spec["kind"],
        "ITK_name": transform.GetName(),
        "linear": linear,
        "point_direction": spec["point_direction"],
        "units": "ITK LPS mm; Soma RAS m",
        "from_space": spec["from_space"],
        "to_space": spec["to_space"],
        "sha256": sha256(path),
        "source_grid": source.geometry(),
        "reference_grid": reference.geometry(),
        "source_sha256": sha256(Path(spec["source_image"])),
        "reference_sha256": sha256(Path(spec["reference"])),
        "inverse_available": inverse_available,
        "anatomical_validity": "INDETERMINATE",
        "landmark_status": "INDETERMINATE",
        "landmark_error_mm": None,
    }
    if "landmarks_source_RAS_m" in spec or "landmarks_target_RAS_m" in spec:
        x = np.asarray(spec["landmarks_source_RAS_m"], float)
        expected = np.asarray(spec["landmarks_target_RAS_m"], float)
        from soma.geometry import Frame

        x = Points(x, Frame.RAS).xyz
        expected = Points(expected, Frame.RAS).xyz
        if x.shape != expected.shape or len(x) < 3:
            raise ValueError("At least three paired controlled landmarks required")
        for values, grid in [(x, source), (expected, reference)]:
            voxel = grid.grid.to_voxel(Points(values, Frame.RAS))
            if np.any(voxel < -1e-5) or np.any(voxel > np.array(grid.shape) - 1 + 1e-5):
                raise ValueError("Controlled landmarks lie outside declared reference/source grid")
        if spec["point_direction"] == "target_to_source":
            x, expected = expected, x
        xyz = ras_lps().apply(Points(x, Frame.RAS)).xyz * 1000
        predicted = np.array([transform.TransformPoint(tuple(point)) for point in xyz]) / 1000
        predicted = ras_lps().inverse().apply(Points(predicted, Frame.LPS)).xyz
        errors = np.linalg.norm(predicted - expected, axis=1) * 1000
        tolerance = float(spec.get("landmark_tolerance_mm", 0.01))
        if not np.isfinite(tolerance) or not 0 < tolerance <= 5:
            raise ValueError("Explicit bounded landmark tolerance required")
        result.update(
            landmark_error_mm=errors.tolist(),
            landmark_status="PASS" if np.max(errors) <= tolerance else "FAIL",
        )
        if result["landmark_status"] == "FAIL":
            raise ValueError("Transform landmark/direction/units check failed")
    return result


def alignment_qc(
    first: np.ndarray[Any, Any], second: np.ndarray[Any, Any], mask: np.ndarray[Any, Any]
) -> dict[str, Any]:
    if first.shape != second.shape or mask.shape != first.shape or np.count_nonzero(mask) < 2:
        raise ValueError("Alignment QC requires explicitly matched grids and mask coverage")
    x, y = first[mask.astype(bool)], second[mask.astype(bool)]
    if not np.isfinite([x, y]).all():
        raise ValueError("Nonfinite alignment intensities")
    return {
        "intensity_correlation": float(np.corrcoef(x, y)[0, 1])
        if np.std(x) > 0 and np.std(y) > 0
        else None,
        "normalized_RMSE": float(
            np.sqrt(
                np.mean(
                    ((x - x.mean()) / max(x.std(), 1e-12) - (y - y.mean()) / max(y.std(), 1e-12))
                    ** 2
                )
            )
        ),
        "scope": "heuristic on supplied common grid; not independent anatomical truth",
    }
