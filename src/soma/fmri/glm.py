"""Production fits delegate to Nilearn; OLS oracle is restricted to small tests."""

from dataclasses import dataclass
from typing import Any

import nibabel as nib
import numpy as np
import pandas as pd
from nilearn.glm.contrasts import compute_fixed_effects
from nilearn.glm.first_level import FirstLevelModel
from scipy.stats import false_discovery_control, norm

from soma.fmri.design import Contrast, ModelConfig, build_design
from soma.fmri.records import FunctionalRun
from soma.imaging.volumes import Volume


def image_for(volume: Volume) -> Any:
    affine = volume.affine_m.copy()
    affine[:3] *= 1000
    image = nib.Nifti1Image(volume.array().astype(np.float32), affine)
    image.header.set_xyzt_units("mm")
    return image


@dataclass
class Fit:
    run: FunctionalRun
    config: ModelConfig
    design: pd.DataFrame
    diagnostics: dict[str, Any]
    model: Any


@dataclass
class Estimate:
    run: FunctionalRun
    contrast: Contrast
    maps: dict[str, Any]
    metadata: dict[str, Any]


def fit(run: FunctionalRun, config: ModelConfig, *, allow_unvalidated_demo: bool = False) -> Fit:
    if run.preprocessing == "unvalidated-educational" and not allow_unvalidated_demo:
        raise ValueError(
            "Raw BOLD is not validated preprocessed data; explicit educational mode required"
        )
    design, report = build_design(run, config)
    model = FirstLevelModel(
        mask_img=image_for(run.mask),
        smoothing_fwhm=config.smoothing_fwhm or None,
        noise_model=config.noise_model,
        standardize=False,
        signal_scaling=False,
        minimize_memory=False,
        n_jobs=1,
        random_state=13042,
        reports=False,
    ).fit(run.image, design_matrices=design)
    # Nilearn RegressionResults.predicted uses whitened_design for AR models.
    # Native residuals must instead use the original modeled Y and unwhitened X.
    native_lags = []
    native_variances = []
    whitened_lags = []
    actual_dof = set()
    for result in model.results_[0].values():
        residual = np.asarray(result.Y) - design.to_numpy() @ result.theta
        denom = np.sum(residual[:-1] ** 2, axis=0)
        native_lags.extend(
            np.divide(
                np.sum(residual[:-1] * residual[1:], axis=0),
                denom,
                out=np.zeros_like(denom),
                where=denom > 0,
            ).tolist()
        )
        native_variances.extend(np.mean(residual**2, axis=0).tolist())
        whitened = np.asarray(result.whitened_residuals)
        scale = np.sum(whitened[:-1] ** 2, axis=0)
        whitened_lags.extend(
            np.divide(
                np.sum(whitened[:-1] * whitened[1:], axis=0),
                scale,
                out=np.zeros_like(scale),
                where=scale > 0,
            ).tolist()
        )
        actual_dof.add(float(result.df_residuals))
    if len(actual_dof) != 1 or next(iter(actual_dof)) != report["residual_dof"]:
        raise ValueError("Unexpected GLM residual degrees of freedom")
    report["mean_whitened_residual_lag1"] = float(np.mean(whitened_lags))
    report["nilearn_residual_dof"] = next(iter(actual_dof))
    report.update(
        {
            "noise_model": config.noise_model,
            "estimator": "OLS"
            if config.noise_model == "ols"
            else f"feasible {config.noise_model.upper()}, voxel AR bins/clusters=100",
            "native_residual_definition": "original modeled Y - unwhitened X @ beta",
            "mean_native_residual_lag1": float(np.mean(native_lags)),
            "residual_variance_mean": float(np.mean(native_variances)),
            "signal_scaling": False,
            "standardize": False,
            "smoothing_fwhm_mm": config.smoothing_fwhm,
            "preprocessing": run.preprocessing,
            "validated_preprocessing_claimed": run.preprocessing == "validated",
        }
    )
    return Fit(run, config, design, report, model)


def contrast(fitted: Fit, definition: Contrast) -> Estimate:
    vector = definition.vector(fitted.design)
    maps = dict(fitted.model.compute_contrast(vector, stat_type="t", output_type="all"))
    # Nilearn also returns an upper-tail p_value; this API exports only the
    # explicitly defined two-sided p map used by the prespecified inference.
    maps.pop("p_value", None)
    mask = fitted.run.mask.array().astype(bool)
    z = np.asarray(maps["z_score"].dataobj)[mask]
    if not np.isfinite(z).all():
        raise ValueError("Nonfinite statistical map")
    p = 2 * norm.sf(np.abs(z))
    adjusted = false_discovery_control(p, method="bh")
    rejected = adjusted <= fitted.config.q
    for name, values in [("p_two_sided", p), ("q_bh", adjusted), ("fdr_reject", rejected)]:
        array = np.zeros(mask.shape, np.float32)
        array[mask] = values
        maps[name] = nib.Nifti1Image(array, fitted.run.image.affine)
        maps[name].header.set_xyzt_units("mm")
    return Estimate(
        fitted.run,
        definition,
        maps,
        {
            "name": definition.name,
            "vector": vector.tolist(),
            "design_names": list(fitted.design),
            "tail": definition.tail,
            "effect_units": "input BOLD units per modeled regressor unit",
            "variance_units": "squared effect units",
            "statistics": "signed t; signed Gaussian-equivalent z",
            "residual_dof": fitted.diagnostics["residual_dof"],
            "noise_model": fitted.config.noise_model,
            "hrf_model": fitted.config.hrf_model,
            "smoothing_fwhm_mm": fitted.config.smoothing_fwhm,
            "correction": "Benjamini-Hochberg FDR",
            "q": fitted.config.q,
            "family_voxels": int(mask.sum()),
            "rejected_voxels": int(rejected.sum()),
            "positive_rejected_voxels": int(np.sum(rejected & (z > 0))),
            "negative_rejected_voxels": int(np.sum(rejected & (z < 0))),
            "preprocessing": fitted.run.preprocessing,
            "exploratory": fitted.run.preprocessing == "unvalidated-educational",
            "population_inference": False,
        },
    )


def fixed_effects(estimates: list[Estimate]) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(estimates) < 2:
        raise ValueError("At least two appropriate runs required")
    first = estimates[0]
    scale = first.run.provenance.get("effect_scale_identity")
    if not scale or any(e.run.provenance.get("effect_scale_identity") != scale for e in estimates):
        raise ValueError("Fixed effects require explicit comparable effect-scale provenance")
    for e in estimates:
        if any(e.metadata[k] != first.metadata[k] for k in ("hrf_model", "smoothing_fwhm_mm")):
            raise ValueError("Fixed-effects HRF basis or smoothing differs")
    identities = [e.run.identity[:1] + e.run.identity[2:3] + e.run.identity[4:] for e in estimates]
    if len(set(identities)) != 1 or len({e.run.identity for e in estimates}) != len(estimates):
        raise ValueError("Fixed effects require distinct runs of same subject/task/space")
    for e in estimates:
        if e.contrast != first.contrast or not e.run.mask.same_grid(first.run.mask):
            raise ValueError("Fixed-effects estimands/grids differ")
        if not np.array_equal(e.run.mask.array(), first.run.mask.array()):
            raise ValueError("Fixed effects require identical masks")
    maps = compute_fixed_effects(
        [e.maps["effect_size"] for e in estimates],
        [e.maps["effect_variance"] for e in estimates],
        mask=image_for(first.run.mask),
        precision_weighted=True,
        dofs=[e.metadata["residual_dof"] for e in estimates],
    )
    return dict(zip(["effect_size", "effect_variance", "stat", "z_score"], maps, strict=True)), {
        "combination": "precision-weighted within-subject fixed effects",
        "runs": [e.run.identity for e in estimates],
        "population_random_effects": False,
    }


def analytical_ols(
    x: np.ndarray[Any, Any], y: np.ndarray[Any, Any], c: np.ndarray[Any, Any]
) -> dict[str, Any]:
    """Independent QR reference for small analytical cases, not a voxel engine."""
    if x.shape[0] > 1000 or y.size > 10000 or np.linalg.matrix_rank(x) != x.shape[1]:
        raise ValueError("Analytical OLS oracle limited to small full-rank examples")
    q, r = np.linalg.qr(x)
    beta = np.linalg.solve(r, q.T @ y)
    residual = y - x @ beta
    dof = x.shape[0] - x.shape[1]
    if dof <= 0:
        raise ValueError("Positive residual degrees of freedom required")
    variance = np.sum(residual**2, axis=0) / dof * np.sum(np.linalg.solve(r.T, c) ** 2)
    return {"beta": beta, "effect": c @ beta, "variance": variance, "dof": dof}
