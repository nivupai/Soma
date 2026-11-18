"""Frozen physical equivalence, reference and factor-isolation BEM study."""

import hashlib
import itertools
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.eeg_benchmark.evaluation import environment_snapshot
from soma.experiments.nonspherical import hierarchical, known_truth
from soma.experiments.source_uncertainty import source_metrics
from soma.geometry import Frame, Points
from soma.protocol.model import SealedProtocol, write_seal
from soma.results.contracts import create_result
from soma.results.io import save_result
from soma.source.bem_discrepancy import (
    DESIGN_SHA,
    design,
    field_metrics,
    geometry,
    homogeneous_series,
    match,
    protocol,
    sensors,
    solve,
)
from soma.source.noise import average_projector
from soma.source.nonspherical import (
    head_parameters,
    native_forward,
    pose,
    radial_projection,
    sensor_targets,
    source_grid,
)
from soma.source.uncertainty import kernels, physical_forward, transform


def run_diagnostics(sealed: SealedProtocol, output: Path) -> dict[str, Any]:
    if sealed.protocol.fingerprint != protocol().protocol.fingerprint:
        raise ValueError("Unapproved diagnostic protocol/threshold change")
    c = design()
    output.mkdir(parents=True, exist_ok=False)
    write_seal(sealed, output / "protocol.json")
    started = time.perf_counter()
    models: list[dict[str, Any]] = []
    comparisons = []
    source_rows = []
    arrays: dict[tuple[str, str], Any] = {}
    inverse_rows = []

    def compute(
        label: str,
        head: int | None,
        levels: list[int],
        points: Any,
        sigmas: list[float],
        *,
        electrodes: Any = None,
        solvers: tuple[str, ...] = ("openmeeg", "mne"),
        ip: bool = True,
        integrator: Any = None,
        boundaries: Any = None,
    ) -> dict[str, Any]:
        bs = geometry(head, levels) if boundaries is None else boundaries
        ss = sensors(head) if electrodes is None else electrodes
        pair = {}
        for solver in solvers:
            row: dict[str, Any] = dict(
                label=label,
                head=head,
                levels=levels,
                solver=solver,
                status="FAILED",
                sigmas_S_m=sigmas,
            )
            try:
                if time.perf_counter() - started > c["budget"]["total_seconds"]:
                    raise TimeoutError("Frozen whole-study budget exceeded")
                g, d = solve(
                    bs,
                    points,
                    ss,
                    sigmas,
                    output / label / solver,
                    solver=solver,
                    ip=ip,
                    integrator=integrator,
                )
                row.update(status="computed", diagnostics=d)
                pair[solver] = g
                arrays[(label, solver)] = g
                pd.DataFrame(g).to_csv(
                    output / label / (solver + "-V_per_Am.csv"), index=False, float_format="%.17g"
                )
            except (ValueError, ArithmeticError, MemoryError, TimeoutError) as exc:
                row.update(
                    reason=str(exc),
                    failure_class="resource_exhaustion"
                    if isinstance(exc, (MemoryError, TimeoutError))
                    else "solver_or_geometry_failure",
                )
            models.append(row)
            print(label, solver, row["status"], flush=True)
        if len(pair) == 2:
            aa = next(
                r["diagnostics"]["contracts"]
                for r in models
                if r["label"] == label and r["solver"] == "openmeeg" and r["status"] == "computed"
            )
            bb = models[-1]["diagnostics"]["contracts"]
            match(aa, bb)
            fm = field_metrics(pair["openmeeg"], pair["mne"])
            zero = np.eye(32) - np.ones((32, 1)) @ np.eye(32)[0:1]
            raw = {
                s: np.load(output / label / s / "result/raw.npy", allow_pickle=False)
                for s in solvers
            }
            fixed = field_metrics(zero @ raw["openmeeg"], zero @ raw["mne"])
            comparisons.append(
                dict(
                    label=label,
                    head=head,
                    levels=levels,
                    **fm,
                    fixed_reference_relative=fixed["relative"],
                    geometry_match=True,
                    sensor_reference_match=True,
                    gate="INDEPENDENT_THREE_LAYER_AGREEMENT_PASS"
                    if fm["relative"] <= 0.10
                    else "AGREEMENT_NOT_ESTABLISHED",
                )
            )
            for source in range(len(points)):
                for orientation in range(3):
                    j = source * 3 + orientation
                    source_rows.append(
                        dict(
                            label=label,
                            head=head,
                            source=source,
                            orientation=["x", "y", "z"][orientation],
                            radius_mm=float(np.linalg.norm(points[source]) * 1000),
                            relative=fm["column_relative"][j],
                            correlation=fm["column_correlation"][j],
                        )
                    )
        return pair

    # A: physical homogeneous sphere using three artificial equal-conductivity interfaces.
    analytical_points = np.array(
        [
            [0, 0, 0],
            [0.035, 0, 0],
            [0, 0.035, 0],
            [0, 0, 0.035],
            [0.055, 0, 0],
            [-0.055 / np.sqrt(14), -0.11 / np.sqrt(14), -0.165 / np.sqrt(14)],
        ]
    )
    ss = sensors(None)
    exact = average_projector(32) @ homogeneous_series(analytical_points, ss)
    short = average_projector(32) @ homogeneous_series(analytical_points, ss, terms=64)
    tail = float(np.linalg.norm(short - exact) / np.linalg.norm(exact))
    if tail > 1e-12:
        raise ArithmeticError("Analytical series truncation check failed")
    references = []
    for level in c["levels"]:
        pair = compute(f"A-{level}", None, [level] * 3, analytical_points, [0.33] * 3)
        for solver, g in pair.items():
            references.append(
                dict(
                    reference="A-homogeneous", level=level, solver=solver, **field_metrics(g, exact)
                )
            )
        bs = geometry(None, [level] * 3)[-1:]
        pair = compute(
            f"A-one-{level}",
            None,
            [level] * 3,
            analytical_points,
            [0.33],
            solvers=("openmeeg",),
            boundaries=bs,
        )
        if pair:
            references.append(
                dict(
                    reference="A-one-interface",
                    level=level,
                    solver="openmeeg",
                    **field_metrics(pair["openmeeg"], exact),
                )
            )
    grid = source_grid()
    # B uses an explicitly approximate MNE three-shell semi-analytical reference.
    semi = physical_forward(
        Points(analytical_points[1:], Frame.MRI),
        Points(ss, Frame.HEAD),
        transform(),
        radii_mm=[81.0, 82.8, 87.3, 90.0],
        sigmas=[0.33, 0.33, 0.004, 0.33],
    ).matrix
    # physical_forward enforces original four-shell dimensions; equivalent merged layers
    # are represented using the original inner radius, with equal first two conductivities.
    for level in c["levels"]:
        pair = compute(f"B-{level}", None, [level] * 3, analytical_points[1:], [0.33, 0.004, 0.33])
        for solver, g in pair.items():
            references.append(
                dict(
                    reference="B-layered-semi-analytic",
                    level=level,
                    solver=solver,
                    **field_metrics(g, semi),
                )
            )
    for head in range(6):
        truth, moments = known_truth(head)
        points = np.vstack([grid.xyz, truth.xyz])
        ss = sensors(head)
        pd.DataFrame(points, columns=["x_m", "y_m", "z_m"]).to_csv(
            output / f"head-{head}-sources.csv", index=False, float_format="%.17g"
        )
        pd.DataFrame(ss, columns=["x_m", "y_m", "z_m"]).to_csv(
            output / f"head-{head}-sensors.csv", index=False, float_format="%.17g"
        )
        for level in c["levels"]:
            compute(f"C-{head}-{level}", head, [level] * 3, points, [0.33, 0.004, 0.33])
        if head in [0, 5]:
            compute(
                f"F-{head}-noIP",
                head,
                [2] * 3,
                points,
                [0.33, 0.004, 0.33],
                solvers=("mne",),
                ip=False,
            )
            compute(
                f"F-{head}-integration",
                head,
                [2] * 3,
                points,
                [0.33, 0.004, 0.33],
                solvers=("openmeeg",),
                integrator=dict(order=5, adaptive_levels=1, tolerance=0.001),
            )
            for interface in range(3):
                levels = [2] * 3
                levels[interface] = 3
                compute(
                    f"F-{head}-interface-{interface}", head, levels, points, [0.33, 0.004, 0.33]
                )
            original, _ = radial_projection(
                geometry(head, [2] * 3)[-1], sensor_targets(head_parameters(head))
            )
            compute(
                f"F-{head}-sensor", head, [2] * 3, points, [0.33, 0.004, 0.33], electrodes=original
            )
            compute(f"F-{head}-conductivity", head, [2] * 3, points, [0.33, 0.008, 0.33])
        fine = arrays.get((f"C-{head}-3", "openmeeg"))
        if fine is None:
            for level, solver, method, source, std, draw in itertools.product(
                [1, 2],
                ["openmeeg", "mne"],
                c["inverse"]["methods"],
                range(12),
                [0.0, 5e-8, 1.5e-7],
                range(8),
            ):
                if std == 0 and draw:
                    continue
                inverse_rows.append(
                    dict(
                        head=head,
                        level=level,
                        solver=solver,
                        method=method,
                        source=source,
                        noise_std_V=std,
                        draw=draw,
                        status="FAILED",
                        reason="finest truth unavailable",
                    )
                )
            continue
        scale = float(np.linalg.norm(fine[:, :144], 2))
        gt = fine[:, 144:]
        clean = np.column_stack(
            [gt[:, i * 3 : i * 3 + 3] @ moment for i, moment in enumerate(moments)]
        )
        rng = np.random.default_rng(27042 + 10000 + head)
        ids: list[dict[str, Any]] = []
        ys = []
        for source, std in itertools.product(range(12), [0.0, 5e-8, 1.5e-7]):
            for draw in range(1 if std == 0 else 8):
                ids.append(dict(source=source, noise_std_V=std, draw=draw))
                ys.append(clean[:, source] + std * average_projector(32) @ rng.normal(size=32))
        y = np.column_stack(ys)
        pd.DataFrame(y).to_csv(
            output / f"head-{head}-measurements_V.csv", index=False, float_format="%.17g"
        )
        for level, solver in itertools.product([1, 2], ["openmeeg", "mne"]):
            g = arrays.get((f"C-{head}-{level}", solver))
            ops = None
            if g is not None:
                try:
                    ops, _ = kernels(native_forward(g[:, :144], grid, ss, pose({})), scale)
                except (ValueError, ArithmeticError) as exc:
                    print("inverse failure", str(exc), flush=True)
            for method in c["inverse"]["methods"]:
                estimates = ops[method] @ y if ops is not None else None
                for col, ident in enumerate(ids):
                    row = dict(
                        head=head,
                        level=level,
                        solver=solver,
                        method=method,
                        **ident,
                        status="computed" if estimates is not None else "FAILED",
                    )
                    if estimates is not None:
                        row.update(
                            source_metrics(estimates[:, col], grid, truth, ident["source"], method)
                        )
                    inverse_rows.append(row)
    # Paired one-factor effects, never optimally rescaled acceptance.
    factors = []
    refinement = []
    for head in range(6):
        for solver in ["openmeeg", "mne"]:
            for lo, hi in [(1, 2), (2, 3)]:
                a = arrays.get((f"C-{head}-{lo}", solver))
                b = arrays.get((f"C-{head}-{hi}", solver))
                if a is not None and b is not None:
                    refinement.append(
                        dict(head=head, solver=solver, coarse=lo, fine=hi, **field_metrics(a, b))
                    )
        for label, solver in list(arrays):
            if not label.startswith(f"F-{head}-"):
                continue
            base = arrays.get((f"C-{head}-2", solver))
            other = arrays.get((f"C-{head}-2", "mne" if solver == "openmeeg" else "openmeeg"))
            if base is not None and other is not None:
                factors.append(
                    dict(
                        head=head,
                        label=label,
                        solver=solver,
                        change_from_baseline=field_metrics(arrays[(label, solver)], base)[
                            "relative"
                        ],
                        difference_from_other_baseline=field_metrics(
                            arrays[(label, solver)], other
                        )["relative"],
                    )
                )
    pd.DataFrame(source_rows).to_csv(output / "source-orientation.csv", index=False)
    pd.DataFrame(inverse_rows).to_csv(output / "inverse.csv", index=False, float_format="%.17g")
    inverse = pd.DataFrame(inverse_rows)
    summaries = []
    for level, solver, method, noise in itertools.product(
        [1, 2], ["openmeeg", "mne"], c["inverse"]["methods"], [0.0, 5e-8, 1.5e-7]
    ):
        g = inverse[
            (inverse.level == level)
            & (inverse.solver == solver)
            & (inverse.method == method)
            & (inverse.noise_std_V == noise)
        ]
        expected = 72 * (1 if noise == 0 else 8)
        row = dict(
            level=level,
            solver=solver,
            method=method,
            noise_std_V=noise,
            status="complete"
            if len(g) == expected and (g.status == "computed").all()
            else "INCOMPLETE",
            planned=expected,
            computed=int((g.status == "computed").sum()),
        )
        if row["status"] == "complete":
            for metric in ["localization_mm", "dispersion_mm", "peak_amplitude_bias_ratio"]:
                if method == "dSPM" and metric == "peak_amplitude_bias_ratio":
                    continue
                v = (
                    g.groupby(["head", "source"])[metric]
                    .mean()
                    .reindex(pd.MultiIndex.from_product([range(6), range(12)]))
                    .to_numpy()
                    .reshape(6, 12)
                )
                row[metric], row[metric + "_low"], row[metric + "_high"] = hierarchical(v)
        summaries.append(row)
    pd.DataFrame(summaries).to_csv(output / "inverse-aggregate.csv", index=False)
    for name, value in [
        ("models", models),
        ("comparisons", comparisons),
        ("references", references),
        ("factors", factors),
        ("refinement", refinement),
    ]:
        (output / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    receipt = dict(
        synthetic_only=True,
        human_subjects=0,
        heads=6,
        design_sha256=DESIGN_SHA,
        protocol_fingerprint=sealed.protocol.fingerprint,
        source_count_per_head=12,
        source_orientation_components=3,
        models_computed=sum(r["status"] == "computed" for r in models),
        models_failed=sum(r["status"] != "computed" for r in models),
        analytical_series_tail_relative=tail,
        inverse_rows=len(inverse),
        inverse_computed=int((inverse.status == "computed").sum()),
        runtime_seconds=time.perf_counter() - started,
        environment=environment_snapshot(),
        implementation_sha256={
            name: hashlib.sha256(
                Path(__file__).parents[1].joinpath("source", name).read_bytes()
            ).hexdigest()
            for name in ["bem_worker.py", "bem_discrepancy.py"]
        },
        experiment_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        four_layer="NOT_ESTABLISHED",
        FEM="NOT_PERFORMED",
        phantom="PHANTOM_NOT_AVAILABLE",
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    domain = dict(
        computation="paired synthetic independent BEM diagnostics",
        inputs={"design": DESIGN_SHA},
        environment=receipt["environment"],
        assumptions=["quasistatic isotropic conductors; ideal dipoles"],
        validation={"scope": "conditional numerical investigation"},
        limitations=[
            "No human anatomical accuracy; no independent four-layer/FEM/phantom validation"
        ],
    )
    envelope = create_result(
        "experiment.manifest",
        domain,
        values=receipt,
        provenance={"protocol": sealed.protocol.fingerprint},
        method={"id": "soma.bem-discrepancy", "version": "1"},
        parameters=c,
        units={"distance": "mm", "current": "A*m"},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(envelope, {}, output / "result")
    return receipt


def read_diagnostics(path: Path) -> dict[str, Any]:
    from soma.results.io import load_result

    e, a = load_result(path)
    if a or e["method"] != {"id": "soma.bem-discrepancy", "version": "1"}:
        raise ValueError("Expected native diagnostic aggregate")
    v = dict(e["payload"]["values"])
    if (
        v.get("synthetic_only") is not True
        or v.get("human_subjects") != 0
        or v.get("design_sha256") != DESIGN_SHA
        or v.get("protocol_fingerprint") != protocol().protocol.fingerprint
    ):
        raise ValueError("Corrupt or unsupported diagnostic scientific identity")
    if (
        v.get("four_layer", "NOT_ESTABLISHED") != "NOT_ESTABLISHED"
        or v.get("FEM", "NOT_PERFORMED") != "NOT_PERFORMED"
        or v.get("phantom", "PHANTOM_NOT_AVAILABLE") != "PHANTOM_NOT_AVAILABLE"
    ):
        raise ValueError("Unsupported independent-reference evidence claim")
    return v
