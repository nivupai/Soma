"""Static vector research figures from the executed frozen numerical tables."""

import json
from pathlib import Path
from typing import Any, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def figures(root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    s = pd.read_csv(root / "summary.csv")
    d = pd.read_csv(root / "forward-diagnostics.csv")
    report = json.loads((root / "summary.json").read_text())
    plt.rcParams.update(
        {
            "figure.constrained_layout.use": True,
            "font.size": 9,
            "svg.hashsalt": "soma-source-v26",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.bbox": "tight",
        }
    )
    colors = {"Tikhonov": "#0072B2", "MNE": "#D55E00", "dSPM": "#009E73"}
    files = []

    def save(fig: Any, name: str) -> None:
        fig.savefig(output / (name + ".svg"), metadata={"Date": None})
        fig.savefig(output / (name + ".pdf"), metadata={"CreationDate": None, "ModDate": None})
        fig.savefig(output / (name + ".png"), dpi=160)
        files.append(name)
        plt.close(fig)

    for families, name, label in [
        (["inner_boundary", "outer_boundary"], "boundary-displacement", "Boundary shift (mm)"),
        (["conductivity"], "conductivity", "Skull conductivity (S/m)"),
        (["electrode"], "electrode", "Electrode RMS displacement (mm)"),
        (
            ["translation", "rotation"],
            "registration",
            "Signed perturbation (mm / degrees; see panel)",
        ),
    ]:
        fig, axes = plt.subplots(
            1, len(families), figsize=(5.4 * len(families), 3.5), squeeze=False
        )
        for ax, family in zip(axes[0], families, strict=True):
            for method, color in colors.items():
                subset = s[
                    (s.family == family) & (s.method == method) & (s.noise_std_V == 5e-8)
                ].merge(d[["id", "magnitude"]], left_on="scenario", right_on="id")
                for _, pattern in subset.groupby(
                    subset.scenario.str.rsplit("-", n=1).str[-1]
                    if family == "electrode"
                    else lambda _: 0
                ):
                    pattern = pattern.sort_values("magnitude")
                    good = pattern[pattern.status == "complete"]
                    ax.plot(
                        good.magnitude,
                        good.localization_mm,
                        "o-",
                        color=color,
                        label=method if family != "electrode" or pattern is not None else None,
                        alpha=0.8,
                    )
                    ax.fill_between(
                        good.magnitude,
                        good.localization_mm_low,
                        good.localization_mm_high,
                        color=color,
                        alpha=0.08,
                    )
            invalid = d[(d.family == family) & (d.status != "computed")]
            for magnitude in sorted(invalid.magnitude.unique()):
                ax.axvline(magnitude, color="grey", ls=":", alpha=0.5)
            ax.set(title=family.replace("_", " "), xlabel=label, ylabel="Mean 3D peak error (mm)")
            handles, labels = ax.get_legend_handles_labels()
            unique = dict(zip(labels, handles, strict=True))
            ax.legend(unique.values(), unique.keys(), fontsize=8)
        fig.suptitle(
            "Synthetic four-shell head · source-cluster 95% Monte Carlo intervals · 0.05 µV noise"
        )
        save(fig, name)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    selected_ids = [
        "inner_boundary-1",
        "outer_boundary-2",
        "conductivity-0.01",
        "electrode-5-0",
        "translation-5",
        "rotation-5",
    ]
    selected = d.set_index("id").loc[selected_ids]
    axes[0].bar(range(len(selected)), selected.relative_forward_error, color="#0072B2")
    axes[0].set_xticks(
        range(len(selected)),
        ["Inner +1 mm", "Outer +2 mm", "Skull .01 S/m", "EEG RMS 5 mm", "Shift 5 mm", "Rotate 5°"],
        rotation=40,
        ha="right",
    )
    axes[0].set(ylabel="Relative Frobenius forward error", title="Explicit physical perturbations")
    singular = np.linalg.svd(
        pd.read_csv(root / "baseline-leadfield_V_per_Am.csv").to_numpy(), compute_uv=False
    )
    axes[1].semilogy(np.arange(1, len(singular) + 1), singular, "o-")
    axes[1].set(
        xlabel="Singular-value index", ylabel="V/(A m)", title="Average-reference baseline spectrum"
    )
    save(fig, "forward-matrices")
    examples = json.loads((root / "examples.json").read_text())["examples"]
    chosen = [
        e
        for e in examples
        if e["method"] == "MNE"
        and e["scenario"] in ["baseline", "conductivity-0.01", "translation-5"]
    ]
    fig, axes = plt.subplots(1, len(chosen), figsize=(4 * len(chosen), 3.5), squeeze=False)
    for ax, e in zip(axes[0], chosen, strict=True):
        xyz = np.asarray(e["grid_mm"])
        value = np.asarray(e["perturbed"]) * 1e9
        im = ax.scatter(xyz[:, 0], xyz[:, 1], c=value, cmap="viridis", s=30)
        ax.scatter(*e["truth_mm"][:2], marker="*", color="red", s=90, label="Known truth")
        ax.set(
            title=e["scenario"], xlabel="True MRI x (mm)", ylabel="True MRI y (mm)", aspect="equal"
        )
        fig.colorbar(im, ax=ax, label="Estimated vector magnitude (nA m)")
    fig.suptitle("Off-grid point-source response · XY projection, not human cortical activity")
    save(fig, "point-spread")
    # Paired effects and estimable factorial contrasts; failed cells are never imputed.
    subset = s[(s.method == "MNE") & (s.noise_std_V == 5e-8)].set_index("scenario")
    effects: list[dict[str, Any]] = []
    for bit, label in zip(
        ["1000", "0100", "0010", "0001"],
        ["boundary", "conductivity", "electrode", "registration"],
        strict=True,
    ):
        row = subset.loc["interaction-" + bit]
        effects.append(
            {"contrast": label, "effect_mm": row.excess_localization_mm, "status": row.status}
        )
    for a, b in [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]:
        ab = ["0"] * 4
        ab[a] = ab[b] = "1"
        aa = ["0"] * 4
        aa[a] = "1"
        bb = ["0"] * 4
        bb[b] = "1"
        cells: list[Any] = [subset.loc["interaction-" + "".join(x)] for x in [ab, aa, bb]]
        ok = all(x.status == "complete" for x in cells)
        contrast_value: float | None = (
            float(
                cells[0].localization_mm
                - cells[1].localization_mm
                - cells[2].localization_mm
                + cast(float, subset.at["baseline", "localization_mm"])
            )
            if ok
            else None
        )
        effects.append(
            {
                "contrast": f"interaction {a + 1}×{b + 1}",
                "effect_mm": contrast_value,
                "status": "estimable" if ok else "NOT_ESTIMABLE",
            }
        )
    pd.DataFrame(effects).to_csv(output / "interaction-contrasts.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 4))
    valid = [e for e in effects if e["effect_mm"] is not None and np.isfinite(e["effect_mm"])]
    ax.barh([e["contrast"] for e in valid], [e["effect_mm"] for e in valid], color="#0072B2")
    ax.axvline(0, color="black", lw=0.6)
    ax.set(
        xlabel="Paired mean peak-error difference / difference-in-differences (mm)",
        title="Conditional effects; failed factorial cells remain NOT_ESTIMABLE",
    )
    save(fig, "uncertainty-decomposition")
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
    axes[0].plot(
        [48, 96],
        [d.iloc[0].forward_seconds, report["dense_grid"]["forward_seconds"]],
        "o-",
        label="forward",
    )
    axes[0].plot(
        [48, 96],
        [d.iloc[0].inverse_seconds, report["dense_grid"]["inverse_seconds"]],
        "o-",
        label="three inverse kernels",
    )
    axes[0].set(
        xlabel="Candidate source locations",
        ylabel="Wall time (s)",
        title="Two fixed grid sizes; one local run",
    )
    axes[0].legend()
    axes[1].plot(
        [48, 96],
        np.array([report["baseline_leadfield_bytes"], report["dense_grid"]["leadfield_bytes"]])
        / 1024,
        "o-",
    )
    axes[1].set(
        xlabel="Candidate source locations",
        ylabel="Lead-field storage (KiB)",
        title=f"Whole-process peak: {report['process_peak_rss_mib']:.0f} MiB",
    )
    save(fig, "resource-scaling")
    return {"figures": files, "interaction_contrasts": effects}
