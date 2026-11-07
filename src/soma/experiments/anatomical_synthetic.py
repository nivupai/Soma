"""Independent synthetic coregistration, conductor and local-uncertainty laboratory."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from soma.anatomy.config import frozen_config
from soma.anatomy.reporting import AnatomyReport
from soma.anatomy.sensitivity import central_differences, forward_difference, local_covariance
from soma.anatomy.surfaces import ConductorSurfaces
from soma.anatomy.synthetic import sphere_forward, sphere_surfaces, synthetic_info
from soma.core.provenance import write_json
from soma.geometry import Frame, Points, Transform
from soma.geometry.coregistration import icp_align, rigid_align
from soma.imaging.surfaces import Mesh
from soma.imaging.validation import transform_error
from soma.source.inverse import Tikhonov
from soma.source.resolution import spatial_metrics


def run_synthetic(
    output: Path, *, seed: int = 42, config_path: Path = Path("configs/source-uncertainty.yaml")
) -> dict[str, Any]:
    cfg = frozen_config(config_path)
    report = AnatomyReport(
        output,
        cfg,
        seed=seed,
        source={"origin": "known synthetic head geometry, not participant anatomy"},
    )
    xyz = np.array(cfg["synthetic_sources_m"])
    info = synthetic_info()
    subdivision = max(cfg["synthetic_bem_subdivisions"])
    with report.stage("surface_readiness"):
        surfaces = sphere_surfaces(subdivision)
        readiness = surfaces.readiness(sensor_compatible=True, anatomical_evidence=True)
    write_json(output / "readiness.json", readiness)
    if readiness["status"] != "PASS":
        raise ValueError("Synthetic conductor does not pass scoped geometric readiness")
    with report.stage("BEM_analytical_reference"):
        analytical, _ = sphere_forward(xyz, analytical=True)
        errors = []
        operators = {}
        for level in cfg["synthetic_bem_subdivisions"]:
            operator, receipt = sphere_forward(xyz, subdivisions=level)
            errors.append(
                {
                    "subdivisions": level,
                    "relative_BEM_vs_analytical_error": float(
                        np.linalg.norm(operator - analytical) / np.linalg.norm(analytical)
                    ),
                    "discretization_role": "separate from registration error",
                }
            )
            operators[f"BEM_{level}"] = operator
        baseline = operators[f"BEM_{subdivision}"]
    # Known noncollinear landmarks, and noncoplanar extra controls for chirality.
    landmarks = Points(
        np.array([[-0.075, 0, 0], [0, 0.1, 0.015], [0.08, 0, -0.005], [0, -0.04, 0.06]]), Frame.HEAD
    )
    matrix = np.eye(4)
    matrix[:3, :3] = Rotation.from_euler("xyz", [8, -5, 12], degrees=True).as_matrix()
    matrix[:3, 3] = [0.004, -0.003, 0.002]
    truth_transform = Transform(Frame.HEAD, Frame.MRI, matrix)
    target = truth_transform.apply(landmarks)
    alignment_rows = []
    coreg_case_operators = []
    with report.stage("coregistration_and_measurement_propagation"):
        for noise_std in [0.0, *cfg["fiducial_sigma_m"]]:
            noisy = Points(
                landmarks.xyz
                + np.random.default_rng(seed).normal(size=landmarks.xyz.shape) * noise_std,
                Frame.HEAD,
            )
            alignment = rigid_align(noisy, target)
            metrics = transform_error(alignment.transform, truth_transform, landmarks.xyz)
            # Isolate estimation error in physical MRI coordinates, leaving the
            # true synthetic forward at identity and source/sensor identities fixed.
            delta = truth_transform.inverse().then(alignment.transform)
            delta = Transform(Frame.HEAD, Frame.MRI, delta.matrix)
            operator, _ = sphere_forward(xyz, subdivisions=subdivision, transform=delta)
            alignment_rows.append(
                {
                    "measurement_std_m": noise_std,
                    "fit_RMS_m": alignment.diagnostics["weighted_RMS_m"],
                    **metrics,
                    "relative_forward_change": forward_difference(baseline, operator)[
                        "relative_frobenius"
                    ],
                }
            )
            coreg_case_operators.append(("fiducial_noise_m", noise_std, operator))
    headshape_rows = []
    scalp = surfaces.meshes[-1].vertices
    known_headshape = truth_transform.inverse().apply(Points(scalp.xyz[::8], Frame.MRI))
    with report.stage("synthetic_headshape_ICP_propagation"):
        for noise_std in [0.0, *cfg["headshape_sigma_m"]]:
            measured = Points(
                known_headshape.xyz
                + np.random.default_rng(seed + 5000).normal(size=known_headshape.xyz.shape)
                * noise_std,
                Frame.HEAD,
            )
            alignment = icp_align(
                measured, scalp, truth_transform, measurement_kind="synthetic_headshape"
            )
            delta = truth_transform.inverse().then(alignment.transform)
            operator, _ = sphere_forward(
                xyz,
                subdivisions=subdivision,
                transform=Transform(Frame.HEAD, Frame.MRI, delta.matrix),
            )
            headshape_rows.append(
                {
                    "measurement_std_m": noise_std,
                    "fit_RMS_m": float(np.sqrt(np.mean(alignment.residuals_m**2))),
                    **transform_error(alignment.transform, truth_transform, known_headshape.xyz),
                    "relative_forward_change": forward_difference(baseline, operator)[
                        "relative_frobenius"
                    ],
                    "scope": (
                        "initialized at truth; spherical scalp cannot establish rotation truth"
                    ),
                }
            )
            coreg_case_operators.append(("headshape_noise_m", noise_std, operator))
    pd.DataFrame(headshape_rows).to_csv(output / "headshape-errors.csv", index=False)
    # Negative controls retain observed rejection; no invalid model generates EEG.
    wrong = target.xyz.copy()
    wrong[[0, 1]] = wrong[[1, 0]]
    try:
        swapped = rigid_align(landmarks, Points(wrong, Frame.MRI))
        correspondence_control = {
            "rejected": False,
            "fit_RMS_m": swapped.diagnostics["weighted_RMS_m"],
            "scope": "wrong labels cannot be certified by optimizer convergence",
        }
    except ValueError as exc:
        correspondence_control = {"rejected": True, "reason": str(exc)}
    broken = list(surfaces.meshes)
    broken[0] = Mesh(broken[0].vertices, np.vstack([broken[0].faces, broken[0].faces[0]]))
    invalid = ConductorSurfaces(
        surfaces.subject, (broken[0], broken[1], broken[2]), surfaces.native, surfaces.provenance
    )
    negative_controls = {
        "incorrect_correspondence": correspondence_control,
        "nonmanifold_boundary": invalid.readiness(sensor_compatible=True, anatomical_evidence=True)[
            "status"
        ],
    }
    write_json(output / "negative-controls.json", negative_controls)
    pd.DataFrame(alignment_rows).to_csv(output / "coregistration-errors.csv", index=False)
    derivatives = {}
    derivative_records = {}

    def pose_translation(value: float) -> Any:
        t = np.eye(4)
        t[0, 3] = value
        return sphere_forward(
            xyz, subdivisions=subdivision, transform=Transform(Frame.HEAD, Frame.MRI, t)
        )[0]

    def pose_rotation(value: float) -> Any:
        t = np.eye(4)
        t[:3, :3] = Rotation.from_euler("z", value).as_matrix()
        return sphere_forward(
            xyz, subdivisions=subdivision, transform=Transform(Frame.HEAD, Frame.MRI, t)
        )[0]

    def electrode(value: float) -> Any:
        changed = info.copy()
        changed["chs"][0]["loc"][0] += value
        return sphere_forward(xyz, subdivisions=subdivision, info=changed)[0]

    def conductivity(value: float) -> Any:
        return sphere_forward(
            xyz, subdivisions=subdivision, conductivities=(0.3, 0.006 + value, 0.3)
        )[0]

    with report.stage("finite_difference_sweeps"):
        for name, fn, steps in [
            ("translation_x", pose_translation, cfg["finite_difference_translation_steps_m"]),
            (
                "rotation_z",
                pose_rotation,
                np.deg2rad(cfg["finite_difference_rotation_steps_deg"]).tolist(),
            ),
            ("electrode0_x", electrode, cfg["finite_difference_electrode_steps_m"]),
            ("skull_sigma", conductivity, cfg["finite_difference_skull_steps_S_m"]),
        ]:
            values, records = central_differences(fn, steps)
            derivatives[name] = values[-1]
            derivative_records[name] = records
    write_json(output / "finite-difference-convergence.json", derivative_records)
    # Local propagation is tested on the full operator vector with a scalar
    # translation variance, without allocating the full operator-vector covariance.
    jacobian = derivatives["translation_x"].reshape(-1, 1)
    sigma = cfg["monte_carlo_translation_std_m"]
    rng = np.random.default_rng(seed + 1000)
    offsets = rng.normal(0, sigma, cfg["monte_carlo_repetitions"])
    with report.stage("local_Monte_Carlo"):
        actual = np.stack([pose_translation(v).ravel() - baseline.ravel() for v in offsets])
    linear = offsets[:, None] * jacobian[:, 0]
    predicted_variance = jacobian[:, 0] ** 2 * sigma**2
    empirical = np.var(actual, axis=0, ddof=1)
    propagation = {
        "parameter": "head_to_MRI_translation_x",
        "std_m": sigma,
        "repetitions": len(offsets),
        "relative_realized_linearization_error": float(
            np.linalg.norm(actual - linear) / np.linalg.norm(actual)
        ),
        "predicted_total_operator_variance": float(predicted_variance.sum()),
        "MC_total_operator_variance": float(empirical.sum()),
        "MC_to_predicted_variance_ratio": float(empirical.sum() / predicted_variance.sum()),
        "parameter_sample_variance_ratio": float(np.var(offsets, ddof=1) / sigma**2),
        "scope": "local small-translation approximation; not a large-error anatomical posterior",
    }
    # Propagate a small sensor observation vector covariance too, where a dense
    # C_channels² matrix is harmless and can be checked independently by MC.
    current = np.zeros(baseline.shape[1])
    current[2] = cfg["synthetic_source_amplitude_Am"]
    observation_jac = derivatives["translation_x"] @ current
    predicted = local_covariance(observation_jac[:, None], np.array([[sigma**2]]))
    actual_observation = actual.reshape(-1, *baseline.shape) @ current
    propagation["sensor_covariance_relative_MC_error"] = float(
        np.linalg.norm(np.cov(actual_observation, rowvar=False) - predicted)
        / np.linalg.norm(predicted)
    )
    from scipy.stats import chi2

    empirical_parameter_variance = float(np.var(offsets, ddof=1))
    predicted_for_sample = local_covariance(
        observation_jac[:, None], np.array([[empirical_parameter_variance]])
    )
    sample_covariance = np.cov(actual_observation, rowvar=False)
    propagation[("sensor_covariance_error_given_realized_parameter_variance")] = float(
        np.linalg.norm(sample_covariance - predicted_for_sample) / np.linalg.norm(sample_covariance)
    )
    propagation[("Gaussian_MC_variance_ratio_95_percent_interval")] = (
        chi2.ppf([0.025, 0.975], len(offsets) - 1) / (len(offsets) - 1)
    ).tolist()
    write_json(output / "local-uncertainty.json", propagation)
    # Fixed dimensionless small-matrix reference regularization; not a cortical
    # replacement for MNE. All mismatch models use identical normalization.
    scale = np.linalg.svd(baseline, compute_uv=False)[0]
    rng = np.random.default_rng(seed + 2000)
    samples = 10000
    training = rng.normal(size=(baseline.shape[0], samples))
    P = np.eye(baseline.shape[0]) - np.ones((baseline.shape[0],) * 2) / baseline.shape[0]
    from soma.source.noise import NoiseModel

    noise = NoiseModel.estimate(training, tuple(info["ch_names"]), P)
    clean = baseline @ current
    epsilon = P @ np.random.default_rng(seed + 3000).normal(size=len(clean))
    epsilon *= (
        np.linalg.norm(clean)
        / np.linalg.norm(epsilon)
        / 10 ** (cfg["synthetic_sensor_SNR_db"] / 20)
    )
    observed = clean + epsilon
    cases = [("correct", 0.0, baseline), *coreg_case_operators]
    conductivity_changes = {}
    for name, sigmas in cfg["conductivity_configurations_S_m"].items():
        if name != "baseline":
            alt, _ = sphere_forward(xyz, subdivisions=subdivision, conductivities=tuple(sigmas))
            cases.append(("conductivity_" + name, 0.0, alt))
            conductivity_changes[name] = forward_difference(baseline, alt)
    for displacement in cfg["translation_m"]:
        cases.append(("translation_x_m", displacement, pose_translation(displacement)))
    for degrees in cfg["rotation_deg"]:
        cases.append(("rotation_z_deg", degrees, pose_rotation(np.deg2rad(degrees))))
    for amplitude in cfg["electrode_sigma_m"]:
        modified = info.copy()
        offset = np.random.default_rng(seed + 4000).normal(size=(len(info["chs"]), 3)) * amplitude
        for ch, delta in zip(modified["chs"], offset, strict=True):
            ch["loc"][:3] += delta
        cases.append(
            (
                "electrode_noise_m",
                amplitude,
                sphere_forward(xyz, subdivisions=subdivision, info=modified)[0],
            )
        )
    rows = []
    reconstructions: dict[str, Any] = {}
    for name, magnitude, operator in cases:
        inverse = Tikhonov(operator / scale, cfg["primary_lambda2"], noise)
        estimated = inverse.solve(observed / scale)
        strength = np.linalg.norm(estimated.reshape(-1, 3), axis=1)
        metrics = spatial_metrics(strength, 0, xyz)
        rows.append(
            {
                "case": name,
                "magnitude": magnitude,
                "relative_leadfield_change": forward_difference(baseline, operator)[
                    "relative_frobenius"
                ],
                "source_relative_error": float(
                    np.linalg.norm(estimated - current) / np.linalg.norm(current)
                ),
                "amplitude_bias_ratio_minus_one": float(
                    np.linalg.norm(estimated[:3]) / np.linalg.norm(current[:3]) - 1
                ),
                "sensor_residual_relative": float(
                    np.linalg.norm(operator @ estimated - observed) / np.linalg.norm(observed)
                ),
                **metrics,
            }
        )
        reconstructions[f"{name}:{magnitude}"] = estimated
    pd.DataFrame(rows).to_csv(output / "source-mismatch.csv", index=False)
    write_json(output / "conductivity-sensitivity.json", conductivity_changes)
    np.savez_compressed(
        output / "synthetic-operators.npz",
        analytical=analytical,
        **operators,
        **{name + "_derivative": value for name, value in derivatives.items()},
        operator_MC_delta=actual,
        linear_operator_MC_delta=linear,
        MC_translation_m=offsets,
        truth_current_Am=current,
        observed_sensor_V=observed,
        source_MRI_m=xyz,
        independent_covariance_training=noise.covariance,
        **reconstructions,
    )
    from soma.visualization.anatomy import synthetic_figures

    synthetic_figures(
        output,
        surfaces,
        alignment_rows,
        errors,
        rows,
        conductivity_changes,
        current,
        reconstructions,
        xyz,
    )
    return report.finish(
        {
            "status": "complete_synthetic",
            "seed": seed,
            "readiness": {k: v for k, v in readiness.items() if k != "quality"},
            "alignment": alignment_rows,
            "headshape_alignment": headshape_rows,
            "negative_controls": negative_controls,
            "discretization_vs_analytical": errors,
            "derivative_convergence": derivative_records,
            "local_propagation": propagation,
            "source_mismatch": rows,
            "truth": "known synthetic currents/geometry only",
            "regularization_policy": "fixed lambda2; no truth-selected estimator",
            "noise_covariance_training_independent": True,
        }
    )
