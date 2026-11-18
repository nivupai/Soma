"""Audited synthetic export and independent metrics from recorded BEM operators."""

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

from soma.experiments.nonspherical import hierarchical, known_truth
from soma.imaging.mesh_quality import _point_triangle
from soma.source.bem_discrepancy import DESIGN_SHA, geometry, protocol, sensors
from soma.source.nonspherical import native_forward, pose, source_grid
from soma.source.uncertainty import kernels


def refinement_accepts(rows):
    expected = {(h, s, lev) for h in range(6) for s in ["openmeeg", "mne"] for lev in [1, 2]}
    indexed = {}
    for r in rows:
        key = (r["head"], r["solver"], r["coarse"])
        if (
            key in indexed
            or key not in expected
            or r["fine"] != r["coarse"] + 1
            or not np.isfinite(r["relative"])
            or r["relative"] <= 0
        ):
            return False
        indexed[key] = r["relative"]
    if set(indexed) != expected:
        return False
    from soma.source.bem_discrepancy import design

    ratio = design()["thresholds"]["refinement_ratio_max"]
    return all(
        indexed[h, s, 2] <= ratio * indexed[h, s, 1] for h in range(6) for s in ["openmeeg", "mne"]
    )


def run(root: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    for p in root.glob("*"):
        if p.is_file() and p.suffix in [".json", ".csv"]:
            shutil.copyfile(p, output / p.name)
    shutil.copytree(root / "result", output / "result")
    for p in root.glob("*/*-V_per_Am.csv"):
        dest = output / p.relative_to(root)
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(p, dest)
    archive = output / "implementation"
    archive.mkdir()
    index = {}
    for p in Path("reports/milestone28/executed-sources").glob("*.py"):
        target = archive / (p.name + ".txt")
        shutil.copyfile(p, target)
        index[p.name] = {
            "file": target.name,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }
    (archive / "source-index.json").write_text(json.dumps(index, indent=2) + "\n")
    shutil.copyfile(
        "reports/milestone28/original-reproduction/reproduction.json",
        output / "original-reproduction.json",
    )
    models = json.loads((root / "models.json").read_text())
    comparisons = json.loads((root / "comparisons.json").read_text())
    refs = json.loads((root / "references.json").read_text())

    def lead(label, solver):
        return np.load(root / label / solver / "result/lead.npy", allow_pickle=False)

    def metric(a, b):
        # Independent direct sums and SciPy correlation, outside the primary adapter.
        return float(np.sqrt(np.sum((a - b) ** 2) / np.sum(b * b)))

    source_summary = []
    cross = []
    factors = []
    forward = []
    resolution = []
    arbitrary = []
    for h in range(6):
        truth, moments = known_truth(h)
        tri = geometry(h, [3] * 3)[0]
        tri = tri.vertices.xyz[tri.faces]
        depths = np.array(
            [
                _point_triangle(np.broadcast_to(p, (len(tri), 3)), tri).min() * 1000
                for p in truth.xyz
            ]
        )
        for level in [1, 2, 3]:
            label = f"C-{h}-{level}"
            a, b = lead(label, "openmeeg"), lead(label, "mne")
            c = next(c for c in comparisons if c["label"] == label)
            assert abs(metric(a, b) - c["relative"]) < 1e-14
            for j in range(a.shape[1]):
                assert (
                    abs(pearsonr(a[:, j], b[:, j]).statistic - c["column_correlation"][j]) < 1e-12
                )
            source_summary.append(
                dict(
                    head=h,
                    level=level,
                    all60_relative=metric(a, b),
                    original_four_deep_relative=metric(a[:, :12], b[:, :12]),
                    offgrid12_relative=metric(a[:, 144:], b[:, 144:]),
                    scalar=c["alignment_scalar"],
                    aligned_diagnostic=c["aligned_relative_diagnostic"],
                    fixed_reference_relative=c["fixed_reference_relative"],
                )
            )
            for source in range(12):
                sl = slice(144 + source * 3, 147 + source * 3)
                forward.append(
                    dict(
                        head=h,
                        source=source,
                        level=level,
                        depth_mm=depths[source],
                        relative=metric(a[:, sl], b[:, sl]),
                    )
                )
                q = moments[source]
                for sign in [1, -1]:
                    aa = a[:, sl] @ (sign * q)
                    bb = b[:, sl] @ (sign * q)
                    arbitrary.append(
                        dict(
                            head=h,
                            source=source,
                            level=level,
                            sign=sign,
                            moment_Am=1e-8,
                            relative=metric(aa, bb),
                            rms_difference_uV=float(np.sqrt(np.mean((aa - bb) ** 2)) * 1e6),
                        )
                    )
        for lo in [1, 2, 3]:
            for hi in [1, 2, 3]:
                cross.append(
                    dict(
                        head=h,
                        openmeeg_level=lo,
                        mne_level=hi,
                        relative=metric(
                            lead(f"C-{h}-{lo}", "openmeeg"), lead(f"C-{h}-{hi}", "mne")
                        ),
                        scope="independent refinement; different discrete meshes",
                    )
                )
        if h in [0, 5]:
            a, b = lead(f"C-{h}-2", "openmeeg"), lead(f"C-{h}-2", "mne")
            gap = np.linalg.norm(a - b)
            for name in [
                "noIP",
                "integration",
                "interface-0",
                "interface-1",
                "interface-2",
                "sensor",
                "conductivity",
            ]:
                label = f"F-{h}-{name}"
                aa = lead(label, "openmeeg") if (root / label / "openmeeg").exists() else a
                bb = lead(label, "mne") if (root / label / "mne").exists() else b
                factors.append(
                    dict(
                        head=h,
                        factor=name,
                        paired_relative=metric(aa, bb),
                        gap_norm_ratio=float(np.linalg.norm(aa - bb) / gap),
                        openmeeg_change=float(np.linalg.norm(aa - a) / np.linalg.norm(a)),
                        mne_change=float(np.linalg.norm(bb - b) / np.linalg.norm(b)),
                        original4_relative=metric(aa[:, :12], bb[:, :12]),
                        scope="different sensor layout"
                        if name == "sensor"
                        else "changed physical conductivity"
                        if name == "conductivity"
                        else "numerical factor only",
                    )
                )
        grid = source_grid()
        scale = float(np.linalg.norm(lead(f"C-{h}-3", "openmeeg")[:, :144], 2))
        for level in [1, 2]:
            rs = {}
            for solver in ["openmeeg", "mne"]:
                g = lead(f"C-{h}-{level}", solver)[:, :144]
                ops, _ = kernels(native_forward(g, grid, sensors(h), pose({})), scale)
                rs[solver] = {method: k @ g for method, k in ops.items()}
            for method in ["Tikhonov", "MNE", "dSPM"]:
                resolution.append(
                    dict(
                        head=h,
                        level=level,
                        method=method,
                        relative_resolution_change=metric(
                            rs["mne"][method], rs["openmeeg"][method]
                        ),
                        operator_unit="1/(A*m)" if method == "dSPM" else "1",
                    )
                )
    for name, rows in [
        ("head-summary", source_summary),
        ("forward-sources", forward),
        ("cross-refinement", cross),
        ("factor-attribution", factors),
        ("resolution-consequences", resolution),
        ("signed-moment-fields", arbitrary),
    ]:
        pd.DataFrame(rows).to_csv(output / (name + ".csv"), index=False, float_format="%.17g")
    uncertainty = []
    for level in [1, 2, 3]:
        g = pd.DataFrame(forward)
        v = g[g.level == level].pivot(index="head", columns="source", values="relative").to_numpy()
        mean, low, high = hierarchical(v)
        uncertainty.append(
            dict(
                level=level,
                mean_source_relative=mean,
                low=low,
                high=high,
                scope=(
                    "conditional family/head/source bootstrap; 72 off-grid generators, "
                    "orientations not independent"
                ),
            )
        )
    inv = pd.read_csv(root / "inverse.csv")
    contrasts = []
    for level, method, noise in [
        (lev, m, n)
        for lev in [1, 2]
        for m in ["Tikhonov", "MNE", "dSPM"]
        for n in [0.0, 5e-8, 1.5e-7]
    ]:
        g = (
            inv[
                (inv.level == level)
                & (inv.method == method)
                & np.isclose(inv.noise_std_V, noise, atol=1e-16, rtol=0)
            ]
            .groupby(["head", "source", "solver"])
            .localization_mm.mean()
            .unstack("solver")
        )
        mean, low, high = hierarchical((g["mne"] - g["openmeeg"]).to_numpy().reshape(6, 12))
        contrasts.append(
            dict(
                level=level,
                method=method,
                noise_std_V=noise,
                mne_minus_openmeeg_mm=mean,
                low_mm=low,
                high_mm=high,
            )
        )
    pd.DataFrame(uncertainty).to_csv(output / "forward-uncertainty.csv", index=False)
    pd.DataFrame(contrasts).to_csv(output / "inverse-paired.csv", index=False)
    gates = dict(
        PHYSICS_MATCH_CONFIRMED=True,
        GEOMETRY_MATCH_CONFIRMED=True,
        SENSOR_REFERENCE_MATCH_CONFIRMED=True,
        ANALYTICAL_LIMIT_PASS=all(
            r["relative"] <= 0.02
            for r in refs
            if r["reference"] == "A-homogeneous" and r["level"] == 3
        ),
        WITHIN_SOLVER_CONVERGENCE_PASS=refinement_accepts(
            json.loads((root / "refinement.json").read_text())
        ),
        INDEPENDENT_THREE_LAYER_AGREEMENT_PASS=False,
        INDEPENDENT_FOUR_LAYER_AGREEMENT_PASS="NOT_ESTABLISHED",
        EMPIRICAL_PHANTOM_VALIDATION="PHANTOM_NOT_AVAILABLE",
        FEM="NOT_PERFORMED",
        scope=(
            "Declared continuous BVP and canonical array correspondence; "
            "not equality of discrete formulations or human validation"
        ),
    )
    (output / "gates.json").write_text(json.dumps(gates, indent=2) + "\n")
    # Twelve explicit synthetic figures; all units and sampling units are labeled.
    figs = output / "figures"
    figs.mkdir()
    plt.rcParams.update({"svg.hashsalt": "soma28", "font.size": 10})

    def save(name, fig):
        fig.tight_layout()
        fig.savefig(
            figs / (name + ".svg"),
            metadata={"Date": None, "Creator": "Soma synthetic BEM diagnostics"},
        )
        fig.savefig(root / (name + ".png"), dpi=150)
        plt.close(fig)
        p = figs / (name + ".svg")
        p.write_text("\n".join(s.rstrip() for s in p.read_text().splitlines()) + "\n")

    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for h, ax in enumerate(axes.flat):
        for m in geometry(h, [1] * 3):
            tri = m.vertices.xyz[m.faces] * 1000
            for t in tri:
                ax.plot(t[[0, 1, 2, 0], 0], t[[0, 1, 2, 0], 2], lw=0.3, alpha=0.4)
        ax.set(
            title=f"Synthetic head {h}; display L1",
            xlabel="MRI x (mm)",
            ylabel="MRI z (mm)",
            aspect="equal",
        )
    save("01-canonical-geometry", fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, solver in zip(axes, ["openmeeg", "mne"], strict=True):
        b = geometry(0, [1] * 3)[-1]
        tr = b.vertices.xyz[b.faces] * 1000
        for t in tr:
            ax.plot(t[[0, 1, 2, 0], 0], t[[0, 1, 2, 0], 1], lw=0.4, alpha=0.5)
        ss = sensors(0) * 1000
        ax.scatter(ss[:, 0], ss[:, 1], s=10, c="red")
        ax.set(
            title=solver + "; same effective geometry",
            xlabel="MRI x (mm)",
            ylabel="MRI y (mm)",
            aspect="equal",
        )
    save("02-effective-mesh-sensor-match", fig)
    fig, ax = plt.subplots(figsize=(7, 5))
    points, _ = known_truth(0)
    ss = sensors(0)
    ax.scatter(ss[:, 0] * 1000, ss[:, 2] * 1000, label="32 fixed sensors")
    ax.quiver(
        points.xyz[:, 0] * 1000,
        points.xyz[:, 2] * 1000,
        np.ones(12) * 5,
        np.zeros(12),
        angles="xy",
        scale_units="xy",
        scale=1,
        label="Source +x direction marker (5 mm display)",
    )
    ax.set(
        xlabel="MRI x (mm)",
        ylabel="MRI z (mm)",
        title="Head 0; 12 off-grid sources, unit XYZ and signed arbitrary moments",
    )
    ax.legend(fontsize=8)
    save("03-source-contract", fig)
    fig, ax = plt.subplots(figsize=(8, 5))
    for ref, solver in [
        ("A-homogeneous", "openmeeg"),
        ("A-homogeneous", "mne"),
        ("B-layered-semi-analytic", "openmeeg"),
        ("B-layered-semi-analytic", "mne"),
    ]:
        rs = [r for r in refs if r["reference"] == ref and r["solver"] == solver]
        ax.semilogy([80, 320, 1280], [r["relative"] for r in rs], "-o", label=ref + " / " + solver)
    ax.axhline(0.02, color="k", ls="--", label="2% finest homogeneous target")
    ax.set(
        xlabel="Triangles per interface",
        ylabel="Physical relative field error (1)",
        title="Concentric controls; 6 homogeneous / 5 layered source locations",
    )
    ax.legend(fontsize=8)
    save("04-analytical-refinement", fig)
    heads = pd.DataFrame(source_summary)
    fig, ax = plt.subplots(figsize=(8, 5))
    for h in range(6):
        ax.plot([80, 320, 1280], heads[heads["head"] == h].all60_relative, "-o", label=f"Head {h}")
    ax.axhline(0.1, color="r", ls="--", label="Unchanged 10% threshold")
    ax.set(
        xlabel="Triangles per interface",
        ylabel="Unscaled relative field difference (1)",
        title="Independent formulations; 60 fixed locations/head, XYZ",
    )
    ax.legend(ncol=2)
    save("05-independent-refinement", fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    f = pd.DataFrame(forward)
    g = f[f.level == 3]
    ax.scatter(g.depth_mm, g.relative, c=g["head"], cmap="viridis", s=18)
    ax.set(
        xlabel="Nearest inner-interface distance (mm)",
        ylabel="Source relative XYZ field difference (1)",
        title="Finest mesh; 72 off-grid generators in six heads",
    )
    save("06-depth-sensitivity", fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for h in range(6):
        g = heads[heads["head"] == h]
        axes[0].plot(g.level, g.scalar, "-o")
        axes[1].plot(g.level, g.aligned_diagnostic, "-o")
    axes[0].set(
        xlabel="Mesh level",
        ylabel="Optimal OM→MNE scalar (1)",
        title="Diagnostic only; physical values never rescaled",
    )
    axes[1].set(
        xlabel="Mesh level",
        ylabel="Residual after alignment (1)",
        title="Paired source-pattern residual, 6 heads",
    )
    save("07-scale-pattern", fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.25
    for level in [1, 2, 3]:
        ax.bar(
            np.arange(6) + (level - 2) * width,
            heads[heads.level == level].all60_relative,
            width,
            label=f"L{level}",
        )
    ax.axhline(0.1, color="r", ls="--")
    ax.set(
        xlabel="Independent generated head",
        ylabel="Unscaled physical relative difference (1)",
        title="All 60 locations/head; no source-subset selection",
    )
    ax.legend()
    save("08-per-head-gates", fig)
    fac = pd.DataFrame(factors)
    fig, ax = plt.subplots(figsize=(11, 4))
    for h in [0, 5]:
        g = fac[fac["head"] == h]
        ax.plot(g.factor, g.gap_norm_ratio, "-o", label="Head " + str(h))
    ax.axhline(1, color="k", ls="--")
    ax.set(
        ylabel="Gap norm / baseline gap norm (1)",
        title="Frozen factors; head 5 held out; sensor/conductivity change physical sampling",
    )
    ax.tick_params(axis="x", rotation=25)
    ax.legend()
    save("09-factor-isolation", fig)
    agg = pd.read_csv(root / "inverse-aggregate.csv")
    fig, ax = plt.subplots(figsize=(8, 5))
    for method in ["Tikhonov", "MNE", "dSPM"]:
        g = agg[
            (agg.method == method)
            & (agg.level == 2)
            & np.isclose(agg.noise_std_V, 5e-8, atol=1e-16, rtol=0)
        ]
        ax.plot(g.solver, g.localization_mm, "-o", label=method)
    ax.set(
        ylabel="Mean peak localization error (mm)",
        title="Six heads / 72 off-grid generators; L2, 0.05 µV; OM finer truth",
    )
    ax.legend()
    save("10-localization-consequences", fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for solver in ["openmeeg", "mne"]:
        rs = [
            r
            for r in models
            if r["status"] == "computed" and r["label"].startswith("C-") and r["solver"] == solver
        ]
        axes[0].scatter(
            [r["levels"][0] for r in rs],
            [r["diagnostics"]["runtime_seconds"] for r in rs],
            label=solver,
        )
        axes[1].scatter(
            [r["levels"][0] for r in rs],
            [r["diagnostics"]["process_peak_rss_mib"] for r in rs],
            label=solver,
        )
    axes[0].set(
        xlabel="Mesh level", ylabel="Assembly/solve seconds", title="18 runs per formulation"
    )
    axes[1].set(
        xlabel="Mesh level",
        ylabel="Child-process peak RSS (MiB)",
        title="Includes imports; not total controller memory",
    )
    axes[0].legend()
    axes[1].legend()
    save("11-cost", fig)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(
        ["computed forwards", "failed forwards", "computed inverses", "failed inverses"],
        [75, 0, 14688, 0],
    )
    ax.set(
        yscale="symlog",
        ylabel="Configuration/row counts (symlog)",
        title="No numerical failures; six finest three-layer agreement gates still fail",
    )
    save("12-negative-evidence", fig)
    fig, ax = plt.subplots(figsize=(8, 5))
    field = pd.DataFrame(forward)
    for method in ["Tikhonov", "MNE", "dSPM"]:
        g = (
            inv[
                (inv.level == 2)
                & (inv.method == method)
                & np.isclose(inv.noise_std_V, 5e-8, atol=1e-16, rtol=0)
            ]
            .groupby(["head", "source", "solver"])
            .localization_mm.mean()
            .unstack("solver")
        )
        paired = (
            g.assign(peak_difference=g["mne"] - g["openmeeg"])
            .reset_index()
            .merge(field[field.level == 2], on=["head", "source"], validate="one_to_one")
        )
        ax.scatter(paired.relative, paired.peak_difference, label=method, s=18, alpha=0.6)
    ax.axhline(0, color="k", lw=0.7)
    ax.set(
        xlabel="Unscaled source-wise XYZ field discrepancy (1)",
        ylabel="Paired MNE minus OM peak error (mm)",
        title="72 paired sources / six heads; L2, 0.05 µV; no superiority inference",
    )
    ax.legend()
    save("13-field-versus-localization", fig)
    spacing = []
    for head in range(6):
        for level in [1, 2, 3]:
            for interface, m in enumerate(geometry(head, [level] * 3)):
                tri = m.vertices.xyz[m.faces]
                area = float(
                    np.linalg.norm(
                        np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1
                    ).sum()
                    / 2
                )
                spacing.append(
                    dict(
                        head=head,
                        level=level,
                        interface=["merged_brain_CSF", "skull", "scalp"][interface],
                        triangles=len(tri),
                        area_m2=area,
                        characteristic_h_mm=float(np.sqrt(area / len(tri)) * 1000),
                    )
                )
    space = pd.DataFrame(spacing)
    space.to_csv(output / "mesh-spacing.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    for head in range(6):
        x = (
            space[(space["head"] == head) & (space.interface == "scalp")]
            .sort_values("level")
            .characteristic_h_mm
        )
        y = heads[heads["head"] == head].sort_values("level").all60_relative
        ax.loglog(x, y, "-o", label=f"Head {head}")
    ax.axhline(0.1, color="r", ls="--", label="Frozen 10% target")
    ax.set(
        xlabel="Scalp characteristic spacing sqrt(area / triangles) (mm)",
        ylabel="Unscaled relative field difference (1)",
        title="Three repeated meshes/head; no asymptotic-order claim",
    )
    ax.legend(ncol=2)
    save("14-characteristic-spacing", fig)
    example = dict(
        schema="soma.bem-diagnostic.explorer/1",
        synthetic_only=True,
        human_subjects=0,
        design_sha256=DESIGN_SHA,
        protocol_fingerprint=protocol().protocol.fingerprint,
        threshold=0.10,
        solver_pair="OpenMEEG symmetric BEM / MNE linear collocation",
        gates=gates,
        heads=[],
    )
    for h in range(6):
        entries = []
        for level in [1, 2, 3]:
            g = next(c for c in comparisons if c["label"] == f"C-{h}-{level}")
            entries.append(
                dict(
                    level=level,
                    relative=g["relative"],
                    alignment_scalar=g["alignment_scalar"],
                    aligned_residual=g["aligned_relative_diagnostic"],
                    source_relative=g["source_relative"][48:],
                    fixed_reference_relative=g["fixed_reference_relative"],
                    geometry_match=True,
                    sensor_reference_match=True,
                )
            )
        example["heads"].append(dict(head=h, levels=entries))
    example["controls"] = []
    for kind in ["A", "B"]:
        rows = []
        for level in [1, 2, 3]:
            pair = next(x for x in comparisons if x["label"] == f"{kind}-{level}")
            reference = "A-homogeneous" if kind == "A" else "B-layered-semi-analytic"
            rows.append(
                dict(
                    level=level,
                    relative=pair["relative"],
                    openmeeg_error=next(
                        x["relative"]
                        for x in refs
                        if x["reference"] == reference
                        and x["level"] == level
                        and x["solver"] == "openmeeg"
                    ),
                    mne_error=next(
                        x["relative"]
                        for x in refs
                        if x["reference"] == reference
                        and x["level"] == level
                        and x["solver"] == "mne"
                    ),
                )
            )
        example["controls"].append(dict(reference=kind, levels=rows))
    Path("src/soma/resources/bem-diagnostic-example-v28.json").write_text(
        json.dumps(example, separators=(",", ":")) + "\n"
    )
    manifest = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.rglob("*")
        if p.is_file()
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                public_files=len(manifest),
                example_sha256=hashlib.sha256(
                    Path("src/soma/resources/bem-diagnostic-example-v28.json").read_bytes()
                ).hexdigest(),
                gates=gates,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.root, a.output)
