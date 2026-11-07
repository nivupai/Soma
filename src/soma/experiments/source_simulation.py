"""Known cortical currents with independent covariance training and fixed inversion."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from neurodsp.sim import sim_oscillation
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

from soma.core.provenance import write_json
from soma.source.inverse import CorticalInverse
from soma.source.resolution import Resolution, spatial_metrics
from soma.source.template import Template
from soma.source.workflow import RunReport, sealed_config, study_forward, synthetic_covariance


def source_waveforms(
    scenario: str, fs: float, duration: float, amplitude: float, phase: float = 0
) -> tuple[np.ndarray[Any, Any], dict[str, Any]]:
    """NeuroDSP oscillation, scaled to peak current amplitude in ampere metres."""
    t = np.arange(round(fs * duration)) / fs
    # NeuroDSP's sine starts at zero with unit variance; quadrature permits an
    # explicitly controlled random phase without any global RNG mutation.
    base = np.asarray(sim_oscillation(duration, fs, 10), dtype=float) / np.sqrt(2)
    quadrature = np.cos(2 * np.pi * 10 * t)
    signal = amplitude * (base * np.cos(phase) + quadrature * np.sin(phase))
    metadata: dict[str, Any] = {
        "frequency_hz": 10,
        "peak_current_Am": amplitude,
        "phase_rad": phase,
        "burst_intervals_s": [],
        "second_source_peak_current_Am": amplitude * (0.8 if scenario == "correlated" else 1),
    }
    if scenario == "amplitude_modulated":
        signal *= 1 + 0.5 * np.sin(2 * np.pi * 0.5 * t)
    if scenario == "bursts":
        intervals = [[0.5, 1.25], [2.5, 3.25]]
        signal *= ((t >= 0.5) & (t < 1.25)) | ((t >= 2.5) & (t < 3.25))
        metadata["burst_intervals_s"] = intervals
    return np.stack(
        [
            signal,
            0.8 * signal
            if scenario == "correlated"
            else amplitude * np.cos(2 * np.pi * 10 * t + phase),
        ]
    ), metadata


def simulate(config_path: Path, output: Path) -> dict[str, Any]:
    config = sealed_config(config_path)
    forward = study_forward()
    report = RunReport(output, config, forward, config["seed"])
    xyz = forward.coordinates.points.xyz
    n = len(xyz)
    # Fixed anatomical-coordinate selection, independent of estimator recovery.
    focal = int(np.argmin(np.linalg.norm(xyz - [-0.04, 0.02, 0.1], axis=1)))
    separated = int(np.argmax(np.linalg.norm(xyz - xyz[focal], axis=1)))
    scalp = Template().scalp_head().xyz
    depth = cKDTree(scalp).query(xyz)[0]
    deep = int(np.argmax(depth))
    shallow = int(np.argmin(depth))
    noise, covariance = synthetic_covariance(
        forward,
        seed=config["seed"] + config["noise_covariance_seed_offset"],
        samples=config["noise_covariance_samples"],
        correlation=config["noise_correlation"],
    )
    kernel = CorticalInverse(
        forward, covariance, lambda2=config["primary_lambda2"], depth=config["primary_depth"]
    ).kernel
    lead = forward.matrix
    rng_mismatch = np.random.default_rng(config["seed"] + 99999)
    perturbation = forward.projector @ rng_mismatch.normal(size=lead.shape)
    perturbation *= (
        config["relative_forward_perturbation"]
        * np.linalg.norm(lead)
        / np.linalg.norm(perturbation)
    )
    # Only simulated truth uses the perturbation; inversion remains fixed.
    mismatch = lead + perturbation
    base_noise = config["noise_correlation"] ** np.abs(
        np.subtract.outer(np.arange(lead.shape[0]), np.arange(lead.shape[0]))
    )
    color = np.linalg.cholesky(base_noise)
    rows = []
    truth_metadata = []
    example: dict[str, Any] = {}
    for scenario_index, scenario in enumerate(config["scenarios"]):
        indices = (
            [focal, separated]
            if scenario in ("separated", "correlated")
            else [deep, shallow]
            if scenario == "depth"
            else [focal]
        )
        true_l = mismatch if scenario == "forward_mismatch" else lead
        for snr in config["snr_db"]:
            for repetition in range(config["repetitions"]):
                seed = config["seed"] + 10000 * scenario_index + repetition
                rng = np.random.default_rng(seed)
                waveforms, wave_meta = source_waveforms(
                    scenario,
                    config["fs_hz"],
                    config["duration_s"],
                    config["current_amplitude_Am"],
                    float(rng.uniform(-np.pi, np.pi)),
                )
                truth = np.zeros((n, waveforms.shape[-1]))
                truth[indices] = waveforms[: len(indices)]
                clean = true_l @ truth
                evaluation_noise = forward.projector @ color @ rng.standard_normal(clean.shape)
                # Oracle SNR control is only a simulation setting, never estimator tuning.
                evaluation_noise *= (
                    np.linalg.norm(clean) / np.linalg.norm(evaluation_noise) / 10 ** (snr / 20)
                )
                y = clean + evaluation_noise
                estimated = kernel @ y
                energy = np.sum(estimated**2, axis=1)
                # Distinct recovery peaks with a predeclared 20-mm exclusion radius.
                ranking = np.argsort(energy)[::-1]
                peaks: list[int] = []
                for index in ranking:
                    if all(np.linalg.norm(xyz[index] - xyz[p]) >= 0.02 for p in peaks):
                        peaks.append(int(index))
                    if len(peaks) == len(indices):
                        break
                distances = np.linalg.norm(
                    xyz[np.array(indices)][:, None] - xyz[np.array(peaks)][None], axis=-1
                )
                a, b = linear_sum_assignment(distances)
                metrics = spatial_metrics(np.sqrt(energy), indices[0], xyz)
                source_error = np.linalg.norm(estimated - truth) / np.linalg.norm(truth)
                amplitude_ratio = np.linalg.norm(estimated[indices]) / np.linalg.norm(
                    truth[indices]
                )
                correlation = float(
                    np.mean([np.corrcoef(estimated[i], truth[i])[0, 1] for i in indices])
                )
                rows.append(
                    {
                        "scenario": scenario,
                        "snr_db": snr,
                        "repetition": repetition,
                        "evaluation_seed": seed,
                        "relative_current_error": float(source_error),
                        "forward_residual_relative": float(
                            np.linalg.norm(lead @ estimated - y) / np.linalg.norm(y)
                        ),
                        "mean_assigned_peak_euclidean_m": float(distances[a, b].mean()),
                        "spatial_dispersion_m": metrics["dispersion_euclidean_m"],
                        "amplitude_bias_ratio_minus_one": float(amplitude_ratio - 1),
                        "timecourse_correlation": correlation,
                    }
                )
                truth_metadata.append(
                    {
                        "scenario": scenario,
                        "snr_db": snr,
                        "repetition": repetition,
                        "indices": indices,
                        "nearest_scalp_vertex_depth_m": depth[indices].tolist(),
                        "source_identifiers": [forward.coordinates.identifiers[i] for i in indices],
                        "waveform": wave_meta,
                        "orientation": "fixed_surface_normal",
                        "seed": seed,
                    }
                )
                if scenario == "focal" and snr == 10 and repetition == 0:
                    example = {
                        "truth": truth,
                        "estimate": estimated,
                        "sensor": y,
                        "noise": evaluation_noise,
                        "times_s": np.arange(y.shape[1]) / config["fs_hz"],
                        "indices": indices,
                    }
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "recovery.csv", index=False)
    write_json(output / "ground-truth.json", truth_metadata)
    np.savez_compressed(output / "example-recovery.npz", **example)
    # Every regularization/depth sensitivity is retained, never select a best by truth.
    sensitivity = []
    y = example["sensor"]
    truth = example["truth"]
    for depth_setting in config["sensitivity_depth"]:
        for lambda2 in config["lambda2_grid"]:
            w = CorticalInverse(forward, covariance, lambda2=lambda2, depth=depth_setting).kernel
            estimate = w @ y
            sensitivity.append(
                {
                    "depth": depth_setting,
                    "lambda2": lambda2,
                    "residual_norm": float(np.linalg.norm(lead @ estimate - y)),
                    "penalty_norm_Am": float(np.linalg.norm(estimate)),
                    "relative_current_error": float(
                        np.linalg.norm(estimate - truth) / np.linalg.norm(truth)
                    ),
                    "sensor_noise_amplification_Am_per_V": float(np.linalg.norm(w, 2)),
                    **spatial_metrics(Resolution(w, lead).psf([focal])[:, 0], focal, xyz),
                }
            )
    pd.DataFrame(sensitivity).to_csv(output / "regularization.csv", index=False)
    np.savez_compressed(
        output / "simulation-operators.npz",
        assumed_forward=lead,
        perturbed_forward=mismatch,
        covariance_training=noise.covariance,
        whitener=noise.whitener,
        primary_inverse_kernel=kernel,
    )
    from scipy.linalg import subspace_angles

    from soma.source.sensitivity import sphere_sensitivity

    sphere_summary, sphere_arrays = sphere_sensitivity()
    write_json(output / "sphere-conductivity.json", sphere_summary)
    np.savez_compressed(output / "sphere-conductivity.npz", **sphere_arrays)
    write_json(
        output / "abstract-mismatch.json",
        {
            "role": "abstract 5 percent operator stress, not physically recomputed conductivity",
            "row_subspace_angles_rad": subspace_angles(lead.T, mismatch.T).tolist(),
            "relative_singular_spectrum_change": float(
                np.linalg.norm(
                    np.linalg.svd(mismatch, compute_uv=False)
                    - np.linalg.svd(lead, compute_uv=False)
                )
                / np.linalg.norm(np.linalg.svd(lead, compute_uv=False))
            ),
        },
    )
    from soma.visualization.source import simulation_figures

    simulation_figures(output, forward, frame, pd.DataFrame(sensitivity), example)
    grouped = (
        frame.groupby(["scenario", "snr_db"])[
            ["mean_assigned_peak_euclidean_m", "relative_current_error", "timecourse_correlation"]
        ]
        .mean()
        .reset_index()
        .to_dict("records")
    )
    return report.finish(
        {
            "status": "complete",
            "cases": len(rows),
            "noise": noise.diagnostics(),
            "covariance_training_seed": config["seed"] + config["noise_covariance_seed_offset"],
            "oracle_role": "SNR simulation control only; no oracle estimator selection",
            "relative_forward_perturbation": float(
                np.linalg.norm(mismatch - lead) / np.linalg.norm(lead)
            ),
            "perturbed_singular_values": np.linalg.svd(mismatch, compute_uv=False).tolist(),
            "aggregates": grouped,
        }
    )
