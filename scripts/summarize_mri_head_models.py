"""Reviewable nonidentifying aggregates only; private anatomical payloads never copied."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.anatomy.public_head_models import validate_public_head_models


def run(local, out):
    public = validate_public_head_models(json.loads((local / "public-summary.json").read_text()))
    rows = json.loads((local / "tissue-results.private.json").read_text())
    baseline = []
    for dataset, stem in [("ibsr-v2", "ibsr"), ("mrbrains13", "mrbrains")]:
        old = pd.read_csv(Path("reports/milestone12-validated") / (stem + "-metrics.csv"))
        new = pd.DataFrame(
            [
                dict(subject=r["subject"], **{k: v for k, v in t.items() if k != "boundaries"})
                for r in rows
                if r["dataset"] == dataset
                for t in r["labels"]
            ]
        )
        joined = new.merge(
            old, on=["subject", "label"], validate="one_to_one", suffixes=("_new", "_old")
        )
        metrics = [
            "Dice",
            "Jaccard",
            "ASSD_mm",
            "HD95_mm",
            "signed_volume_error_mm3",
            "absolute_volume_error_mm3",
        ]
        delta = {m: float(abs(joined[m + "_new"] - joined[m + "_old"]).max()) for m in metrics}
        baseline.append(
            dict(
                dataset=dataset,
                compared_tissue_rows=len(joined),
                max_absolute_difference=delta,
                independent_algorithm_unchanged=True,
            )
        )
        selected = np.array([r["macro_Dice"] for r in rows if r["dataset"] == dataset])
        rng = np.random.default_rng(32042)
        means = selected[rng.integers(0, len(selected), (2000, len(selected)))].mean(axis=1)
        low, high = np.quantile(means, [0.025, 0.975])
        c = next(x for x in public["cohorts"] if x["dataset"] == dataset)
        c["macro_Dice_lower"] = float(low)
        c["macro_Dice_upper"] = float(high)
    public["baseline_comparison"] = baseline
    for entry in public.get("mesh_quality", []):
        record = json.loads((local / f"geometry-{entry['level']}" / "receipt.json").read_text())
        for row, q in zip(entry["boundaries"], record["surface_checks"]["quality"], strict=True):
            row.update(
                duplicate_faces=q["duplicate_faces"],
                inconsistent_oriented_edges=q["inconsistent_oriented_edges"],
                outward_global_winding=q["outward_global_winding"],
                triangle_quality_median=q["triangle_quality_median"],
                self_intersections=q["self_intersection_check"][
                    "intersecting_or_touching_triangle_pairs"
                ]
                if q["self_intersection_check"]
                else None,
                positive_enclosed_volume=q["signed_volume_m3"] > 0,
            )
        entry["minimum_interface_separation_mm"] = (
            min(
                x["minimum_triangle_distance_m"]
                for x in record["surface_checks"]["nesting"].get("pairs", [])
            )
            * 1000
            if record["surface_checks"]["nesting"].get("pairs")
            else None
        )
    public["numerical_target_failures"] = [
        x for x in public.get("comparisons", []) if not x["passed"]
    ]
    validate_public_head_models(public)
    out.mkdir(parents=True, exist_ok=True)
    (out / "aggregate.json").write_text(json.dumps(public, indent=2, allow_nan=False) + "\n")
    pd.DataFrame(public["tissue_metrics"]).to_csv(out / "tissue-aggregate.csv", index=False)
    pd.DataFrame(public["cohorts"]).to_csv(out / "cohorts.csv", index=False)
    pd.DataFrame(public.get("comparisons", [])).to_csv(
        out / "numerical-comparisons.csv", index=False
    )
    pd.DataFrame(public.get("inverse_summary", [])).to_csv(
        out / "conditional-inverse.csv", index=False
    )
    pd.DataFrame(public.get("forward", [])).to_csv(out / "forward-QC.csv", index=False)
    (out / "M12-baseline-replication.json").write_text(json.dumps(baseline, indent=2) + "\n")
    m33 = {
        "schema": "soma.anatomical-uncertainty-inputs/1",
        "anatomical_reference_distribution_available": False,
        "baseline_status": public["anatomy_status"],
        "clinical_source_accuracy": False,
        "tissue_reference_metrics": (
            "tissue-aggregate.csv; annotation semantics differ by dataset and "
            "are not skull/scalp ground truth"
        ),
        "conductivity": {
            "brain_S_m": 0.3,
            "skull_S_m": 0.006,
            "scalp_S_m": 0.3,
            "evidence": "declared model assumptions, not participant measurements",
            "exploratory_factors": [0.5, 1, 2],
        },
        "surface_displacement_mm": {
            "values": [-1, -0.5, 0.5, 1],
            "evidence": (
                "exploratory subvoxel/voxel-scale sensitivity only; no "
                "independent conductor error distribution"
            ),
        },
        "coregistration_mm": {
            "values": [1, 3],
            "evidence": (
                "exploratory rigid translation sensitivity, not calibrated TRE; "
                "scalp residual is fit discrepancy"
            ),
        },
        "rotation_degrees": {"values": [1], "evidence": "exploratory, not measured distribution"},
        "source_domains": {
            "counts": [64, 128],
            "evidence": (
                "explicit MRI GM voxel measure in conservatively contained ROI; "
                "limited cortical coverage"
            ),
        },
        "mesh_refinement": public.get("comparisons", []),
        "inter_subject_full_head_variability": "not estimated from one curated anatomy",
        "next_study_not_executed": True,
    }
    (out / "M33-inputs.json").write_text(json.dumps(m33, indent=2) + "\n")
    fig = out / "figures"
    fig.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 10,
            "svg.hashsalt": "soma-m32-v1",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    def save(name, title):
        plt.title(title)
        plt.tight_layout()
        p = fig / (name + ".svg")
        plt.savefig(p, metadata={"Date": None})
        p.write_text("\n".join(x.rstrip() for x in p.read_text().splitlines()) + "\n")
        plt.savefig(local / (name + ".png"))
        plt.close()

    t = pd.DataFrame(public["tissue_metrics"])
    for dataset, g in t.groupby("dataset"):
        plt.plot(g.name, g.Dice, "o-", label=dataset)
    plt.ylim(0, 1)
    plt.axhline(0.8, color="black", ls="--", label="frozen research target")
    plt.ylabel("Mean Dice")
    plt.legend()
    save("01-tissue-overlap", "Known reference cohorts; unchanged independent intensity baseline")
    for dataset, g in t.groupby("dataset"):
        plt.plot(g.name, g.HD95_mm, "o-", label=dataset)
    plt.axhline(5, color="black", ls="--")
    plt.ylabel("Mean HD95 (mm)")
    plt.legend()
    save("02-boundary-errors", "Brain-tissue boundary distances, not conductor accuracy")
    for dataset, g in t.groupby("dataset"):
        plt.plot(g.name, g.signed_volume_error_mm3 / 1000, "o-", label=dataset)
    plt.axhline(0, color="black")
    plt.ylabel("Prediction minus reference (mL)")
    plt.legend()
    save("03-volume-differences", "Subject-averaged tissue volume differences")
    plt.bar(
        ["Validated", "QC only", "Not ready"],
        [0, 1, sum(c["completed"] for c in public["cohorts"])],
    )
    plt.ylabel("Cases, distinct evidence roles")
    save("04-readiness", "One MRI-derived conductor; tissue cases lack full-head evidence")
    comp = pd.DataFrame(public.get("comparisons", []))
    plt.bar(
        comp.comparison,
        comp.relative * 100,
        color=["#c35454" if not x else "#439b91" for x in comp.passed],
    )
    plt.axhline(10, color="black", ls="--")
    plt.xticks(rotation=15, ha="right")
    plt.ylabel("Unscaled field difference (%)")
    save("05-numerical-comparisons", "Common physical model comparisons; no anatomical truth")
    for q in public.get("mesh_quality", []):
        plt.scatter([q["level"]] * 3, [x["triangle_quality_min"] for x in q["boundaries"]], s=30)
    plt.axhline(0.01, color="black", ls="--")
    plt.xlabel("BEM icosahedral level")
    plt.ylabel("Minimum triangle quality")
    save("06-mesh-quality", "All attempted MRI-derived boundaries; geometric QC only")
    inv = pd.DataFrame(public.get("inverse_summary", []))
    if len(inv):
        for method, g in inv[inv.noise_V == 5e-8].groupby("method"):
            plt.plot(g.candidates, g.localization_mm, "o-", label=method)
        plt.xlabel("MRI-region candidates")
        plt.ylabel("Mean simulated peak error (mm)")
        plt.legend()
        save(
            "07-conditional-inverse",
            "Synthetic off-grid activity in real MRI-derived geometry; one head",
        )
    p = Path("src/soma/resources/mri-head-models-example-v32.json")
    p.write_text(json.dumps(public, separators=(",", ":"), allow_nan=False) + "\n")
    source_manifest = {
        str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    (out / "manifest.json").write_text(json.dumps(source_manifest, indent=2) + "\n")
    print(
        "Public aggregate and figures validated; no participant assets or "
        "input fingerprints exported"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("local", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.local, a.output)
