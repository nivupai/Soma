"""Paired continuous-source and reconstruction-grid benchmarks."""

from pathlib import Path
from typing import Any

import mne
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from soma.anatomy.reporting import AnatomyReport
from soma.anatomy.uncertainty import perturb_transform
from soma.benchmarks.config import configuration
from soma.benchmarks.offgrid import (
    ContinuousDipole,
    direction,
    evaluate_forward,
    offgrid,
    reconstruction_metrics,
    reconstruction_operator,
    source_grid,
)
from soma.core.provenance import write_json
from soma.geometry import Frame, Points
from soma.reliability.config import stream
from soma.reliability.workflows import paired_interval


def _summary(metrics: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in metrics.items():
        if name == "peak_index":
            continue
        a = np.asarray(value)
        if a.ndim == 0:
            result[name] = {"mean": float(a), "repetitions": 1, "low95": None, "high95": None}
        elif len(a) > 1:
            result[name] = paired_interval(a)
        else:
            result[name] = {"mean": float(a[0]), "repetitions": 1, "low95": None, "high95": None}
    return result


def realistic_example(cfg: dict[str, Any], output: Path) -> dict[str, Any]:
    from soma.anatomy.synthetic import discrete_sources
    from soma.imaging.mesh_quality import contains
    from soma.source.individual import individual_forward, prepare_sample
    from soma.source.inverse import CorticalInverse
    from soma.source.workflow import synthetic_covariance

    assets, model, src, prepared = prepare_sample()
    reference, receipt = individual_forward(model, src)
    noise, cov = synthetic_covariance(reference, seed=cfg["seed"] + 100000, samples=10000)
    xyz_reference = model.head_to_mri.apply(reference.coordinates.points).xyz
    positions = [[-0.04, -0.02, 0.05], [0.02, 0, 0.01]]
    true_forwards = {}
    rows: list[dict[str, Any]] = []
    failures = []
    arrays = {}
    for j, position in enumerate(positions):
        if not contains(model.surfaces.meshes[0], np.array([position]))[0]:
            failures.append(
                {
                    "position": position,
                    "reason": "prespecified dipole outside computational inner skull",
                }
            )
            continue
        explicit = discrete_sources(np.array([position]))
        explicit[0]["subject_his_id"] = "sample"
        bem = mne.read_bem_solution(receipt["BEM"]["path"], verbose=False)
        native = mne.make_forward_solution(
            model.info,
            trans=model.head_to_mri.to_mne(),
            src=explicit,
            bem=bem,
            meg=False,
            eeg=True,
            mindist=0,
            n_jobs=1,
            verbose=False,
        )
        expected = model.head_to_mri.inverse().apply(Points(np.array([position]), Frame.MRI)).xyz
        if not np.allclose(native["source_rr"], expected, atol=1e-9):
            raise ValueError("Continuous participant forward changed source identity")
        true_forwards[j] = (
            reference.projector
            @ native["sol"]["data"]
            @ np.linalg.inv(model.head_to_mri.matrix[:3, :3])
        )
        arrays[f"true_forward_{j}_V_per_Am"] = true_forwards[j]
    for spacing in ("ico2", "ico3"):
        src = mne.setup_source_space(
            "sample",
            spacing=spacing,
            surface="white",
            subjects_dir=assets.subjects_dir,
            add_dist=False,
            n_jobs=1,
            verbose=False,
        )
        fwd, fwd_receipt = individual_forward(model, src)
        xyz = model.head_to_mri.apply(fwd.coordinates.points)
        for orientation in ("fixed", "free"):
            inverse = CorticalInverse(fwd, cov, lambda2=1 / 9, orientation=orientation)
            lead = (
                fwd.matrix
                if orientation == "fixed"
                else fwd.projector @ fwd.native_free["sol"]["data"]
            )
            arrays[f"{spacing}_{orientation}_lead"] = lead
            arrays[spacing + "_grid_MRI_m"] = xyz.xyz
            for j, position in enumerate(positions):
                if j not in true_forwards:
                    continue
                nearest_reference = int(cKDTree(xyz_reference).query(position)[1])
                normal = (
                    model.head_to_mri.matrix[:3, :3]
                    @ reference.native_fixed["source_nn"][nearest_reference]
                )
                normal = normal / np.linalg.norm(normal)
                tangent = np.cross(normal, [1.0, 0, 0])
                tangent /= np.linalg.norm(tangent)
                for angle in (0, 30):
                    vector = normal * np.cos(np.deg2rad(angle)) + tangent * np.sin(
                        np.deg2rad(angle)
                    )
                    dipole = ContinuousDipole(
                        Points(np.array([position]), Frame.MRI),
                        vector,
                        cfg["source_moment_Am"],
                        "sample",
                    )
                    try:
                        distance, nearest = offgrid(
                            dipole, xyz, subject="sample", tolerance_m=cfg["offgrid_tolerance_m"]
                        )
                    except ValueError as exc:
                        failures.append(
                            {"spacing": spacing, "position": position, "error": str(exc)}
                        )
                        continue
                    clean = true_forwards[j] @ (vector * dipole.moment_Am)
                    epsilon = reference.projector @ stream(
                        cfg["seed"], 12000 + j * 100 + angle
                    ).normal(size=(len(clean), cfg["monte_carlo"]))
                    epsilon *= np.linalg.norm(clean) / np.sqrt(noise.rank) / 10**0.5
                    for label, observed in [
                        ("noiseless", clean[:, None]),
                        ("SNR10", clean[:, None] + epsilon),
                    ]:
                        estimate = inverse.kernel @ observed
                        # MNE free vectors are surface-local; their norm is invariant.
                        metrics = reconstruction_metrics(
                            estimate, lead, observed, dipole, xyz, nearest
                        )
                        if np.min(metrics["peak_error_mm"]) + 1e-6 < distance * 1000:
                            raise ValueError("Vertex localization violated geometric lower bound")
                        rows.append(
                            {
                                "spacing": spacing,
                                "orientation": orientation,
                                "source": j,
                                "angle_deg": angle,
                                "noise": label,
                                "metrics": _summary(metrics),
                                "truth": dipole.receipt(),
                                "source_count": len(xyz.xyz),
                                "shared_assumptions": (
                                    "same participant BEM/sensors; separately evaluated continuous "
                                    "dipole; cortical normal borrowed from nearest ico3 vertex"
                                ),
                                "forward_cache": fwd_receipt["forward"]["cache_key"]
                                if "forward" in fwd_receipt
                                else fwd_receipt.get("FWD", {}),
                                "anatomical_truth": "unavailable; computational geometry only",
                            }
                        )
                        arrays[f"{spacing}_{orientation}_{j}_{angle}_{label}_estimated_Am"] = (
                            estimate
                        )
    np.savez_compressed(
        output / "realistic-BEM.npz",
        **arrays,
        truth_positions_MRI_m=np.array(positions),
        head_to_MRI_m=model.head_to_mri.matrix,
    )
    write_json(
        output / "realistic-BEM.json",
        {
            "rows": rows,
            "failures": failures,
            "identity": prepared["identity"],
            "BEM_sha256": receipt["BEM"]["sha256"],
        },
    )
    return {
        "status": "conditional_BEM_complete"
        if rows and not failures
        else "conditional_BEM_partial",
        "rows": rows,
        "failures": failures,
        "anatomical_readiness": "INDETERMINATE",
    }


def source_benchmark(config: Path, output: Path, *, grid_only: bool = False) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(
        output,
        cfg,
        source={
            "reference": "independently evaluated continuous analytical layered-sphere dipoles"
        },
        seed=cfg["seed"],
    )
    P = np.eye(24) - np.ones((24, 24)) / 24
    rows: list[dict[str, Any]] = []
    receipts = {}
    arrays = {}
    operators = {}
    interactions = []
    failed: list[dict[str, Any]] = []
    true_positions = np.array(cfg["true_positions_m"])
    grids = {h: source_grid(h) for h in cfg["source_spacing_m"]}
    true_matrices = {}
    with report.stage("continuous_truth_forward"):
        for j, position in enumerate(true_positions):
            true_matrices[j], r = evaluate_forward(Points(position[None], Frame.MRI))
            receipts["truth_" + str(j)] = r

    def operator(
        h: float, kind: str, representation: str, lambda2: float, variant: str = "baseline"
    ) -> tuple[Any, Any, dict[str, Any]]:
        key = (h, kind, representation, lambda2, variant)
        if key not in operators:
            kwargs: dict[str, Any] = {}
            if variant in ("boundary", "boundary_registration"):
                kwargs["radii"] = (0.081, 0.085, 0.09)
            if variant == "conductivity":
                kwargs["sigmas"] = (0.3, 0.003, 0.3)
            if variant in ("registration", "boundary_registration"):
                from soma.geometry import Transform

                kwargs["transform"] = perturb_transform(
                    Transform(Frame.HEAD, Frame.MRI, np.eye(4)), translation_m=0.001
                )
            cart, receipt = evaluate_forward(grids[h], kind=kind, **kwargs)
            kernel, lead, diagnostics = reconstruction_operator(
                cart, grids[h], orientation=representation, lambda2=lambda2
            )
            operators[key] = (kernel, lead, diagnostics)
            name = f"{h}:{kind}:{representation}:{lambda2}:{variant}"
            receipts[name] = receipt
            arrays[name + ":lead"] = lead
            arrays[str(h) + ":grid_MRI_m"] = grids[h].xyz
        return operators[key]

    def evaluate(
        j: int,
        angle: int,
        h: float,
        kind: str,
        representation: str,
        lambda2: float,
        variant: str = "baseline",
    ) -> tuple[Any, dict[str, Any]]:
        position = true_positions[j]
        dipole = ContinuousDipole(
            Points(position[None], Frame.MRI), direction(position, angle), cfg["source_moment_Am"]
        )
        nearest_distance, nearest = offgrid(
            dipole, grids[h], tolerance_m=cfg["offgrid_tolerance_m"]
        )
        kernel, lead, diagnostics = operator(h, kind, representation, lambda2, variant)
        clean = true_matrices[j] @ (dipole.orientation * dipole.moment_Am)
        unit_noise = P @ stream(cfg["seed"], 20000 + j * 100 + angle).normal(
            size=(24, cfg["monte_carlo"])
        )
        unit_noise *= np.linalg.norm(clean) / np.sqrt(23) / 10**0.5
        id = f"{j}:{angle}:{h}:{kind}:{representation}:{lambda2}:{variant}"
        noisy = None
        for noise_label, observed in [
            ("noiseless", clean[:, None]),
            ("SNR10", clean[:, None] + unit_noise),
        ]:
            estimate = kernel @ observed
            metrics = reconstruction_metrics(estimate, lead, observed, dipole, grids[h], nearest)
            if np.min(metrics["peak_error_mm"]) + 1e-7 < nearest_distance * 1000:
                raise ValueError("Peak error below nearest-grid geometric bound")
            baseline_lead = operator(h, kind, representation, lambda2, "baseline")[1]
            analytical_lead = operator(h, "analytical", representation, lambda2, "baseline")[1]
            row = {
                "source": j,
                "angle_deg": angle,
                "spacing_m": h,
                "conductor": kind,
                "representation": representation,
                "lambda2": lambda2,
                "variant": variant,
                "noise": noise_label,
                "truth": dipole.receipt(),
                "source_depth_m": 0.08 - float(np.linalg.norm(position)),
                "metrics": _summary(metrics),
                "operator": diagnostics,
                "truth_forward_cache_key": receipts["truth_" + str(j)]["forward"]["cache_key"],
                "relative_leadfield_change_from_same_grid_baseline": float(
                    np.linalg.norm(lead - baseline_lead) / np.linalg.norm(baseline_lead)
                ),
                "relative_leadfield_change_from_analytical_grid": float(
                    np.linalg.norm(lead - analytical_lead) / np.linalg.norm(analytical_lead)
                ),
                "inverse_crime_class": "forward_geometry_mismatch"
                if variant == "registration"
                else "conductor_model_mismatch"
                if variant != "baseline"
                else "offgrid_shared_analytical_conductor"
                if kind == "analytical"
                else "offgrid_distinct_analytical_BEM_discretizations",
                "shared_physics": (
                    "isotropic concentric shells, common electrodes; no fully "
                    "physical independence claim"
                ),
            }
            rows.append(row)
            arrays[id + ":" + noise_label + ":peak_mm"] = metrics["peak_error_mm"]
            arrays[id + ":" + noise_label + ":nearest_ratio"] = metrics[
                "nearest_vertex_amplitude_ratio"
            ]
            if noise_label == "SNR10":
                noisy = metrics["peak_error_mm"]
        return noisy, row

    with report.stage("source_grid_inverse_sweep"):
        for h in grids:
            for kind in ("analytical", "BEM"):
                for representation in ("fixed", "free"):
                    for lambda2 in [1 / 9] if grid_only else cfg["lambda2"]:
                        for j in range(len(true_positions)):
                            for angle in (0, 30):
                                evaluate(j, angle, h, kind, representation, lambda2)
    # Explicit inverse-crime positive control, not promoted as independent validation.
    h = cfg["source_spacing_m"][0]
    grid = grids[h]
    index = len(grid.xyz) // 3
    kernel, lead, diagnostics = operator(h, "analytical", "fixed", 1 / 9)
    current = np.zeros(len(grid.xyz))
    current[index] = cfg["source_moment_Am"]
    observed = lead @ current
    control = {
        "class": "same_grid_operator_column_control",
        "independent_forward": False,
        "source_index": index,
        "resolution_diagonal_gain": float(kernel[index] @ lead[:, index]),
        "recovered_true_vertex_ratio": float((kernel @ observed)[index] / cfg["source_moment_Am"]),
    }
    if not grid_only:
        with report.stage("boundary_registration_factorial"):
            for h in grids:
                cells = {}
                for variant, bits in [
                    ("baseline", (0, 0)),
                    ("boundary", (1, 0)),
                    ("registration", (0, 1)),
                    ("boundary_registration", (1, 1)),
                    ("conductivity", None),
                ]:
                    values, row = evaluate(0, 0, h, "BEM", "fixed", 1 / 9, variant)
                    if bits is not None:
                        cells[bits] = values
                difference = cells[1, 1] - cells[1, 0] - cells[0, 1] + cells[0, 0]
                interactions.append(
                    {
                        "spacing_m": h,
                        "metric": "peak_error_mm",
                        "paired_difference_of_differences": paired_interval(difference),
                    }
                )
                arrays[str(h) + ":boundary_registration_interaction_mm"] = difference
    realistic: dict[str, Any] = {"status": "not_requested_in_grid_only_command"}
    if cfg["realistic_BEM"] and not grid_only:
        with report.stage("conditional_participant_BEM"):
            try:
                realistic = realistic_example(cfg, output)
            except FileNotFoundError as exc:
                realistic = {
                    "status": "missing_explicit_sample_cache",
                    "reason": str(exc),
                }
    write_json(output / "source-results.json", rows)
    write_json(output / "forward-receipts.json", receipts)
    np.savez_compressed(output / "source-arrays.npz", **arrays, true_positions_MRI_m=true_positions)
    flat = [
        {
            "source": r["source"],
            "angle_deg": r["angle_deg"],
            "spacing_m": r["spacing_m"],
            "conductor": r["conductor"],
            "representation": r["representation"],
            "lambda2": r["lambda2"],
            "variant": r["variant"],
            "noise": r["noise"],
            **{k: v["mean"] for k, v in r["metrics"].items()},
        }
        for r in rows
    ]
    pd.DataFrame(flat).to_csv(output / "source-results.csv", index=False)
    from soma.benchmarks.plots import source_plots

    source_plots(output, rows, grids, true_positions, interactions)
    return report.finish(
        {
            "status": "complete_source_grid_study" if grid_only else "complete_offgrid_study",
            "source_rows": len(rows),
            "source_evaluations": sum(
                int(r["metrics"]["peak_error_mm"]["repetitions"]) for r in rows
            ),
            "source_counts": {str(h): len(g.xyz) for h, g in grids.items()},
            "control": control,
            "interactions": interactions,
            "realistic_BEM": realistic,
            "failures": failed,
            "offgrid_tolerance_m": cfg["offgrid_tolerance_m"],
            "independent_physics_claimed": False,
            "no_grid_field_interpolation_used": True,
            "truth": true_positions.tolist(),
            "conductor_reference": (
                "analytical approximation shares spherical physics with BEM; discretizations differ"
            ),
        }
    )
