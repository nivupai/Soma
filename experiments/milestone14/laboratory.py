"""Synthetic adapter/ROI/retest exercise; no real preprocessing or human ICC claim."""

import json
import runpy
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.anatomy.reporting import AnatomyReport
from soma.core.provenance import sha256, write_json
from soma.experiments.fmri_simulation import simulate
from soma.fmri.audit_plots import preprocessing_figures
from soma.fmri.confounds import configure_confounds
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import contrast, fit
from soma.fmri.preprocessing_audit import audit_preprocessing, load_audited_run
from soma.fmri.reliability import cohort_reliability, regional_reliability, session_reliability
from soma.fmri.spatial import SpatialMap
from soma.imaging.nifti import load_nifti
from soma.imaging.volumes import Volume
from soma.validation.plots import save


def main() -> None:
    root = Path("reports/milestone14-laboratory")
    report = AnatomyReport(root, {"synthetic": True, "n_subjects": 10, "seed": 14042}, seed=14042)
    fixture = (root / "synthetic-source").resolve()
    fixture.mkdir()
    # The repository test fixture is explicitly synthetic; bind its orchestration hash.
    bundle = runpy.run_path("tests/fmri14/conftest.py")["bundle"].__wrapped__(fixture)
    with report.stage("preprocessing_import"):
        audit = audit_preprocessing(bundle)
        if not audit["eligible"]:
            raise ValueError(str(audit))
        run = load_audited_run(bundle, audit)
        definitions = json.loads(bundle.confound_json.read_text())
    sensitivity = []
    with report.stage("confound_sensitivity"):
        for strategy in ["minimal", "expanded", "compcor", "fd-spikes"]:
            cfg, qc = configure_confounds(run, definitions, strategy=strategy)
            fitted = fit(run, cfg)
            e = contrast(fitted, Contrast("task", {"task": 1}))
            sensitivity.append(
                {
                    "strategy": strategy,
                    "QC": qc,
                    "foreground_mean_beta": float(e.maps["effect_size"].get_fdata().mean()),
                    "rejected_voxels": e.metadata["rejected_voxels"],
                }
            )
            if strategy == "minimal":
                preprocessing_figures(root, run, fitted, load_nifti(bundle.t1), qc)
    cfg = ModelConfig(noise_model="ar1", drift_model=None, confound_columns=("motion", "trend"))
    rows = []
    paired = []
    regional = []
    first_map = None
    second_map = None
    rng = np.random.default_rng(14042)
    with report.stage("ten_subject_synthetic_cohort"):
        for index in range(10):
            beta = float(3 + rng.normal(0, 0.8))
            estimates = []
            for visit, session in enumerate(["A", "B"]):
                r, truth = simulate(
                    14242 + index * 2 + visit, beta=beta + 0.2 * visit, ar=0.3, session=session
                )
                r = replace(
                    r,
                    subject=f"synthetic{index:02}",
                    provenance={**r.provenance, "roi_ontology": "analytic-v1"},
                )
                e = contrast(fit(r, cfg), Contrast("task", {"task": 1}))
                estimates.append(e)
                rows.append(
                    {
                        "subject": r.subject,
                        "session": session,
                        "effect": float(
                            e.maps["effect_size"].get_fdata()[truth["positive"]].mean()
                        ),
                    }
                )
            paired.append(session_reliability(*estimates))
            roi = SpatialMap(
                Volume(truth["positive"].astype(np.uint8), r.mask.affine_m, "labels"),
                r.subject,
                r.space,
                "analytic region",
                {
                    "source": "entirely synthetic",
                    "atlas_name": "positive sphere-like grid region",
                    "atlas_version": "1",
                    "hemisphere_convention": "known analytic RAS origin",
                    "label_mapping": {1: "positive known-effect ROI"},
                },
            )
            regional.append(regional_reliability(*estimates, roi))
            if index == 0:
                first_map = estimates[0].maps["effect_size"].get_fdata()
                second_map = estimates[1].maps["effect_size"].get_fdata()
        population = cohort_reliability(pd.DataFrame(rows))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
    table = pd.DataFrame(rows).pivot(index="subject", columns="session", values="effect")
    for i, values in enumerate(table.to_numpy()):
        axes[0].plot([0, 1], values, alpha=0.7, label=f"synthetic{i:02}")
    axes[0].set(
        xticks=[0, 1],
        xticklabels=["A", "B"],
        ylabel="analytic positive-ROI effect",
        title="10 synthetic participants; two sessions",
    )
    axes[1].scatter(table.A, table.B)
    axes[1].set(
        xlabel="session A ROI",
        ylabel="session B ROI",
        title=f"Synthetic ICC(A,1)={population['ICC']:.3f}",
    )
    axes[2].bar([r["strategy"] for r in sensitivity], [r["rejected_voxels"] for r in sensitivity])
    axes[2].tick_params(axis="x", rotation=25)
    axes[2].set(title="Synthetic import sensitivity, not accuracy", ylabel="BH rejections")
    save(
        root,
        "cohort-ROI-sensitivity",
        fig,
        {
            "subject_session_effects": table.to_numpy(),
            "synthetic_subjects": np.array(table.index, dtype=str),
            "first_session_effect": first_map,
            "second_session_effect": second_map,
            "confound_rejections": [r["rejected_voxels"] for r in sensitivity],
        },
    )
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    for ax, data, title in zip(
        axes,
        [first_map[:, :, 3], second_map[:, :, 3], second_map[:, :, 3] - first_map[:, :, 3]],
        ["synthetic00 / A", "synthetic00 / B", "B-A: change includes noise"],
        strict=True,
    ):
        image = ax.imshow(data.T, origin="lower", cmap="coolwarm")
        fig.colorbar(image, ax=ax)
        ax.set(title=title, xlabel="native voxel i", ylabel="native voxel j")
    save(
        root,
        "session-contrast-maps",
        fig,
        {"session_A": first_map, "session_B": second_map, "difference": second_map - first_map},
    )
    write_json(root / "preprocessing-audit.json", audit)
    write_json(root / "synthetic-subject-ROI.json", rows)
    write_json(root / "session-reliability.json", paired)
    write_json(root / "regional-reliability.json", regional)
    report.finish(
        {
            "status": "complete",
            "synthetic_only": True,
            "preprocessing_audit_status": audit["status"],
            "anatomical_certification": False,
            "cohort": population,
            "confound_sensitivity": sensitivity,
            "real_human_ICC": None,
            "fixture_source_sha256": sha256(Path("tests/fmri14/conftest.py")),
            "orchestration_sha256": sha256(Path(__file__)),
        }
    )


if __name__ == "__main__":
    main()
