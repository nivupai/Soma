"""Paired off-grid experiments on the frozen M26 physical model."""

import hashlib
import itertools
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.anatomy.sensitivity import central_differences, forward_difference
from soma.eeg_benchmark.evaluation import environment_snapshot
from soma.geometry import Frame, Points
from soma.protocol.model import SealedProtocol, write_seal
from soma.results.contracts import create_result
from soma.results.io import load_result, save_result
from soma.source.uncertainty import (
    DESIGN_SHA256,
    Array,
    candidate_grid,
    check_protocol,
    design,
    electrode_positions,
    kernels,
    physical_forward,
    protocol,
    scenarios,
    transform,
)
from soma.workflow.model import digest


def known_truth() -> tuple[Points, Array]:
    c = design()
    rng = np.random.default_rng(c["seed"])
    xyz = rng.normal(size=(c["truth_cases"], 3))
    xyz[:, 2] = np.abs(xyz[:, 2])
    xyz /= np.linalg.norm(xyz, axis=1)[:, None]
    xyz *= rng.uniform(*c["truth_radius_mm"], size=(len(xyz), 1)) / 1000
    moments = rng.normal(size=xyz.shape)
    moments *= c["truth_amplitude_Am"] / np.linalg.norm(moments, axis=1)[:, None]
    return Points(xyz, Frame.MRI), moments


def source_metrics(
    estimate: Array, grid: Points, truth: Points, case: int, method: str
) -> dict[str, Any]:
    if (
        grid.frame != Frame.MRI
        or truth.frame != Frame.MRI
        or not 0 <= case < len(truth.xyz)
        or estimate.shape != (len(grid.xyz) * 3,)
        or not np.isfinite(estimate).all()
    ):
        raise ValueError("Ground-truth pairing, coordinate frame or estimate mismatch")
    amplitude = np.linalg.norm(estimate.reshape(-1, 3), axis=1)
    if not np.any(amplitude > 0):
        raise ValueError("Zero source estimate has no peak")
    distance = np.linalg.norm(grid.xyz - truth.xyz[case], axis=1) * 1000
    peak = int(np.argmax(amplitude))
    energy = amplitude**2
    return {
        "peak": peak,
        "localization_mm": float(distance[peak]),
        "dispersion_mm": float(np.sqrt(energy @ distance**2 / energy.sum())),
        "nearest_grid_mm": float(np.min(distance)),
        "peak_amplitude_bias_ratio": None
        if method == "dSPM"
        else float(amplitude[peak] / design()["truth_amplitude_Am"] - 1),
        "energy_outside_20mm": float(energy[distance > 20].sum() / energy.sum()),
    }


def aggregate(rows: pd.DataFrame) -> pd.DataFrame:
    """Source-cluster bootstrap; never count paired noise vectors as independent heads."""
    c = design()
    out = []
    keys = ["scenario", "method", "source", "noise_std_V", "draw"]
    planned = {s["id"]: s for s in scenarios()}
    if (
        rows.duplicated(keys).any()
        or not set(rows.source).issubset(range(c["truth_cases"]))
        or not set(rows.scenario).issubset(planned)
        or not set(rows.method).issubset(c["methods"])
        or not set(rows.noise_std_V).issubset(c["noise_std_V"])
        or any(
            r.draw not in range(1 if r.noise_std_V == 0 else c["noise_draws"])
            for r in rows.itertuples()
        )
    ):
        raise ValueError("Unknown or duplicate generator/measurement/protocol pairing")
    baseline = rows[rows.scenario == "baseline"][
        ["source", "noise_std_V", "draw", "method", "localization_mm"]
    ].rename(columns={"localization_mm": "baseline_localization_mm"})
    if baseline.duplicated(["source", "noise_std_V", "draw", "method"]).any():
        raise ValueError("Duplicated ground-truth/noise pairing")
    paired = rows.merge(
        baseline, on=["source", "noise_std_V", "draw", "method"], how="left", validate="many_to_one"
    )
    paired["excess_localization_mm"] = paired.localization_mm - paired.baseline_localization_mm
    for scenario, method, noise in itertools.product(planned, c["methods"], c["noise_std_V"]):
        group = paired[
            (paired.scenario == scenario)
            & (paired.method == method)
            & (paired.noise_std_V == noise)
        ]
        expected = c["truth_cases"] * (1 if noise == 0 else c["noise_draws"])
        complete = (
            len(group) == expected
            and (group.status == "computed").all()
            and group.source.nunique() == c["truth_cases"]
            and not group.duplicated(["source", "draw"]).any()
            and all(
                len(x) == (1 if noise == 0 else c["noise_draws"])
                for _, x in group.groupby("source")
            )
        )
        r = {
            "scenario": scenario,
            "family": planned[scenario]["family"],
            "method": method,
            "noise_std_V": noise,
            "planned": expected,
            "computed": int((group.status == "computed").sum()),
            "status": "complete" if complete else "INCOMPLETE",
            "independent_generators": c["truth_cases"],
        }
        for metric in [
            "localization_mm",
            "dispersion_mm",
            "peak_amplitude_bias_ratio",
            "excess_localization_mm",
        ]:
            r[metric] = r[metric + "_low"] = r[metric + "_high"] = None
            if not complete or (method == "dSPM" and metric == "peak_amplitude_bias_ratio"):
                continue
            values = group.groupby("source")[metric].mean().to_numpy()
            if not np.isfinite(values).all() or len(values) != c["truth_cases"]:
                continue
            draws = (
                np.random.default_rng(c["seed"] + 900)
                .choice(values, (c["bootstrap_repetitions"], len(values)))
                .mean(axis=1)
            )
            low, high = np.quantile(draws, [0.025, 0.975])
            r.update(
                {
                    metric: float(values.mean()),
                    metric + "_low": float(low),
                    metric + "_high": float(high),
                }
            )
        out.append(r)
    return pd.DataFrame(out)


def run_uncertainty(sealed: SealedProtocol, output: Path) -> dict[str, Any]:
    check_protocol(sealed)
    c = design()
    output.mkdir(parents=True, exist_ok=False)
    write_seal(sealed, output / "protocol.json")
    started = time.perf_counter()
    grid, truth = candidate_grid(), known_truth()
    locations, moments = truth
    electrodes = electrode_positions()
    reference = physical_forward(grid, electrodes, transform())
    true_forward = physical_forward(locations, electrodes, transform())
    if np.min(np.linalg.norm(locations.xyz[:, None] - grid.xyz[None], axis=2)) < 1e-6:
        raise ValueError("Truth accidentally overlaps inverse grid")
    pd.DataFrame(reference.matrix).to_csv(
        output / "baseline-leadfield_V_per_Am.csv", index=False, float_format="%.17g"
    )
    pd.DataFrame(true_forward.matrix).to_csv(
        output / "truth-leadfield_V_per_Am.csv", index=False, float_format="%.17g"
    )
    scale = float(np.linalg.norm(reference.matrix, 2))
    clean = np.column_stack(
        [true_forward.matrix[:, 3 * i : 3 * i + 3] @ m for i, m in enumerate(moments)]
    )
    rng = np.random.default_rng(c["seed"] + 500)
    columns, indexes = [], []
    for source in range(c["truth_cases"]):
        for std in c["noise_std_V"]:
            for draw in range(1 if std == 0 else c["noise_draws"]):
                columns.append(
                    clean[:, source] + std * reference.projector @ rng.normal(size=c["sensors"])
                )
                indexes.append({"source": source, "noise_std_V": std, "draw": draw})
    measured = np.column_stack(columns)
    pairing = digest(
        {"truth": locations.xyz.tolist(), "moments": moments.tolist(), "index": indexes}
    )
    pd.DataFrame(measured).to_csv(output / "measurements_V.csv", index=False, float_format="%.17g")
    pd.DataFrame(locations.xyz * 1000, columns=["x_mm", "y_mm", "z_mm"]).to_csv(
        output / "truth-locations.csv", index=False
    )
    pd.DataFrame(moments, columns=["qx_Am", "qy_Am", "qz_Am"]).to_csv(
        output / "truth-moments.csv", index=False
    )
    pd.DataFrame(grid.xyz * 1000, columns=["x_mm", "y_mm", "z_mm"]).to_csv(
        output / "inverse-grid.csv", index=False
    )
    pd.DataFrame(indexes).to_csv(output / "measurement-index.csv", index=False)
    rows, diagnostics, examples = [], [], []
    baseline_estimates: dict[str, Array] = {}
    for scenario in scenarios():
        start = time.perf_counter()
        name = scenario["id"]
        try:
            radii = list(c["shell_radii_mm"])
            radii[1] += scenario["inner_mm"]
            radii[2] += scenario["outer_mm"]
            sigmas = list(c["conductivities_S_m"])
            sigmas[2] = scenario["skull"]
            t = transform(scenario["translation_mm"], scenario["rotation_deg"])
            f = physical_forward(
                grid,
                electrode_positions(scenario["electrode_mm"], scenario["pattern"]),
                t,
                radii,
                sigmas,
            )
            forward_seconds = time.perf_counter() - start
            inverse_started = time.perf_counter()
            operators, inverse_check = kernels(f, scale)
            inverse_seconds = time.perf_counter() - inverse_started
            difference = forward_difference(reference.matrix, f.matrix)
            diagnostic = {
                **scenario,
                **f.diagnostics,
                **inverse_check,
                "forward_seconds": forward_seconds,
                "inverse_seconds": inverse_seconds,
                "relative_forward_error": difference["relative_frobenius"],
                "spectrum_relative_error": difference["relative_spectrum_change"],
                "registration_rms_mm": float(
                    np.sqrt(
                        np.mean(
                            np.sum(
                                (t.apply(Points(grid.xyz, Frame.HEAD)).xyz - grid.xyz) ** 2, axis=1
                            )
                        )
                    )
                    * 1000
                ),
                "forward_sha256": hashlib.sha256(f.matrix.tobytes()).hexdigest(),
                "status": "computed",
            }
            for method, kernel in operators.items():
                estimate = kernel @ measured
                if name == "baseline":
                    baseline_estimates[method] = estimate
                resolution = kernel @ f.matrix
                true_psf = kernel @ true_forward.matrix
                diagnostic[method + "_resolution_frobenius"] = float(np.linalg.norm(resolution))
                diagnostic[method + "_resolution_units"] = "1/(A m)" if method == "dSPM" else "1"
                for j, index in enumerate(indexes):
                    values = source_metrics(
                        estimate[:, j], grid, locations, index["source"], method
                    )
                    rows.append(
                        {
                            "scenario": name,
                            "family": scenario["family"],
                            "method": method,
                            **index,
                            "status": "computed",
                            **values,
                            "sensor_residual_relative": float(
                                np.linalg.norm(f.matrix @ estimate[:, j] - measured[:, j])
                                / np.linalg.norm(measured[:, j])
                            )
                            if method != "dSPM"
                            else None,
                        }
                    )
                if name in [
                    "baseline",
                    "conductivity-0.01",
                    "outer_boundary-2",
                    "electrode-5-0",
                    "translation-5",
                    "rotation-5",
                    "interaction-1111",
                ]:
                    magnitudes = np.linalg.norm(estimate[:, 0].reshape(-1, 3), axis=1)
                    baseline_map = np.linalg.norm(
                        baseline_estimates[method][:, 0].reshape(-1, 3), axis=1
                    )
                    examples.append(
                        {
                            "scenario": name,
                            "family": scenario["family"],
                            "method": method,
                            "grid_mm": (grid.xyz * 1000).tolist(),
                            "truth_mm": (locations.xyz[0] * 1000).tolist(),
                            "baseline": baseline_map.tolist(),
                            "perturbed": magnitudes.tolist(),
                            "metrics": source_metrics(estimate[:, 0], grid, locations, 0, method),
                            "psf_frobenius": float(np.linalg.norm(true_psf)),
                            "units": "dimensionless" if method == "dSPM" else "A m",
                        }
                    )
        except (ValueError, RuntimeError, np.linalg.LinAlgError) as error:
            diagnostic = {**scenario, "status": "FAILED", "reason": str(error)}
            existing = {
                (r["method"], r["source"], r["noise_std_V"], r["draw"])
                for r in rows
                if r["scenario"] == name
            }
            for method in c["methods"]:
                for index in indexes:
                    if (
                        method,
                        index["source"],
                        index["noise_std_V"],
                        index["draw"],
                    ) not in existing:
                        rows.append(
                            {
                                "scenario": name,
                                "family": scenario["family"],
                                "method": method,
                                **index,
                                "status": "FAILED",
                                "localization_mm": None,
                                "dispersion_mm": None,
                                "peak_amplitude_bias_ratio": None,
                                "reason": str(error),
                            }
                        )
        diagnostic["runtime_seconds"] = time.perf_counter() - start
        diagnostics.append(diagnostic)
    frame = pd.DataFrame(rows)
    for family, group in frame.groupby("family"):
        group.to_csv(output / (str(family) + "-cases.csv"), index=False, float_format="%.17g")
    summary = aggregate(frame)
    summary.to_csv(output / "summary.csv", index=False, float_format="%.17g")
    pd.DataFrame(diagnostics).to_csv(
        output / "forward-diagnostics.csv", index=False, float_format="%.17g"
    )
    (output / "examples.json").write_text(
        json.dumps(
            {"synthetic_only": True, "frame": "true MRI mm", "examples": examples},
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )

    # Fixed numerical convergence diagnostics, not an outcome-selected primary model.
    def boundary(delta: float) -> Array:
        radii = list(c["shell_radii_mm"])
        radii[2] += delta
        return physical_forward(grid, electrodes, transform(), radii).matrix

    _, derivative = central_differences(boundary, c["derivative_steps_mm"])
    dense_started = time.perf_counter()
    dense_grid = candidate_grid(2)
    dense = physical_forward(dense_grid, electrodes, transform())
    dense_forward_seconds = time.perf_counter() - dense_started
    dense_inverse_started = time.perf_counter()
    dense_ops, _ = kernels(dense, scale)
    dense_inverse_seconds = time.perf_counter() - dense_inverse_started
    convergence = []
    for method, kernel in dense_ops.items():
        estimates = kernel @ clean
        for i in range(c["truth_cases"]):
            convergence.append(
                {
                    "method": method,
                    "source": i,
                    **source_metrics(estimates[:, i], dense_grid, locations, i, method),
                }
            )
    pd.DataFrame(convergence).to_csv(output / "grid-convergence.csv", index=False)
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        2**20 if sys.platform == "darwin" else 1024
    )
    report = {
        "schema": "soma.source-uncertainty/1",
        "synthetic_only": True,
        "protocol_fingerprint": sealed.protocol.fingerprint,
        "design_sha256": DESIGN_SHA256,
        "pairing_fingerprint": pairing,
        "configurations": len(scenarios()),
        "independent_generators": c["truth_cases"],
        "inverse_grid_sources": len(grid.xyz),
        "measurements_per_configuration": len(indexes),
        "methods": c["methods"],
        "case_rows": len(rows),
        "failed_rows": int((frame.status != "computed").sum()),
        "failed_configurations": [d["id"] for d in diagnostics if d["status"] != "computed"],
        "derivative_convergence": derivative,
        "dense_grid": {
            "sources": len(dense_grid.xyz),
            "forward_seconds": dense_forward_seconds,
            "inverse_seconds": dense_inverse_seconds,
            "leadfield_bytes": dense.matrix.nbytes,
        },
        "baseline_leadfield_bytes": reference.matrix.nbytes,
        "measurement_sha256": hashlib.sha256(measured.tobytes()).hexdigest(),
        "implementation_sha256": {
            "experiment": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "physics": hashlib.sha256(
                Path(physical_forward.__code__.co_filename).read_bytes()
            ).hexdigest(),
        },
        "runtime_seconds": time.perf_counter() - started,
        "process_peak_rss_mib": peak_rss,
        "memory_scope": "whole controller peak, includes imports; not isolated case allocations",
        "human_subjects": 0,
        "uncertainty_scope": c["interval_unit"],
        "environment": environment_snapshot(),
    }
    report["files"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.iterdir())
        if p.is_file()
    }
    domain = {
        "computation": "physical synthetic source uncertainty",
        "inputs": {"design": DESIGN_SHA256},
        "environment": report["environment"],
        "assumptions": ["isotropic spherical conductor, fixed synthetic head"],
        "validation": {"scope": "conditional numerical simulation"},
        "limitations": ["not MRI segmentation or human source localization validation"],
    }
    envelope = create_result(
        "experiment.manifest",
        domain,
        values=report,
        provenance={"protocol": sealed.protocol.fingerprint},
        method={"id": "soma.source-uncertainty", "version": "1"},
        parameters=c,
        units={"distance": "mm", "current": "A*m"},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(envelope, {}, output / "manifest")
    (output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def read_uncertainty(path: Path) -> dict[str, Any]:
    envelope, arrays = load_result(path)
    if envelope["method"] != {"id": "soma.source-uncertainty", "version": "1"} or arrays:
        raise ValueError("Expected aggregate uncertainty manifest")
    d = dict(envelope["payload"]["values"])
    if (
        d["synthetic_only"] is not True
        or d["human_subjects"] != 0
        or d["design_sha256"] != DESIGN_SHA256
    ):
        raise ValueError("Unapproved human result or design drift")
    if d["protocol_fingerprint"] != protocol().protocol.fingerprint:
        raise ValueError("Unapproved result protocol")
    return d
