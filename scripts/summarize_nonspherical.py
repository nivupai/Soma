"""Publish only reviewed synthetic tables/figures from the frozen experiment."""

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

from soma.source.nonspherical import head_parameters, meshes


def run(root: Path, references: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    figures = output / "figures"
    figures.mkdir()
    rows = pd.read_csv(root / "reconstructions.csv")
    summary = pd.read_csv(root / "aggregate.csv")
    models = json.loads((root / "models.json").read_text())
    from soma.experiments.nonspherical import hierarchical

    contrasts = []
    for noise in [0.0, 5e-8, 1.5e-7]:
        paired = (
            rows[
                (rows.status == "computed")
                & np.isclose(rows.noise_std_V, noise, atol=1e-16, rtol=0)
            ]
            .groupby(["head", "source", "case", "method"])
            .localization_mm.mean()
            .unstack(["case", "method"])
        )
        for case in sorted(rows["case"].unique()):
            for a, b in [("Tikhonov", "MNE"), ("MNE", "dSPM")]:
                if (case, a) in paired and (case, b) in paired:
                    v = (
                        (paired[(case, a)] - paired[(case, b)])
                        .reindex(pd.MultiIndex.from_product([range(6), range(12)]))
                        .to_numpy()
                        .reshape(6, 12)
                    )
                    if np.isfinite(v).all():
                        mean, low, high = hierarchical(v)
                        contrasts.append(
                            dict(
                                case=case,
                                noise_std_V=noise,
                                contrast=a + " minus " + b,
                                mean_mm=mean,
                                low_mm=low,
                                high_mm=high,
                            )
                        )
        for method in ["Tikhonov", "MNE", "dSPM"]:
            keys = [
                (case, method)
                for case in ["interaction", "skull_thickness", "conductivity", "mesh-2"]
            ]
            if all(k in paired for k in keys):
                v = (
                    (paired[keys[0]] - paired[keys[1]] - paired[keys[2]] + paired[keys[3]])
                    .reindex(pd.MultiIndex.from_product([range(6), range(12)]))
                    .to_numpy()
                    .reshape(6, 12)
                )
                if np.isfinite(v).all():
                    mean, low, high = hierarchical(v)
                    contrasts.append(
                        dict(
                            case="thickness x conductivity",
                            noise_std_V=noise,
                            contrast=method,
                            mean_mm=mean,
                            low_mm=low,
                            high_mm=high,
                        )
                    )
    pd.DataFrame(contrasts).to_csv(output / "paired-contrasts.csv", index=False)

    for name in [
        "aggregate.csv",
        "per-head.csv",
        "per-source.csv",
        "models.json",
        "receipt.json",
        "protocol.json",
    ]:
        shutil.copyfile(root / name, output / name)
    for h in range(6):
        dest = output / f"head-{h}"
        dest.mkdir()
        for name in [
            "truth_m.csv",
            "moments_Am.csv",
            "sensors_m.csv",
            "fine_candidate_V_per_Am.csv",
            "truth_V_per_Am.csv",
            "measurements_V.csv",
            "identities.json",
            "convergence.json",
            "independent-control.json",
        ]:
            shutil.copyfile(root / f"head-{h}" / name, dest / name)
        rows[rows["head"] == h].to_csv(
            dest / "reconstructions.csv", index=False, float_format="%.17g"
        )
    shutil.copytree(root / "result", output / "result")
    shutil.copyfile(references / "references.json", output / "references.json")
    refs = json.loads((references / "references.json").read_text())
    plt.rcParams.update(
        {
            "svg.hashsalt": "soma-m27",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    def save(name, fig):
        fig.tight_layout()
        fig.savefig(
            figures / (name + ".svg"), metadata={"Date": None, "Creator": "Soma synthetic M27"}
        )
        fig.savefig(root / (name + ".png"), dpi=160)
        plt.close(fig)
        p = figures / (name + ".svg")
        p.write_text("\n".join(line.rstrip() for line in p.read_text().splitlines()) + "\n")

    fig, axs = plt.subplots(2, 3, figsize=(12, 7))
    for h, ax in enumerate(axs.flat):
        for j, m in enumerate(meshes(head_parameters(h), 1)):
            tri = m.vertices.xyz[m.faces] * 1000
            for t in tri:
                ax.plot(
                    t[[0, 1, 2, 0], 0],
                    t[[0, 1, 2, 0], 2],
                    lw=0.3,
                    alpha=0.4,
                    color=plt.cm.viridis(j / 3),
                )
        ax.set(
            title=f"Head {h}: {head_parameters(h)['family']}",
            xlabel="MRI x (mm)",
            ylabel="MRI z (mm)",
            aspect="equal",
        )
    fig.suptitle("Six independent generated heads · XZ projection · display mesh L1")
    save("01-geometry", fig)
    fine = [m for m in models if m["case"] == "truth"]
    base = [m for m in models if m["case"].startswith("mesh-") and m["status"] == "computed"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for h in range(6):
        ms = [m for m in base if m["head"] == h] + [fine[h]]
        axs[0].plot(
            [m["level"] for m in ms],
            [min(q["triangle_quality_min"] for q in m["geometry"]["quality"]) for m in ms],
            "-o",
            label=f"Head {h}",
        )
        axs[1].plot(
            [m["level"] for m in ms], [m["geometry"]["minimum_thickness_mm"] for m in ms], "-o"
        )
    axs[0].set(
        xlabel="Subdivision level",
        ylabel="Minimum triangle quality (1)",
        title="Four interfaces; one curve/head",
    )
    axs[1].set(xlabel="Subdivision level", ylabel="Minimum tissue thickness (mm)")
    axs[0].legend(ncol=2)
    save("02-quality", fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    for h in range(6):
        cv = json.loads((root / f"head-{h}/convergence.json").read_text())
        ax.semilogy([20, 80, 320], cv["errors"], "-o", label=f"Head {h}: {cv['status']}")
    ax.axhline(0.05, ls="--", color="k", label="Frozen 5% threshold")
    ax.set(
        xlabel="Triangles/interface (finest reference: 1280)",
        ylabel="Relative Frobenius field error (1)",
        title="Whole-model convergence includes sensor projection",
    )
    ax.legend(fontsize=8)
    save("03-forward-convergence", fig)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    for ref in sorted({r["reference"] for r in refs["rows"]}):
        rs = [r for r in refs["rows"] if r["reference"] == ref]
        axs[0].semilogy([r["level"] for r in rs], [r["error"] for r in rs], "-o", label=ref)
    controls = [
        json.loads((root / f"head-{h}/independent-control.json").read_text()) for h in range(6)
    ]
    axs[1].bar(range(6), [r.get("relative_error", np.nan) for r in controls])
    axs[1].axhline(0.1, color="r", ls="--")
    axs[0].set(
        xlabel="Mesh level", ylabel="Relative field error (1)", title="Level A: limiting references"
    )
    axs[0].legend(fontsize=7)
    axs[1].set(
        xlabel="Independent synthetic head",
        ylabel="Relative field difference (1)",
        title="Level C: matched THREE layers only, L2",
    )
    save("04-independent-references", fig)

    def selected(noise=5e-8):
        return summary[np.isclose(summary.noise_std_V, noise, atol=1e-16, rtol=0)]

    fig, ax = plt.subplots(figsize=(7, 4))
    for method in ["Tikhonov", "MNE", "dSPM"]:
        d = selected()
        d = (
            d[(d.method == method) & d["case"].isin(["mesh-0", "mesh-1", "mesh-2"])]
            .set_index("case")
            .reindex(["mesh-0", "mesh-1", "mesh-2"])
        )
        ax.errorbar(
            range(3),
            d.localization_mm,
            yerr=[
                d.localization_mm - d.localization_mm_low,
                d.localization_mm_high - d.localization_mm,
            ],
            label=method,
            marker="o",
            capsize=3,
        )
    ax.set(
        xlabel="Estimated mesh level",
        ylabel="Peak localization error (mm)",
        title="72 sources / six heads · 0.05 µV noise · conditional 95% intervals",
    )
    ax.legend()
    save("05-localization-mesh", fig)
    fig, ax = plt.subplots(figsize=(11, 5))
    names = [
        "mesh-2",
        "skull_shift",
        "skull_thickness",
        "csf_boundary",
        "local_skull",
        "electrode",
        "registration",
        "conductivity",
        "interaction",
        "sphere-control",
    ]
    for mi, method in enumerate(["Tikhonov", "MNE", "dSPM"]):
        d = selected()
        d = d[d.method == method].set_index("case").reindex(names)
        ax.plot(np.arange(len(names)) + (mi - 1) * 0.1, d.localization_mm, "-o", label=method)
    ax.set(
        xticks=range(len(names)),
        xticklabels=names,
        ylabel="Peak localization error (mm)",
        title="72 paired sources · six heads · 0.05 µV noise; sphere control newly generated",
    )
    ax.tick_params(axis="x", rotation=35)
    ax.legend()
    save("06-localization-perturbation", fig)
    explorer = json.loads((root / "explorer.json").read_text())
    fig, axs = plt.subplots(1, 3, figsize=(12, 4))
    e = explorer["heads"][0]
    grid = np.asarray(e["grid_mm"])
    for ax, method in zip(axs, ["Tikhonov", "MNE", "dSPM"], strict=True):
        amp = np.asarray(e["estimates"][method])
        ax.scatter(
            grid[:, 0], grid[:, 1], s=10 + 250 * amp / amp.max(), c=amp / amp.max(), cmap="viridis"
        )
        ax.scatter(*np.asarray(e["truth_mm"])[:2], marker="+", c="r", s=150)
        ax.set(
            xlabel="MRI x (mm)",
            ylabel="MRI y (mm)",
            title=method + " · own normalized scale",
            aspect="equal",
        )
    fig.suptitle(
        "Visualization example: head 0, off-grid source 0, noiseless L2 · no human inference"
    )
    save("07-source-distribution", fig)
    fig, ax = plt.subplots(figsize=(10, 4))
    failure = (
        rows.assign(failed=rows.status != "computed")
        .groupby(["head", "case"])
        .failed.mean()
        .unstack()
        .reindex(columns=names[:-1] + ["mesh-0", "mesh-1", "sphere-control"])
    )
    im = ax.imshow(failure.to_numpy(), vmin=0, vmax=1, cmap="Reds", aspect="auto")
    fig.colorbar(im, ax=ax, label="Fraction failed planned reconstructions (1)")
    ax.set(
        yticks=range(6),
        ylabel="Independent generated head",
        xticks=range(len(failure.columns)),
        xticklabels=failure.columns,
        title="Every planned configuration retained; no outcome filtering",
    )
    ax.tick_params(axis="x", rotation=35)
    save("08-failures", fig)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    for method in ["Tikhonov", "MNE", "dSPM"]:
        d = selected()
        d = d[d.method == method].set_index("case")
        vals = [
            d.loc[n, "excess_mm"]
            for n in ["mesh-0", "mesh-1", "skull_thickness", "conductivity", "interaction"]
        ]
        axs[0].plot(range(5), vals, "-o", label=method)
        interaction = (
            d.loc["interaction", "localization_mm"]
            - d.loc["skull_thickness", "localization_mm"]
            - d.loc["conductivity", "localization_mm"]
            + d.loc["mesh-2", "localization_mm"]
        )
        axs[1].bar(method, interaction)
    axs[0].set(
        xticks=range(5),
        xticklabels=["L0", "L1", "thickness", "sigma", "joint"],
        ylabel="Paired excess peak error vs L2 (mm)",
        title="Conditional six-head/source mean",
    )
    axs[0].legend()
    axs[1].set(
        ylabel="Difference of paired differences (mm)", title="Thickness × conductivity interaction"
    )
    axs[1].axhline(0, color="k", lw=0.5)
    save("09-attribution", fig)
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for h in range(6):
        ms = [m for m in base if m["head"] == h] + [fine[h]]
        ds = [m.get("diagnostics", m) for m in ms]
        axs[0].semilogy(
            [m["level"] for m in ms], [d["runtime_seconds"] for d in ds], "-o", label=f"Head {h}"
        )
        axs[1].plot([m["level"] for m in ms], [d["process_peak_rss_mib"] for d in ds], "-o")
    axs[0].set(
        xlabel="Mesh level",
        ylabel="Isolated assembly/solve seconds",
        title="Per-head forward call (excludes controller QC)",
    )
    axs[0].legend(ncol=2, fontsize=8)
    axs[1].set(
        xlabel="Mesh level",
        ylabel="Child process peak RSS (MiB)",
        title="Imports included; not matrix allocation alone",
    )
    save("10-cost", fig)
    # Display discretizations are separately labeled and never substituted in analysis.
    for e in explorer["heads"]:
        e["display_meshes"] = {
            str(level): [
                dict(xyz_mm=(m.vertices.xyz * 1000).tolist(), faces=m.faces.tolist())
                for m in meshes(head_parameters(e["head"]), level)
            ]
            for level in range(3)
        }
    explorer.update(synthetic_only=True, human_subjects=0)
    packaged = Path("src/soma/resources/nonspherical-example-v27.json")
    packaged.write_text(json.dumps(explorer, separators=(",", ":")) + "\n")
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
                packaged_sha256=hashlib.sha256(packaged.read_bytes()).hexdigest(),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--references", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.root, a.references, a.output)
