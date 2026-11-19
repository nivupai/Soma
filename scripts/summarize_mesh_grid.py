"""Independent numerical audits and synthetic M30 exports; no participant inputs."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.eeg_benchmark.evaluation import environment_snapshot
from soma.experiments.mesh_grid import design, protocol
from soma.experiments.nonspherical import hierarchical
from soma.results.contracts import create_result
from soma.results.io import save_result
from soma.source.grid_diagnostics import resolution_difference
from soma.source.mesh_replication import candidate_grid
from soma.source.nonspherical import source_grid


def run(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    fig = out / "figures"
    fig.mkdir()
    c = design()
    models = json.loads((root / "models.json").read_text())
    comparisons = json.loads((root / "comparisons.json").read_text())
    receipt = json.loads((root / "receipt.json").read_text())
    geometry = json.loads((root / "geometry.json").read_text())
    json.loads((root / "resolutions.json").read_text())
    for p in root.iterdir():
        if p.is_file() and p.suffix in [".json", ".csv"]:
            shutil.copyfile(p, out / p.name)
    # All primary evaluation cells are enumerated, even if an upstream truth failed.
    inverse = pd.read_csv(root / "inverse.csv")
    primary = inverse[inverse.status != "geometry_truth_sensitivity"].copy()
    keys = ["head", "spacing_mm", "solver", "method", "source", "noise_std_V", "draw"]
    if primary.duplicated(keys).any():
        raise ValueError("Duplicate independent evaluation keys")
    expected = {
        (h, s, solver, m, src, std, d)
        for h in range(6)
        for s in [0, 30, 20, 15]
        for solver in ["fem", "openmeeg"]
        for m in ["Tikhonov", "MNE", "dSPM"]
        for src in range(12)
        for std in [0.0, 5e-8, 1.5e-7]
        for d in range(1 if std == 0 else 8)
    }
    actual = set(primary[keys].itertuples(index=False, name=None))
    missing = expected - actual
    if actual - expected:
        raise ValueError("Undeclared inverse evaluation cells")
    if missing:
        failure_rows = [
            dict(
                zip(keys, row, strict=True),
                status="FAILED",
                reason="planned evaluation absent after upstream failure",
            )
            for row in sorted(missing)
        ]
        inverse = pd.concat([inverse, pd.DataFrame(failure_rows)], ignore_index=True)
        inverse.to_csv(out / "inverse.csv", index=False)
    primary = inverse[inverse.status == "computed"].copy()
    assert (primary.excess_localization_mm >= -1e-9).all()
    # Independently check nearest-bound interpretation and actual excess.
    assert np.allclose(
        primary.localization_mm - primary.nearest_grid_mm,
        primary.excess_localization_mm,
        atol=1e-10,
    )
    aggregate = []
    paired = []
    for (spacing, method, std), group in primary.groupby(["spacing_mm", "method", "noise_std_V"]):
        for solver, g in group.groupby("solver"):
            source_mean = g.groupby(["head", "source"])[
                [
                    "localization_mm",
                    "nearest_grid_mm",
                    "excess_localization_mm",
                    "dispersion_mm",
                    "peak_amplitude_bias_ratio",
                ]
            ].mean()
            row = dict(
                spacing_mm=int(spacing),
                candidates=int(g.candidates.iloc[0]),
                method=method,
                noise_std_V=std,
                solver=solver,
                independent_heads=g["head"].nunique(),
                independent_sources=len(source_mean),
            )
            for metric in [
                "localization_mm",
                "nearest_grid_mm",
                "excess_localization_mm",
                "dispersion_mm",
            ]:
                matrix = (
                    source_mean[metric]
                    .unstack("source")
                    .reindex(index=range(6), columns=range(12))
                    .to_numpy()
                )
                if np.isfinite(matrix).all():
                    mean, lo, hi = hierarchical(matrix)
                    row.update({metric: mean, metric + "_lower": lo, metric + "_upper": hi})
            row["physical_peak_bias_ratio"] = (
                None if method == "dSPM" else float(source_mean.peak_amplitude_bias_ratio.mean())
            )
            aggregate.append(row)
        a = group.groupby(["head", "source", "solver"]).localization_mm.mean().unstack("solver")
        if {"fem", "openmeeg"}.issubset(a.columns):
            matrix = (
                (a.openmeeg - a.fem)
                .unstack("source")
                .reindex(index=range(6), columns=range(12))
                .to_numpy()
            )
            if np.isfinite(matrix).all():
                mean, lo, hi = hierarchical(matrix)
                paired.append(
                    dict(
                        spacing_mm=int(spacing),
                        method=method,
                        noise_std_V=std,
                        OM_minus_FEM_mm=mean,
                        lower=lo,
                        upper=hi,
                    )
                )
    pd.DataFrame(aggregate).to_csv(out / "grid-summary.csv", index=False)
    pd.DataFrame(paired).to_csv(out / "paired-model-effects.csv", index=False)
    peak_keys = ["head", "spacing_mm", "method", "source", "noise_std_V", "draw"]
    peak_table = primary.pivot(index=peak_keys, columns="solver", values="peak").dropna()
    displacement = []
    for index, row in peak_table.iterrows():
        head, spacing, method, source, std, draw = index
        grid = (
            source_grid().xyz[np.r_[0:6, 24:30]]
            if spacing == 0
            else candidate_grid(int(spacing)).xyz
        )
        left, right = int(row["fem"]), int(row["openmeeg"])
        if not 0 <= left < len(grid) or not 0 <= right < len(grid):
            raise ValueError("Invalid estimated peak index")
        displacement.append(
            dict(
                zip(peak_keys, index, strict=True),
                paired_peak_displacement_mm=float(np.linalg.norm(grid[left] - grid[right]) * 1000),
            )
        )
    pd.DataFrame(displacement).to_csv(out / "paired-peak-displacement.csv", index=False)
    refinement = []
    for head in range(6):
        for alt, levels in [(0, [(1, 2), (2, 3)]), (1, [(2, 3)])]:
            for a, b in levels:
                p = root / f"F-{head}-{a}-{alt}-V_per_Am.csv"
                q = root / f"F-{head}-{b}-{alt}-V_per_Am.csv"
                if p.exists() and q.exists():
                    x = np.loadtxt(p, delimiter=",")
                    y = np.loadtxt(q, delimiter=",")
                    refinement.append(
                        dict(
                            head=head,
                            alternative=bool(alt),
                            low=a,
                            high=b,
                            relative=float(np.linalg.norm(x - y) / np.linalg.norm(y)),
                        )
                    )
    pd.DataFrame(refinement).to_csv(out / "mesh-refinement.csv", index=False)
    matrix_comparisons = []
    diagonals = []
    for head, spacing, method in [
        (h, s, m) for h in range(6) for s in [0, 30, 20, 15] for m in ["Tikhonov", "MNE", "dSPM"]
    ]:
        a = root / f"grid-{head}-{spacing}-openmeeg-{method}-resolution.npy"
        b = root / f"grid-{head}-{spacing}-fem-{method}-resolution.npy"
        if not a.exists() or not b.exists():
            continue
        grid = source_grid().xyz[np.r_[0:6, 24:30]] if spacing == 0 else candidate_grid(spacing).xyz
        unit = "1/(A*m)" if method == "dSPM" else "1"
        x = np.load(a)
        y = np.load(b)
        difference = resolution_difference(x, y, grid, grid, unit, unit)
        for solver, matrix in [("openmeeg", x), ("fem", y)]:
            diagonals.append(
                dict(
                    head=head,
                    spacing_mm=spacing,
                    method=method,
                    solver=solver,
                    units=unit,
                    source_major_XYZ_diagonal=np.diag(matrix).tolist(),
                )
            )
        matrix_comparisons.append(
            dict(
                head=head,
                spacing_mm=spacing,
                method=method,
                relative_resolution_difference=difference,
                units=unit,
                shape=list(x.shape),
            )
        )
    (out / "paired-resolution.json").write_text(json.dumps(matrix_comparisons, indent=2) + "\n")
    (out / "resolution-diagonals.json").write_text(json.dumps(diagonals, indent=2) + "\n")
    decomposition = []
    for head in range(6):
        a = root / f"F-{head}-3-1-V_per_Am.csv"
        b = root / f"F-{head}-3-1-BEM-alt-V_per_Am.csv"
        d = Path("experiments/milestone29") / f"C-{head}-3-openmeeg-V_per_Am.csv"
        if a.exists() and b.exists():
            gm = np.loadtxt(a, delimiter=",")
            alt = np.loadtxt(b, delimiter=",")
            std = np.loadtxt(d, delimiter=",")
            numerical = gm - alt
            geometric = alt - std
            combined = gm - std
            scale = np.linalg.norm(std)
            assert np.allclose(numerical + geometric, combined, rtol=1e-12, atol=1e-12)
            decomposition.append(
                dict(
                    head=head,
                    matched_alternative_residual_norm=float(np.linalg.norm(numerical) / scale),
                    BEM_geometry_delta_norm=float(np.linalg.norm(geometric) / scale),
                    combined_norm=float(np.linalg.norm(combined) / scale),
                    vector_cosine=float(
                        np.sum(numerical * geometric)
                        / (np.linalg.norm(numerical) * np.linalg.norm(geometric))
                    ),
                    scope="common std-BEM denominator; vector components may cancel",
                )
            )
    pd.DataFrame(decomposition).to_csv(out / "error-components.csv", index=False)
    cost = []
    for r in models:
        if r["status"] == "computed":
            d = r.get("diagnostics", {})
            cost.append(
                dict(
                    label=r["label"],
                    kind=r["kind"],
                    head=r["head"],
                    level=r.get("level"),
                    alternative=r.get("alternative", False),
                    solver=r.get("solver", "fem"),
                    spacing_mm=r.get("spacing_mm"),
                    nodes=d.get("nodes"),
                    elements=d.get("elements"),
                    min_mean_ratio=d.get("min_mean_ratio"),
                    native_minSICN=d.get("native_minSICN"),
                    mesh_seconds=d.get("mesh_seconds"),
                    solve_seconds=d.get("solve_seconds"),
                    peak_MiB=d.get("peak_solver_MiB"),
                    residual=d.get("residual"),
                    current_imbalance=d.get("current_imbalance"),
                    boundary_coordinate_max_m=d.get("boundary_coordinate_max_m"),
                )
            )
    pd.DataFrame(cost).to_csv(out / "cost-quality.csv", index=False)
    for row in cost:
        if row["kind"] == "grid" and row["solver"] == "openmeeg":
            parts = [
                json.loads(p.read_text())
                for p in root.glob(row["label"] + "-batch*/result/diagnostics.json")
            ]
            if parts:
                row["solve_seconds"] = sum(p["runtime_seconds"] for p in parts)
                row["peak_MiB"] = max(p["process_peak_rss_mib"] for p in parts)
    pd.DataFrame(cost).to_csv(out / "cost-quality.csv", index=False)
    kernel_cost = []
    for head, spacing, solver in [
        (h, s, m) for h in [0, 5] for s in [0, 30, 20, 15] for m in ["fem", "openmeeg"]
    ]:
        target = root / f"kernel-cost-{head}-{spacing}-{solver}.json"
        if not target.exists():
            subprocess.run(
                [
                    sys.executable,
                    "scripts/mesh_grid_cost.py",
                    str(root),
                    str(head),
                    str(spacing),
                    solver,
                    str(target),
                ],
                check=True,
                env=dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"),
                stdout=subprocess.DEVNULL,
            )
        kernel_cost.append(json.loads(target.read_text()))
    pd.DataFrame(
        [{k: v for k, v in row.items() if k != "resolution_norms"} for row in kernel_cost]
    ).to_csv(out / "inverse-cost.csv", index=False)
    # Direct-sum field norms independently audit the main adapter's metrics.
    for r in comparisons:
        label = r["label"]
        condition = r["condition"]
        if condition == "B matched":
            a = np.loadtxt(root / (label + "-V_per_Am.csv"), delimiter=",")
            b = np.loadtxt(
                Path("experiments/milestone29")
                / f"C-{r['head']}-{r['level']}-openmeeg-V_per_Am.csv",
                delimiter=",",
            )
            rel = np.sqrt(
                sum(float(x * x) for x in (a - b).ravel()) / sum(float(x * x) for x in b.ravel())
            )
            assert np.isclose(rel, r["relative"], rtol=1e-13)

    def save(name, xlabel, ylabel):
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(name.replace("-", " ") + "\nSynthetic numerical experiment")
        plt.tight_layout()
        plt.savefig(fig / (name + ".svg"))
        plt.close()

    with np.load(root / "mesh-0-2-0/mesh.npz", allow_pickle=False) as z:
        v, t, labels = [z[k] for k in ["vertices", "tetrahedra", "labels"]]
        centres = v[t].mean(axis=1)
        sel = np.abs(centres[:, 2]) < 0.003
        plt.scatter(
            centres[sel, 0] * 1000, centres[sel, 1] * 1000, c=labels[sel], s=3, cmap="viridis"
        )
        plt.axis("equal")
        plt.colorbar(ticks=[0, 1, 2, 3])
        save("01-independent-volume", "x (mm)", "y (mm), element-centroid slice |z|<3mm")
        pd.DataFrame(v, columns=["x_m", "y_m", "z_m"]).to_csv(
            out / "head0-gmsh-vertices_m.csv", index=False
        )
        pd.DataFrame(np.c_[t, labels], columns=["a", "b", "c", "d", "tissue"]).to_csv(
            out / "head0-gmsh-tetrahedra.csv", index=False
        )
    g = pd.DataFrame(geometry)
    plt.scatter(g.level, g.sampled_max_mm, c=g.tissue)
    save(
        "02-interface-deviations",
        "alternative angular level",
        "sampled max deviation to std finest boundary (mm)",
    )
    costs = pd.DataFrame(cost)
    f = costs[costs.kind == "forward"]
    plt.scatter(f.elements, f.min_mean_ratio, c=f.alternative.astype(int))
    save(
        "03-mesh-quality", "tetrahedral elements (count)", "minimum mean ratio (1), std/alternative"
    )
    for head in range(6):
        rows = [r for r in comparisons if r["condition"] == "B matched" and r["head"] == head]
        plt.plot(
            [r["level"] for r in rows], [r["relative"] for r in rows], "-o", label=f"head{head}"
        )
    plt.axhline(0.1, c="red", ls="--")
    plt.legend()
    save("04-matched-fields", "mesh level", "unscaled Gmsh FEM / std BEM relative error (1)")
    for family in ["H", "S"]:
        for alt in [0, 1]:
            rows = [
                r
                for r in comparisons
                if r["condition"] == "analytical " + family and r["label"].endswith("-" + str(alt))
            ]
            plt.semilogy(
                [r["level"] for r in rows],
                [r["relative"] for r in rows],
                "-o",
                label=family + (" independent surface" if alt else " std surface"),
            )
    plt.axhline(0.02, c="gray", ls="--")
    plt.legend()
    save(
        "05-analytical-accuracy",
        "mesh level",
        "relative error vs independent analytical solution (1)",
    )
    for condition in ["B matched", "B alternative matched", "C distinct boundary"]:
        rows = [r for r in comparisons if r["condition"] == condition and r["level"] == 3]
        plt.plot([r["head"] for r in rows], [r["relative"] for r in rows], "o-", label=condition)
    plt.axhline(0.1, c="red", ls="--")
    plt.legend()
    save(
        "06-boundary-versus-solver",
        "head identity",
        "finest physical field relative difference (1)",
    )
    summary = pd.DataFrame(aggregate)
    noise = summary[summary.noise_std_V == 5e-8]
    for (method, solver), part in noise.groupby(["method", "solver"]):
        part = part.sort_values("candidates")
        plt.plot(part.candidates, part.localization_mm, "o-", label=method + " " + solver)
    plt.xscale("linear")
    plt.legend(fontsize=7)
    save(
        "07-grid-localization",
        "candidate count",
        "mean peak localization error (mm), .05µV noise",
    )
    for solver, part in noise[noise.method == "Tikhonov"].groupby("solver"):
        part = part.sort_values("candidates")
        plt.plot(part.candidates, part.localization_mm, "o-", label=solver + " actual")
    part = noise[(noise.method == "Tikhonov") & (noise.solver == "fem")].sort_values("candidates")
    plt.plot(part.candidates, part.nearest_grid_mm, "s--", label="grid-optimal lower bound")
    plt.legend()
    save("08-grid-lower-bound", "candidate count", "localization distance (mm)")
    res = pd.DataFrame(matrix_comparisons)
    for method, part in res.groupby("method"):
        plt.scatter(part.spacing_mm, part.relative_resolution_difference, label=method)
    plt.legend()
    save(
        "09-resolution",
        "grid spacing (mm);0=legacy12",
        "paired same-grid resolution difference (1)",
    )
    src = pd.read_csv(root / "forward-sources.csv")
    part = src[(src.condition == "B matched") & (src.level == 3) & src.independent_source]
    plt.scatter(part.source - 12, part.relative, c=part["head"])
    save(
        "10-source-sensitivity",
        "independent source identity within head",
        "combined XYZ relative field difference (1)",
    )
    plt.scatter(costs.elements, costs.solve_seconds)
    save("11-computational-cost", "tetrahedral elements", "batch-accumulated solve time (s)")
    status = pd.Series([r["status"] for r in models]).value_counts()
    plt.bar(status.index, status.values)
    save("12-configuration-status", "reported configuration state", "number of rows (count)")
    spread = pd.read_csv(root / "point-spread.csv")
    sp = spread[
        (spread["head"] == 0)
        & (spread.spacing_mm == 15)
        & (spread.solver == "fem")
        & (spread.method == "Tikhonov")
        & (spread.probe == 0)
    ]
    plt.scatter(sp.x_m * 1000, sp.y_m * 1000, c=sp.response_frobenius, s=15)
    plt.colorbar(label="XYZ response Frobenius (1)")
    save(
        "13-point-spread",
        "candidate x (mm; z projected)",
        "candidate y (mm); nearest candidate to truth0",
    )
    depth = pd.read_csv("experiments/milestone29/source-depth-audit.csv")
    sp = src[(src.condition == "B matched") & (src.level == 3) & src.independent_source].copy()
    sp["source"] = sp.source - 12
    sp = sp.merge(
        depth[["head", "source", "brain_boundary_distance_mm"]],
        on=["head", "source"],
        validate="one_to_one",
    )
    sp.to_csv(out / "forward-depth.csv", index=False)
    plt.scatter(sp.brain_boundary_distance_mm, sp.relative, c=sp["head"])
    save(
        "14-geometric-depth",
        "distance to std finest brain boundary (mm)",
        "unscaled combined XYZ field difference (1)",
    )
    for axis in range(3):
        rows = [r for r in comparisons if r["condition"] == "B matched" and r["level"] == 3]
        plt.plot(
            [r["head"] for r in rows],
            [r["orientation_relative"][axis] for r in rows],
            "o-",
            label="XYZ"[axis],
        )
    plt.legend()
    save("15-orientation", "head identity", "orientation-specific relative field difference (1)")
    kc = pd.DataFrame(kernel_cost)
    for solver, group in kc.groupby("solver"):
        plt.scatter(group.candidates, group.seconds, label=solver)
    plt.legend()
    save(
        "16-inverse-computational-cost",
        "candidate count",
        "post-run isolated kernel/resolution time (s)",
    )
    for solver, group in kc.groupby("solver"):
        plt.scatter(group.candidates, group.peak_MiB, label=solver)
    plt.legend()
    save(
        "17-inverse-memory", "candidate count", "post-run isolated peak RSS including imports (MiB)"
    )
    receipt.update(
        inverse_rows=len(inverse),
        inverse_computed=int((inverse.status == "computed").sum()),
        inverse_failed=int((inverse.status == "FAILED").sum()),
        geometry_truth_rows=int((inverse.status == "geometry_truth_sensitivity").sum()),
        missing_evaluations_enumerated=len(missing),
        new_field_arrays=int(
            sum(
                r["status"] == "computed" and not (r["kind"] == "grid" and r.get("spacing_mm") == 0)
                for r in models
            )
            + sum("BEM_alternative_diagnostics" in r for r in models)
        ),
        reused_legacy_grid_arrays=int(
            sum(r["kind"] == "grid" and r.get("spacing_mm") == 0 for r in models)
        ),
    )
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    domain = dict(
        computation="independent meshing and paired source-grid convergence",
        inputs={
            "parent_manifest": hashlib.sha256(
                Path("experiments/milestone29/manifest.json").read_bytes()
            ).hexdigest(),
            "design": hashlib.sha256(
                Path("src/soma/resources/mesh-grid-v30.json").read_bytes()
            ).hexdigest(),
        },
        environment=environment_snapshot(),
        assumptions=["synthetic isotropic quasistatic conductors"],
        validation={"scope": "conditional numerical study"},
        limitations=c["limitations"],
    )
    envelope = create_result(
        "experiment.manifest",
        domain,
        values=receipt,
        provenance={"protocol": protocol().protocol.fingerprint},
        method={"id": "soma.mesh-grid", "version": "1"},
        parameters=c,
        units={"distance": "mm", "current": "A*m"},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(envelope, {}, root / "native-result")
    shutil.copytree(root / "native-result", out / "result")
    archive = out / "implementation"
    archive.mkdir()
    index = json.loads(Path("reports/milestone30/executed-sources/index.json").read_text())
    public_index = {}
    for source, entry in index.items():
        filename = entry["file"] + ".txt"
        target = archive / filename
        shutil.copyfile(Path("reports/milestone30/executed-sources") / entry["file"], target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Executed source hash mismatch")
        public_index[source] = dict(file=filename, sha256=entry["sha256"])
    (archive / "source-index.json").write_text(json.dumps(public_index, indent=2) + "\n")
    public = dict(
        schema="soma.mesh-grid.explorer/1",
        synthetic_only=True,
        human_subjects=0,
        threshold=0.1,
        protocol=protocol().protocol.fingerprint,
        mesher="Gmsh4.15.2",
        receipt=receipt,
        comparisons=[
            dict(
                head=r["head"],
                level=r["level"],
                condition=r["condition"],
                relative=r["relative"],
                orientation=r["orientation_relative"],
            )
            for r in comparisons
        ],
        grid_summary=aggregate,
        paired=paired,
        geometry=geometry,
        peaks=json.loads((root / "peaks.json").read_text()),
        configurations=[{k: r[k] for k in ["label", "status", "kind"]} for r in models],
        limitations=c["limitations"],
    )
    raw = json.dumps(public, indent=2, allow_nan=False) + "\n"
    Path("src/soma/resources/mesh-grid-example-v30.json").write_text(raw)
    for p in fig.glob("*.svg"):
        p.write_text("\n".join(line.rstrip() for line in p.read_text().splitlines()) + "\n")
    mesh_comparison(root, out)
    subprocess.run(
        [sys.executable, "scripts/mesh_grid_uncertainty.py", str(root), str(out)], check=True
    )
    (out / "manifest.json").write_text(
        json.dumps(
            {
                str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in out.rglob("*")
                if p.is_file()
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            dict(receipt=receipt, resource_sha256=hashlib.sha256(raw.encode()).hexdigest()),
            indent=2,
        )
    )


def mesh_comparison(root: Path, out: Path) -> None:
    from matplotlib.collections import LineCollection

    from soma.imaging.mesh_quality import _point_triangle
    from soma.source.mesh_replication import boundaries

    previous = Path("experiments/milestone29")
    radial_v = pd.read_csv(previous / "head0-volume-vertices_m.csv").to_numpy()
    radial = pd.read_csv(previous / "head0-volume-tetrahedra.csv").to_numpy(int)
    with np.load(root / "mesh-0-2-0/mesh.npz", allow_pickle=False) as z:
        gm_v, gm_t, gm_l = [z[k] for k in ["vertices", "tetrahedra", "labels"]]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, (vertices, tets, labels, name) in zip(
        axes,
        [
            (radial_v, radial[:, :4], radial[:, 4], "M29 radial"),
            (gm_v, gm_t, gm_l, "independent Gmsh"),
        ],
        strict=True,
    ):
        segments = []
        colors = []
        for cell, tissue in zip(vertices[tets], labels, strict=True):
            if cell[:, 2].min() > 0 or cell[:, 2].max() < 0:
                continue
            points = []
            for i in range(4):
                for j in range(i):
                    a, b = cell[i], cell[j]
                    if a[2] * b[2] < 0:
                        points.append((a + (b - a) * (-a[2]) / (b[2] - a[2]))[:2])
                    elif a[2] == 0:
                        points.append(a[:2])
                    elif b[2] == 0:
                        points.append(b[:2])
            if len(points) < 3:
                continue
            pp = np.unique(np.round(points, 15), axis=0)
            if len(pp) < 3:
                continue
            centre = pp.mean(axis=0)
            pp = pp[np.argsort(np.arctan2(pp[:, 1] - centre[1], pp[:, 0] - centre[0]))] * 1000
            segments.append(np.vstack([pp, pp[0]]))
            colors.append(tissue)
        collection = LineCollection(segments, cmap="viridis", linewidths=0.35)
        collection.set_array(np.asarray(colors))
        ax.add_collection(collection)
        ax.autoscale()
        ax.set_aspect("equal")
        ax.set_xlabel("x (mm)")
        ax.set_ylabel("y (mm)")
        ax.set_title(f"{name}: {len(tets):,} tetrahedra")
    fig.suptitle("Matched level2 interfaces; exact z=0 tetrahedral cuts — synthetic head0")
    fig.tight_layout()
    fig.savefig(out / "figures/18-radial-versus-independent-mesh.svg")
    plt.close(fig)
    alt = boundaries(0, 3, True)
    std = boundaries(0, 3)
    rows = []
    for tissue, (a, b) in enumerate(zip(alt, std, strict=True)):
        triangles = b.vertices.xyz[b.faces]
        for index, point in enumerate(a.vertices.xyz):
            distance = float(
                _point_triangle(np.broadcast_to(point, (len(triangles), 3)), triangles).min() * 1000
            )
            rows.append(
                dict(
                    tissue=tissue,
                    vertex=index,
                    x_m=point[0],
                    y_m=point[1],
                    z_m=point[2],
                    distance_to_std_mm=distance,
                )
            )
    table = pd.DataFrame(rows)
    table.to_csv(out / "interface-deviation-map.csv", index=False)
    scalp = table[table.tissue == 3]
    fig = plt.figure(figsize=(7, 5))
    ax = fig.add_subplot(projection="3d")
    points = ax.scatter(
        scalp.x_m * 1000,
        scalp.y_m * 1000,
        scalp.z_m * 1000,
        c=scalp.distance_to_std_mm,
        s=8,
        cmap="viridis",
    )
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_zlabel("z (mm)")
    ax.set_title(
        "Alternative scalp vertices — synthetic head0\nDistance to std finest polyhedral boundary"
    )
    fig.colorbar(points, ax=ax, label="sampled distance (mm)", shrink=0.6)
    fig.tight_layout()
    fig.savefig(out / "figures/19-interface-deviation-map.svg")
    plt.close(fig)
    for path in out.joinpath("figures").glob("*.svg"):
        path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    run(a.root, a.output)
