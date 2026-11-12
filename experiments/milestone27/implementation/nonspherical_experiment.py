"""Frozen synthetic BEM experiment; no participant data or outcome-dependent tuning."""

import hashlib
import itertools
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.eeg_benchmark.evaluation import environment_snapshot
from soma.experiments.source_uncertainty import source_metrics
from soma.geometry import Frame, Points
from soma.protocol.model import SealedProtocol, write_seal
from soma.results.contracts import create_result
from soma.results.io import save_result
from soma.source.noise import average_projector
from soma.source.nonspherical import (
    DESIGN_SHA,
    cases,
    check_protocol,
    check_sources,
    convergence,
    design,
    head_parameters,
    meshes,
    native_forward,
    pose,
    radial_projection,
    sensor_targets,
    source_grid,
    validate_meshes,
)
from soma.source.nonspherical_solver import solve
from soma.source.uncertainty import electrode_positions, kernels, physical_forward, transform
from soma.workflow.model import digest


def known_truth(head: int) -> tuple[Points, Any]:
    c = design()
    head_parameters(head)
    rng = np.random.default_rng(c["seed"] + 1000 + head)
    xyz = rng.normal(size=(c["sources_per_head"], 3))
    xyz[:, 2] = np.abs(xyz[:, 2])
    xyz /= np.linalg.norm(xyz, axis=1)[:, None]
    xyz *= (
        rng.uniform(float(c["truth_radius_mm"][0]), float(c["truth_radius_mm"][1]), (len(xyz), 1))
        / 1000
    )
    moment = rng.normal(size=xyz.shape)
    moment *= c["source_amplitude_Am"] / np.linalg.norm(moment, axis=1)[:, None]
    return Points(xyz, Frame.MRI), moment


def hierarchical(values: Any) -> tuple[float, float, float]:
    """Fixed family strata, resample heads then sources; noise already averaged."""
    c = design()
    a = np.asarray(values, dtype=float)
    if a.shape != (6, 12) or not np.isfinite(a).all():
        raise ValueError("Complete paired six-head/twelve-source matrix required")
    rng = np.random.default_rng(c["seed"] + 30000)
    heads = np.concatenate(
        [rng.integers(i, i + 2, (c["bootstrap_repetitions"], 2)) for i in (0, 2, 4)], axis=1
    )
    sources = rng.integers(0, 12, (c["bootstrap_repetitions"], 6, 12))
    samples = a[heads[:, :, None], sources].mean(axis=(1, 2))
    low, high = np.quantile(samples, [0.025, 0.975])
    return float(a.mean()), float(low), float(high)


def aggregate(rows: pd.DataFrame) -> pd.DataFrame:
    c = design()
    names = [r["id"] for r in cases()] + ["sphere-control"]
    keys = ["head", "case", "source", "noise_std_V", "draw", "method"]
    if (
        rows.duplicated(keys).any()
        or not set(rows.case).issubset(names)
        or not set(rows.method).issubset(c["methods"])
    ):
        raise ValueError("Duplicate/unknown paired configuration")
    if any(
        r.head not in range(6)
        or r.source not in range(12)
        or r.noise_std_V not in c["noise_std_V"]
        or r.draw not in range(1 if r.noise_std_V == 0 else 8)
        for r in rows.itertuples()
    ):
        raise ValueError("Unknown truth/noise identity")
    base = rows[rows.case == "mesh-2"][
        ["head", "source", "noise_std_V", "draw", "method", "localization_mm"]
    ].rename(columns={"localization_mm": "base_mm"})
    paired = rows.merge(
        base,
        on=["head", "source", "noise_std_V", "draw", "method"],
        how="left",
        validate="many_to_one",
    )
    paired["excess_mm"] = paired.localization_mm - paired.base_mm
    out = []
    for case, method, noise in itertools.product(names, c["methods"], c["noise_std_V"]):
        g = paired[
            (paired.case == case) & (paired.method == method) & (paired.noise_std_V == noise)
        ]
        expected = 72 * (1 if noise == 0 else 8)
        complete = len(g) == expected and (g.status == "computed").all()
        row = dict(
            case=case,
            method=method,
            noise_std_V=noise,
            planned=expected,
            computed=int((g.status == "computed").sum()),
            status="complete" if complete else "INCOMPLETE",
        )
        for metric in (
            "localization_mm",
            "dispersion_mm",
            "peak_amplitude_bias_ratio",
            "excess_mm",
        ):
            row[metric] = row[metric + "_low"] = row[metric + "_high"] = None
            if complete and not (method == "dSPM" and metric == "peak_amplitude_bias_ratio"):
                v = (
                    g.groupby(["head", "source"])[metric]
                    .mean()
                    .reindex(pd.MultiIndex.from_product([range(6), range(12)]))
                    .to_numpy()
                    .reshape(6, 12)
                )
                if np.isfinite(v).all():
                    row[metric], row[metric + "_low"], row[metric + "_high"] = hierarchical(v)
        out.append(row)
    return pd.DataFrame(out)


def run_nonspherical(sealed: SealedProtocol, output: Path) -> dict[str, Any]:
    check_protocol(sealed)
    c = design()
    output.mkdir(parents=True, exist_ok=False)
    write_seal(sealed, output / "protocol.json")
    started = time.perf_counter()
    grid = source_grid()
    records: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    for head in c["head_ids"]:
        p = head_parameters(head)
        root = output / f"head-{head}"
        root.mkdir()
        truth, moments = known_truth(head)
        if np.min(np.linalg.norm(grid.xyz[:, None] - truth.xyz[None], axis=2)) < 1e-6:
            raise ValueError("Inverse crime: overlapping truth/grid")
        fine = meshes(p, 3)
        fq = validate_meshes(fine)
        check_sources(fine[0], grid)
        check_sources(fine[0], truth)
        sensors, projection = radial_projection(fine[-1], sensor_targets(p))
        fine_g, fd = solve(
            fine, np.vstack([grid.xyz, truth.xyz]), sensors, c["conductivities_S_m"], root / "fine"
        )
        reference = fine_g[:, :144]
        gt = fine_g[:, 144:]
        scale = float(np.linalg.norm(reference, 2))
        clean = np.column_stack(
            [gt[:, i * 3 : i * 3 + 3] @ moment for i, moment in enumerate(moments)]
        )
        rng = np.random.default_rng(c["seed"] + 10000 + head)
        ids, measured = [], []
        for source, std in itertools.product(range(12), c["noise_std_V"]):
            for draw in range(1 if std == 0 else 8):
                ids.append(dict(source=source, noise_std_V=std, draw=draw))
                measured.append(
                    clean[:, source] + std * average_projector(32) @ rng.normal(size=32)
                )
        y = np.column_stack(measured)
        pairing = digest(
            dict(
                truth=truth.xyz.tolist(),
                moments=moments.tolist(),
                identities=ids,
                measured=y.tolist(),
            )
        )
        for name, data in [
            ("truth_m", truth.xyz),
            ("moments_Am", moments),
            ("sensors_m", sensors),
            ("fine_candidate_V_per_Am", reference),
            ("truth_V_per_Am", gt),
            ("measurements_V", y),
        ]:
            pd.DataFrame(data).to_csv(root / (name + ".csv"), index=False, float_format="%.17g")
        (root / "identities.json").write_text(
            json.dumps(
                dict(head=p, pairing=pairing, measurements=ids, projection_mm=projection.tolist()),
                indent=2,
            )
        )
        models.append(dict(head=head, case="truth", level=3, status="computed", geometry=fq, **fd))
        leads = {}
        for case in cases() + [dict(id="sphere-control", level=-1, family="sphere")]:
            row: dict[str, Any] = dict(
                head=head,
                case=case["id"],
                level=case["level"],
                family=p["family"],
                pairing=pairing,
                status="failed",
            )
            ops = None
            try:
                if time.perf_counter() - started > c["total_budget_s"]:
                    raise TimeoutError("Frozen whole-study budget exhausted")
                if case["id"] == "sphere-control":
                    fw = physical_forward(grid, electrode_positions(), transform())
                    true_sphere = physical_forward(truth, electrode_positions(), transform())
                    sphere_clean = np.column_stack(
                        [
                            true_sphere.matrix[:, i * 3 : i * 3 + 3] @ m
                            for i, m in enumerate(moments)
                        ]
                    )
                    case_y = (
                        y
                        - clean[:, [i["source"] for i in ids]]
                        + sphere_clean[:, [i["source"] for i in ids]]
                    )
                    g = fw.matrix
                    row.update(
                        reference_scope="new sphere control; separate clean voltages, paired noise",
                        diagnostics=fw.diagnostics,
                    )
                else:
                    b = meshes(p, case["level"], case)
                    qc = validate_meshes(b)
                    check_sources(b[0], grid)
                    t = pose(case)
                    targets = t.apply(Points(sensor_targets(p, case), Frame.HEAD)).xyz
                    ss, pe = radial_projection(b[-1], targets)
                    baseline_ss, _ = radial_projection(b[-1], sensor_targets(p))
                    extra = float(
                        np.max(
                            np.linalg.norm(ss - targets, axis=1)
                            - np.linalg.norm(baseline_ss - sensor_targets(p), axis=1)
                        )
                        * 1000
                    )
                    if extra > c["sensor_extra_projection_limit_mm"]:
                        raise ValueError("Invalid geometry: extra sensor projection limit")
                    sigmas = list(c["conductivities_S_m"])
                    sigmas[2] = case["skull"]
                    g, d = solve(b, grid.xyz, ss, sigmas, root / case["id"])
                    leads[case["id"]] = g
                    electrodes_head = t.inverse().apply(Points(ss, Frame.MRI)).xyz
                    fw = native_forward(g, grid, electrodes_head, t)
                    case_y = y
                    row.update(
                        geometry=qc,
                        diagnostics=d,
                        projection_max_mm=float(np.max(pe, axis=None)),
                        extra_projection_mm=extra,
                        conductivities_S_m=sigmas,
                        forward_relative=float(
                            np.linalg.norm(g - reference) / np.linalg.norm(reference)
                        ),
                        voltage_rms_difference_uV=float(
                            np.linalg.norm((g - reference) * 1e-8) / np.sqrt(g.size) * 1e6
                        ),
                    )
                ops, kd = kernels(fw, scale)
                row.update(status="computed", inverse_diagnostics=kd)
                if case["id"] == "mesh-2":
                    display = meshes(p, 1)
                    display_sensors, _ = radial_projection(display[-1], sensor_targets(p))
                    estimates = {
                        name: np.linalg.norm((k @ case_y[:, 0]).reshape(-1, 3), axis=1).tolist()
                        for name, k in ops.items()
                    }
                    examples.append(
                        dict(
                            head=head,
                            family=p["family"],
                            display_level=1,
                            analysis_level=2,
                            surfaces=[
                                dict(
                                    xyz_mm=(m.vertices.xyz * 1000).tolist(), faces=m.faces.tolist()
                                )
                                for m in display
                            ],
                            sensors_mm=(display_sensors * 1000).tolist(),
                            truth_mm=(truth.xyz[0] * 1000).tolist(),
                            grid_mm=(grid.xyz * 1000).tolist(),
                            estimates=estimates,
                        )
                    )
            except (ValueError, ArithmeticError, MemoryError, TimeoutError) as exc:
                message = str(exc)
                kind = (
                    "resource_exhaustion"
                    if isinstance(exc, (MemoryError, TimeoutError))
                    else "invalid_geometry"
                    if "geometry" in message.lower() or "dipole" in message.lower()
                    else "forward_solver_nonconvergence"
                    if "Forward-solver" in message
                    else "inverse_solver_failure"
                )
                row.update(failure_class=kind, reason=message)
            for method in c["methods"]:
                estimates_array = ops[method] @ case_y if ops is not None else None
                for column, ident in enumerate(ids):
                    r = dict(
                        head=head,
                        case=case["id"],
                        method=method,
                        **ident,
                        status=row["status"],
                        localization_mm=None,
                        dispersion_mm=None,
                        peak_amplitude_bias_ratio=None,
                    )
                    if estimates_array is not None:
                        r.update(
                            source_metrics(
                                estimates_array[:, column], grid, truth, ident["source"], method
                            )
                        )
                    else:
                        r.update(failure_class=row["failure_class"], reason=row["reason"])
                    records.append(r)
            models.append(row)
            print(head, case["id"], row["status"], flush=True)
        errors = [
            next(
                (
                    m.get("forward_relative")
                    for m in models
                    if m["head"] == head and m["case"] == f"mesh-{level}"
                ),
                None,
            )
            for level in range(3)
        ]
        cv = (
            convergence([float(e) for e in errors if e is not None])
            if all(e is not None for e in errors)
            else dict(status="INCOMPLETE", errors=errors)
        )
        # The independent three-layer control deliberately merges brain and CSF.
        b3 = meshes(p, 2)[1:]
        ss, _ = radial_projection(b3[-1], sensor_targets(p))
        control = dict(
            head=head,
            scope="matched THREE layers only; brain/CSF merged",
            full_four_layer="NOT_ESTABLISHED",
        )
        try:
            om, od = solve(b3, grid.xyz[:4], ss, [0.33, 0.004, 0.33], root / "control-openmeeg")
            mn, md = solve(
                b3, grid.xyz[:4], ss, [0.33, 0.004, 0.33], root / "control-mne", solver="mne"
            )
            err = float(np.linalg.norm(om - mn) / np.linalg.norm(mn))
            control.update(
                relative_error=err,
                status="AGREEMENT" if err <= c["independent_three_layer_rtol"] else "DISAGREEMENT",
                openmeeg=od,
                mne=md,
            )
        except (ValueError, TimeoutError) as exc:
            control.update(status="FAILED", reason=str(exc))
        (root / "convergence.json").write_text(json.dumps(cv, indent=2))
        (root / "independent-control.json").write_text(json.dumps(control, indent=2))
    rows = pd.DataFrame(records)
    rows.to_csv(output / "reconstructions.csv", index=False, float_format="%.17g")
    summary = aggregate(rows)
    summary.to_csv(output / "aggregate.csv", index=False, float_format="%.17g")
    rows.groupby(["head", "case", "method", "noise_std_V"])[
        ["localization_mm", "dispersion_mm"]
    ].mean().to_csv(output / "per-head.csv")
    rows.groupby(["head", "source", "case", "method", "noise_std_V"])[
        ["localization_mm", "dispersion_mm"]
    ].mean().to_csv(output / "per-source.csv")
    (output / "models.json").write_text(json.dumps(models, indent=2, allow_nan=False))
    (output / "explorer.json").write_text(
        json.dumps(
            dict(
                schema="soma.nonspherical.explorer/1",
                design_sha256=DESIGN_SHA,
                heads=examples,
                convergence=[
                    dict(head=h, **json.loads((output / f"head-{h}/convergence.json").read_text()))
                    for h in range(6)
                ],
                failures=[m for m in models if m["status"] != "computed"],
            ),
            indent=2,
        )
    )
    receipt = dict(
        design_sha256=DESIGN_SHA,
        protocol_fingerprint=sealed.protocol.fingerprint,
        environment=environment_snapshot(),
        synthetic_only=True,
        human_subjects=0,
        implementation_sha256={
            "experiment": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        },
        runtime_seconds=time.perf_counter() - started,
        heads=6,
        sources=72,
        unique_vectors=1224,
        reconstruction_rows=len(rows),
        computed=int((rows.status == "computed").sum()),
        failed=int((rows.status != "computed").sum()),
        C_four_layer="NOT_ESTABLISHED",
        FEM="NOT_PERFORMED",
        D="PHANTOM_NOT_AVAILABLE",
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2))
    domain = {
        "computation": "frozen nonspherical synthetic BEM uncertainty",
        "inputs": {"design": DESIGN_SHA},
        "environment": receipt["environment"],
        "assumptions": ["isotropic piecewise constant conductivities; ideal dipoles"],
        "validation": {"scope": "conditional synthetic numerical comparison"},
        "limitations": ["no human accuracy; four-layer independence not established"],
    }
    result = create_result(
        "experiment.manifest",
        domain,
        values=receipt,
        provenance={"protocol": sealed.protocol.fingerprint},
        method={"id": "soma.nonspherical", "version": "1"},
        parameters=c,
        units={"distance": "mm", "current": "A*m"},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(result, {}, output / "result")
    manifest = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.rglob("*")
        if p.is_file() and p.suffix in {".csv", ".json"} and not p.name.endswith(".local.json")
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return receipt


def read_nonspherical(path: Path) -> dict[str, Any]:
    """Read the native aggregate envelope; never accept human export relabeling."""
    from soma.results.io import load_result
    from soma.source.nonspherical import protocol

    envelope, arrays = load_result(path)
    if arrays or envelope["method"] != {"id": "soma.nonspherical", "version": "1"}:
        raise ValueError("Expected nonspherical aggregate result")
    value = dict(envelope["payload"]["values"])
    if value.get("synthetic_only") is not True or value.get("human_subjects") != 0:
        raise ValueError("Only synthetic nonparticipant results accepted")
    if (
        value.get("design_sha256") != DESIGN_SHA
        or value.get("protocol_fingerprint") != protocol().protocol.fingerprint
    ):
        raise ValueError("Changed result design/protocol")
    return value
