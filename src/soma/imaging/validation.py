"""Geometry diagnostics and independent physical landmark acceptance metrics."""

from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from soma.geometry import Transform
from soma.imaging.volumes import Volume


def validate_volume(
    volume: Volume,
    *,
    expected_axis_codes: tuple[str, str, str] | None = None,
    check_data: bool = False,
) -> dict[str, Any]:
    geometry = volume.geometry()
    diagnostics = list(volume.metadata.get("diagnostics", []))
    if expected_axis_codes is not None and tuple(geometry["axis_codes"]) != expected_axis_codes:
        diagnostics.append(
            "unexpected_storage_axis_codes; this alone is not anatomical left_right_error"
        )
    if min(volume.spacing_m) < 0.0001 or max(volume.spacing_m) > 0.02:
        diagnostics.append("unusual_structural_voxel_spacing")
    # Independent homogeneous multiplication vs our VoxelMap, including outside-grid points.
    probes = np.array([[0.0, 0, 0], [1.0, 2, 3], np.array(volume.shape) - 1])
    world = volume.grid.to_world(probes)
    roundtrip = volume.grid.to_voxel(world)
    error = float(np.max(np.abs(roundtrip - probes)))
    result: dict[str, Any] = {
        "geometry": geometry,
        "metadata": volume.metadata,
        "diagnostics": diagnostics,
        "voxel_roundtrip_max_voxels": error,
        "physical_roundtrip_bound_m": error * float(np.linalg.norm(volume.affine_m[:3, :3], 2)),
        "finite_data_checked": check_data,
    }
    if check_data:
        data = volume.array()
        result["nonfinite_voxels"] = int(np.sum(~np.isfinite(data)))
        result["valid"] = bool(np.isfinite(data).all())
    else:
        result["valid"] = True
    return result


def transform_error(estimated: Transform, truth: Transform, landmarks_m: Any) -> dict[str, float]:
    landmarks = np.asarray(landmarks_m)
    predicted = landmarks @ estimated.matrix[:3, :3].T + estimated.matrix[:3, 3]
    expected = landmarks @ truth.matrix[:3, :3].T + truth.matrix[:3, 3]
    distances = np.linalg.norm(predicted - expected, axis=1)

    # Polar factors compare rotations separately from affine scaling/shear.
    def rotation(matrix: Any) -> Any:
        u, _, vt = np.linalg.svd(matrix)
        return u @ vt

    relative = rotation(estimated.matrix[:3, :3]) @ rotation(truth.matrix[:3, :3]).T
    return {
        "translation_error_m": float(np.linalg.norm(estimated.matrix[:3, 3] - truth.matrix[:3, 3])),
        "rotation_error_deg": float(np.rad2deg(Rotation.from_matrix(relative).magnitude())),
        "median_landmark_TRE_m": float(np.median(distances)),
        "max_landmark_TRE_m": float(np.max(distances)),
        "affine_linear_error_frobenius": float(
            np.linalg.norm(estimated.matrix[:3, :3] - truth.matrix[:3, :3])
        ),
        "inverse_consistency_error": float(
            np.linalg.norm(estimated.inverse().matrix @ estimated.matrix - np.eye(4))
        ),
    }
