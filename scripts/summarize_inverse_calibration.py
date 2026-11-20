"""Auditable source-cluster summaries and figures for the frozen M31 experiment."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.run_inverse_calibration import DESIGN_SHA, grids, lead_for
from soma.imaging.mesh_quality import _point_triangle
from soma.source.mesh_replication import boundaries
from soma.source.noise import NoiseModel, average_projector
from soma.source.prior_calibration import (
    PriorInverse,
    SourcePrior,
    cell_volumes,
    conditional_interval,
)

KEYS = ["grid", "candidates", "prior", "method", "noise_std_V", "policy"]


def run(root, out):
    out.mkdir(parents=True, exist_ok=True)
    fig = out / "figures"
    fig.mkdir(exist_ok=True)
    x = pd.read_csv(root / "reconstructions.csv")
    geometry = []
    sources = json.loads((root / "sources.json").read_text())
    for head in range(6):
        surface = boundaries(head, 3)[0]
        triangles = surface.vertices.xyz[surface.faces]
        for source in sources:
            if source["head"] != head:
                continue
            point = np.array(source["xyz_m"])
            distance = _point_triangle(np.broadcast_to(point, (len(triangles), 3)), triangles)
            depth = float(distance.min() * 1000)
            if depth <= 0:
                raise ValueError("Invalid positive source-to-brain distance")
            geometry.append(dict(head=head, source=source["source"], brain_surface_depth_mm=depth))
    source_geometry = pd.DataFrame(geometry)
    source_geometry.to_csv(out / "source-geometry.csv", index=False)
    x = x.merge(source_geometry, on=["head", "source"], validate="many_to_one")

    ops = pd.read_csv(root / "operators.csv")
    rep = pd.read_csv(root / "M30-replication.csv")
    failures = json.loads((root / "failures.json").read_text())
    receipt = json.loads((root / "receipt.json").read_text())
    assert receipt["heads"] == 6 and receipt["operator_rows"] + len(failures) == 3726
    assert (
        len(x) == receipt["reconstruction_rows"]
        and not x.duplicated(["head", "source", "draw", "solver", *KEYS]).any()
    )
    cell_keys = [
        "head",
        "grid",
        "solver",
        "prior",
        "method",
        "policy",
        "noise_std_V",
        "source",
        "draw",
    ]
    expected = {
        (h, grid, solver, prior, method, policy, std, source, draw)
        for h in range(6)
        for grid in grids()
        for solver in (
            ["fem", "openmeeg"] if h in [0, 5] and grid in ["cart20", "nested2"] else ["fem"]
        )
        for prior in ["unweighted", "cell_volume", "total_variance"]
        for method in ["Tikhonov", "MNE", "dSPM"]
        for policy in ["historical", "spectral", "prediction"]
        for std in [0.0, 5e-8, 1.5e-7]
        for source in range(16)
        for draw in range(1 if std == 0 else 2)
    }
    actual = set(x[cell_keys].itertuples(index=False, name=None))
    if not failures and actual != expected:
        raise ValueError("Missing or undeclared scientific reconstruction cells")
    assert (x.excess_mm >= -1e-9).all()
    metrics = [
        "localization_mm",
        "nearest_mm",
        "excess_mm",
        "dispersion_mm",
        "whitened_residual",
        "sensor_clean_MSE",
    ]
    summary = []
    for key, g in x[(x.solver == "fem") & (x.split == "test")].groupby(KEYS):
        source = g.groupby(["head", "source"])[metrics].mean()
        row = dict(zip(KEYS, key, strict=True))
        row.update(heads=6, sources=60, noise_averaged_first=True)
        for metric in metrics:
            a = source[metric].unstack().reindex(range(6)).to_numpy()
            m, lo, hi = conditional_interval(a)
            row.update({metric: m, metric + "_lower": lo, metric + "_upper": hi})
        summary.append(row)
    agg = pd.DataFrame(summary)
    agg.to_csv(out / "heldout-summary.csv", index=False)
    # Strict paired contrasts use identical sources and noise draws; clusters unchanged.
    contrasts = []
    for dimension, reference, alternatives in [
        ("prior", "unweighted", ["cell_volume", "total_variance"]),
        ("policy", "historical", ["spectral", "prediction"]),
    ]:
        join = ["head", "source", "draw", "grid", "method", "noise_std_V", "solver"] + (
            ["prior"] if dimension == "policy" else ["policy"]
        )
        ref = x[(x.solver == "fem") & (x.split == "test") & (x[dimension] == reference)]
        for alt in alternatives:
            pair = ref.merge(
                x[(x.solver == "fem") & (x.split == "test") & (x[dimension] == alt)],
                on=join,
                validate="one_to_one",
                suffixes=("_ref", "_alt"),
            )
            group = ["grid", "method", "noise_std_V"] + (
                ["prior"] if dimension == "policy" else ["policy"]
            )
            for key, g in pair.groupby(group):
                delta = (
                    (g.localization_mm_alt - g.localization_mm_ref)
                    .groupby([g["head"], g.source])
                    .mean()
                    .unstack()
                    .reindex(range(6))
                    .to_numpy()
                )
                m, lo, hi = conditional_interval(delta)
                contrasts.append(
                    dict(
                        zip(group, key, strict=True),
                        dimension=dimension,
                        reference=reference,
                        alternative=alt,
                        mean_delta_mm=m,
                        lower=lo,
                        upper=hi,
                    )
                )
    pd.DataFrame(contrasts).to_csv(out / "paired-contrasts.csv", index=False)
    # Held-out new seed sensitivity is separate from the combined primary estimand.
    new = x[(x.solver == "fem") & x.new_heldout].groupby(KEYS).localization_mm.mean().reset_index()
    new.to_csv(out / "new-heldout-only.csv", index=False)
    # Two-head BEM/FEM subset: no six-head or population CI is fabricated.
    join = ["head", "source", "draw", *KEYS]
    a = x[(x.solver == "fem") & (x.split == "test")]
    b = x[(x.solver == "openmeeg") & (x.split == "test")]
    pair = a.merge(b, on=join, validate="one_to_one", suffixes=("_fem", "_bem"))
    pair["BEM_minus_FEM_mm"] = pair.localization_mm_bem - pair.localization_mm_fem
    pair.groupby(KEYS).BEM_minus_FEM_mm.agg(["mean", "min", "max"]).reset_index().to_csv(
        out / "BEM-FEM-paired.csv", index=False
    )
    # Compare whitened prior covariances on a common sensor space, not incompatible source matrices.
    cov = []
    gg = grids()
    p = average_projector(32)
    noise = NoiseModel((5e-8) ** 2 * p, tuple(f"E{i:02}" for i in range(32)), p)
    for head in range(6):
        for method in ["Tikhonov", "MNE", "dSPM"]:
            for kind in ["unweighted", "cell_volume", "total_variance"]:
                matrices = {}
                for name, grid in gg.items():
                    inv = PriorInverse(
                        lead_for(head, name, "fem", grid),
                        grid,
                        SourcePrior.create(grid, kind, cell_volumes(grid)),
                        noise,
                        method,
                    )
                    matrices[name] = inv.components()[2]
                for name, grid in gg.items():
                    b0 = matrices["nested2"]
                    b1 = matrices[name]
                    cov.append(
                        dict(
                            head=head,
                            grid=name,
                            candidates=len(grid),
                            method=method,
                            prior=kind,
                            whitened_trace=float(np.trace(b1)),
                            relative_to_nested_finest=float(
                                np.linalg.norm(b1 - b0) / np.linalg.norm(b0)
                            ),
                        )
                    )
    covariance = pd.DataFrame(cov)
    covariance.to_csv(out / "prior-covariance.csv", index=False)
    replication = (
        rep[rep.noise_std_V == 5e-8]
        .groupby(["candidates", "method"])[["nearest_mm", "localization_mm", "kernel_relative"]]
        .mean()
        .reset_index()
    )
    replication.to_csv(out / "M30-replication-summary.csv", index=False)
    # Every plotted point comes from saved numerical tables. Lines connect observed grids only.
    plt.rcParams.update(
        {
            "svg.hashsalt": "soma-m31-v1",
            "font.size": 10,
            "figure.dpi": 130,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    def save(name, title):
        plt.title(title)
        plt.tight_layout()
        plt.savefig(fig / (name + ".svg"), metadata={"Date": None})
        target = fig / (name + ".svg")
        target.write_text(
            "\n".join(line.rstrip() for line in target.read_text().splitlines()) + "\n"
        )
        plt.close()

    for method, g in replication.groupby("method"):
        plt.plot(g.candidates, g.localization_mm, "o-", label=method)
    plt.plot(
        replication.groupby("candidates").nearest_mm.mean().index,
        replication.groupby("candidates").nearest_mm.mean().values,
        "k--",
        label="nearest geometric bound",
    )
    plt.xlabel("Candidates")
    plt.ylabel("Mean error (mm)")
    plt.legend()
    save("01-M30-replication", "Original M30, 72 sources, 0.05 µV; recreated kernels")
    f = plt.figure()
    ax = f.add_subplot(projection="3d")
    for name in ["nested0", "nested1", "nested2"]:
        ax.scatter(*(gg[name] * 1000).T, s=4, label=name)
    ax.set(xlabel="MRI x (mm)", ylabel="MRI y (mm)", zlabel="MRI z (mm)")
    ax.legend()
    save("02-nesting", "Nested union grids: 33 → 173 → 481")
    for name in ["nested0", "nested1", "nested2"]:
        plt.plot(np.sort(cell_volumes(gg[name])) * 1e9, label=name)
    plt.xlabel("Cell rank")
    plt.ylabel("Approximate cell volume (mm³)")
    plt.legend()
    save("03-volumes", "Fixed Sobol Voronoi quadrature over common ball")
    cv = covariance[(covariance.method == "Tikhonov") & covariance.grid.str.startswith("nested")]
    for kind, g in cv.groupby("prior"):
        plt.plot(g.groupby("candidates").whitened_trace.mean(), "o-", label=kind)
    plt.yscale("log")
    plt.xlabel("Candidates")
    plt.ylabel("Whitened prior trace")
    plt.legend()
    save("04-covariance", "Raw physical prior covariance scaling across density")
    curves = pd.read_csv(root / "regularization-curves.csv")
    curve = curves[
        (curves["head"] == 0)
        & (curves.grid == "nested2")
        & (curves.prior == "cell_volume")
        & (curves.method == "MNE")
        & (curves.solver == "fem")
    ]
    for std, g in curve.groupby("noise_std_V"):
        plt.loglog(g.alpha, g.calibration_repeat_MSE, "o-", label=f"{std * 1e6:g} µV")
    plt.xlabel("Alpha")
    plt.ylabel("Whitened calibration repeat MSE")
    plt.legend()
    save("05-regularization", "Independent-repeat tuning: six calibration sources, head 0")
    chosen = agg[
        (agg.prior == "cell_volume")
        & (agg.policy == "spectral")
        & (agg.noise_std_V == 5e-8)
        & agg.grid.str.startswith("nested")
    ]
    for metric, num in [("localization_mm", "06"), ("excess_mm", "07")]:
        for method, g in chosen.groupby("method"):
            g = g.sort_values("candidates")
            plt.errorbar(
                g.candidates,
                g[metric],
                yerr=[g[metric] - g[metric + "_lower"], g[metric + "_upper"] - g[metric]],
                fmt="o-",
                label=method,
            )
        plt.xlabel("Candidates")
        plt.ylabel(metric + " (mm)")
        plt.legend()
        save(num + "-" + metric, "Held-out sources; conditional hierarchical 95% intervals")
    osel = ops[
        (ops.solver == "fem")
        & (ops.policy == "spectral")
        & (ops.prior == "cell_volume")
        & (ops.noise_std_V == 5e-8)
        & ops.grid.str.startswith("nested")
    ]
    for method, g in osel.groupby("method"):
        plt.plot(g.groupby("candidates").PSF_RMS_width_mm.mean(), "o-", label=method)
    plt.xlabel("Candidates")
    plt.ylabel("PSF RMS width (mm)")
    plt.legend()
    save("08-point-spread", "Unit-orientation-block response about nearest new-source candidate")
    nt = new[
        (new.grid == "nested2") & (new.prior == "cell_volume") & (new.noise_std_V == 5e-8)
    ].pivot(index="method", columns="policy", values="localization_mm")
    nt.plot.bar(ax=plt.gca())
    plt.ylabel("Mean peak error (mm)")
    save("09-new-heldout", "24 newly seeded sources: descriptive sensitivity")
    sens = (
        x[
            (x.solver == "fem")
            & (x.grid == "nested2")
            & (x.prior == "cell_volume")
            & (x.policy == "spectral")
            & (x.method == "MNE")
            & (x.split == "test")
        ]
        .groupby(["head", "source", "noise_std_V"])[["brain_surface_depth_mm", "localization_mm"]]
        .mean()
        .reset_index()
    )
    for std, g in sens.groupby("noise_std_V"):
        plt.scatter(g.brain_surface_depth_mm, g.localization_mm, s=12, label=f"{std * 1e6:g} µV")
    plt.xlabel("Distance below finest brain interface (mm)")
    plt.ylabel("Peak error (mm)")
    plt.legend()
    save("10-noise-depth", "Each point is a source average, not an independent participant")
    inter = agg[
        (agg.grid == "nested2") & (agg.policy == "spectral") & (agg.noise_std_V == 5e-8)
    ].pivot(index="method", columns="prior", values="localization_mm")
    inter.plot.bar(ax=plt.gca())
    plt.ylabel("Held-out peak error (mm)")
    save("11-prior-method", "Prior and inverse-method interactions, observed values")
    cost = (
        ops[(ops.solver == "fem") & ops.grid.str.startswith("nested")]
        .groupby("candidates")[["seconds", "peak_RSS_MiB"]]
        .mean()
    )
    ax = plt.gca()
    ax.plot(cost.index, cost.seconds, "o-", label="Kernel seconds")
    ax.set(xlabel="Candidates", ylabel="Kernel seconds")
    ax2 = ax.twinx()
    ax2.plot(cost.index, cost.peak_RSS_MiB, "s--", color="orange")
    ax2.set_ylabel("Cumulative process peak RSS (MiB)")
    save(
        "12-runtime-memory", "Observed inverse cost; process RSS includes imports and earlier grids"
    )
    # Read-only packaged example uses actual source-level records, no interpolation.
    resource = {
        "schema": "soma.inverse-calibration.explorer/1",
        "synthetic_only": True,
        "human_subjects": 0,
        "design_sha256": DESIGN_SHA,
        "warning": (
            "Synthetic six-head study only. Native meshing portability is NOT established. "
            "Conditional intervals are not human-population coverage. "
            "dSPM amplitudes are dimensionless."
        ),
        "receipt": receipt,
        "summary": agg.to_dict("records"),
        "new_heldout": new.to_dict("records"),
        "examples": json.loads((root / "examples.json").read_text()),
        "failures": failures,
        "source_metrics": x[(x.solver == "fem") & (x.split == "test")]
        .groupby([*KEYS, "head", "source"])[
            [
                "depth_radius_mm",
                "brain_surface_depth_mm",
                "orientation_radial_cosine",
                "localization_mm",
                "dispersion_mm",
            ]
        ]
        .mean()
        .reset_index()
        .to_dict("records"),
        "operator_summary": ops[ops.solver == "fem"]
        .groupby(KEYS)[["PSF_RMS_width_mm", "EDF", "condition_regularized", "boundary_optimum"]]
        .mean()
        .reset_index()
        .to_dict("records"),
    }
    # Source metrics for every head/condition are available in the tables; package a
    # bounded, explicitly labeled head0 detail slice for interactive depth filtering.
    resource["source_metrics"] = [
        v for v in resource["source_metrics"] if v["head"] == 0 and v["noise_std_V"] == 5e-8
    ]
    Path("src/soma/resources/inverse-calibration-example-v31.json").write_text(
        json.dumps(resource, separators=(",", ":"), allow_nan=False) + "\n"
    )
    for name in [
        "operators.csv",
        "regularization-curves.csv",
        "M30-replication.csv",
        "point-spread.csv",
        "sources.json",
        "failures.json",
        "receipt.json",
    ]:
        shutil.copyfile(root / name, out / name)
    for p in root.glob("grid-*.csv"):
        shutil.copyfile(p, out / p.name)
    for p in root.glob("truth-new-*.csv"):
        shutil.copyfile(p, out / p.name)
    for p in root.glob("measurements-*.csv"):
        shutil.copyfile(p, out / p.name)
    for (head, block), g in x.groupby([x["head"], x.source // 8]):
        g.to_csv(out / f"reconstructions-head{head}-block{block}.csv", index=False)
    summary_record = {
        "schema": "soma.inverse-calibration.summary/1",
        "design_sha256": DESIGN_SHA,
        "receipt": receipt,
        "replication_max_kernel_relative": float(rep.kernel_relative.max()),
        "boundary_prediction_fraction": ops[ops.policy == "prediction"]
        .groupby("noise_std_V")
        .boundary_optimum.mean()
        .to_dict(),
        "BEM_FEM_mean_abs_peak_difference_mm": float(abs(pair.BEM_minus_FEM_mm).mean()),
        "conditional_uncertainty": (
            "heads nested sources, noise averaged; uncalibrated simulation coverage"
        ),
        "all_scientific_failures": failures,
        "native_release_gate": "BLOCK_RELEASE_CHANGED_NATIVE_SIGNATURE_PRESERVED",
    }
    (out / "summary.json").write_text(json.dumps(summary_record, indent=2) + "\n")
    hashes = {
        str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name not in ["manifest.json"]
    }
    (out / "manifest.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(summary_record)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.root, a.output)
