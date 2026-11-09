"""Verify immutable inputs/reports and publish aggregate evidence only."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np

from soma.core.provenance import sha256
from soma.fmri.audit_workflows import frozen_protocol
from soma.fmri.calibration import gls_oracle
from soma.pipeline.cache import source_hash
from soma.simulations.calibration import atomic_json


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    frozen_protocol()
    development = read(Path("data/derived/milestone14/spm-development-inspection.json"))
    assert len(development["BOLD"]) == 1 and development["preprocessing_inferred"] is False
    ledger = read(Path("data/derived/milestone14/baseline-ledger.json"))
    for group in ["tests", "reports"]:
        for name, expected in ledger[group].items():
            assert sha256(Path(name)) == expected, (group, name)
    source = source_hash()
    assert source == Path("data/derived/milestone14/final-source.sha256").read_text().strip()
    archive = read(Path("data/derived/milestone14/raw-inspection/inventory.json"))
    assets = archive["pilot_assets"]
    assert len(assets) == 4 and not archive["all_other_subject_images_fetched"]
    total_bytes = 0
    for row in assets:
        path = Path("data/external/ds000114") / row["path"]
        assert path.stat().st_size == row["expected_size"]
        assert sha256(path) == row["sha256"]
        expected = hashlib.new(row["annex_algorithm"], path.read_bytes()).hexdigest()
        assert expected == row["annex_digest"]
        total_bytes += path.stat().st_size
    for name, expected in archive["metadata_sha256"].items():
        assert sha256(Path("data/external/ds000114") / name) == expected
    anatomy_hash = hashlib.sha256(
        b"".join(str(p).encode() + p.read_bytes() for p in sorted(Path("src/soma").rglob("*.py")))
    ).hexdigest()
    hashes = 0
    arrays = 0
    PNGs = 0
    roots = [
        Path("reports/milestone14-" + n)
        for n in ["audit", "pilot", "cohort", "sensitivity", "laboratory", "calibration"]
    ]
    seen = set()
    for root in roots:
        for path in root.rglob("manifest.json"):
            if path in seen:
                continue
            seen.add(path)
            metadata = read(path)
            assert metadata["source_tree_sha256"] == anatomy_hash
            assert metadata["application_version"] == "0.14.0"
            for relative, expected in metadata["outputs_sha256"].items():
                assert sha256(path.parent / relative) == expected, (path, relative)
                hashes += 1
        for path in root.rglob("*.npz"):
            with np.load(path, allow_pickle=False) as items:
                for key in items.files:
                    item = items[key]
                    assert item.dtype.kind != "O"
                    if item.dtype.kind in "fci":
                        assert np.isfinite(item).all(), path
                    arrays += 1
        PNGs += len(list(root.rglob("*.png")))
    audit, pilot, cohort, sensitivity, lab, cal = [read(r / "summary.json") for r in roots]
    assert all(x["status"] == "unavailable" for x in [audit, pilot, cohort, sensitivity])
    assert (
        audit["raw_runs_inspected"] == 2
        and audit["raw_T1_references"] == 2
        and audit["eligible_sessions"] == 0
    )
    assert pilot["subjects_completed"] == 0 and cohort["subjects_attempted"] == 0
    assert lab["orchestration_sha256"] == sha256(Path("experiments/milestone14/laboratory.py"))
    assert lab["fixture_source_sha256"] == sha256(Path("tests/fmri14/conftest.py"))
    assert lab["status"] == "complete" and lab["synthetic_only"] and lab["real_human_ICC"] is None
    assert read(roots[4] / "preprocessing-audit.json")["anatomical_validity"] == "INDETERMINATE"
    assert cal["status"] == "complete" and not cal["failures"]
    assert (
        read(Path("reports/milestone14-calibration-affine-review/summary.json"))["summary"]
        == cal["summary"]
    )
    assert (
        read(Path("reports/milestone14-laboratory-affine-review/summary.json"))["cohort"]
        == lab["cohort"]
    )
    assert read(roots[5] / "manifest.json")["parameters"]["seed"] == 15142
    rows = json.loads((roots[5] / "replicates.json").read_text())
    assert len(rows) == 2500
    assert len([r for r in rows if r["model"] == "known-covariance-GLS-reference"]) == 400
    for group in cal["summary"]:
        assert group["n_realizations"] == 100
    # Independent dense covariance-weighted normal equations versus Cholesky/QR.
    rng = np.random.default_rng(14042)
    x = np.c_[np.ones(30), np.linspace(-1, 1, 30), rng.normal(size=30)]
    covariance = 0.6 ** np.abs(np.subtract.outer(np.arange(30), np.arange(30)))
    y = x @ np.array([[2.0], [0.5], [-0.3]]) + rng.normal(0, 0.2, (30, 1))
    c = np.array([0.0, 1.0, -1.0])
    actual = gls_oracle(x, y, covariance, c)
    precision = np.linalg.inv(covariance)
    inverse = np.linalg.inv(x.T @ precision @ x)
    beta = inverse @ x.T @ precision @ y
    residual = y - x @ beta
    variance = float((residual.T @ precision @ residual)[0, 0] / 27 * (c @ inverse @ c))
    errors = {
        "max_beta_error": float(np.max(abs(actual["beta"] - beta))),
        "contrast_variance_error": float(abs(actual["variance"][0] - variance)),
    }
    assert max(errors.values()) < 1e-12
    execution = json.loads(Path("data/derived/milestone14/final-execution.json").read_text())
    assert all(r["returncode"] == r["expected"] for r in execution)
    full = Path("/private/tmp/soma-m14-full-tests.log").read_text()
    offline = Path("/private/tmp/soma-m14-offline-tests.log").read_text()
    assert "815 passed" in full and "798 passed" in offline
    receipt = {
        "milestone": 14,
        "version": version("soma-neuro"),
        "baseline": "0312635",
        "source_tree_sha256": source,
        "AnatomyReport_source_tree_sha256": anatomy_hash,
        "hash_algorithms": "pipeline: src-relative; AnatomyReport: repository-relative paths",
        "libraries": {
            n: version(n) for n in ["nilearn", "numpy", "scipy", "nibabel", "SimpleITK", "pybids"]
        },
        "baseline_test_files_unchanged": len(ledger["tests"]),
        "historical_report_files_unchanged": len(ledger["reports"]),
        "verified_output_hashes": hashes,
        "finite_figure_arrays": arrays,
        "inspected_PNGs": PNGs,
        "dataset_coverage": {
            "dataset": "ds000114v1.0.2",
            "license": "CC0",
            "raw_subjects_fetched": 1,
            "raw_motor_runs": 2,
            "raw_T1s": 2,
            "raw_bytes": total_bytes,
            "raw_shapes": [[64, 64, 30, 184], [64, 64, 30, 184]],
            "TR_s": 2.5,
            "adequate_preprocessed_sessions": 0,
            "human_models_fitted": 0,
            "human_retest_completed": False,
            "cohort_subjects_attempted": 0,
        },
        "SPM_development": "prior raw educational case re-inspected; no new confirmatory fit",
        "preprocessing": "fMRIPrep and Docker runtime unavailable; no external preprocessing",
        "calibration": {
            "scenarios": 7,
            "realizations_per_scenario": 100,
            "seeds": [15142, 15241],
            "pairing": "paired scenarios/estimators;100 independent seeds per scenario",
            "image_fits": 2100,
            "small_known_covariance_references": 400,
            "failures": 0,
            "summary": cal["summary"],
            "wall_s": cal["wall_s"],
            "peak_RSS_MiB": cal["process_peak_RSS_MiB"],
        },
        "independent_GLS_oracle": errors,
        "synthetic_reliability": lab["cohort"],
        "synthetic_confound_sensitivity": [
            {
                "strategy": r["strategy"],
                "BH_rejections": r["rejected_voxels"],
                "residual_dof": r["QC"]["design"]["residual_dof"],
            }
            for r in lab["confound_sensitivity"]
        ],
        "synthetic_lab_wall_s": lab["wall_s"],
        "synthetic_lab_peak_RSS_MiB": lab["process_peak_RSS_MiB"],
        "tests": {
            "baseline_passed": 762,
            "added_passed": 53,
            "full_passed": 815,
            "offline_passed": 798,
            "offline_deselected": 17,
        },
        "complete_acceptance": False,
        "blocked_real_criteria": [
            "audited human preprocessing",
            "two-session motor pilot",
            "bounded human cohort reliability",
            "registered motor ROIs",
            "real cross-cohort EEG/fMRI comparison",
        ],
        "scientific_scope": "software/numerical evidence; no anatomical or clinical certification",
        "privacy": "aggregate receipt; images, identities and medical fingerprints ignored",
    }
    atomic_json(Path("experiments/milestone14/verification.json"), receipt)
    print("Verified immutable baselines, inputs, outputs, calibration and real-data gaps.")


if __name__ == "__main__":
    main()
