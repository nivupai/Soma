"""Auditable synthetic FEM exports, independent norms, paired summaries and figures."""

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
from scipy.stats import pearsonr

from soma.eeg_benchmark.evaluation import environment_snapshot
from soma.experiments.fem_reference import design, protocol
from soma.experiments.nonspherical import hierarchical
from soma.results.contracts import create_result
from soma.results.io import save_result
from soma.source.bem_discrepancy import sensors
from soma.source.fem_reference import radial_mesh
from soma.source.nonspherical import head_parameters, meshes, source_grid


def run(root, output):
    output.mkdir(parents=True, exist_ok=False)
    fig = output / "figures"
    fig.mkdir()
    c = design()
    models = json.loads((root / "models.json").read_text())
    pairs = json.loads((root / "comparisons.json").read_text())
    refs = json.loads((root / "analytical.json").read_text())
    receipt = json.loads((root / "receipt.json").read_text())
    for p in root.iterdir():
        if p.is_file() and p.suffix in [".json", ".csv"]:
            shutil.copyfile(p, output / p.name)

    # Raw child exceptions can contain local interpreter paths. Public failures
    # retain the actual numerical rejection while local tracebacks stay ignored.
    for model in models:
        if model["status"] == "computed":
            continue
        log = root / (model["label"] + "-" + model["solver"]) / "worker.log"
        text = log.read_text() if log.exists() else ""
        errors = [
            line.split("ValueError: ", 1)[1]
            for line in text.splitlines()
            if line.startswith("ValueError: ")
        ]
        if not errors:
            raise ValueError("Failure requires explicit reviewed public diagnosis")
        model["reason"] = errors[-1]
    (output / "models.json").write_text(json.dumps(models, indent=2) + "\n")

    def lead(label, solver):
        p = root / (label + "-" + solver)
        return (
            np.loadtxt(p / "lead.csv", delimiter=",")
            if solver == "fem"
            else np.load(p / "result/lead.npy", allow_pickle=False)
        )

    audit = []
    for m in models:
        if m["status"] != "computed":
            continue
        g = lead(m["label"], m["solver"])
        np.savetxt(output / (m["label"] + "-" + m["solver"] + "-V_per_Am.csv"), g, delimiter=",")
        d = m["diagnostics"]
        audit.append(
            dict(
                label=m["label"],
                head=m["head"],
                level=m["level"],
                solver=m["solver"],
                seconds=d.get("seconds", d.get("runtime_seconds")),
                peak_MiB=d.get("peak_child_MiB", d.get("process_peak_rss_mib")),
                elements=d.get("elements"),
                nodes=d.get("nodes"),
                quality=d.get("min_mean_ratio"),
                residual=d.get("relative_residual"),
                imbalance=d.get("preprojection_current_imbalance"),
                exact_surface_facets=d.get("surface_audit", {}).get("exact_surface_facets"),
            )
        )
    for p in pairs:
        a = lead(p["label"], p["solver"])
        b = lead(p["label"], "fem")
        diff = a - b
        direct = float(
            np.sqrt(sum(float(x * x) for x in diff.ravel()))
            / np.sqrt(sum(float(x * x) for x in b.ravel()))
        )
        assert np.isclose(direct, p["relative"], rtol=1e-13)
        correlations = [float(pearsonr(a[:, i], b[:, i]).statistic) for i in range(a.shape[1])]
        assert np.allclose(correlations, p["column_correlation"], atol=1e-12)
    pd.DataFrame(audit).to_csv(output / "mesh-cost-audit.csv", index=False)
    matching = []
    spectra = []
    for m in models:
        if m["status"] != "computed":
            continue
        g = lead(m["label"], m["solver"])
        sv = np.linalg.svd(g, compute_uv=False)
        rank = int(np.sum(sv > sv[0] * 1e-12))
        spectra.append(
            dict(
                label=m["label"],
                solver=m["solver"],
                rank=rank,
                condition_nonnull=float(sv[0] / sv[rank - 1]),
                singular_values=sv.tolist(),
                units="V/(A*m)",
            )
        )
        if m["solver"] != "openmeeg" or not m["label"].startswith(("C-", "S-", "H-")):
            continue
        fem_packet = root / (m["label"] + "-fem") / "input.npz"
        if not fem_packet.exists():
            continue
        with (
            np.load(fem_packet, allow_pickle=False) as f,
            np.load(root / (m["label"] + "-openmeeg") / "input.npz", allow_pickle=False) as b,
        ):
            assert np.array_equal(f["sources"], b["points"]) and np.array_equal(
                f["sensors"], b["sensors"]
            )
            n = len(b["v0"])
            steps = m["level"]
            cursor = 0
            maximum = 0.0
            for layer in range(4):
                cursor += (4 if layer == 0 else 1) * steps
                actual = f["vertices"][1 + (cursor - 1) * n : 1 + cursor * n]
                maximum = max(
                    maximum, float(np.max(np.linalg.norm(actual - b[f"v{layer}"], axis=1)))
                )
            assert maximum < 1e-14
            cell = f["vertices"][f["tetrahedra"]]
            volumes = (
                np.linalg.det(np.stack([cell[:, j] - cell[:, 0] for j in (1, 2, 3)], axis=2)) / 6
            )
            assert np.all(volumes > 0)
            previous = 0.0
            volume_errors = []
            for tissue in range(4):
                tri = b[f"v{tissue}"][b[f"f{tissue}"]]
                enclosed = float(np.sum(tri[:, 0] * np.cross(tri[:, 1], tri[:, 2])) / 6)
                expected = enclosed - previous
                actual = float(volumes[f["labels"] == tissue].sum())
                assert expected > 0 and abs(actual - expected) / expected < 1e-10
                volume_errors.append(abs(actual - expected) / expected)
                previous = enclosed
            matching.append(
                dict(
                    label=m["label"],
                    max_boundary_coordinate_difference_m=maximum,
                    source_coordinates_exact=True,
                    sensor_coordinates_exact=True,
                    interface_connectivity_exact=True,
                    max_tissue_volume_relative_difference=max(volume_errors),
                )
            )
    (output / "physical-matching.json").write_text(json.dumps(matching, indent=2) + "\n")
    (output / "singular-spectra.json").write_text(json.dumps(spectra, indent=2) + "\n")

    primary = pd.DataFrame(
        [
            dict(
                head=p["head"],
                level=p["level"],
                relative=p["relative"],
                alpha=p["alignment_scalar"],
                aligned=p["aligned_relative_diagnostic"],
                rms_uV=p["rms_difference_uV"],
                **{f"axis_{i}": e for i, e in enumerate(p["orientation_relative"])},
            )
            for p in pairs
            if p["label"].startswith("C-")
        ]
    )
    primary.to_csv(output / "head-fields.csv", index=False)
    forward = pd.read_csv(root / "source-fields.csv")
    selected = forward[forward.label.str.startswith("C-") & forward.independent_draw]
    hierarchical_rows = []
    for level in (1, 2, 3):
        a = (
            selected[selected.level == level]
            .assign(source=lambda x: x.source - 12)
            .pivot(index="head", columns="source", values="relative")
            .reindex(index=range(6), columns=range(12))
            .to_numpy()
        )
        if np.isfinite(a).all():
            mean, lo, hi = hierarchical(a)
            hierarchical_rows.append(
                dict(level=level, mean=mean, lower=lo, upper=hi, heads=6, sources_per_head=12)
            )
    pd.DataFrame(hierarchical_rows).to_csv(output / "hierarchical-fields.csv", index=False)
    inverse = pd.read_csv(root / "inverse.csv")
    paired = []
    agg = []
    for (method, std), group in inverse.groupby(["method", "noise_std_V"]):
        means = group.groupby(["head", "source", "solver"]).localization_mm.mean().unstack("solver")
        differences = (
            (means["openmeeg"] - means["fem"])
            .unstack("source")
            .reindex(index=range(6), columns=range(12))
            .to_numpy()
        )
        if np.isfinite(differences).all():
            mean, lo, hi = hierarchical(differences)
            paired.append(
                dict(method=method, noise_std_V=std, OM_minus_FEM_mm=mean, lower=lo, upper=hi)
            )
        for solver, g in group.groupby("solver"):
            agg.append(
                dict(
                    method=method,
                    noise_std_V=std,
                    solver=solver,
                    localization_mm=float(g.localization_mm.mean()),
                    dispersion_mm=float(g.dispersion_mm.mean()),
                    physical_peak_bias_ratio=None
                    if method == "dSPM"
                    else float(g.peak_amplitude_bias_ratio.mean()),
                )
            )
    pd.DataFrame(paired).to_csv(output / "paired-inverse.csv", index=False)
    grid = source_grid().xyz[np.r_[0:6, 24:30]]
    keys = ["head", "source", "noise_std_V", "draw", "method"]
    peaks = inverse.pivot(index=keys, columns="solver", values="peak").dropna()
    displacement = (
        np.linalg.norm(
            grid[peaks["openmeeg"].to_numpy(int)] - grid[peaks["fem"].to_numpy(int)], axis=1
        )
        * 1000
    )
    displacements = peaks.reset_index()[keys]
    displacements["peak_displacement_mm"] = displacement
    displacements.to_csv(output / "paired-peak-displacement.csv", index=False)
    resolution = []
    from soma.geometry import Frame, Points
    from soma.source.nonspherical import native_forward, pose
    from soma.source.uncertainty import kernels

    for head in range(6):
        scale = float(np.linalg.norm(lead(f"C-{head}-3", "fem")[:, :36], 2))
        ops = {}
        res = {}
        for solver in ["fem", "openmeeg"]:
            g = lead(f"C-{head}-2", solver)[:, :36]
            ops[solver], _ = kernels(
                native_forward(g, Points(grid, Frame.MRI), sensors(head), pose({})), scale
            )
            res[solver] = {method: k @ g for method, k in ops[solver].items()}
        for method in res["fem"]:
            a = res["openmeeg"][method]
            b = res["fem"][method]
            resolution.append(
                dict(
                    head=head,
                    method=method,
                    relative_resolution_difference=float(np.linalg.norm(a - b) / np.linalg.norm(b)),
                    resolution_units="1/(A*m)" if method == "dSPM" else "1",
                )
            )
    pd.DataFrame(resolution).to_csv(output / "resolution-differences.csv", index=False)

    pd.DataFrame(agg).to_csv(output / "inverse-summary.csv", index=False)
    controls = []
    baseline = lead("C-0-2", "fem")
    for label in ["F-0-2-r1-q8", "F-0-2-r3-q8", "F-0-2-r2-q4"]:
        if any(m["label"] == label and m["status"] == "computed" for m in models):
            controls.append(
                dict(
                    label=label,
                    relative_field_change=float(
                        np.linalg.norm(lead(label, "fem") - baseline) / np.linalg.norm(baseline)
                    ),
                )
            )
    pd.DataFrame(controls).to_csv(output / "error-controls.csv", index=False)

    def save(name, xlabel, ylabel):
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(name.replace("-", " ") + " — synthetic only")
        plt.tight_layout()
        plt.savefig(fig / (name + ".svg"))
        plt.close()

    v, t, labels, q = radial_mesh(meshes(head_parameters(0), 2), 2)
    pd.DataFrame(v, columns=["x_m", "y_m", "z_m"]).to_csv(
        output / "head0-volume-vertices_m.csv", index=False
    )
    pd.DataFrame(np.c_[t, labels], columns=["a", "b", "c", "d", "tissue"]).to_csv(
        output / "head0-volume-tetrahedra.csv", index=False
    )
    from matplotlib.collections import LineCollection

    segments = []
    colors = []
    for cell, tissue in zip(v[t], labels, strict=True):
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
    plt.gca().add_collection(collection)
    plt.gca().autoscale()
    bar = plt.colorbar(collection, ticks=[0, 1, 2, 3])
    bar.ax.set_yticklabels(["brain", "CSF", "skull", "scalp"])
    plt.axis("equal")
    save("01-four-compartment-volume", "x (mm)", "y (mm); exact tetrahedron cross-section z=0")
    aud = pd.DataFrame(audit)
    fem = aud[aud.solver == "fem"]
    plt.scatter(fem.elements, fem.quality)
    save("02-mesh-quality", "tetrahedral elements (count)", "minimum tetrahedron mean ratio (1)")
    for family in ["H", "S"]:
        for solver in ["fem", "openmeeg"]:
            rows = [
                r for r in refs if r.get("solver") == solver and r["label"].startswith(family + "-")
            ]
            plt.semilogy(
                [r["level"] for r in rows],
                [r["relative"] for r in rows],
                "-o",
                label=family + " " + solver,
            )
    plt.axhline(0.02, ls="--", c="gray")
    plt.legend()
    save(
        "03-analytical-convergence",
        "mesh level (repeated configuration)",
        "relative physical error (1)",
    )
    for head, g in primary.groupby("head"):
        plt.plot(g.level, g.relative, "-o", label=f"head {head}")
    plt.axhline(0.1, c="red", ls="--", label="frozen 10% target")
    plt.legend()
    save("04-independent-refinement", "mesh level", "unscaled OM/FEM relative field difference (1)")
    a = lead("C-0-3", "openmeeg")[:, 36] * 1e-8 * 1e6
    b = lead("C-0-3", "fem")[:, 36] * 1e-8 * 1e6
    pd.DataFrame(dict(sensor=range(32), openmeeg_uV=a, fem_uV=b)).to_csv(
        output / "sensor-example.csv", index=False
    )
    plt.plot(a, "o-", label="OM")
    plt.plot(b, "s-", label="FEM")
    plt.legend()
    save(
        "05-sensor-potentials",
        "sensor index",
        "average-referenced voltage (µV), first offgrid +X 10 nA m",
    )
    g = selected[selected.level == 3]
    plt.scatter(g.depth_radius_mm, g.relative, c=g["head"])
    save(
        "06-source-depth",
        "source radius from origin (mm; not cortical depth)",
        "combined XYZ field relative difference (1)",
    )
    for i in range(3):
        plt.plot(
            primary[primary.level == 3]["head"],
            primary[primary.level == 3][f"axis_{i}"],
            "o-",
            label="XYZ"[i],
        )
    plt.legend()
    save("07-orientation", "head identity", "orientation field relative difference (1)")
    g = primary[primary.level == 3]
    plt.scatter(g.alpha, g.aligned, c=g["head"])
    save(
        "08-scale-pattern",
        "diagnostic OM→FEM scalar (not applied)",
        "residual after diagnostic alignment (1)",
    )
    plt.bar(g["head"], g.relative)
    plt.axhline(0.1, c="red", ls="--")
    save("09-per-head", "head identity", "finest physical relative difference (1)")
    g = pd.DataFrame(agg)
    g = g[g.noise_std_V == 5e-8]
    for solver, part in g.groupby("solver"):
        plt.plot(part.method, part.localization_mm, "o-", label=solver)
    plt.legend()
    save(
        "10-source-localization",
        "inverse method; fixed level2 estimates",
        "mean peak error (mm), noise .05 µV",
    )
    if controls:
        plt.bar(range(len(controls)), [r["relative_field_change"] for r in controls])
        plt.xticks(range(len(controls)), ["radial 1", "radial 3", "quadrature 4"])
    save(
        "11-error-controls",
        "head0 paired controls vs level2/radial2/q8",
        "relative FEM field change (1)",
    )
    plt.scatter(fem.elements, fem.seconds, label="time (left)")
    plt.ylabel("assembly and solution time (s)")
    right = plt.gca().twinx()
    right.scatter(fem.elements, fem.peak_MiB, c="orange", marker="x", label="RSS (right)")
    right.set_ylabel("peak solver-child RSS (MiB; imports included)")
    left = plt.gcf().axes[0]
    h1, l1 = left.get_legend_handles_labels()
    h2, l2 = right.get_legend_handles_labels()
    left.legend(h1 + h2, l1 + l2, loc="upper left")
    plt.sca(left)
    save(
        "12-computational-cost",
        "tetrahedral elements (count)",
        "assembly and field solution time (s)",
    )
    # Native M17 envelope complements auditable text exports; no participant images.
    environment = environment_snapshot()
    receipt["environment"] = environment
    envelope = create_result(
        "experiment.manifest",
        dict(
            computation="independent P1 FEM full-subtraction four-layer validation",
            inputs={"design": sealed_hash()},
            environment=environment,
            assumptions=["quasistatic isotropic conductivity; ideal dipoles; polyhedral surfaces"],
            validation={"scope": "conditional numerical investigation"},
            limitations=c["limitations"],
        ),
        values=receipt,
        provenance={"protocol": protocol().protocol.fingerprint},
        method={"id": "soma.fem-reference", "version": "1"},
        parameters=c,
        units={"distance": "mm", "current": "A*m"},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    if not (root / "native-result").exists():
        save_result(envelope, {}, root / "native-result")
    shutil.copytree(root / "native-result", output / "result")
    archive = output / "implementation"
    archive.mkdir()
    index = {}
    for name, path in {
        "source-fem_reference.py": Path("src/soma/source/fem_reference.py"),
        "source-fem_worker.py": Path("src/soma/source/fem_worker.py"),
        "experiment-fem_reference.py": Path("src/soma/experiments/fem_reference.py"),
    }.items():
        snapshot = Path("reports/milestone29/executed-sources-r2") / name
        if not snapshot.is_file():
            raise ValueError("Unique executed source snapshot required")
        target = archive / (name + ".txt")
        shutil.copyfile(snapshot, target)
        index[str(path.relative_to("src/soma"))] = dict(
            artifact=target.name, sha256=hashlib.sha256(target.read_bytes()).hexdigest()
        )
    (archive / "source-index.json").write_text(json.dumps(index, indent=2) + "\n")
    summary = dict(
        schema="soma.fem-reference.explorer/1",
        synthetic_only=True,
        human_subjects=0,
        threshold=0.1,
        protocol=protocol().protocol.fingerprint,
        receipt=receipt,
        heads=primary.to_dict("records"),
        analytical=refs,
        controls=controls,
        inverse=agg,
        mesh_audit=audit,
        source_fields=selected.to_dict("records"),
        validation_scope="independent synthetic FEM/BEM; no human or phantom accuracy",
    )
    raw = json.dumps(summary, indent=2, allow_nan=False) + "\n"
    Path("src/soma/resources/fem-reference-example-v29.json").write_text(raw)
    print(
        json.dumps(
            {
                "receipt": receipt,
                "resource_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "figures": len(list(fig.glob("*.svg"))),
            },
            indent=2,
        )
    )
    for path in fig.glob("*.svg"):
        path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    manifest = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.rglob("*")
        if p.is_file()
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def sealed_hash():
    return protocol().protocol.document()["optional_metadata"]["design_sha256"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    run(a.root, a.output)
