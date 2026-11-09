"""Audit private results and publish only aggregate numerical/software evidence."""

import hashlib
import json
import time
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np

from soma.core.provenance import sha256
from soma.fmri.design import Contrast
from soma.fmri.ingestion import select_run
from soma.fmri.workflows import analyze, configuration, freeze_check
from soma.pipeline.cache import source_hash
from soma.simulations.calibration import atomic_json
from soma.validation.plots import save


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    freeze_check()
    ledger = read(Path("data/derived/milestone13/baseline-ledger.json"))
    for group in ["tests", "reports"]:
        for path, expected in ledger[group].items():
            assert sha256(Path(path)) == expected, (group, path)
    source = source_hash()
    assert source == Path("data/derived/milestone13/final-source.sha256").read_text().strip()
    report_hash = hashlib.sha256(
        b"".join(str(p).encode() + p.read_bytes() for p in sorted(Path("src/soma").rglob("*.py")))
    ).hexdigest()
    roots = [
        Path("reports/milestone13-" + label)
        for label in ["spm", "synthetic", "supplemental", "contrast-cli"]
    ]
    files = 0
    arrays = 0
    figures = 0
    for root in roots + [roots[1] / "primary"]:
        m = read(root / "manifest.json")
        assert m["source_tree_sha256"] == report_hash
        if m["source"].get("input_sha256"):
            assert sha256(Path(m["source"]["source"])) == m["source"]["input_sha256"]
        for relative, expected in m["outputs_sha256"].items():
            assert sha256(root / relative) == expected, (root, relative)
            files += 1
        for path in root.glob("*.npz"):
            with np.load(path, allow_pickle=False) as values:
                for key in values.files:
                    a = values[key]
                    assert a.dtype.kind != "O"
                    if a.dtype.kind in "fci":
                        assert np.isfinite(a).all(), path
                    arrays += 1
        figures += len(list(root.glob("*.png")))
    spm = read(roots[0] / "summary.json")
    lab = read(roots[1] / "summary.json")
    supp = read(roots[2] / "summary.json")
    assert all(x["status"] == "complete" for x in [spm, lab, supp])
    assert spm["source_tree_sha256"] == source and supp["source_tree_sha256"] == source
    assert spm["design"]["rank"] == 15 and spm["design"]["residual_dof"] == 69
    assert spm["validated_preprocessing_claimed"] is False
    assert lab["oracle"]["max_effect_error"] < 1e-7 and supp["spatial_oracle_max_error"] < 1e-10
    for name in [
        "effect_size",
        "effect_variance",
        "stat",
        "z_score",
        "fdr_reject",
        "p_two_sided",
        "q_bh",
    ]:
        original = next((roots[0] / "soma-reports").glob("*_" + name + ".nii.gz"))
        repeated = next((roots[3] / "soma-reports").glob("*_" + name + ".nii.gz"))
        reviewed = next(
            Path("reports/milestone13-spm-diagnostic-review/soma-reports").glob(
                "*_" + name + ".nii.gz"
            )
        )
        for path in [repeated, reviewed]:
            np.testing.assert_array_equal(
                nib.load(original).get_fdata(), nib.load(path).get_fdata()
            )
    for root in [roots[0], roots[1] / "primary", roots[3]]:
        validation = read(root / "derivative-validation.json")
        assert validation["status"] == "PASS"
    source_root = Path("data/external/spm-auditory/spm_auditory/MoAEpilot")
    run = select_run(
        source_root,
        subject="01",
        task="auditory",
        mask=Path("reports/milestone13-spm-input-preparation/foreground-mask.nii.gz"),
        exploratory_raw=True,
    )
    cfg = replace(
        configuration(Path("configs/fmri-design.yaml")), initial_spikes=4, smoothing_fwhm=6.0
    )
    start = time.perf_counter()
    resumed = analyze(
        run,
        cfg,
        Contrast("listening", {"listening": 1.0}),
        roots[0],
        allow_unvalidated_demo=True,
        resume=True,
    )
    resume_wall = time.perf_counter() - start
    assert resumed["verified_output_reuse"] is True
    maps = read(roots[1] / "primary/soma-reports/contrast.json")
    assert maps["preprocessing"] == "synthetic"
    optional = read(Path("data/derived/milestone13/openneuro-metadata/summary.json"))
    optional_public = {
        key: {
            k: value[k]
            for k in [
                "dataset_DOI",
                "subjects",
                "selected_sessions",
                "selected_BOLD_files",
                "selected_MEG_files",
                "preprocessed_BOLD_files",
                "confounds_tables",
                "real_analysis_ready",
            ]
        }
        for key, value in optional.items()
    }
    # Extra presentation plots remain separate, not mutations of sealed report outputs.
    presentation = Path("reports/milestone13-audit-figures")
    presentation.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    axes[0].bar(["whole EPI foreground"], [spm["ROI"][0]["mean_effect"]])
    axes[0].set(title="Raw educational SPM ROI: descriptive", ylabel="native BOLD effect units")
    keys = list(lab["null"])
    rates = [lab["null"][k]["uncorrected_p05_fraction_mean"] for k in keys]
    axes[1].bar(keys, rates)
    axes[1].axhline(0.05, color="black")
    axes[1].set(title="Synthetic null uncorrected p<.05", ylabel="mean voxel fraction")
    save(
        presentation,
        "ROI-null",
        fig,
        {
            "SPM_foreground_mean_effect": [spm["ROI"][0]["mean_effect"]],
            "null_fraction": rates,
            "null_labels": np.array(keys),
        },
    )
    receipt = {
        "milestone": 13,
        "version": version("soma-neuro"),
        "baseline_revision": "73b9ed0",
        "source_tree_sha256": source,
        "AnatomyReport_source_tree_sha256": report_hash,
        "hash_algorithms": "pipeline: src/soma-relative paths; AnatomyReport: repository-relative",
        "baseline_test_files_unchanged": len(ledger["tests"]),
        "historical_report_files_unchanged": len(ledger["reports"]),
        "audited_output_hashes": files,
        "audited_figure_arrays": arrays,
        "inspected_primary_PNGs": figures,
        "nilearn": version("nilearn"),
        "libraries": {
            name: version(name)
            for name in ["numpy", "scipy", "nibabel", "pybids", "bids-validator-deno"]
        },
        "SPM": {
            "n_runs": 1,
            "shape": [64, 64, 64, 84],
            "TR_s": 7,
            "supplied_listening_blocks": 7,
            "rank": spm["design"]["rank"],
            "residual_dof": spm["design"]["residual_dof"],
            "condition_number": spm["design"]["condition_number"],
            "analysis_voxels": spm["contrast"]["family_voxels"],
            "FDR_rejections": spm["contrast"]["rejected_voxels"],
            "positive": spm["contrast"]["positive_rejected_voxels"],
            "negative": spm["contrast"]["negative_rejected_voxels"],
            "ROI_mean_effect_native_units": spm["ROI"][0]["mean_effect"],
            "preprocessing": "raw educational, not validated",
            "schema": "supported analysis mask PASS; custom statistics not standardized",
            "wall_s": spm["wall_s"],
            "peak_RSS_MiB": spm["process_peak_RSS_MiB"],
            "native_lag1": spm["design"]["mean_native_residual_lag1"],
            "whitened_lag1": spm["design"]["mean_whitened_residual_lag1"],
            "review_fix_and_contrast_refit_change_to_statistical_maps": 0.0,
            "completed_output_verified_reuse_wall_s": resume_wall,
        },
        "synthetic": {
            "oracle": lab["oracle"],
            "null": lab["null"],
            "spatial_oracle_max_error": supp["spatial_oracle_max_error"],
            "test_retest": {
                k: lab["synthetic_retest"][k]
                for k in [
                    "map_correlation",
                    "activation_Dice",
                    "voxel_RMSE",
                    "mean_two_session_sample_variance",
                ]
            },
            "sensitivity": lab["sensitivity"],
            "wall_s": lab["wall_s"],
            "peak_RSS_MiB": lab["process_peak_RSS_MiB"],
        },
        "component_performance": supp["component_times_s"],
        "supplemental_peak_RSS_MiB": supp["process_peak_RSS_MiB"],
        "optional_data": optional_public,
        "real_test_retest_completed": False,
        "real_multimodal_completed": False,
        "tests": {
            "baseline": 691,
            "new": 71,
            "full": 762,
            "offline": 745,
            "integration_deselected_offline": 17,
        },
        "privacy": "aggregate only; no participant IDs, image hashes or voxel data",
        "limitations": [
            "raw SPM preprocessing and motion evidence unavailable",
            "AR1 finite-sample null miscalibration",
            "no independent clinical/anatomical certification",
            "no real registered multimodal comparison",
        ],
    }
    assert "762 passed" in Path("/private/tmp/soma-m13-full-tests.log").read_text()
    assert "745 passed" in Path("/private/tmp/soma-m13-offline-tests.log").read_text()
    atomic_json(Path("experiments/milestone13/verification.json"), receipt)
    print("Verified baselines, hashes, arrays, schema, refit equality and reuse.")


if __name__ == "__main__":
    main()
