"""Matched continuous-source prior/grid sweeps with explicit physical assumptions."""

import time
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from soma.anatomy.reporting import AnatomyReport
from soma.benchmarks.offgrid import (
    ContinuousDipole,
    direction,
    evaluate_forward,
    offgrid,
    reconstruction_metrics,
    source_grid,
)
from soma.core.provenance import write_json
from soma.geometry import Frame, Points
from soma.reliability.inverse import array_hash
from soma.reliability.workflows import paired_interval
from soma.source.noise import NoiseModel, average_projector
from soma.source.priors import fit_prior, make_prior, normalize_prior
from soma.validation.config import configuration


def source_prior_study(config: Path, output: Path) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    p = average_projector(24)
    truth_positions = np.array(cfg["positions_MRI_m"])
    arrays: dict[str, Any] = {}
    receipts = {}
    failures: list[dict[str, Any]] = []
    rows = []
    contrasts = []
    operators = {}
    records = {}
    sample_times = np.arange(cfg["samples"]) / cfg["sample_rate_Hz"]
    signals = np.array(
        [
            np.cos(2 * np.pi * cfg["signal_frequency_Hz"] * sample_times),
            np.cos(2 * np.pi * cfg["signal_frequency_Hz"] * sample_times + np.arccos(0.8)),
        ]
    )
    arrays["waveforms"] = signals
    arrays["time_s"] = sample_times
    arrays["truth_positions_MRI_m"] = truth_positions
    with report.stage("continuous_truth_forward"):
        truth, r = evaluate_forward(Points(truth_positions, Frame.MRI))
        receipts["continuous_truth"] = r
        arrays["continuous_truth_lead_V_per_Am"] = truth
    rng = np.random.default_rng(cfg["seed"])
    standard = p @ rng.standard_normal((24, cfg["repetitions"]))
    arrays["matched_standard_noise"] = standard
    source_cases = []
    for i, angle in product(range(len(truth_positions)), cfg["angles_deg"]):
        position = truth_positions[i]
        dipole = ContinuousDipole(
            Points(position[None], Frame.MRI), direction(position, angle), cfg["truth_moment_Am"]
        )
        y = truth[:, 3 * i : 3 * i + 3] @ dipole.orientation * dipole.moment_Am
        scale = float(np.linalg.norm(y) / np.sqrt(23) / cfg["snr"])
        obs = np.column_stack((y, y[:, None] + scale * standard))
        source_cases.append((i, angle, dipole, obs))
        arrays[f"truth_{i}_{angle}_observations_V"] = obs
    models = ["analytical"] if cfg["grid_mode"] else cfg["reconstruction_models"]
    noises = ["matched"] if cfg["grid_mode"] else cfg["noise_models"]
    baseline_scale = {}
    with report.stage("forward_prior_inverse_sweep"):
        for spacing, representation in product(cfg["spacings_m"], cfg["orientations"]):
            grid = source_grid(spacing)
            normal = grid.xyz / np.linalg.norm(grid.xyz, axis=1)[:, None]
            ids = tuple(array_hash(x) for x in grid.xyz)
            n = len(ids)
            k = 1 if representation == "fixed" else 3
            areas = np.full(n, 4 * np.pi * cfg["fixed_source_surface_radius_m"] ** 2 / n)
            grid_name = f"{spacing}_{representation}"
            arrays[grid_name + "__positions_MRI_m"] = grid.xyz
            arrays[grid_name + "__quadrature_m2"] = areas
            for model, noise_name in product(models, noises):
                if noise_name != "matched" and model != "analytical":
                    continue
                noise_cov = (
                    p if noise_name == "matched" else p @ np.diag(np.linspace(0.25, 4, 24)) @ p
                )
                noise = NoiseModel(noise_cov, tuple(f"EEG{i}" for i in range(24)), p)
                kwargs: dict[str, Any] = {}
                kind = "analytical" if model == "analytical" else "BEM"
                if model == "boundary_1mm":
                    kwargs["radii"] = (0.081, 0.085, 0.09)
                if model == "skull_half":
                    kwargs["sigmas"] = (0.3, 0.003, 0.3)
                cache_key = (spacing, model)
                if cache_key not in operators:
                    cart, r = evaluate_forward(grid, kind=kind, **kwargs)
                    operators[cache_key] = cart
                    receipts[f"{spacing}_{model}"] = r
                cart = operators[cache_key]
                lead = np.einsum("cni,ni->cn", cart.reshape(24, n, 3), normal) if k == 1 else cart
                lw = noise.whitener @ lead
                base_key = (representation, noise_name)
                if base_key not in baseline_scale:
                    if spacing != cfg["spacings_m"][0]:
                        raise ValueError("Baseline source spacing must be evaluated first")
                    baseline_scale[base_key] = float(np.sum(lw * lw) / noise.rank)
                lambdas = (
                    cfg["lambda2"] if model == "analytical" and noise_name == "matched" else [1 / 9]
                )
                for policy in cfg["policies"]:
                    prior_start = time.perf_counter()
                    raw = make_prior(
                        lw,
                        ids,
                        orientation=representation,
                        policy=policy,
                        normals=normal,
                        areas_m2=areas,
                        depth_exponent=cfg["depth_exponent"],
                        depth_cap=cfg["depth_cap"],
                        loose=cfg["loose_tangential_variance"],
                    )
                    prior_wall_s = time.perf_counter() - prior_start
                    arrays[f"{grid_name}_{model}_{noise_name}_{policy}__raw_prior_blocks"] = (
                        raw.blocks
                    )
                    for norm in cfg["normalizations"]:
                        prior = (
                            raw
                            if norm == "none"
                            else normalize_prior(
                                raw, lead, noise, target=cfg["normalization_target_sensor_trace"]
                            )
                        )
                        for lam in lambdas:
                            alpha = lam * baseline_scale[base_key]
                            fit_start = time.perf_counter()
                            inverse = fit_prior(lead, prior, noise, alpha=alpha, source_ids=ids)
                            fit_wall_s = time.perf_counter() - fit_start
                            name = f"{grid_name}_{model}_{noise_name}_{policy}_{norm}_{lam}"
                            gain = (
                                np.array(inverse.diagnostics.pop("resolution_diagonal"))
                                .reshape(n, k)
                                .sum(axis=1)
                            )
                            arrays[name + "__resolution_gain"] = gain
                            inverse_record = {
                                **inverse.diagnostics,
                                "prior_construction_wall_s": prior_wall_s,
                                "inverse_fit_wall_s": fit_wall_s,
                                "lambda2": lam,
                                "source_count": n,
                                "spacing_m": spacing,
                                "representation": representation,
                                "model": model,
                                "fitted_noise": noise_name,
                                "normalization": norm,
                                "policy": policy,
                                "lead_sha256": array_hash(lead),
                                "noise_sha256": array_hash(noise_cov),
                            }
                            records[name] = inverse_record
                            for i, angle, dipole, observations in source_cases:
                                nearest_distance, nearest = offgrid(
                                    dipole, grid, tolerance_m=cfg["offgrid_tolerance_m"]
                                )
                                estimate = inverse.apply(observations)
                                metrics = reconstruction_metrics(
                                    estimate, lead, observations, dipole, grid, nearest
                                )
                                if np.any(
                                    metrics["peak_error_mm"] + 1e-8 < nearest_distance * 1000
                                ):
                                    raise ValueError(
                                        "Localization violates geometric grid lower bound"
                                    )
                                prefix = name + f"__truth_{i}_{angle}"
                                for key, val in metrics.items():
                                    arrays[prefix + "__" + key] = np.asarray(val)
                                psf = inverse.kernel @ lead[:, nearest * k : (nearest + 1) * k]
                                psf_energy = np.sum(psf.reshape(n, k, k) ** 2, axis=(1, 2))
                                psf_total = float(psf_energy.sum())
                                arrays[prefix + "__selected_PSF_energy"] = psf_energy
                                row = {
                                    "selected_PSF_off_nearest_energy": float(
                                        1 - psf_energy[nearest] / psf_total
                                    ),
                                    "selected_PSF_dispersion_mm": float(
                                        np.sqrt(
                                            np.sum(
                                                psf_energy
                                                * np.sum(
                                                    (grid.xyz - grid.xyz[nearest]) ** 2, axis=1
                                                )
                                            )
                                            / psf_total
                                        )
                                        * 1000
                                    ),
                                    "operator": name,
                                    "source": i,
                                    "angle_deg": angle,
                                    "depth_from_80mm_brain_mm": float(
                                        (0.08 - np.linalg.norm(dipole.position.xyz)) * 1000
                                    ),
                                    "nearest_grid_mm": nearest_distance * 1000,
                                    "nearest_resolution_gain": float(gain[nearest]),
                                    "noisefree": {
                                        key: float(np.asarray(val).flat[0])
                                        for key, val in metrics.items()
                                    },
                                    "noise": {
                                        key: paired_interval(np.asarray(val)[1:])
                                        for key, val in metrics.items()
                                        if np.asarray(val).ndim == 1
                                    },
                                    "prior": policy,
                                    "normalization": norm,
                                    "spacing_m": spacing,
                                    "lambda2": lam,
                                    "model": model,
                                    "representation": representation,
                                    "fitted_noise": noise_name,
                                }
                                rows.append(row)
                            if not cfg["grid_mode"] and lam == 1 / 9:
                                # Full time-series pair, corr .8, with deterministic
                                # independent noise.
                                first, second = source_cases[0], source_cases[2]
                                a = truth[:, :3] @ first[2].orientation * cfg["truth_moment_Am"]
                                b = truth[:, 3:6] @ second[2].orientation * cfg["truth_moment_Am"]
                                paired = a[:, None] * signals[0] + b[:, None] * signals[1]
                                pair_noise = p @ np.random.default_rng(
                                    cfg["seed"] + 99
                                ).standard_normal(paired.shape)
                                pair_noise *= (
                                    np.linalg.norm(paired) / np.linalg.norm(pair_noise) / cfg["snr"]
                                )
                                observed_pair = paired + pair_noise
                                fitted = inverse.apply(observed_pair)
                                strength = np.linalg.norm(fitted.reshape(n, k, -1), axis=(1, 2))
                                peak = int(np.argmax(strength))
                                coverage = [
                                    float(np.linalg.norm(grid.xyz[peak] - pos) * 1000)
                                    for pos in truth_positions[:2]
                                ]
                                arrays[name + "__pair_strength_Am_time_norm"] = strength
                                inverse_record["correlated_pair"] = {
                                    "waveform_correlation": float(np.corrcoef(signals)[0, 1]),
                                    "global_peak_distance_to_each_source_mm": coverage,
                                    "sensor_residual_relative": float(
                                        np.linalg.norm(lead @ fitted - observed_pair)
                                        / np.linalg.norm(observed_pair)
                                    ),
                                    "attribution": (
                                        "joint estimate; global peak is "
                                        "not isolated source localization"
                                    ),
                                }
    with report.stage("paired_noise_contrasts"):
        raw_rows = {
            (r["operator"].replace("_none_", "_NORM_"), r["source"], r["angle_deg"]): r
            for r in rows
            if r["normalization"] == "none"
        }
        for r in rows:
            if r["normalization"] != "sensor_trace":
                continue
            contrast_key = (
                r["operator"].replace("_sensor_trace_", "_NORM_"),
                r["source"],
                r["angle_deg"],
            )
            base = raw_rows[contrast_key]
            comparisons = {}
            for metric in ["peak_error_mm", "nearest_vertex_amplitude_ratio", "dispersion_mm"]:
                suffix = f"__truth_{r['source']}_{r['angle_deg']}__{metric}"
                comparisons[metric] = paired_interval(
                    arrays[r["operator"] + suffix][1:] - arrays[base["operator"] + suffix][1:]
                )
            contrasts.append(
                {
                    "operator": r["operator"],
                    "source": r["source"],
                    "angle_deg": r["angle_deg"],
                    "contrast": "sensor_trace minus raw, paired noise",
                    "comparisons": comparisons,
                    "primary": r["prior"] == "uniform",
                }
            )
    arrays["baseline_scale_values"] = np.array(list(baseline_scale.values()))
    np.savez_compressed(output / "prior-arrays.npz", **arrays)
    write_json(output / "operators.json", records)
    write_json(output / "source-results.json", {"rows": rows, "contrasts": contrasts})
    write_json(output / "forward-receipts.json", receipts)
    summary = {
        "status": "complete",
        "source_rows": len(rows),
        "operator_count": len(records),
        "source_evaluations": len(rows) * (cfg["repetitions"] + 1),
        "failures": failures,
        "grid_source_counts": {str(h): len(source_grid(h).xyz) for h in cfg["spacings_m"]},
        "source_covariance_units": "A2 m2; estimated coefficients A m",
        "quadrature_definition": cfg["area_definition"],
        "independent_human_subjects": 0,
        "shared_assumptions": (
            "MNE isotropic concentric spheres; continuous "
            "independent point evaluation; no interpolated columns"
        ),
        "same_grid_control": (
            "analytical unit tests and MNE equivalence "
            "only; no same-grid truth in scored off-grid rows"
        ),
        "normalization_guarantees": (
            "sensor prior trace only, not grid invariance or unbiased amplitude"
        ),
        "primary_contrast": (
            "normalized-minus-raw uniform; all other policy comparisons exploratory"
        ),
        "baseline_scale_by_representation_noise": {str(k): v for k, v in baseline_scale.items()},
        "correlated_pair_cases": sum("correlated_pair" in r for r in records.values()),
        "MNE_equivalence": "see independently tested uniform depth=None trace/rank convention",
    }
    from soma.validation.plots import prior_plots

    prior_plots(output, rows, records, arrays)
    return report.finish(summary)
