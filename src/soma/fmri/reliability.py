"""Session differences and subject-level absolute-agreement reliability."""

from typing import Any

import numpy as np
import pandas as pd

from soma.fmri.glm import Estimate
from soma.fmri.retest import retest
from soma.statistics.hierarchical import ResamplingConfig, subject_bootstrap


def session_reliability(first: Estimate, second: Estimate) -> dict[str, Any]:
    a, b = first.run, second.run
    if a.preprocessing not in {"validated", "synthetic"} or b.preprocessing not in {
        "validated",
        "synthetic",
    }:
        raise ValueError(
            "M14 reliability requires audited preprocessed or explicitly synthetic runs"
        )
    scale = a.provenance.get("effect_scale_identity")
    if not scale or scale != b.provenance.get("effect_scale_identity"):
        raise ValueError("Session effect scales are not explicitly comparable")
    if any(first.metadata[k] != second.metadata[k] for k in ["hrf_model", "smoothing_fwhm_mm"]):
        raise ValueError("Session HRF/smoothing comparability differs")
    if a.provenance.get("roi_ontology") != b.provenance.get("roi_ontology"):
        raise ValueError("Session ROI ontology differs")
    result = retest(first, second)
    mask = a.mask.array().astype(bool) & b.mask.array().astype(bool)
    effects = [np.asarray(e.maps["effect_size"].dataobj) for e in [first, second]]
    reject = [np.asarray(e.maps["fdr_reject"].dataobj).astype(bool) & mask for e in [first, second]]
    sign_results = {}
    for sign in [1, -1]:
        active = [r & (values * sign > 0) for r, values in zip(reject, effects, strict=True)]
        denom = sum(int(x.sum()) for x in active)
        features: list[Any] = []
        for selected, values in zip(active, effects, strict=True):
            if not np.any(selected):
                features.append(None)
                continue
            index = np.unravel_index(
                np.argmax(np.where(selected, values * sign, -np.inf)), values.shape
            )
            features.append(a.mask.grid.to_world(np.asarray([index], float)).xyz[0])
        displacement = (
            float(np.linalg.norm(features[0] - features[1]) * 1000)
            if all(x is not None for x in features)
            else None
        )
        sign_results["positive" if sign == 1 else "negative"] = {
            "Dice": 2 * int(np.sum(active[0] & active[1])) / denom if denom else None,
            "extremum_displacement_mm": displacement,
            "feature_scope": "FDR-selected noisy extrema; not exact anatomy",
        }
    means = result["ROI_mean_effects"]
    difference = means[1] - means[0]
    result.update(
        {
            "sign_specific": sign_results,
            "absolute_ROI_change": abs(difference),
            "symmetric_relative_ROI_change": 2 * difference / (abs(means[0]) + abs(means[1]))
            if abs(means[0]) + abs(means[1]) > 1e-8
            else None,
            "relative_change_warning": "near-zero means unstable; ratio undefined at zero",
            "mask_intersection_fraction": [
                float(mask.sum() / r.mask.array().sum()) for r in [a, b]
            ],
            "within_session_mean_voxel_variance": [
                float(np.asarray(e.maps["effect_variance"].dataobj)[mask].mean())
                for e in [first, second]
            ],
            "ROI_mean_standard_error": "not available without spatial covariance",
            "motion_QC": [r.provenance.get("motion_QC") for r in [a, b]],
            "statistical_units": {
                "session_comparison": "paired maps of one participant",
                "cohort": "participant",
            },
            "preprocessing_audit_identities": [
                r.provenance.get("audit_identity", "synthetic") for r in [a, b]
            ],
        }
    )
    return result


def _icc(values: np.ndarray[Any, Any]) -> float | None:
    n, k = values.shape
    grand = values.mean()
    row = values.mean(axis=1)
    column = values.mean(axis=0)
    ms_subject = k * np.sum((row - grand) ** 2) / (n - 1)
    ms_session = n * np.sum((column - grand) ** 2) / (k - 1)
    ms_error = np.sum((values - row[:, None] - column[None, :] + grand) ** 2) / ((n - 1) * (k - 1))
    denominator = ms_subject + (k - 1) * ms_error + k * (ms_session - ms_error) / n
    return float((ms_subject - ms_error) / denominator) if abs(denominator) > 1e-15 else None


def cohort_reliability(
    table: pd.DataFrame,
    *,
    statistical_unit: str = "subject",
    seed: int = 14042,
    n_bootstrap: int = 2000,
) -> dict[str, Any]:
    if statistical_unit != "subject":
        raise ValueError("Voxels are not independent participants")
    if (
        not {"subject", "session", "effect"}.issubset(table)
        or table.duplicated(["subject", "session"]).any()
    ):
        raise ValueError("Unique subject/session ROI observations required")
    wide = table.pivot(index="subject", columns="session", values="effect")
    if wide.shape[1] != 2 or len(wide) < 5 or not np.isfinite(wide.to_numpy()).all():
        raise ValueError("ICC requires at least5 complete participants and exactly two sessions")
    values = wide.to_numpy(float)
    estimate = _icc(values)
    rng = np.random.default_rng(seed)
    boot = [_icc(values[rng.integers(0, len(values), len(values))]) for _ in range(n_bootstrap)]
    valid = np.array([v for v in boot if v is not None])
    delete = [_icc(np.delete(values, i, axis=0)) for i in range(len(values))]
    differences = values[:, 1] - values[:, 0]
    mean = subject_bootstrap(differences, ResamplingConfig(seed=seed, n_bootstrap=n_bootstrap))
    return {
        "model": "ICC(A,1), two-way random, absolute agreement, single measurement",
        "assumptions": "independent subjects; two exchangeable random sessions, balanced sample",
        "n_subjects": len(values),
        "n_sessions": 2,
        "ICC": estimate,
        "subject_bootstrap_CI95": np.quantile(valid, [0.025, 0.975]).tolist()
        if len(valid)
        else None,
        "undefined_bootstrap_draws": len(boot) - len(valid),
        "delete_one_ICC": delete,
        "mean_paired_effect_change": mean,
        "between_subject_mean_variance": float(np.var(values.mean(axis=1), ddof=1)),
        "mean_within_subject_two_session_variance": float(np.mean(differences**2) / 2),
        "voxel_independence_assumed": False,
        "negative_ICC_clamped": False,
        "uncertainty_scope": "participant resampling; not registration or clinical validity",
    }


def regional_reliability(
    first: Estimate, second: Estimate, roi: Any, chain: Any = None
) -> dict[str, Any]:
    from soma.fmri.spatial import SpatialMap, align_roi
    from soma.imaging.volumes import Volume

    session_reliability(first, second)
    if not all(
        roi.provenance.get(key)
        for key in ["atlas_name", "atlas_version", "hemisphere_convention", "label_mapping"]
    ):
        raise ValueError(
            "Explicit atlas version, hemisphere conventions and label mapping required"
        )
    target = SpatialMap(
        Volume(first.maps["effect_size"].get_fdata(), first.run.mask.affine_m),
        first.run.subject,
        first.run.space,
        "BOLD effect",
        {"source": "audited first-level estimate"},
    )
    aligned = align_roi(roi, target, chain)
    labels = aligned.volume.array()
    mapping = {int(k): v for k, v in roi.provenance["label_mapping"].items()}
    if not set(np.unique(labels)).issubset({0, *mapping}):
        raise ValueError("Unknown atlas labels")
    common = first.run.mask.array().astype(bool) & second.run.mask.array().astype(bool)
    rows = []
    for label, name in mapping.items():
        region = labels == label
        covered = region & common
        means = [
            float(e.maps["effect_size"].get_fdata()[covered].mean()) if np.any(covered) else None
            for e in [first, second]
        ]
        difference = means[1] - means[0] if means[0] is not None and means[1] is not None else None
        rows.append(
            {
                "label": label,
                "name": name,
                "ROI_voxels": int(region.sum()),
                "common_mask_voxels": int(covered.sum()),
                "coverage_fraction": float(covered.sum() / region.sum())
                if np.any(region)
                else None,
                "session_mean_effects": means,
                "signed_difference": difference,
                "absolute_difference": abs(difference) if difference is not None else None,
                "ROI_standard_error": "unavailable without spatial covariance",
                "partial_volume_warning": True,
            }
        )
    return {
        "atlas": roi.provenance,
        "regions": rows,
        "unit": "paired ROI mean effects within one participant",
        "population_ICC": "requires independent subjects; not estimated here",
    }
