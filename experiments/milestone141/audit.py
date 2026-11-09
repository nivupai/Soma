"""Validate private receipts and publish aggregate synthetic evidence only.

Run from repository root, after experiments and tests. Never exports human hashes.
"""

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from soma.pipeline.cache import source_hash


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: str) -> Any:
    return json.loads(Path(path).read_text())


def main() -> None:
    ledger = load("data/derived/milestone141/baseline-ledger.json")
    preserved = {}
    for group, files in ledger.items():
        for name, expected in files.items():
            assert digest(Path(name)) == expected, name
        preserved[group] = len(files)
    for seal in ["configs/milestone141-freeze.json", "configs/milestone141-policy-freeze.json"]:
        for name, expected in load(seal)["files_sha256"].items():
            assert digest(Path(name)) == expected, name
    root = Path("reports/milestone141-null-audit")
    summary = load(str(root / "summary.json"))
    rows = load(str(root / "diagnostic-rows.json"))
    seal = load("configs/milestone141-policy-freeze.json")
    assert source_hash() == seal["source_tree_sha256"]
    assert digest(root / "summary.json") == seal["calibration_summary_sha256"]
    assert len(rows) == summary["rows"] == 19456
    assert {r["dof"] for r in rows} == {36, 96, 196}
    repository_hash = hashlib.sha256(
        b"".join(str(p).encode() + p.read_bytes() for p in sorted(Path("src/soma").rglob("*.py")))
    ).hexdigest()
    archive = subprocess.check_output(["git", "archive", "8e24b6e", "src/soma"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        baseline_parts = []
        for member in sorted(tree.getmembers(), key=lambda m: m.name):
            if member.isfile() and member.name.endswith(".py"):
                stream = tree.extractfile(member)
                assert stream is not None
                baseline_parts.append(member.name.encode() + stream.read())
    baseline_hash = hashlib.sha256(b"".join(baseline_parts)).hexdigest()
    artifacts = {}
    for folder in [
        root,
        Path("reports/milestone141-reproduction"),
        Path("reports/milestone141-preprocessing-plan"),
        Path("reports/milestone141-human-pilot"),
    ]:
        manifest = load(str(folder / "manifest.json"))
        expected_source = baseline_hash if folder.name.endswith("reproduction") else repository_hash
        assert manifest["source_tree_sha256"] == expected_source, folder
        for name, expected in manifest["outputs_sha256"].items():
            assert digest(folder / name) == expected, name
        artifacts[folder.name] = digest(folder / "manifest.json")
    for path in root.glob("*.npz"):
        arrays = np.load(path, allow_pickle=False)
        for name in arrays.files:
            a = arrays[name]
            assert a.dtype.kind != "O", (path, name)
            if a.dtype.kind in "biufc":
                assert np.isfinite(a).all(), (path, name)
            if path.name == "p-values.npz":
                assert ((a >= 0) & (a <= 1)).all()
            if name.endswith("-X"):
                assert np.linalg.matrix_rank(a) == 4
            if name.endswith("-spatial-C"):
                g = arrays[name.replace("-spatial-C", "-G")]
                np.testing.assert_allclose(a, 0.25 * g @ g.T, atol=1e-12)
    old_root = Path("reports/milestone141-before-inventory-fix/milestone141-null-audit")
    deterministic_checks = 0
    if old_root.exists():
        for name in ["p-values.npz", "design-covariance.npz"]:
            a, b = np.load(root / name), np.load(old_root / name)
            assert set(a.files) == set(b.files)
            for key in a.files:
                np.testing.assert_array_equal(a[key], b[key])
                deterministic_checks += 1
    original = load("reports/milestone141-reproduction/summary.json")
    rates = {
        r["model"]: r["BH_any_rejection"]["estimate"]
        for r in original["summary"]
        if "BH_any_rejection" in r
    }
    assert rates == {"ols": 1.0, "ar1": 0.23, "ar2": 0.24}
    extras = {
        name: digest(Path("reports/milestone141-reproduction") / name)
        for name in ["reconstruction.json", "reconstructed-design-covariance.npz"]
    }
    # Added reconstruction is separate from the original reproduction manifest.
    Path("reports/milestone141-reproduction/reconstruction-receipt.json").write_text(
        json.dumps({"supplemental_outputs_sha256": extras}, indent=2) + "\n"
    )
    ready = load("reports/milestone141-preprocessing-plan/summary.json")
    inventory = load("reports/milestone141-preprocessing-plan/private-inventory.json")
    for acq in inventory["acquisitions"]:
        assert digest(Path(acq["path"])) == acq["sha256"]
    pilot = load("reports/milestone141-human-pilot/summary.json")
    assert ready["BIDS_status"] == "PASS" and not ready["executed"]
    assert pilot["subjects_completed"] == pilot["raw_models_fitted"] == 0
    assert pilot["source_tree_sha256"] == source_hash()
    # Bootstrap independent replicate FDPs, never treating voxels as MC samples.
    mixture = []
    rng = np.random.default_rng(1411999)
    for model in ["ols", "ar1", "ar2", "known-GLS"]:
        group = [r for r in rows if r["case"] == "spatial-ar1-mixture-m343" and r["model"] == model]
        for method in ["bh", "by", "bonferroni"]:
            fdp = np.array([r[method]["FDP"] for r in group])
            samples = rng.choice(fdp, size=(10000, len(fdp)), replace=True).mean(axis=1)
            mixture.append(
                {
                    "model": model,
                    "correction": method,
                    "mean_FDP": float(fdp.mean()),
                    "bootstrap95": np.quantile(samples, [0.025, 0.975]).tolist(),
                    "mean_power": float(
                        np.mean([r[method]["true_positive_fraction"] for r in group])
                    ),
                }
            )
    for path in root.glob("*.png"):
        if old_root.exists():
            assert digest(path) == digest(old_root / path.name), path
    check_summaries = {}
    for label, path, target in [
        ("full", "/private/tmp/soma-m141-full-tests.log", "851 passed"),
        ("offline", "/private/tmp/soma-m141-offline-tests.log", "834 passed"),
    ]:
        log = Path(path).read_text()
        assert target in log, label
        check_summaries[label] = log.splitlines()[-1].strip("= ")
    for name in ["ruff", "format", "mypy", "dependencies"]:
        log = Path(f"/private/tmp/soma-m141-{name}.log").read_text()
        check_summaries[name] = log.splitlines()[-1]
    bids = load("reports/milestone141-preprocessing-plan/BIDS-validation.json")
    issues = bids["details"]["issues"]["issues"]
    assert all(issue["severity"] == "warning" for issue in issues)
    assert len(inventory["files"]["events"]) == 1
    counts = {
        k: shutil.which(k) is not None for k in ["docker", "apptainer", "singularity", "fmriprep"]
    }
    receipt = {
        "baseline": "8e24b6e",
        "version": "0.14.1",
        "preserved_files": preserved,
        "source_tree_sha256_pipeline": source_hash(),
        "manifest_sha256": artifacts,
        "protocol_sha256": digest(Path("docs/MILESTONE14_1_PROTOCOL.md")),
        "reconstruction_supplement_sha256": extras,
        "checks": check_summaries,
        "libraries": {
            name: version(name)
            for name in [
                "soma-neuro",
                "numpy",
                "scipy",
                "nilearn",
                "nibabel",
                "scikit-learn",
                "pybids",
                "bids-validator-deno",
            ]
        },
        "tests": {
            "baseline": 815,
            "full": 851,
            "new": 36,
            "offline": 834,
            "offline_deselected": 17,
        },
        "historical_any_BH_rejection": rates,
        "BIDS_warning_entries": len(issues),
        "BIDS_warning_codes": sorted({issue["code"] for issue in issues}),
        "BIDS_wrapper_version": bids["package_version"],
        "BIDS_wrapper_schema_field": bids["schema_version"],
        "BIDS_embedded_schema_version": bids["details"]["summary"]["schemaVersion"],
        "deterministic_arrays_equal_to_initial_staged_run": deterministic_checks,
        "diagnostic_rows": len(rows),
        "calibration": summary["summaries"],
        "mixture_bootstrap_seed": 1411999,
        "mixture_bootstrap_replications": 10000,
        "mixture_uncertainty": mixture,
        "max_t_z_p_difference": summary["max_SciPy_t_vs_Nilearn_z_p_error"],
        "wall_s": summary["wall_s"],
        "process_peak_RSS_MiB": summary["process_peak_RSS_MiB"],
        "BIDS_status": ready["BIDS_status"],
        "preprocessing_executed": False,
        "runtime_executables": counts,
        "human_completed": 0,
        "image_digest": ready["image"]["digest"],
        "image_layers_downloaded": False,
        "limits": "conditional synthetic evidence only; human derivatives unavailable",
    }
    Path("experiments/milestone141/verification.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    print(json.dumps({"preserved": preserved, "rows": len(rows), "human_completed": 0}))


if __name__ == "__main__":
    main()
