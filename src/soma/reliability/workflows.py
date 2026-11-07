"""Real matched model audit, inverse calibration, and attribution orchestration."""

import itertools
from pathlib import Path
from typing import Any

import mne
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from scipy.stats import t as student_t

from soma.anatomy.reporting import AnatomyReport
from soma.anatomy.surfaces import distance_to_surface
from soma.anatomy.uncertainty import perturb_transform
from soma.anatomy.workflow import coregistration_comparison
from soma.core.provenance import write_json
from soma.geometry import Frame, Transform
from soma.reliability.config import configuration, stream
from soma.reliability.evidence import assess_anatomy
from soma.reliability.inverse import calibrated_inverse, estimate_metrics, selected_calibration
from soma.reliability.registration import registration_experiments
from soma.source.individual import individual_forward, prepare_sample, require_correspondence
from soma.source.inverse import CorticalInverse
from soma.source.workflow import synthetic_covariance


def prepare(cfg: dict[str, Any]) -> tuple[Any, Any, Any, dict[str, Any], Any, Any, Any, Any]:
    assets, model, src, prepared = prepare_sample(Path(cfg["individual_config"]))
    fwd, receipt = individual_forward(model, src)
    noise, cov = synthetic_covariance(fwd, seed=cfg["seed"] + 100000, samples=10000)
    return assets, model, src, prepared, fwd, receipt, noise, cov


def require_head_mri(transform: Transform) -> None:
    if transform.source != Frame.HEAD or transform.destination != Frame.MRI or not transform.rigid:
        raise ValueError("Audit requires rigid HEAD→MRI, never its inverse interpreted in place")


def compare_transform(candidate: Transform, reference: Transform, points: Any) -> dict[str, float]:
    require_head_mri(candidate)
    require_head_mri(reference)
    r = candidate.matrix[:3, :3] @ reference.matrix[:3, :3].T
    return {
        "rotation_difference_deg": float(Rotation.from_matrix(r).magnitude() * 180 / np.pi),
        "translation_difference_mm": float(
            np.linalg.norm(candidate.matrix[:3, 3] - reference.matrix[:3, 3]) * 1000
        ),
        "point_displacement_RMS_mm": float(
            np.sqrt(
                np.mean(
                    np.sum((candidate.apply(points).xyz - reference.apply(points).xyz) ** 2, axis=1)
                )
            )
            * 1000
        ),
    }


def audit_coreg(output: Path, dataset: str = "mne-sample") -> dict[str, Any]:
    if dataset != "mne-sample":
        raise ValueError("Coregistration audit requires matched MNE sample cache")
    cfg = configuration(Path("configs/inverse-audit.yaml"))
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    with report.stage("assets_and_surface_QC"):
        assets, model, src, prepared = prepare_sample(Path(cfg["individual_config"]))
    report.source = prepared["identity"]
    require_head_mri(model.head_to_mri)
    with report.stage("Soma_comparison"):
        soma = coregistration_comparison(assets, model)
    with report.stage("MNE_supported_coregistration"):
        coreg = mne.coreg.Coregistration(
            model.info, assets.subject, subjects_dir=assets.subjects_dir, fiducials="estimated"
        )
        coreg.fit_fiducials(lpa_weight=1, nasion_weight=1, rpa_weight=1, verbose=False)
        fid = Transform.from_mne(coreg.trans)
        coreg.fit_icp(
            n_iterations=30,
            lpa_weight=0,
            nasion_weight=0,
            rpa_weight=0,
            hsp_weight=1,
            eeg_weight=0,
            hpi_weight=0,
            verbose=False,
        )
        icp = Transform.from_mne(coreg.trans)
    head, target, _ = assets.fiducials()
    hsp = assets.digitized(4)
    comparisons = {}
    for name, transform in [
        ("distributed", model.head_to_mri),
        ("MNE_fiducials", fid),
        ("MNE_ICP_headshape_only", icp),
        ("Soma_fiducials", Transform(Frame.HEAD, Frame.MRI, np.array(soma["SVD_transform_m"]))),
        ("Soma_ICP", Transform(Frame.HEAD, Frame.MRI, np.array(soma["ICP_transform_m"]))),
    ]:
        comparisons[name] = {
            "matrix_HEAD_to_MRI_m": transform.matrix.tolist(),
            "proxy_fiducial_discrepancy_mm": (
                np.linalg.norm(transform.apply(head).xyz - target.xyz, axis=1) * 1000
            ).tolist(),
            "common_ico3_headshape_triangle_distances_mm": (
                distance_to_surface(transform.apply(hsp), model.surfaces.meshes[-1]) * 1000
            ).tolist(),
            "difference_from_distributed_not_truth": compare_transform(
                transform, model.head_to_mri, hsp
            ),
        }
    with report.stage("asymmetric_registration_simulations"):
        registration = registration_experiments(cfg["seed"], cfg["registration_repetitions"])
    pd.DataFrame(registration["records"]).to_csv(output / "registration.csv", index=False)
    write_json(output / "registration.json", registration)
    write_json(output / "comparison.json", comparisons)
    geometry: dict[str, Any] = {
        "measured_fiducials_HEAD_m": head.xyz,
        "proxy_fiducials_MRI_m": target.xyz,
        "headshape_HEAD_m": hsp.xyz,
        "measured_EEG_HEAD_m": np.array([c["loc"][:3] for c in model.info["chs"]]),
        "scalp_MRI_m": model.surfaces.meshes[-1].vertices.xyz,
    }
    for name, values in comparisons.items():
        transform = Transform(Frame.HEAD, Frame.MRI, np.array(values["matrix_HEAD_to_MRI_m"]))
        geometry[name + "_headshape_MRI_m"] = transform.apply(hsp).xyz
    np.savez_compressed(output / "audited-geometry.npz", **geometry)
    from soma.reliability.plots import coreg_plots

    coreg_plots(output, comparisons, registration, geometry)
    return report.finish(
        {
            "status": "complete_audit",
            "dataset": dataset,
            "subject": "sample",
            "Soma": soma,
            "comparisons": comparisons,
            "registration_coverage": registration["coverage"],
            "simulation_failures": registration["failures"],
            "repetitions_per_scenario": cfg["registration_repetitions"],
            "true_real_transform_error": None,
            "residual_definitions": {
                "fiducial_fit": (
                    "Euclidean residual to the same MNI-derived MRI targets used in fit"
                ),
                "proxy_discrepancy": (
                    "distributed transform of measured head cardinals versus "
                    "derived MRI estimates; no truth"
                ),
                "headshape": "EXTRA points to common ico3 scalp triangles, not EEG or HPI",
                "reference_difference": (
                    "matrix/point differences against distributed transform, not "
                    "independent anatomical error"
                ),
            },
            "MNE_vs_Soma_fiducial_matrix_max_difference": float(
                np.max(np.abs(fid.matrix - np.array(soma["SVD_transform_m"])))
            ),
            "MNE_ICP_scope": (
                "headshape only, starts at MNE fiducial fit; MNE loaded scalp"
                " differs from Soma ico3 nearest-vertex trimmed objective"
            ),
            "anatomical_readiness": "INDETERMINATE",
        }
    )


def historical_audit(
    cfg: dict[str, Any], fwd: Any, cov: Any, model: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(cfg["historical_reports"])
    import json

    old = json.loads((path / "uncertainty/summary.json").read_text())
    with np.load(path / "uncertainty/recovery-examples.npz", allow_pickle=False) as data:
        truth = data["truth_Am"]
        measured = data["measured_V"]
        stored_cov = data["independent_noise_covariance"]
    with np.load(path / "individual/individual-forward.npz", allow_pickle=False) as data:
        if (
            not np.allclose(data["lead_field"], fwd.matrix, rtol=0, atol=1e-10)
            or not np.array_equal(data["lh_vertices"], fwd.vertices[0])
            or not np.array_equal(data["rh_vertices"], fwd.vertices[1])
        ):
            raise ValueError("Historical source/forward ordering differs")
    if not np.allclose(stored_cov, cov.data, rtol=1e-12, atol=1e-25):
        raise ValueError("Historical covariance differs")
    index = old["true_source_index"]
    est = calibrated_inverse(fwd, cov)
    W = est.kernel
    clean = fwd.matrix @ truth
    noise = measured - clean
    reconstructed = W @ measured
    noiseless = W @ clean
    noise_source = W @ noise
    gain = float(W[index] @ fwd.matrix[:, index])
    den = float(truth[index] @ truth[index])
    signed = float(reconstructed[index] @ truth[index] / den)
    orthogonal = reconstructed[index] - signed * truth[index]
    ratio = est.amplitude_ratio(reconstructed[index], truth[index])
    direct = (
        CorticalInverse(fwd, cov).apply(mne.EvokedArray(measured, fwd.info.copy(), nave=1)).data
    )
    result = {
        "original_bias": old["cases"][0]["amplitude_bias_ratio_minus_one"],
        "reproduced_bias": ratio - 1,
        "historical_metric_valid": True,
        "units": "A m",
        "definition": (
            "unsigned temporal L2 amplitude at generating fixed-normal source / truth L2 - 1"
        ),
        "true_index": index,
        "true_source_id": fwd.coordinates.identifiers[index],
        "resolution_diagonal_gain": gain,
        "noiseless_amplitude_ratio": est.amplitude_ratio(noiseless[index], truth[index]),
        "signed_waveform_transfer": signed,
        "noise_coherent_transfer": float(noise_source[index] @ truth[index] / den),
        "orthogonal_noise_energy_ratio": float(orthogonal @ orthogonal / den),
        "RMS_ratio_squared_identity_error": float(
            abs(ratio**2 - signed**2 - orthogonal @ orthogonal / den)
        ),
        "kernel_vs_direct_MNE_relative_error": float(
            np.linalg.norm(direct - reconstructed) / np.linalg.norm(direct)
        ),
        "noiseless_WL_prediction_relative_error": float(
            np.linalg.norm(noiseless - np.outer(W @ fwd.matrix[:, index], truth[index]))
            / np.linalg.norm(noiseless)
        ),
        "noise_free_source_relative_error": float(
            np.linalg.norm(noiseless - truth) / np.linalg.norm(truth)
        ),
        "interpretation": (
            "historical RMS metric valid; distributed resolution "
            "attenuation and realized noise are separate"
        ),
        "inverse_cache": est.receipt,
    }
    return result, {
        "truth_Am": truth,
        "measured_V": measured,
        "noiseless_Am": noiseless,
        "estimated_Am": reconstructed,
        "noise_source_Am": noise_source,
        "kernel_Am_per_V": W,
        "lead_V_per_Am": fwd.matrix,
        "head_to_MRI_m": model.head_to_mri.matrix,
    }


def inverse_study(config: Path, output: Path, *, resolution_only: bool = False) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    with report.stage("prepare"):
        assets, model, src, prepared, fwd, receipt, noise, cov = prepare(cfg)
    report.source = prepared["identity"]
    with report.stage("historical_reproduction"):
        historical, arrays = historical_audit(cfg, fwd, cov, model)
    np.savez_compressed(output / "historical-audit.npz", **arrays)
    write_json(output / "historical-audit.json", historical)
    xyz = model.head_to_mri.apply(fwd.coordinates.points).xyz
    with report.stage("source_depth"):
        depth = distance_to_surface(
            model.head_to_mri.apply(fwd.coordinates.points), model.surfaces.meshes[0]
        )
    indices = list(
        dict.fromkeys([historical["true_index"], int(np.argmax(depth)), int(np.argmin(depth))])
    )
    rows: list[dict[str, Any]] = []
    receipts = {}
    selected = {}
    failures = []
    methods = ["MNE"] if resolution_only else cfg["methods"]
    with report.stage("inverse_regularization_selected_resolution"):
        for loose, depth_weight, lambda2, method in itertools.product(
            cfg["loose"], cfg["depth"], cfg["lambda2"], methods
        ):
            label = f"{method}:loose{loose}:depth{depth_weight}:lambda{lambda2}"
            try:
                inverse = calibrated_inverse(
                    fwd, cov, method=method, loose=loose, depth=depth_weight, lambda2=lambda2
                )
                lead = fwd.matrix if loose == 0 else fwd.projector @ fwd.native_free["sol"]["data"]
                selected_ids = indices if loose == 0 else [3 * i + 2 for i in indices]
                cal = selected_calibration(inverse.kernel, lead, selected_ids, cov.data)
                receipts[label] = inverse.receipt
                if depth_weight == 0.8 and lambda2 == 1 / 9 and method == "MNE":
                    selected.update({label + ":" + k: v for k, v in cal.items()})
                for index in indices:
                    truth = np.zeros((len(xyz), 1 if loose == 0 else 3, 1))
                    truth[index, -1, 0] = 1e-8
                    recovered = (inverse.kernel @ (fwd.matrix[:, index] * 1e-8)).reshape(
                        truth.shape
                    )
                    metrics = estimate_metrics(recovered, truth, xyz, index)
                    normal_index = index if loose == 0 else 3 * index + 2
                    row = {
                        "method": method,
                        "units": inverse.units,
                        "loose": loose,
                        "depth_weight": depth_weight,
                        "lambda2": lambda2,
                        "index": index,
                        "depth_inner_skull_m": float(depth[index]),
                        "normal_resolution_gain": float(cal["diagonal_gain"][normal_index]),
                        "normal_transfer_units": "dimensionless"
                        if method == "MNE"
                        else "statistic / (A m)",
                        "noise_variance_units": "(A m)^2" if method == "MNE" else "statistic^2",
                        "noise_output_variance": float(cal["noise_variance"][normal_index]),
                        "noise_operator_norm": cal["noise_operator_norm"],
                        **metrics,
                    }
                    if method == "MNE":
                        row["amplitude_norm_ratio_at_true_source"] = inverse.amplitude_ratio(
                            recovered[index], truth[index]
                        )
                        row["normal_signed_transfer"] = float(recovered[index, -1, 0] / 1e-8)
                        row["sensor_residual_relative"] = float(
                            np.linalg.norm(lead @ recovered.ravel() - fwd.matrix[:, index] * 1e-8)
                            / np.linalg.norm(fwd.matrix[:, index] * 1e-8)
                        )
                        row["source_relative_error"] = float(
                            np.linalg.norm(recovered - truth) / np.linalg.norm(truth)
                        )
                    rows.append(row)
            except ValueError as exc:
                failures.append({"setting": label, "error": str(exc)})
    pd.DataFrame(rows).to_csv(output / "inverse-sweep.csv", index=False)
    write_json(output / "inverse-caches.json", receipts)
    np.savez_compressed(
        output / "selected-resolution.npz",
        **selected,
        source_MRI_m=xyz,
        depth_inner_skull_m=depth,
        indices=indices,
    )
    from soma.reliability.plots import inverse_plots

    inverse_plots(output, pd.DataFrame(rows), selected, historical, fwd, indices)
    return report.finish(
        {
            "status": "complete_resolution_study" if resolution_only else "complete_inverse_audit",
            "historical": historical,
            "selected_indices": indices,
            "settings": len(receipts),
            "metric_rows": len(rows),
            "failures": failures,
            "source_count": len(xyz),
            "shape": list(fwd.matrix.shape),
            "rank": noise.rank,
            "readiness": "INDETERMINATE",
            "full_dense_K_allocated": False,
            "source_clearance_audit": {
                "minimum_triangle_distance_m": float(depth.min()),
                "count_triangle_distance_below_5mm": int(np.sum(depth < 0.005)),
                "count_triangle_distance_below_1mm": int(np.sum(depth < 0.001)),
                "shallowest_index": int(np.argmin(depth)),
                "shallowest_nearest_vertex_distance_m": float(
                    cKDTree(model.surfaces.meshes[0].vertices.xyz).query(xyz[np.argmin(depth)])[0]
                ),
                "scope": (
                    "post-protocol diagnostic: MNE mindist uses nearest vertices, "
                    "not exact triangles; no sources changed"
                ),
            },
            "forward_diagnostics": {
                k: v
                for k, v in fwd.diagnostics().items()
                if k in ("retained_condition", "rank", "underdetermined")
            },
            "units_policy": (
                "MNE A m; dSPM/sLORETA dimensionless statistics, no physical "
                "amplitude/residual claims"
            ),
            "forward_cache": receipt,
        }
    )


def evidence_study(config: Path, output: Path) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    with report.stage("surface_QC_and_assets"):
        assets, model, src, prepared = prepare_sample(Path(cfg["individual_config"]))
    report.source = prepared["identity"]
    with report.stage("surface_volume_evidence"):
        evidence = assess_anatomy(assets, model, prepared, cfg["mask_sample_limit"])
    write_json(output / "evidence.json", evidence)
    from soma.reliability.plots import evidence_plots

    evidence_plots(output, evidence)
    return report.finish(
        {
            "status": evidence["status"],
            "anatomical_certification": False,
            "evidence_records": evidence["records"],
            "derivative_summary": {
                name: {k: v for k, v in values.items() if "distance_m" not in k}
                for name, values in evidence["derivative_checks"].items()
            },
            "source_subject": model.subject,
        }
    )


def paired_interval(values: Any) -> dict[str, float | int]:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("Independent finite simulation replicates required")
    mean = float(x.mean())
    half = float(student_t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))
    return {"mean": mean, "low95": mean - half, "high95": mean + half, "repetitions": len(x)}


def interaction(cells: dict[tuple[int, ...], Any], factors: tuple[int, ...]) -> Any:
    """Difference of differences at the low levels of other factors, paired draws."""
    if not factors or len(set(factors)) != len(factors):
        raise ValueError("Unique selected factors required")
    result = None
    for bits in itertools.product((0, 1), repeat=len(factors)):
        key = [0] * len(next(iter(cells)))
        for factor, bit in zip(factors, bits, strict=True):
            key[factor] = bit
        value = np.asarray(cells[tuple(key)]) * ((-1) ** (len(bits) - sum(bits)))
        result = value if result is None else result + value
    return result


def uncertainty_study(config: Path, output: Path) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    with report.stage("prepare"):
        assets, model, src, prepared, base, receipt, noise, cov = prepare(cfg)
    report.source = prepared["identity"]
    xyz = model.head_to_mri.apply(base.coordinates.points).xyz
    index = int(np.argmin(np.linalg.norm(xyz - [-0.04, -0.02, 0.05], axis=1)))
    truth = np.zeros(len(xyz))
    truth[index] = 1e-8
    clean = base.matrix @ truth
    n = len(clean)
    correlation = 0.35 ** np.abs(np.subtract.outer(np.arange(n), np.arange(n)))
    noise_shape = base.projector @ np.linalg.cholesky(correlation)
    common = noise_shape @ stream(cfg["seed"], 90000).standard_normal((n, cfg["noise_repetitions"]))
    scale = np.linalg.norm(clean) / np.sqrt(np.trace(base.projector @ correlation @ base.projector))
    primary = calibrated_inverse(base, cov)
    noise_free = primary.kernel @ clean
    baseline_error = float(np.linalg.norm(noise_free - truth) / np.linalg.norm(truth))
    rows: list[dict[str, Any]] = []
    arrays = {
        "truth_Am": truth,
        "source_MRI_m": xyz,
        "common_unit_sensor_noise": common,
        "evaluation_noise_scale_V_at_0dB": np.array(scale),
        "evaluation_covariance_V2_at_10dB": (scale**2 / 10) * noise_shape @ noise_shape.T,
        "covariance_V2": cov.data,
        "head_to_MRI_m": model.head_to_mri.matrix,
    }
    cells = {}
    failures = []
    cache_receipts = {}

    def evaluate(
        name: str, fwd: Any, lambda2: float, snr: float = 10, cell: tuple[int, ...] | None = None
    ) -> None:
        require_correspondence(base, fwd)
        inv = calibrated_inverse(fwd, cov, lambda2=lambda2)
        cache_receipts[name] = inv.receipt
        measured = clean[:, None] + common * scale / 10 ** (snr / 20)
        estimate = inv.kernel @ measured
        errors = np.linalg.norm(estimate - truth[:, None], axis=0) / np.linalg.norm(truth)
        peaks = np.linalg.norm(xyz[np.argmax(np.abs(estimate), axis=0)] - xyz[index], axis=1) * 1000
        arrays[name + ":relative_error"] = errors
        arrays[name + ":peak_error_mm"] = peaks
        arrays[name + ":forward"] = fwd.matrix
        arrays[name + ":estimated_current_Am"] = estimate
        metrics: dict[str, Any] = {
            **paired_interval(errors),
            "correct_model_noiseless_relative_error": baseline_error,
            "peak_error_mm": paired_interval(peaks),
            "snr_db": snr,
            "lambda2": lambda2,
            "case": name,
            "baseline_change": None,
        }
        rows.append(metrics)
        if cell is not None:
            cells[cell] = errors

    with report.stage("one_factor_and_SNR_simulations"):
        for snr in cfg["snr_db"]:
            evaluate("noise_SNR_" + str(snr), base, 1 / 9, snr)
        evaluate("correct", base, 1 / 9)
        registration, _ = individual_forward(
            model,
            src,
            head_to_mri=perturb_transform(model.head_to_mri, translation_m=cfg["translation_m"]),
        )
        evaluate("registration", registration, 1 / 9)
        modified = model.info.copy()
        offset = stream(cfg["seed"], 91000).normal(0, cfg["electrode_sd_m"], (n, 3))
        for ch, delta in zip(modified["chs"], offset, strict=True):
            ch["loc"][:3] += delta
        electrode, _ = individual_forward(model, src, info=modified)
        evaluate("electrode", electrode, 1 / 9)
        conductivity, _ = individual_forward(
            model, src, conductivities=(0.3, cfg["skull_sigma_S_m"], 0.3)
        )
        evaluate("conductivity", conductivity, 1 / 9)
        rotation, _ = individual_forward(
            model,
            src,
            head_to_mri=perturb_transform(model.head_to_mri, rotation_deg=cfg["rotation_deg"]),
        )
        evaluate("forward_rotation_mismatch", rotation, 1 / 9)
        evaluate("regularization", base, 1)
    with report.stage("paired_factorial_interactions"):
        for reg, skull, regularization in itertools.product((0, 1), repeat=3):
            try:
                fwd, _ = individual_forward(
                    model,
                    src,
                    head_to_mri=perturb_transform(
                        model.head_to_mri, translation_m=cfg["translation_m"] if reg else 0
                    ),
                    conductivities=(0.3, cfg["skull_sigma_S_m"] if skull else 0.006, 0.3),
                )
                evaluate(
                    f"factorial_{reg}{skull}{regularization}",
                    fwd,
                    1 if regularization else 1 / 9,
                    cell=(reg, skull, regularization),
                )
            except ValueError as exc:
                failures.append({"cell": [reg, skull, regularization], "error": str(exc)})
    reference = arrays["correct:relative_error"]
    for row in rows:
        row["baseline_change"] = paired_interval(
            arrays[row["case"] + ":relative_error"] - reference
        )
        row["total_error_change_from_noiseless_baseline"] = row["mean"] - baseline_error
    interactions = {}
    if len(cells) == 8:
        for factors in [(0, 1), (0, 2), (1, 2), (0, 1, 2)]:
            values = interaction(cells, factors)
            label = ",".join(map(str, factors))
            interactions[label] = paired_interval(values)
            arrays["interaction_" + label] = values
    np.savez_compressed(output / "paired-simulations.npz", **arrays)
    write_json(
        output / "paired-results.json",
        {
            "one_factor_and_cells": rows,
            "interactions": interactions,
            "inverse_caches": cache_receipts,
        },
    )
    from soma.reliability.plots import attribution_plots

    attribution_plots(output, rows, interactions, arrays)
    return report.finish(
        {
            "status": "complete_paired_attribution",
            "cases": rows,
            "interactions": interactions,
            "failures": failures,
            "independent_noise_realizations": cfg["noise_repetitions"],
            "evaluations": len(rows) * cfg["noise_repetitions"],
            "truth_index": index,
            "baseline_noiseless_error": baseline_error,
            "noise_assumptions": (
                "Fixed independent 1-uV training covariance and lambda; "
                "evaluation noise rescaled to each SNR, not refitted"
            ),
            "forward_shape": list(base.matrix.shape),
            "scope": (
                "paired conditional simulation; fixed selected perturbations,"
                " not additive biological variance decomposition"
            ),
            "factors": ["3mm registration x", "skull conductivity .003 S/m", "lambda2 1"],
            "anatomical_readiness": "INDETERMINATE",
            "baseline_forward_cache": receipt,
        }
    )
