"""Two-session descriptive reliability, never population ICC or causal decomposition."""

from typing import Any

import numpy as np

from soma.fmri.glm import Estimate


def retest(first: Estimate, second: Estimate) -> dict[str, Any]:
    a, b = first.run, second.run
    if any(first.metadata[key] != second.metadata[key] for key in ("q", "correction", "tail")):
        raise ValueError("Retest thresholds/corrections/tails differ")
    if a.subject != b.subject or a.task != b.task or a.space != b.space or a.session == b.session:
        raise ValueError("Retest requires same subject/task/space and distinct documented sessions")
    if first.contrast != second.contrast or not a.mask.same_grid(b.mask):
        raise ValueError("Retest contrast or spatial grid mismatch")
    evidence = a.provenance.get("cross_session_alignment")
    if not evidence or evidence != b.provenance.get("cross_session_alignment"):
        raise ValueError("Validated cross-session anatomical alignment evidence required")
    common = a.mask.array().astype(bool) & b.mask.array().astype(bool)
    if np.count_nonzero(common) < 2:
        raise ValueError("Insufficient common mask coverage")
    x, y = [np.asarray(e.maps["effect_size"].dataobj)[common] for e in [first, second]]
    active = [
        np.asarray(e.maps["fdr_reject"].dataobj)[common].astype(bool) for e in [first, second]
    ]
    denom = sum(int(v.sum()) for v in active)
    return {
        "subject": a.subject,
        "sessions": [a.session, b.session],
        "task": a.task,
        "contrast": first.contrast.name,
        "space": a.space,
        "map_correlation": float(np.corrcoef(x, y)[0, 1])
        if np.std(x) > 0 and np.std(y) > 0
        else None,
        "activation_Dice": 2 * int(np.sum(active[0] & active[1])) / denom if denom else None,
        "threshold": "per-session two-sided BH FDR",
        "q": [first.metadata["q"], second.metadata["q"]],
        "common_mask_voxels": int(common.sum()),
        "ROI_mean_effects": [float(x.mean()), float(y.mean())],
        "ROI_mean_difference": float((y - x).mean()),
        "voxel_RMSE": float(np.sqrt(np.mean((y - x) ** 2))),
        "mean_two_session_sample_variance": float(np.mean((y - x) ** 2) / 2),
        "ICC": "not estimated from two maps of one subject",
        "registration_error_separated": False,
        "physiological_change_identified": False,
        "population_generalization": False,
    }
