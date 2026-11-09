"""Known-covariance small GLS oracle and reproducible voxel/family calibration."""

from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from scipy.linalg import cholesky, solve_triangular, toeplitz
from scipy.ndimage import gaussian_filter
from scipy.signal import lfilter
from scipy.stats import t

from soma.anatomy.reporting import AnatomyReport
from soma.core.provenance import write_json
from soma.experiments.fmri_simulation import simulate
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import contrast, fit
from soma.reliability.registration import wilson


def gls_oracle(
    x: np.ndarray[Any, Any],
    y: np.ndarray[Any, Any],
    covariance: np.ndarray[Any, Any],
    c: np.ndarray[Any, Any],
) -> dict[str, Any]:
    if x.ndim != 2 or y.ndim != 2 or len(x) > 1000 or y.size > 10000 or len(x) != len(y):
        raise ValueError("GLS reference is restricted to small aligned matrices")
    if (
        covariance.shape != (len(x), len(x))
        or not np.isfinite(covariance).all()
        or not np.allclose(covariance, covariance.T)
    ):
        raise ValueError("Finite symmetric temporal covariance required")
    if (
        not np.isfinite(x).all()
        or not np.isfinite(y).all()
        or c.shape != (x.shape[1],)
        or not np.isfinite(c).all()
    ):
        raise ValueError("Invalid GLS design/data/contrast")
    lower = cholesky(covariance, lower=True)
    wx = solve_triangular(lower, x, lower=True)
    wy = solve_triangular(lower, y, lower=True)
    if np.linalg.matrix_rank(wx) != x.shape[1] or len(x) <= x.shape[1]:
        raise ValueError("Full rank and positive GLS DOF required")
    q, r = np.linalg.qr(wx)
    beta = np.linalg.solve(r, q.T @ wy)
    residual = wy - wx @ beta
    dof = len(x) - x.shape[1]
    scale = np.sum(residual**2, axis=0) / dof
    variance = scale * np.sum(np.linalg.solve(r.T, c) ** 2)
    return {
        "beta": beta,
        "effect": c @ beta,
        "variance": variance,
        "residual_scale": scale,
        "dof": dof,
        "whitened_residual": residual,
        "whitened_design": wx,
    }


def stationary_covariance(n: int, coefficients: tuple[float, ...]) -> np.ndarray[Any, Any]:
    if n < 2 or len(coefficients) > 2 or any(not np.isfinite(v) for v in coefficients):
        raise ValueError("Supported finite AR coefficients required")
    if not coefficients:
        return np.eye(n)
    from scipy.linalg import solve_discrete_lyapunov

    order = len(coefficients)
    transition = np.zeros((order, order))
    transition[0] = coefficients
    if order > 1:
        transition[1, 0] = 1
    if np.max(np.abs(np.linalg.eigvals(transition))) >= 1:
        raise ValueError("Stationary AR process required")
    innovations = np.zeros((order, order))
    innovations[0, 0] = 1
    stationary = solve_discrete_lyapunov(transition, innovations)
    vector = stationary[:, 0]
    lags = []
    for _ in range(n):
        lags.append(vector[0])
        vector = transition @ vector
    return np.asarray(toeplitz(lags))


def calibration_run(seed: int, scenario: str) -> tuple[Any, dict[str, Any], tuple[float, ...]]:
    allowed = {
        "gaussian-null",
        "ar1-null",
        "ar1-effect",
        "ar2-null",
        "hrf-delay",
        "omitted-nuisance",
        "smoothing",
    }
    if scenario not in allowed:
        raise ValueError("Unknown prespecified calibration scenario")
    null = scenario.endswith("null")
    coefficients = (
        () if scenario == "gaussian-null" else (0.5, 0.2) if scenario == "ar2-null" else (0.6,)
    )
    run, truth = simulate(
        seed, beta=0 if null else 3, noise=0, hrf_delay=2 if scenario == "hrf-delay" else 0
    )
    rng = np.random.default_rng(np.random.SeedSequence([seed, 14]))
    errors = rng.normal(0, 0.5, (*run.mask.shape, run.n_scans + 500))
    errors = lfilter([1.0], np.r_[1.0, -np.asarray(coefficients)], errors, axis=-1)[..., 500:]
    image = nib.Nifti1Image(
        (run.image.get_fdata() + errors).astype(np.float32), run.image.affine, run.image.header
    )
    return replace(run, image=image), truth, coefficients


def calibration_experiment(config: dict[str, Any], output: Path) -> dict[str, Any]:
    if not isinstance(config.get("replicates"), int) or config["replicates"] < 2:
        raise ValueError("At least two prespecified Monte Carlo realizations required")
    if not config.get("models") or not set(config["models"]).issubset({"ols", "ar1", "ar2"}):
        raise ValueError("Unsupported calibration models")
    from soma.pipeline.derivatives import private_output

    private_output(output)
    report = AnatomyReport(output, config, seed=config["seed"])
    rows = []
    failures = []
    definition = Contrast("task", {"task": 1.0})
    base = ModelConfig(
        noise_model="ols", drift_model=None, confound_columns=("motion", "trend"), q=config["q"]
    )
    with report.stage("Monte_Carlo"):
        for scenario in config["scenarios"]:
            for replicate in range(config["replicates"]):
                seed = int(config["seed"]) + replicate
                run, truth, coefficients = calibration_run(seed, scenario)
                for model in config["models"]:
                    try:
                        cfg = replace(
                            base,
                            noise_model=model,
                            confound_columns=()
                            if scenario == "omitted-nuisance"
                            else base.confound_columns,
                            smoothing_fwhm=3 if scenario == "smoothing" else 0,
                        )
                        fitted = fit(run, cfg)
                        estimate = contrast(fitted, definition)
                        voxel = (1, 3, 3)
                        beta = float(estimate.maps["effect_size"].get_fdata()[voxel])
                        se = float(np.sqrt(estimate.maps["effect_variance"].get_fdata()[voxel]))
                        target_beta = (
                            gaussian_filter(truth["beta"].astype(float), 1 / np.sqrt(8 * np.log(2)))
                            if scenario == "smoothing"
                            else truth["beta"]
                        )
                        true_beta = float(target_beta[voxel])
                        dof = estimate.metadata["residual_dof"]
                        half = float(t.ppf(0.975, dof) * se)
                        p = estimate.maps["p_two_sided"].get_fdata()
                        rejected = estimate.maps["fdr_reject"].get_fdata().astype(bool)
                        active = np.abs(target_beta) > 1e-10
                        rows.append(
                            {
                                "scenario": scenario,
                                "seed": seed,
                                "model": model,
                                "beta": beta,
                                "SE": se,
                                "true_beta": true_beta,
                                "CI95_covers": bool(abs(beta - true_beta) <= half),
                                "voxel_p05": bool(p[voxel] < 0.05),
                                "null_voxel_fraction_p05": float(np.mean(p[~active] < 0.05)),
                                "BH_any_rejection": bool(np.any(rejected)),
                                "BH_false_discovery_fraction": float(
                                    np.sum(rejected & ~active) / max(1, rejected.sum())
                                ),
                                "BH_true_positive_fraction": float(np.mean(rejected[active]))
                                if np.any(active)
                                else None,
                                "native_lag1": fitted.diagnostics["mean_native_residual_lag1"],
                                "whitened_lag1": fitted.diagnostics["mean_whitened_residual_lag1"],
                                "condition_number": fitted.diagnostics["condition_number"],
                                "dof": dof,
                            }
                        )
                        if model == "ols" and scenario in {
                            "gaussian-null",
                            "ar1-null",
                            "ar1-effect",
                            "ar2-null",
                        }:
                            x = fitted.design.to_numpy()
                            y = run.image.get_fdata()[voxel][:, None]
                            oracle = gls_oracle(
                                x,
                                y,
                                stationary_covariance(run.n_scans, coefficients),
                                definition.vector(fitted.design),
                            )
                            effect = float(oracle["effect"][0])
                            stderr = float(np.sqrt(oracle["variance"][0]))
                            rows.append(
                                {
                                    "scenario": scenario,
                                    "seed": seed,
                                    "model": "known-covariance-GLS-reference",
                                    "beta": effect,
                                    "SE": stderr,
                                    "true_beta": true_beta,
                                    "CI95_covers": bool(
                                        abs(effect - true_beta)
                                        <= t.ppf(0.975, oracle["dof"]) * stderr
                                    ),
                                    "voxel_p05": bool(
                                        2 * t.sf(abs(effect / stderr), oracle["dof"]) < 0.05
                                    ),
                                    "scope": "one voxel, known covariance reference",
                                }
                            )
                    except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
                        failures.append(
                            {
                                "scenario": scenario,
                                "seed": seed,
                                "model": model,
                                "diagnostic": str(exc),
                            }
                        )
    summaries = []
    for scenario in config["scenarios"]:
        for model in [*config["models"], "known-covariance-GLS-reference"]:
            group = [r for r in rows if r["scenario"] == scenario and r["model"] == model]
            if not group:
                continue
            n = len(group)
            beta_samples = np.array([r["beta"] for r in group])
            ses = np.array([r["SE"] for r in group])
            summary = {
                "scenario": scenario,
                "model": model,
                "n_realizations": n,
                "beta_bias": float(np.mean([r["beta"] - r["true_beta"] for r in group])),
                "empirical_beta_SD": float(np.std(beta_samples, ddof=1)) if n > 1 else None,
                "mean_estimated_SE": float(ses.mean()),
                "SE_to_empirical_SD": float(ses.mean() / np.std(beta_samples, ddof=1))
                if n > 1 and np.std(beta_samples) > 0
                else None,
                "statistical_unit": "independent seeded realization, not voxel",
            }
            for name in ["CI95_covers", "voxel_p05", "BH_any_rejection"]:
                if name in group[0]:
                    count = sum(r[name] for r in group)
                    summary[name] = {
                        "estimate": count / n,
                        "Wilson95": wilson(count, n),
                        "successes": count,
                        "n": n,
                    }
            for name in [
                "null_voxel_fraction_p05",
                "BH_false_discovery_fraction",
                "BH_true_positive_fraction",
                "whitened_lag1",
                "native_lag1",
                "condition_number",
            ]:
                if name in group[0] and group[0][name] is not None:
                    summary[name] = float(np.mean([r[name] for r in group]))
            summaries.append(summary)
    from soma.fmri.audit_plots import calibration_figures

    calibration_figures(output, summaries)
    write_json(output / "replicates.json", rows)
    return report.finish(
        {
            "status": "complete" if not failures else "incomplete",
            "summary": summaries,
            "failures": failures,
            "scope": "synthetic calibration, finite Monte Carlo; not human inference certification",
            "libraries": {name: version(name) for name in ("nilearn", "numpy", "scipy")},
        }
    )
