"""Verify private artifacts and emit a public, aggregate-only acceptance receipt."""

import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.core.provenance import sha256
from soma.pipeline.cache import source_hash
from soma.simulations.calibration import atomic_json
from soma.validation.plots import save


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    root = Path("reports/milestone12-validated")
    supplemental = Path("reports/milestone12-supplemental-acceptance")
    ledger = read(Path("data/derived/milestone12/baseline-ledger.json"))
    for group in ("tests", "reports"):
        for path, expected in ledger[group].items():
            assert sha256(Path(path)) == expected, (group, path)
    frozen = read(Path("configs/milestone12-freeze.json"))
    for path, expected in frozen["files_sha256"].items():
        assert sha256(Path(path)) == expected, path
    source = source_hash()
    master = read(root / "manifest.json")
    anatomy_hash = hashlib.sha256(
        b"".join(str(p).encode() + p.read_bytes() for p in sorted(Path("src/soma").rglob("*.py")))
    ).hexdigest()
    assert master["source_tree_sha256"] == anatomy_hash
    for path, expected in master["outputs_sha256"].items():
        assert sha256(root / path) == expected, path
    runs = list(root.glob("*/reports/*/run.json"))
    assert len(runs) == 23
    checked_derivatives = 0
    for path in runs:
        run = read(path)
        assert run["status"] == "complete" and run["implementation"] == source
        assert run["qc"]["numerical_status"] == "PASS"
        assert run["qc"]["anatomical_status"] == "INDETERMINATE"
        assert sha256(Path(run["source"]["image"])) == run["source"]["sha256"]
        reference = run["source"]["legacy"]["reference"]
        assert sha256(Path(reference)) == run["source"]["auxiliary_sha256"]["reference"]
        assert read(path.parent / "manifest.json")["source_tree_sha256"] == source
        assert len(run["stages"]) == 11
        for stage in run["stages"]:
            assert stage["status"] == "complete"
            assert sha256(Path(stage["cache"]["path"])) == stage["cache"]["sha256"]
        output = path.parents[2] / "derivatives/soma"
        for relative, expected in run["derivatives"]["files"].items():
            assert sha256(output / relative) == expected
            checked_derivatives += 1
        assert (
            sha256(output / "dataset_description.json")
            == run["derivatives"]["dataset_description_sha256"]
        )
    summary = read(root / "summary.json")
    assert summary["status"] == "complete" and not summary["failures"]
    aggregate = {}
    validation = {}
    distributions = supplemental / "cohort-distributions"
    distributions.mkdir(exist_ok=True)
    for dataset, count in [("ibsr", 18), ("mrbrains", 5)]:
        values = summary["datasets"][dataset]
        assert values["completed"] == count and values["max_absolute_baseline_difference"] == 0
        df = pd.read_csv(root / (dataset + "-metrics.csv"))
        assert len(df) == count * 3
        metrics = ["Dice", "Jaccard", "ASSD_mm", "HD95_mm", "signed_volume_error_mm3"]
        assert np.isfinite(df[metrics].to_numpy()).all()
        aggregate[dataset] = {
            **values,
            "tissue_mean_metrics": df.groupby("name")[metrics].mean().to_dict("index"),
        }
        v = summary["derivative_validation"][dataset]
        assert v["full_schema_status"] == "PASS" and v["structural_checks"] == "PASS"
        issues = v["official_validator"]["details"]["issues"]["issues"]
        assert not [i for i in issues if i["severity"] == "error"]
        validation[dataset] = {
            "status": "PASS",
            "images": v["images"],
            "validator": v["official_validator"]["package_version"],
            "schema": v["official_validator"]["schema_version"],
            "warning_codes": sorted({i["code"] for i in issues}),
        }
        fig, axes = plt.subplots(1, 5, figsize=(16, 4), layout="constrained")
        arrays = {}
        for axis, metric in zip(axes, metrics, strict=True):
            names = sorted(df["name"].unique())
            data = [df.loc[df["name"] == name, metric].to_numpy() for name in names]
            axis.boxplot(data, tick_labels=names)
            axis.set_title(metric)
            for name, array in zip(names, data, strict=True):
                arrays[metric + "_" + name] = array
        fig.suptitle(dataset + ": known tissue references; no fresh holdout or conductor claim")
        save(distributions, dataset + "-tissue-metrics", fig, arrays)
    extra = read(supplemental / "summary.json")
    assert extra["source_tree_sha256"] == source
    assert extra["cache_cross_run_hits"] == 11 and extra["recovered_stage_hits"] == 4
    assert extra["corruption_detected"] and extra["interruption_detected"]
    for v in extra["validation"].values():
        assert v.get("full_schema_status", v.get("status")) == "PASS"
    supplemental_runs = list(supplemental.rglob("run.json"))
    assert len(supplemental_runs) == 5
    for path in supplemental_runs:
        run = read(path)
        assert run["status"] == "complete" and run["implementation"] == source
        assert sha256(Path(run["source"]["image"])) == run["source"]["sha256"]
        output = path.parents[2] / "derivatives/soma"
        for relative, expected in run["derivatives"]["files"].items():
            assert sha256(output / relative) == expected
        for stage in run["stages"]:
            assert sha256(Path(stage["cache"]["path"])) == stage["cache"]["sha256"]
    for name, filename in [("supplemental", "summary.json"), ("performance", "performance.json")]:
        location = (
            supplemental
            if name == "supplemental"
            else Path("reports/milestone12-component-performance-acceptance")
        )
        assert read(location / filename)["orchestration_sha256"] == sha256(
            Path("experiments/milestone12") / (name + ".py")
        )
    assert "690 passed" in Path("/private/tmp/soma-m12-final-tests.log").read_text()
    assert "673 passed" in Path("/private/tmp/soma-m12-offline-tests.log").read_text()
    npz_count = 0
    for parent in [root, supplemental]:
        for path in parent.rglob("*.npz"):
            with np.load(path, allow_pickle=False) as arrays:
                for name in arrays.files:
                    array = arrays[name]
                    assert array.dtype.kind != "O"
                    if array.dtype.kind in "fci":
                        assert np.isfinite(array).all(), path
            npz_count += 1
    receipt = {
        "milestone": 12,
        "version": "0.12.0",
        "baseline_revision": ledger["revision"],
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "libraries": {
                name: version(name)
                for name in (
                    "soma-neuro",
                    "numpy",
                    "scipy",
                    "nibabel",
                    "SimpleITK",
                    "scikit-image",
                    "pybids",
                    "bidsschematools",
                    "bids-validator-deno",
                )
            },
        },
        "supplemental_complete_runs_verified": len(supplemental_runs),
        "source_tree_sha256": source,
        "source_hash_algorithm": "pipeline relative paths under src/soma plus file contents",
        "anatomy_report_source_sha256": anatomy_hash,
        "anatomy_hash_algorithm": "repository-relative src/soma paths plus file contents",
        "baseline_test_files_unchanged": len(ledger["tests"]),
        "historical_report_files_unchanged": len(ledger["reports"]),
        "derivative_files_verified": checked_derivatives,
        "numerically_valid_runs": len(runs),
        "stages_per_run": 11,
        "figure_npz_verified": npz_count,
        "human_figure_count": len(list(root.rglob("*.png"))),
        "datasets": aggregate,
        "BIDS_validation": validation,
        "cache_and_recovery": {
            "cross_run_stage_hits": extra["cache_cross_run_hits"],
            "interrupted_resume_stage_hits": extra["recovered_stage_hits"],
            "corruption_detected": extra["corruption_detected"],
            "repair": "explicit quarantine and rebuild",
            "completed_human_runs_verified_reused": 23,
            "completed_resume_reads_stage_cache": False,
        },
        "human_performance": {
            "wall_s": summary["wall_s"],
            "cpu_s": summary["cpu_s"],
            "peak_RSS_MiB": summary["process_peak_RSS_MiB"],
            "dataset_timings": summary["performance"],
        },
        "component_performance": read(
            Path("reports/milestone12-component-performance-acceptance/performance.json")
        ),
        "supplemental_performance": extra["performance"],
        "supplemental_BIDS_status": "raw and all three derivative datasets PASS",
        "tests": {
            "baseline_passed": 636,
            "new_passed": 55,
            "offline": {"passed": 673, "failed": 1, "deselected": 17},
            "including_integration": {"passed": 690, "failed": 1},
            "known_failure": "unchanged test_protocol_and_installed_version_match_source "
            "asserts 0.11.0; user explicitly required retain and report its failure",
        },
        "acceptance": "implemented with one user-directed historical version-test failure",
        "anatomical_certification": False,
        "fresh_external_holdout": False,
        "privacy": "aggregate receipt only; individual manifests, source hashes and images ignored",
    }
    atomic_json(Path("experiments/milestone12/verification.json"), receipt)
    print(
        "Verified historical files, 23 runs, source/cache/output hashes, metrics and figure arrays."
    )


if __name__ == "__main__":
    main()
