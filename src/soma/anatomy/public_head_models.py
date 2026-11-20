"""Strict public aggregate boundary: anatomy and data-derived fingerprints stay local."""

import json
from typing import Any

import numpy as np

DESIGN_SHA = "89690086412e8682d4f4d19e7657644588b7e240590f15afd2dd464c3cf5d619"
ALLOWED = {
    "baseline_comparison",
    "numerical_target_failures",
    "tissue_metrics",
    "cohorts",
    "tissue_failures",
    "confusion",
    "implementation_sha256",
    "anatomy_status",
    "geometry",
    "readiness",
    "source_coverage",
    "model",
    "segmentation_evidence",
    "full_conductor_accuracy_established",
    "forward_executed",
    "forward",
    "comparisons",
    "inverse_summary",
    "inverse_sources",
    "mesh_quality",
    "electrode_QC",
    "failures",
    "FEM",
    "schema",
    "design_sha256",
    "human_MRI_used",
    "human_localization_accuracy",
    "private_viewer_required",
    "raw_assets_redistributed",
    "seconds",
    "peak_process_MiB",
}
DENIED = {
    "subject",
    "subject_id",
    "participant",
    "path",
    "image",
    "reference_path",
    "assets_sha256",
    "source_sha256",
    "input_sha256",
    "sha256",
    "affine",
    "affine_m",
    "voxel_to_mri_m",
    "voxel_to_RAS_m",
    "head_to_MRI_m",
    "vertices",
    "vertices_m",
    "faces",
    "sources_m",
    "sensors_m",
    "electrodes_m",
    "lead",
    "image_slice",
    "reference_slice",
    "raw_subject_info",
}


def validate_public_head_models(value: dict[str, Any]) -> dict[str, Any]:
    if (
        set(value) - ALLOWED
        or value.get("schema") != "soma.mri-head-model.aggregate/1"
        or value.get("design_sha256") != DESIGN_SHA
    ):
        raise ValueError("Unsupported public anatomical aggregate identity or fields")
    if (
        value.get("human_MRI_used") is not True
        or value.get("human_localization_accuracy") is not False
        or value.get("raw_assets_redistributed") is not False
        or value.get("private_viewer_required") is not True
    ):
        raise ValueError("Unsupported human-anatomy or redistribution claim")

    def scan(x: Any) -> None:
        if isinstance(x, dict):
            if set(x) & DENIED:
                raise ValueError("Participant anatomy/identity/fingerprint cannot be public")
            for k, v in x.items():
                if "sha256" in k and k not in ["design_sha256", "implementation_sha256"]:
                    raise ValueError("Unapproved public data fingerprint")
                scan(v)
        elif isinstance(x, list):
            for v in x:
                scan(v)
        elif isinstance(x, float) and not np.isfinite(x):
            raise ValueError("Nonfinite public metric")
        elif isinstance(x, str) and any(t in x for t in ["/Users/", "/home/", "C:\\Users\\"]):
            raise ValueError("Private path cannot be public")

    scan(value)
    if value.get("anatomy_status") not in [
        "VALIDATED_ANATOMY",
        "QC_ONLY_ANATOMY",
        "NOT_READY_FOR_FORWARD_MODEL",
    ]:
        raise ValueError("Missing anatomical readiness status")
    if (
        value.get("anatomy_status") != "VALIDATED_ANATOMY"
        and value.get("full_conductor_accuracy_established") is not False
    ):
        raise ValueError("Geometric QC cannot establish anatomical accuracy")
    comparisons = value.get("comparisons", [])
    if not isinstance(comparisons, list):
        raise ValueError("Numerical comparison table required")
    for row in comparisons:
        relative, target = row.get("relative"), row.get("target")
        if (
            not isinstance(relative, (float, int))
            or relative < 0
            or target != 0.1
            or row.get("passed") is not (relative <= target)
            or row.get("anatomical_accuracy") is not False
        ):
            raise ValueError("Numerical target or evidence relabeling rejected")
    return value


def read_public_head_models(raw: bytes) -> dict[str, Any]:
    def invalid(_: str) -> None:
        raise ValueError("Invalid public JSON numeric constant")

    value = json.loads(raw, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("Public report object required")
    return validate_public_head_models(value)
