"""Bounded synthetic matrix laboratory; never a replacement human voxel GLM."""

from pathlib import Path
from typing import Any

import numpy as np
from nilearn.glm.contrasts import compute_contrast
from nilearn.glm.first_level import run_glm
from nilearn.glm.regression import ARModel
from scipy.ndimage import gaussian_filter, label
from scipy.signal import lfilter
from scipy.stats import kstest, norm, t

from soma.anatomy.reporting import AnatomyReport
from soma.core.provenance import write_json
from soma.experiments.fmri_simulation import simulate
from soma.fmri.calibration import gls_oracle, stationary_covariance
from soma.fmri.design import Contrast, ModelConfig, build_design
from soma.fmri.inference import adjust_probabilities
from soma.reliability.registration import wilson


def fixed_design(n: int) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    run, _ = simulate(1401000, n_scans=n, noise=0, beta=0)
    x, _ = build_design(run, ModelConfig(drift_model=None, confound_columns=("motion", "trend")))
    return x.to_numpy(), Contrast("task", {"task": 1.0}).vector(x)


def matrix_fit(
    y: np.ndarray[Any, Any], x: np.ndarray[Any, Any], c: np.ndarray[Any, Any], model: str
) -> dict[str, Any]:
    if not 8 <= len(x) <= 200 or y.ndim != 2 or y.shape[0] != len(x) or not 1 <= y.shape[1] <= 1000:
        raise ValueError("Synthetic matrix laboratory supports n<=200, voxels<=1000 only")
    if np.linalg.matrix_rank(x) != x.shape[1] or not np.isfinite(y).all() or len(x) <= x.shape[1]:
        raise ValueError("Full-rank finite aligned data and positive DOF required")
    if model not in {"ols", "ar1", "ar2"}:
        raise ValueError("Unsupported diagnostic estimator")
    labels, results = run_glm(y, x, noise_model=model, bins=100, n_jobs=1, random_state=13042)
    estimate = compute_contrast(labels, results, c, stat_type="t")
    stat = np.asarray(estimate.stat()).ravel()
    p = 2 * t.sf(abs(stat), estimate.dof)
    z_p = 2 * norm.sf(abs(estimate.z_score()))
    order = 0 if model == "ols" else int(model[-1])
    rho = np.zeros((y.shape[1], order))
    native_lag = np.zeros(y.shape[1])
    white_lag = np.zeros(y.shape[1])
    for key, result in results.items():
        selected = labels == key
        if order:
            rho[selected] = np.asarray(result.model.rho)
        for residual, target in [
            (result.Y - x @ result.theta, native_lag),
            (result.whitened_residuals, white_lag),
        ]:
            target[selected] = np.sum(residual[:-1] * residual[1:], axis=0) / np.maximum(
                np.sum(residual[:-1] ** 2, axis=0), 1e-30
            )
    return {
        "effect": np.asarray(estimate.effect).ravel(),
        "SE": np.sqrt(np.asarray(estimate.variance).ravel()),
        "t": stat,
        "p": p,
        "dof": float(estimate.dof),
        "rho": rho,
        "native_lag": native_lag,
        "white_lag": white_lag,
        "max_z_to_t_p_error": float(np.max(abs(p - z_p))),
    }


def reference_fit(
    y: np.ndarray[Any, Any],
    x: np.ndarray[Any, Any],
    c: np.ndarray[Any, Any],
    covariance: np.ndarray[Any, Any],
) -> dict[str, Any]:
    if y.shape[1] > 1000 or len(x) > 200:
        raise ValueError("Reference restricted to synthetic study bounds")
    effects = []
    ses = []
    for start in range(0, y.shape[1], max(1, 10000 // len(x))):
        result = gls_oracle(x, y[:, start : start + max(1, 10000 // len(x))], covariance, c)
        effects.extend(result["effect"].tolist())
        ses.extend(np.sqrt(result["variance"]).tolist())
    effect = np.array(effects)
    se = np.array(ses)
    dof = len(x) - x.shape[1]
    stat = effect / se
    return {"effect": effect, "SE": se, "t": stat, "p": 2 * t.sf(abs(stat), dof), "dof": float(dof)}


def generator(
    seed: int,
    stage: int,
    case: int,
    replicate: int,
    covariance: str,
    n: int,
    side: int,
    spatial: str = "independent",
) -> dict[str, Any]:
    if (
        covariance not in {"iid", "ar1", "ar2"}
        or n not in {40, 100, 200}
        or side not in {1, 3, 7, 10}
    ):
        raise ValueError("Unprespecified diagnostic geometry/noise")
    if spatial not in {"independent", "correlated", "smoothed", "mixture"}:
        raise ValueError("Unsupported spatial condition")
    x, c = fixed_design(n)
    m = side**3
    coefficients = () if covariance == "iid" else (0.6,) if covariance == "ar1" else (0.5, 0.2)
    rng = np.random.default_rng(np.random.SeedSequence([seed, stage, case, replicate]))
    innovations = rng.normal(0, 0.5, (m, n + 500))
    errors = lfilter([1.0], np.r_[1.0, -np.array(coefficients)], innovations, axis=-1)[:, 500:].T
    g = np.eye(m)
    if spatial in {"correlated", "smoothed"}:
        sigma = 0.75 if spatial == "correlated" else 6 / (3 * np.sqrt(8 * np.log(2)))
        g = gaussian_filter(
            np.eye(m).reshape(side, side, side, m), (sigma, sigma, sigma, 0)
        ).reshape(m, m)
        errors = errors @ g.T
    beta = np.zeros(m)
    if spatial == "mixture":
        beta[: max(1, m // 10)] = 1.0
        beta[-max(1, m // 10) :] = -1.0
    mean = (100 + 0.3 * x[:, 1] + 2 * x[:, 2])[:, None] + x[:, 0, None] * beta
    y = mean + errors
    return {
        "Y": y,
        "X": x,
        "c": c,
        "beta": beta,
        "coefficients": coefficients,
        "C": stationary_covariance(n, coefficients),
        "G": g,
        "spatial_C": g @ g.T if spatial in {"correlated", "smoothed"} else g,
        "mean": mean,
        "shape": (side, side, side),
        "stream_key": [seed, stage, case, replicate],
    }


def probability_summary(values: np.ndarray[Any, Any]) -> dict[str, Any]:
    values = np.asarray(values, float)
    count = int(np.sum(values < 0.05))
    ks = kstest(values, "uniform")
    return {
        "n": len(values),
        "p05": count / len(values),
        "p05_Wilson95": wilson(count, len(values)),
        "KS_D": float(ks.statistic),
        "KS_p_diagnostic_only": float(ks.pvalue),
        "DKW95_halfwidth": float(np.sqrt(np.log(40) / (2 * len(values)))),
        "quantiles": np.quantile(values, [0.001, 0.01, 0.025, 0.05, 0.5, 0.95]).tolist(),
    }


def audit_null(config: dict[str, Any], output: Path) -> dict[str, Any]:
    from soma.pipeline.derivatives import private_output

    private_output(output)
    if min(config["single_replications"], config["spatial_replications"]) < 2:
        raise ValueError("At least two diagnostic realizations required")
    report = AnatomyReport(output, config, seed=config["seed"])
    rows = []
    summaries = []
    p_arrays: dict[str, Any] = {}
    design_arrays: dict[str, Any] = {}
    max_p_error = 0.0
    with report.stage("single_voxel"):
        for index, (noise, n) in enumerate(config["single_conditions"]):
            case = f"single-{noise}-n{n}"
            grouped: dict[str, list[dict[str, Any]]] = {
                model: []
                for model in [
                    *config["models"],
                    "known-GLS",
                    "estimated-stationary-AR1",
                    "known-conditional-AR",
                ]
            }
            for rep in range(config["single_replications"]):
                data = generator(config["seed"], 1, index, rep, noise, n, 1)
                x, c, y = data["X"], data["c"], data["Y"]
                fits = {m: matrix_fit(y, x, c, m) for m in config["models"]}
                fits["known-GLS"] = reference_fit(y, x, c, data["C"])
                residual = y - x @ np.linalg.lstsq(x, y, rcond=None)[0]
                rho = float(
                    n / (n - 1) * np.sum(residual[:-1] * residual[1:]) / np.sum(residual**2)
                )
                if abs(rho) < 1:
                    fits["estimated-stationary-AR1"] = reference_fit(
                        y, x, c, stationary_covariance(n, (rho,))
                    )
                if data["coefficients"]:
                    conditional = ARModel(x, np.asarray(data["coefficients"])).fit(y)
                    w = np.eye(n)
                    for lag, coef in enumerate(data["coefficients"], 1):
                        w[lag:] -= coef * np.eye(n)[:-lag]
                    inverse = np.linalg.solve(w, np.eye(n))
                    fits["known-conditional-AR"] = reference_fit(y, x, c, inverse @ inverse.T)
                    error = float(
                        np.max(
                            abs(conditional.theta - np.linalg.lstsq(w @ x, w @ y, rcond=None)[0])
                        )
                    )
                    if error > 1e-8:
                        raise ValueError("Known conditional whitening coefficient mismatch")
                for model, f in fits.items():
                    half = float(t.ppf(0.975, f["dof"]) * f["SE"][0])
                    max_p_error = max(max_p_error, f.get("max_z_to_t_p_error", 0.0))
                    row = {
                        "case": case,
                        "replicate": rep,
                        "model": model,
                        "p": float(f["p"][0]),
                        "effect": float(f["effect"][0]),
                        "SE": float(f["SE"][0]),
                        "coverage": bool(abs(f["effect"][0]) <= half),
                        "dof": f["dof"],
                        "OLS_residual_rho": rho,
                        "estimated_rho": f["rho"][0].tolist() if "rho" in f else [],
                        "native_lag": float(f["native_lag"][0]) if "native_lag" in f else None,
                        "white_lag": float(f["white_lag"][0]) if "white_lag" in f else None,
                    }
                    rows.append(row)
                    grouped[model].append(row)
            for model, group in grouped.items():
                if not group:
                    continue
                p = np.array([r["p"] for r in group])
                p_arrays[case + "-" + model] = p
                covered = sum(r["coverage"] for r in group)
                effects = np.array([r["effect"] for r in group])
                se = np.array([r["SE"] for r in group])
                summaries.append(
                    {
                        "case": case,
                        "model": model,
                        "marginal": probability_summary(p),
                        "coverage": covered / len(group),
                        "coverage_Wilson95": wilson(covered, len(group)),
                        "bias": float(effects.mean()),
                        "empirical_SD": float(effects.std(ddof=1)),
                        "mean_SE": float(se.mean()),
                        "mean_OLS_residual_rho": float(
                            np.mean([r["OLS_residual_rho"] for r in group])
                        ),
                        "mean_estimated_rho": np.mean(
                            [r["estimated_rho"] for r in group], axis=0
                        ).tolist()
                        if group[0]["estimated_rho"]
                        else [],
                        "mean_white_lag": float(np.mean([r["white_lag"] for r in group]))
                        if group[0]["white_lag"] is not None
                        else None,
                    }
                )
            design_arrays[case + "-X"] = x
            design_arrays[case + "-C"] = data["C"]
            design_arrays[case + "-c"] = c
    with report.stage("spatial_families"):
        for index, (noise, spatial, side) in enumerate(config["spatial_conditions"]):
            case = f"spatial-{noise}-{spatial}-m{side**3}"
            grouped = {m: [] for m in [*config["models"], "known-GLS"]}
            case_p: dict[str, list[Any]] = {m: [] for m in grouped}
            for rep in range(config["spatial_replications"]):
                d = generator(config["seed"], 2, index, rep, noise, 100, side, spatial)
                x, c, y = d["X"], d["c"], d["Y"]
                active = d["beta"] != 0
                fits = {m: matrix_fit(y, x, c, m) for m in config["models"]}
                fits["known-GLS"] = reference_fit(y, x, c, d["C"])
                for model, f in fits.items():
                    case_p[model].append(f["p"])
                    max_p_error = max(max_p_error, f.get("max_z_to_t_p_error", 0.0))
                    record = {
                        "case": case,
                        "model": model,
                        "replicate": rep,
                        "n_voxels": len(active),
                        "global_null": not np.any(active),
                        "marginal_first_p": float(f["p"][0]),
                        "mean_null_p05": float(np.mean(f["p"][~active] < 0.05)),
                        "dof": f["dof"],
                        "max_z_to_t_p_error": f.get("max_z_to_t_p_error", 0.0),
                    }
                    if "rho" in f and f["rho"].shape[1]:
                        tail = f["p"] < config["q"] / len(active)
                        record["mean_rho"] = f["rho"].mean(axis=0).tolist()
                        record["extreme_tail_rho"] = (
                            f["rho"][tail].mean(axis=0).tolist() if np.any(tail) else None
                        )
                    for method in ["bh", "by", "bonferroni"]:
                        rejected = adjust_probabilities(f["p"], method) <= config["q"]
                        false = rejected & ~active
                        components, nclusters = label(false.reshape(d["shape"]))
                        sizes = np.bincount(components.ravel())[1:]
                        record[method] = {
                            "any_rejection": bool(np.any(rejected)),
                            "FDP": float(false.sum() / max(1, rejected.sum())),
                            "true_positive_fraction": float(rejected[active].mean())
                            if np.any(active)
                            else None,
                            "false_clusters": int(nclusters),
                            "max_false_cluster": int(np.max(sizes)) if len(sizes) else 0,
                        }
                    rows.append(record)
                    grouped[model].append(record)
            for model, group in grouped.items():
                p_arrays[case + "-" + model] = np.array(case_p[model])
                summary = {
                    "case": case,
                    "model": model,
                    "n_realizations": len(group),
                    "marginal": probability_summary(
                        np.array([r["marginal_first_p"] for r in group])
                    ),
                    "mean_null_p05": float(np.mean([r["mean_null_p05"] for r in group])),
                    "global_null": group[0]["global_null"],
                }
                for method in ["bh", "by", "bonferroni"]:
                    count = sum(r[method]["any_rejection"] for r in group)
                    summary[method] = {
                        "any_rejection": count / len(group),
                        "Wilson95": wilson(count, len(group)),
                        "empirical_FDR": float(np.mean([r[method]["FDP"] for r in group])),
                        "mean_max_false_cluster": float(
                            np.mean([r[method]["max_false_cluster"] for r in group])
                        ),
                    }
                summaries.append(summary)
            design_arrays[case + "-G"] = d["G"]
            design_arrays[case + "-spatial-C"] = 0.25 * d["spatial_C"]
            design_arrays[case + "-X"] = x
            design_arrays[case + "-temporal-C"] = d["C"]
            design_arrays[case + "-beta"] = d["beta"]
            iid_var = float(c @ np.linalg.solve(x.T @ x, c))
            ar_var = float(c @ np.linalg.solve(x.T @ np.linalg.solve(d["C"], x), c))
            design_arrays[case + "-variance-equivalent-N"] = np.array([len(x) * iid_var / ar_var])
    write_json(output / "diagnostic-rows.json", rows)
    np.savez_compressed(output / "p-values.npz", **p_arrays)
    np.savez_compressed(output / "design-covariance.npz", **design_arrays)
    from soma.fmri.null_plots import null_figures

    null_figures(output, summaries, p_arrays)
    return report.finish(
        {
            "status": "complete",
            "summaries": summaries,
            "rows": len(rows),
            "max_SciPy_t_vs_Nilearn_z_p_error": max_p_error,
            "scope": "synthetic matrix diagnostics; no human calibration certification",
            "nominal_DOF": "n-rank(X), not corrected for estimated covariance uncertainty",
            "effective_N_definition": "contrast variance equivalent only, not Student-t DOF",
        }
    )
