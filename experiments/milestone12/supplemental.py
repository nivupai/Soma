"""Local synthetic coverage/recovery and one fixed IBSR development N4 demonstration."""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np

from soma.core.provenance import sha256, write_json
from soma.imaging.nifti import save_nifti
from soma.imaging.volumes import Volume
from soma.pipeline.cache import StageCache, source_hash
from soma.pipeline.derivatives import official_validate, private_output, validate_derivatives
from soma.pipeline.engine import configuration, run_pipeline
from soma.pipeline.ingestion import inspect_bids, legacy_records, select_bids
from soma.pipeline.workflows import qc_reports


def main() -> None:
    root = Path("reports/milestone12-supplemental-acceptance")
    private_output(root)
    root.mkdir(parents=True, exist_ok=False)
    raw = Path("data/derived/milestone12/synthetic-bids-acceptance")
    raw.mkdir(parents=True, exist_ok=False)
    (raw / "dataset_description.json").write_text(
        json.dumps(
            {
                "Name": "Soma entirely synthetic structural MRI",
                "BIDSVersion": "1.11.2",
                "DatasetType": "raw",
                "Authors": ["Soma research software"],
            }
        )
    )
    (raw / "README").write_text(
        "Synthetic concentric tissue intensity phantom for numerical software checks. "
        "No human subjects. Not evidence of anatomical accuracy.\n"
    )
    (raw / "T1w.json").write_text(
        json.dumps(
            {
                "RepetitionTime": 2.0,
                "EchoTime": 0.003,
                "MagneticFieldStrength": 3.0,
                "Manufacturer": "Synthetic",
            }
        )
    )
    image_path = raw / "sub-01/anat/sub-01_T1w.nii.gz"
    image_path.parent.mkdir(parents=True)
    xyz = np.indices((25, 25, 25)).transpose(1, 2, 3, 0) - 12
    radius = np.linalg.norm(xyz, axis=-1)
    data = np.zeros(radius.shape, dtype=np.float32)
    data[radius < 10] = 20
    data[radius < 7] = 70
    data[radius < 4] = 120
    save_nifti(Volume(data, np.diag([0.001, 0.001, 0.001, 1.0])), image_path)
    record = select_bids(raw, "01")
    cfg = configuration(Path("configs/mri-pipeline.yaml"))
    cache = Path("data/derived/m12-supplemental-acceptance-cache")
    before = sha256(image_path)
    first = run_pipeline(
        record,
        cfg,
        root / "synthetic/derivatives/soma",
        report_root=root / "synthetic/reports",
        cache_root=cache,
    )
    hit = run_pipeline(
        record,
        cfg,
        root / "cross-run-hit/derivatives/soma",
        report_root=root / "cross-run-hit/reports",
        cache_root=cache,
    )
    if hit["cache_hits"] != 11:
        raise ValueError("Cross-run cache reuse failed")
    interrupted = False
    try:
        run_pipeline(
            record,
            cfg,
            root / "interruption/derivatives/soma",
            report_root=root / "interruption/reports",
            cache_root=cache / "interruption",
            interrupt_after="preprocessing",
        )
    except InterruptedError:
        interrupted = True
    recovery = run_pipeline(
        record,
        cfg,
        root / "interruption/derivatives/soma",
        report_root=root / "interruption/reports",
        cache_root=cache / "interruption",
        resume=True,
    )
    probe = StageCache(cache / "corruption")

    def build() -> dict[str, np.ndarray]:
        return {"value": np.array([1.0, 2.0])}

    _, receipt = probe.run("probe", {}, {}, build)
    Path(receipt["path"]).write_bytes(b"corrupt private cache for recovery experiment")
    detected = False
    try:
        probe.run("probe", {}, {}, build)
    except ValueError:
        detected = True
    _, repaired = StageCache(cache / "corruption", repair=True).run("probe", {}, {}, build)
    all_stages = deepcopy(cfg)
    all_stages["n4"] = {"enabled": True, "iterations": [2], "shrink_factor": 1}
    all_stages["mask"]["policy"] = "threshold"
    all_stages["surfaces"]["labels"] = [3]
    reference = root / "resampling-target.nii.gz"
    save_nifti(
        Volume(np.zeros((23, 23, 23), np.float32), np.diag([0.0011, 0.0011, 0.0011, 1.0])),
        reference,
    )
    all_stages["resampling"] = {"enabled": True, "reference": str(reference)}
    complete = run_pipeline(
        record,
        all_stages,
        root / "all-stages/derivatives/soma",
        report_root=root / "all-stages/reports",
        cache_root=cache,
    )
    n4 = deepcopy(cfg)
    n4["n4"] = {"enabled": True, "iterations": [2], "shrink_factor": 4}
    ibsr = legacy_records(
        Path("data/external/ibsr"), Path("data/external/mrbrains"), dataset="ibsr"
    )[0]
    actual = run_pipeline(
        ibsr,
        n4,
        root / "development-n4/derivatives/soma",
        report_root=root / "development-n4/reports",
        cache_root=cache,
    )
    if sha256(image_path) != before:
        raise ValueError("Synthetic source changed")
    checks = {
        "raw": official_validate(raw),
        "synthetic": validate_derivatives(root / "synthetic/derivatives/soma"),
        "all_stages": validate_derivatives(root / "all-stages/derivatives/soma"),
        "development_n4": validate_derivatives(root / "development-n4/derivatives/soma"),
    }
    qc_reports(root, root / "qc-summary")
    result = {
        "status": "complete",
        "source_tree_sha256": source_hash(),
        "orchestration_sha256": sha256(Path(__file__)),
        "index": inspect_bids(raw),
        "cache_cross_run_hits": hit["cache_hits"],
        "interruption_detected": interrupted,
        "recovered_stage_hits": recovery["cache_hits"],
        "corruption_detected": detected,
        "explicit_cache_repair": repaired["recovery"],
        "validation": checks,
        "optional_synthetic_qc": complete["qc"],
        "development_n4_qc": actual["qc"],
        "performance": {
            "synthetic_wall_s": first["wall_s"],
            "cross_run_hit_wall_s": hit["wall_s"],
            "all_stages_wall_s": complete["wall_s"],
            "development_n4_wall_s": actual["wall_s"],
        },
        "anatomical_accuracy_improvement_claimed": False,
    }
    write_json(root / "summary.json", result)
    print("Supplemental synthetic, N4, cache, recovery and validation complete.")


if __name__ == "__main__":
    main()
