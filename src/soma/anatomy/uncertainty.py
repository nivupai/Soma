"""Real matched EEG geometry/conductivity perturbations with fixed inverse settings."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from soma.anatomy.config import frozen_config
from soma.anatomy.reporting import AnatomyReport
from soma.anatomy.sensitivity import forward_difference
from soma.core.provenance import write_json
from soma.geometry import Frame, Points, Transform
from soma.geometry.coregistration import align_fiducials, icp_align
from soma.source.individual import individual_forward, prepare_sample, require_correspondence
from soma.source.inverse import CorticalInverse
from soma.source.resolution import spatial_metrics
from soma.source.workflow import synthetic_covariance


def perturb_transform(
    base: Transform, *, translation_m: float = 0, rotation_deg: float = 0
) -> Transform:
    update = np.eye(4)
    update[:3, :3] = Rotation.from_euler("z", rotation_deg, degrees=True).as_matrix()
    update[0, 3] = translation_m
    return base.then(Transform(Frame.MRI, Frame.MRI, update))


def uncertainty_workflow(config_path: Path, output: Path) -> dict[str, Any]:
    config = frozen_config(config_path)
    report = AnatomyReport(output, config, seed=config["seed"])
    with report.stage("prepare"):
        assets, model, src, prepared = prepare_sample(Path(config["individual_config"]))
    report.source = prepared["identity"]
    with report.stage("baseline_forward"):
        baseline, baseline_receipt = individual_forward(model, src)
    noise, cov = synthetic_covariance(
        baseline, seed=config["seed"] + 100000, samples=config["noise_covariance_samples"]
    )
    xyz_mri = model.head_to_mri.apply(baseline.coordinates.points).xyz
    true_index = int(np.argmin(np.linalg.norm(xyz_mri - [-0.04, -0.02, 0.05], axis=1)))
    t = np.arange(640) / 160
    truth = np.zeros((len(xyz_mri), len(t)))
    truth[true_index] = config["synthetic_source_amplitude_Am"] * np.sin(2 * np.pi * 10 * t)
    clean = baseline.matrix @ truth
    rng = np.random.default_rng(config["seed"])
    n = len(model.info["ch_names"])
    correlation = 0.35 ** np.abs(np.subtract.outer(np.arange(n), np.arange(n)))
    color = np.linalg.cholesky(correlation)
    noise_scale = (
        np.linalg.norm(clean)
        / np.sqrt(clean.shape[1] * np.trace(baseline.projector @ correlation @ baseline.projector))
        / 10 ** (config["synthetic_sensor_SNR_db"] / 20)
    )
    sensor_noise = noise_scale * baseline.projector @ color @ rng.normal(size=clean.shape)
    independent_variance_draws = (
        noise_scale
        * baseline.projector
        @ color
        @ np.random.default_rng(config["seed"] + 8888).normal(
            size=(n, config["monte_carlo_repetitions"])
        )
    )
    measured = clean + sensor_noise
    scenarios: list[tuple[str, float, Transform, Any, tuple[float, float, float], Any]] = [
        ("correct", 0.0, model.head_to_mri, model.info, (0.3, 0.006, 0.3), None)
    ]
    for magnitude in config["translation_m"]:
        scenarios.append(
            (
                "translation_x_m",
                magnitude,
                perturb_transform(model.head_to_mri, translation_m=magnitude),
                model.info,
                (0.3, 0.006, 0.3),
                None,
            )
        )
    for magnitude in config["rotation_deg"]:
        scenarios.append(
            (
                "rotation_z_deg",
                magnitude,
                perturb_transform(model.head_to_mri, rotation_deg=magnitude),
                model.info,
                (0.3, 0.006, 0.3),
                None,
            )
        )
    for magnitude in config["electrode_sigma_m"]:
        info = model.info.copy()
        offsets = (
            np.random.default_rng(config["seed"] + 100).normal(size=(len(info["chs"]), 3))
            * magnitude
        )
        for ch, offset in zip(info["chs"], offsets, strict=True):
            ch["loc"][:3] += offset
        scenarios.append(
            (
                "electrode_noise_m",
                magnitude,
                model.head_to_mri,
                info,
                (0.3, 0.006, 0.3),
                {"realized_electrode_RMS_m": float(np.sqrt(np.mean(np.sum(offsets**2, axis=1))))},
            )
        )
    for name, sigmas in config["conductivity_configurations_S_m"].items():
        if name != "baseline":
            scenarios.append(
                ("conductivity_" + name, 0.0, model.head_to_mri, model.info, tuple(sigmas), None)
            )
    head, target, origin = assets.fiducials()
    fid_base = align_fiducials(head, ("LPA", "nasion", "RPA"), target, ("LPA", "nasion", "RPA"))
    scenarios.append(
        (
            "fiducial_refit_no_noise",
            0.0,
            fid_base.transform,
            model.info,
            (0.3, 0.006, 0.3),
            {"MRI_targets": "MNI-derived, no independent MRI truth"},
        )
    )
    for magnitude in config["fiducial_sigma_m"]:
        noisy = Points(
            head.xyz
            + np.random.default_rng(config["seed"] + 200).normal(size=head.xyz.shape) * magnitude,
            Frame.HEAD,
        )
        fit = align_fiducials(noisy, ("LPA", "nasion", "RPA"), target, ("LPA", "nasion", "RPA"))
        scenarios.append(
            (
                "fiducial_noise_m",
                magnitude,
                fit.transform,
                model.info,
                (0.3, 0.006, 0.3),
                {
                    "fitting_RMS_m": fit.diagnostics["weighted_RMS_m"],
                    "true_transform_error": None,
                    "MRI_targets": "derived, not anatomical truth",
                },
            )
        )
    hsp = assets.digitized(4)
    fit0 = icp_align(
        hsp,
        model.surfaces.meshes[-1].vertices,
        model.head_to_mri,
        measurement_kind="digitized_headshape",
    )
    scenarios.append(
        (
            "headshape_refit_no_noise",
            0.0,
            fit0.transform,
            model.info,
            (0.3, 0.006, 0.3),
            fit0.diagnostics,
        )
    )
    for magnitude in config["headshape_sigma_m"]:
        noisy = Points(
            hsp.xyz
            + np.random.default_rng(config["seed"] + 300).normal(size=hsp.xyz.shape) * magnitude,
            Frame.HEAD,
        )
        fit = icp_align(
            noisy,
            model.surfaces.meshes[-1].vertices,
            model.head_to_mri,
            measurement_kind="digitized_headshape",
        )
        scenarios.append(
            (
                "headshape_noise_m",
                magnitude,
                fit.transform,
                model.info,
                (0.3, 0.006, 0.3),
                fit.diagnostics,
            )
        )
    rows = []
    channel_sensitivity = {}
    refit_operators = {}
    cache_receipts = {}
    examples: dict[str, Any] = {}
    with report.stage("physical_perturbation_sweep"):
        for name, magnitude, transform, info, sigmas, extra in scenarios:
            label = f"{name}:{magnitude}"
            try:
                fwd, receipt = individual_forward(
                    model, src, head_to_mri=transform, info=info, conductivities=sigmas
                )
                require_correspondence(baseline, fwd)
                difference = forward_difference(baseline.matrix, fwd.matrix)
                inverse = CorticalInverse(fwd, cov, lambda2=config["primary_lambda2"], depth=0.8)
                estimate = inverse.kernel @ measured
                energy = np.sum(estimate**2, axis=1)
                metrics = spatial_metrics(np.sqrt(energy), true_index, xyz_mri)
                source_var = np.var(
                    inverse.kernel @ independent_variance_draws, axis=1, ddof=1
                ).sum()
                row = {
                    "case": name,
                    "magnitude": magnitude,
                    "status": "computed",
                    "relative_leadfield_change": difference["relative_frobenius"],
                    "relative_spectrum_change": difference["relative_spectrum_change"],
                    "source_relative_error": float(
                        np.linalg.norm(estimate - truth) / np.linalg.norm(truth)
                    ),
                    "amplitude_bias_ratio_minus_one": float(
                        np.linalg.norm(estimate[true_index]) / np.linalg.norm(truth[true_index]) - 1
                    ),
                    "sensor_residual_relative": float(
                        np.linalg.norm(fwd.matrix @ estimate - measured) / np.linalg.norm(measured)
                    ),
                    "source_noise_variance_Am2": float(source_var),
                    **metrics,
                }
                if name.endswith("refit_no_noise"):
                    refit_operators[name] = fwd.matrix
                refit = (
                    "fiducial_refit_no_noise"
                    if name == "fiducial_noise_m"
                    else "headshape_refit_no_noise"
                    if name == "headshape_noise_m"
                    else None
                )
                if refit in refit_operators:
                    row["measurement_only_change_vs_unperturbed_refit"] = float(
                        np.linalg.norm(fwd.matrix - refit_operators[refit])
                        / np.linalg.norm(refit_operators[refit])
                    )
                rows.append(row)
                cache_receipts[label] = receipt
                channel_sensitivity[label] = difference
                if name in ("correct", "conductivity_skull_low") or (
                    name == "translation_x_m" and magnitude == 0.005
                ):
                    examples[label] = np.sqrt(energy / len(t))
                write_json(
                    output / (f"case-{len(rows):02d}.json"),
                    {
                        "case": label,
                        "transform": transform.matrix.tolist(),
                        "conductivities_S_m": sigmas,
                        "extra": extra,
                        "forward": fwd.diagnostics(),
                        "metrics": row,
                        "cache": receipt,
                    },
                )
            except ValueError as exc:
                rows.append(
                    {"case": name, "magnitude": magnitude, "status": "rejected", "reason": str(exc)}
                )
    pd.DataFrame(rows).to_csv(output / "mismatch.csv", index=False)
    write_json(output / "channel-and-spectrum-sensitivity.json", channel_sensitivity)
    np.savez_compressed(
        output / "recovery-examples.npz",
        **examples,
        source_MRI_m=xyz_mri,
        true_index=true_index,
        truth_Am=truth,
        measured_V=measured,
        independent_noise_covariance=noise.covariance,
    )
    from soma.visualization.anatomy import uncertainty_figures

    uncertainty_figures(output, pd.DataFrame(rows), examples, xyz_mri, true_index)
    return report.finish(
        {
            "status": "complete_conditional_research",
            "subject": model.subject,
            "readiness_status": prepared["readiness"]["status"],
            "cases": rows,
            "true_source_index": true_index,
            "true_source_id": baseline.coordinates.identifiers[true_index],
            "truth_role": (
                "synthetic current on participant geometry; no real neural "
                "truth; fixed inverse settings"
            ),
            "baseline_cache": baseline_receipt,
            "alternative_independent_anatomy": (
                "not available with validated corresponding sources; no arbitrary MRI substitution"
            ),
            "source_noise_variance_scope": (
                "20 independent sensor-noise draws at fixed geometry/current;"
                " not an anatomical posterior"
            ),
            "noise": noise.diagnostics(),
        }
    )
