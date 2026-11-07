"""Asymmetric 3D registration phantoms with independent held-out targets."""

from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation
from scipy.stats import chi2

from soma.anatomy.synthetic import sphere_mesh
from soma.geometry import Frame, Points, Transform
from soma.geometry.coregistration import icp_align, rigid_align
from soma.reliability.config import stream


def wilson(successes: int, count: int) -> list[float]:
    if count < 1 or not 0 <= successes <= count:
        raise ValueError("Valid independent binomial trials required")
    z = 1.959963984540054
    p = successes / count
    center = (p + z * z / (2 * count)) / (1 + z * z / count)
    half = z * np.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / (1 + z * z / count)
    return [float(center - half), float(center + half)]


def phantom() -> tuple[Points, Points, Points, Transform]:
    vertices, _ = sphere_mesh(2, 1)
    u = vertices
    radial = 1 + 0.12 * u[:, 0] * u[:, 1] + 0.1 * u[:, 2] ** 3 + 0.08 * u[:, 0] ** 3
    xyz = u * radial[:, None] * [0.075, 0.09, 0.105]
    fit = Points(
        np.array([[-0.075, 0, 0], [0, 0.095, 0.012], [0.08, 0, -0.005], [0, -0.055, 0.07]]),
        Frame.HEAD,
    )
    held = Points(xyz[[3, 19, 35, 57, 78, 101, 129, 150]] * 0.7, Frame.HEAD)
    matrix = np.eye(4)
    matrix[:3, :3] = Rotation.from_euler("xyz", [8, -5, 12], degrees=True).as_matrix()
    matrix[:3, 3] = [0.004, -0.003, 0.002]
    return Points(xyz, Frame.HEAD), fit, held, Transform(Frame.HEAD, Frame.MRI, matrix)


def target_covariance(source: Points, targets: Points, held: Points, covariance: Any) -> Any:
    """Delta method through independent SVD fits, evaluated at a held-out target."""
    if source.frame != Frame.HEAD or targets.frame != Frame.MRI or held.frame != Frame.HEAD:
        raise ValueError("Explicit HEAD fitting/held-out points and MRI targets required")
    c = np.asarray(covariance, dtype=float)
    n = source.xyz.size
    if (
        c.shape != (n, n)
        or not np.isfinite(c).all()
        or not np.allclose(c, c.T)
        or np.min(np.linalg.eigvalsh(c)) < 0
    ):
        raise ValueError("Landmark covariance must match ordered coordinates and be PSD")
    jac = np.empty((3, n))
    h = 1e-6
    for j in range(n):
        offset = np.zeros_like(targets.xyz)
        offset.flat[j] = h
        plus = (
            rigid_align(source, Points(targets.xyz + offset, Frame.MRI))
            .transform.apply(held)
            .xyz[0]
        )
        minus = (
            rigid_align(source, Points(targets.xyz - offset, Frame.MRI))
            .transform.apply(held)
            .xyz[0]
        )
        jac[:, j] = (plus - minus) / (2 * h)
    return jac @ c @ jac.T


def registration_experiments(seed: int = 42, repetitions: int = 100) -> dict[str, Any]:
    if not 2 <= repetitions <= 1000:
        raise ValueError("Registration repetitions must be bounded 2..1000")
    surface, fit, held, truth = phantom()
    target = truth.apply(fit)
    scalp = truth.apply(surface)
    held_truth = truth.apply(held)
    independent = np.eye(12) * 0.002**2
    correlated = np.kron(np.full((4, 4), 0.6) + np.eye(4) * 0.4, np.eye(3) * 0.002**2)
    anisotropic = np.kron(np.eye(4), np.diag(np.array([0.001, 0.002, 0.004]) ** 2))
    cases = [
        "independent",
        "correlated",
        "anisotropic",
        "wrong_correspondence",
        "outlier",
        "headshape",
        "partial_headshape",
        "incorrect_initial_orientation",
    ]
    records = []
    coverage = {}
    param_cov = {}
    failures = []
    for case_id, name in enumerate(cases):
        covariance = {"correlated": correlated, "anisotropic": anisotropic}.get(name, independent)
        predicted = target_covariance(fit, target, held, covariance) if case_id < 3 else None
        samples = []
        covered = 0
        attempts = 0
        for rep in range(repetitions):
            rng = stream(seed, 10000 + case_id * 1000 + rep)
            observed = target.xyz + rng.multivariate_normal(np.zeros(12), covariance).reshape(4, 3)
            try:
                if name == "wrong_correspondence":
                    observed = observed[[1, 0, 2, 3]]
                if name == "outlier":
                    observed[0] += [0.02, 0, 0]
                if case_id < 5:
                    result = rigid_align(fit, Points(observed, Frame.MRI))
                    train = float(np.sqrt(np.mean(result.residuals_m**2)))
                else:
                    ids = np.arange(len(surface.xyz))[::2]
                    if name == "partial_headshape":
                        ids = ids[surface.xyz[ids, 0] > 0]
                    measured = Points(
                        surface.xyz[ids] + rng.normal(0, 0.002, (len(ids), 3)), Frame.HEAD
                    )
                    initial = truth.matrix.copy()
                    initial[:3, :3] = (
                        Rotation.from_euler(
                            "z", 60 if name == "incorrect_initial_orientation" else 3, degrees=True
                        ).as_matrix()
                        @ initial[:3, :3]
                    )
                    initial[:3, 3] += [0.003, 0, 0]
                    result = icp_align(
                        measured,
                        scalp,
                        Transform(Frame.HEAD, Frame.MRI, initial),
                        measurement_kind="synthetic_headshape",
                    )
                    train = float(np.sqrt(np.mean(result.residuals_m[result.inliers] ** 2)))
                delta = result.transform.matrix[:3, :3] @ truth.matrix[:3, :3].T
                rv = Rotation.from_matrix(delta).as_rotvec()
                te = result.transform.matrix[:3, 3] - truth.matrix[:3, 3]
                errors = result.transform.apply(held).xyz - held_truth.xyz
                record = {
                    "case": name,
                    "repeat": rep,
                    "fit_RMS_mm": train * 1000,
                    "heldout_TRE_RMS_mm": float(np.sqrt(np.mean(np.sum(errors**2, axis=1))) * 1000),
                    "rotation_error_deg": float(np.linalg.norm(rv) * 180 / np.pi),
                    "translation_error_mm": float(np.linalg.norm(te) * 1000),
                    "estimated_translation_x_mm": float(result.transform.matrix[0, 3] * 1000),
                    "estimated_rotation_angle_deg": float(
                        Rotation.from_matrix(result.transform.matrix[:3, :3]).magnitude()
                        * 180
                        / np.pi
                    ),
                }
                if predicted is not None:
                    covered += int(
                        errors[0] @ np.linalg.solve(predicted, errors[0]) <= chi2.ppf(0.95, 3)
                    )
                    attempts += 1
                records.append(record)
                samples.append(np.r_[rv, te])
                if name == "outlier":
                    try:
                        robust = rigid_align(
                            fit, Points(observed, Frame.MRI), robust_cutoff_m=0.006, seed=seed + rep
                        )
                        records.append(
                            {
                                "case": "outlier_robust",
                                "repeat": rep,
                                "fit_RMS_mm": robust.diagnostics["weighted_RMS_m"] * 1000,
                                "heldout_TRE_RMS_mm": float(
                                    np.sqrt(
                                        np.mean(
                                            np.sum(
                                                (robust.transform.apply(held).xyz - held_truth.xyz)
                                                ** 2,
                                                axis=1,
                                            )
                                        )
                                    )
                                    * 1000
                                ),
                                "rotation_error_deg": float(
                                    Rotation.from_matrix(
                                        robust.transform.matrix[:3, :3] @ truth.matrix[:3, :3].T
                                    ).magnitude()
                                    * 180
                                    / np.pi
                                ),
                                "translation_error_mm": float(
                                    np.linalg.norm(
                                        robust.transform.matrix[:3, 3] - truth.matrix[:3, 3]
                                    )
                                    * 1000
                                ),
                            }
                        )
                    except ValueError as exc:
                        failures.append(
                            {"case": "outlier_robust", "repeat": rep, "error": str(exc)}
                        )
            except ValueError as exc:
                failures.append({"case": name, "repeat": rep, "error": str(exc)})
        if samples:
            param_cov[name] = np.cov(np.stack(samples), rowvar=False).tolist()
        if predicted is not None:
            coverage[name] = {
                "covered": covered,
                "count": attempts,
                "coverage": covered / attempts if attempts else None,
                "Wilson_95_interval": wilson(covered, attempts) if attempts else None,
                "predicted_target_covariance_m2": predicted.tolist(),
                "scope": "first held-out target; assigned Gaussian noise model; trials independent",
            }
    return {
        "records": records,
        "coverage": coverage,
        "transform_parameter_covariance_rad_m": param_cov,
        "failures": failures,
        "truth_head_to_MRI_m": truth.matrix.tolist(),
        "fitting_HEAD_m": fit.xyz.tolist(),
        "heldout_HEAD_m": held.xyz.tolist(),
        "surface_HEAD_m": surface.xyz.tolist(),
        "noise_covariances_m2": {
            "independent": independent.tolist(),
            "correlated": correlated.tolist(),
            "anisotropic": anisotropic.tolist(),
        },
        "repetitions_per_scenario": repetitions,
        "seed": seed,
    }
