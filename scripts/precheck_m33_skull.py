"""MRI-only pre-check before sealing a skull test protocol (reads no CT, scores nothing).

Runs the v3.1 MRI pipeline (head crop, SynthSeg, watershed) on 3 subjects (first, middle, last
by sorted ID) and checks completion, SynthSeg intracranial volume, the MRI-only QC ratio,
runtime and peak memory. Prints PASS/FAIL per check and writes ``precheck.json``.

    python -m scripts.precheck_m33_skull --data DIR --work DIR
"""

import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from scripts.dev_m33_skull import build_watershed, fs_env
from scripts.run_m33_segmentation import run_synthseg
from scripts.run_m33_skull_v2 import QC_RATIO_RANGE, SYNTHSEG_CMD, mesh_volume_ml
from scripts.run_m33_skull_v3 import load
from soma.anatomy.fs_skull import crop_head_top, load_watershed
from soma.imaging.nifti import save_nifti
from soma.pipeline.synthseg import load_synthseg

ICV_RANGE_ML = (1000.0, 2000.0)
MAX_MINUTES = 20.0
MAX_PEAK_GB = 10.0


def peak_child_gb() -> float:
    # macOS reports ru_maxrss in bytes.
    return float(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss) / 1e9


def check(case: str, data: Path, work: Path, env: dict[str, str]) -> dict[str, Any]:
    t0 = time.perf_counter()
    stage = work / "staging" / case
    stage.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"case": case}
    try:
        if not (stage / "mr.nii.gz").exists():
            save_nifti(crop_head_top(load(data / case / "mr.nii.gz")), stage / "mr.nii.gz")
        synth = load_synthseg(
            run_synthseg(SYNTHSEG_CMD, stage / "mr.nii.gz", work / "synthseg" / case)
        )
        icv = float((synth.array() > 0).sum() * np.prod(synth.spacing_m * 1000) / 1000)
        subject = build_watershed(case, work / "fs", env, work / "staging")
        ratio = (
            mesh_volume_ml(load_watershed(subject, case)["inner_skull"]) / icv
            if icv
            else float("inf")
        )
        result.update({"completed": True, "icv_ml": icv, "qc_ratio": ratio})
    except (subprocess.CalledProcessError, ValueError, OSError) as exc:
        result.update({"completed": False, "error": f"{type(exc).__name__}: {exc}"})
    result["minutes"] = (time.perf_counter() - t0) / 60
    result["peak_child_gb"] = peak_child_gb()
    result["checks"] = {
        "completed": bool(result.get("completed")),
        "icv_in_range": ICV_RANGE_ML[0] <= result.get("icv_ml", 0) <= ICV_RANGE_ML[1],
        "qc_ratio_in_range": QC_RATIO_RANGE[0] <= result.get("qc_ratio", -1) <= QC_RATIO_RANGE[1],
        "runtime_ok": result["minutes"] <= MAX_MINUTES,
        "memory_ok": result["peak_child_gb"] <= MAX_PEAK_GB,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    args.data, args.work = args.data.resolve(), args.work.resolve()  # FreeSurfer steps chdir
    cases = sorted(p.name for p in args.data.iterdir() if (p / "mr.nii.gz").exists())
    if len(cases) < 3:
        raise SystemExit("Need at least 3 subjects with mr.nii.gz")
    picks = [cases[0], cases[len(cases) // 2], cases[-1]]
    env = fs_env()
    results = [check(c, args.data, args.work, env) for c in picks]
    passed = all(all(r["checks"].values()) for r in results)
    args.work.mkdir(parents=True, exist_ok=True)
    (args.work / "precheck.json").write_text(
        json.dumps({"passed": passed, "subjects": results}, indent=1)
    )
    for r in results:
        flags = " ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in r["checks"].items())
        print(r["case"], flags)
    print("PRE-CHECK", "PASSED" if passed else "FAILED")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
