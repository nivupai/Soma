"""M33 skull protocol v3.1 = v3 + MRI-only head crop, on SynthRAD2025 head-and-neck.

Refuses to score until docs/MILESTONE33_SKULL_PROTOCOL_V31.md is sealed by the owner in
configs/m33-skull-v31-freeze.json (``python -m scripts.seal_m33_skull_v31``), and the model
file must match the SHA256 recorded in that seal. Each case: crop the T1 with
``crop_head_top`` into a staging folder (CT and mask are linked unchanged), then the v3 method.

    python -m scripts.run_m33_skull_v31 --case 1HNA001        # one case (resumable)
    python -m scripts.run_m33_skull_v31 --aggregate           # after every case is done
"""

import argparse
import json
import pickle
from importlib.metadata import version
from pathlib import Path
from typing import Any

from scripts.dev_m33_skull import fs_env
from scripts.run_m33_skull_v3 import evaluate, load
from scripts.run_m33_skull_validation import SEED, require_frozen_protocol, summarize
from soma.anatomy.fs_skull import crop_head_top
from soma.core.provenance import sha256, write_json
from soma.datasets.human_mri import safe_local_output
from soma.imaging.nifti import save_nifti

PROTOCOL = Path("docs/MILESTONE33_SKULL_PROTOCOL_V31.md")
FREEZE = Path("configs/m33-skull-v31-freeze.json")
DATA = Path("/Volumes/YOTUO/soma-data/synthrad2025/hn")
SUBJECTS = Path("/Volumes/YOTUO/soma-data/fs-subjects-hn-crop")
MODEL = Path("reports/milestone33/skull-dev-crop/refine-model-v3.1-final.pkl")
OUTPUT = Path("reports/milestone33/skull-v31")


def test_cases() -> list[str]:
    return sorted(
        p.name
        for p in DATA.iterdir()
        if all((p / f).exists() for f in ("mr.nii.gz", "ct.nii.gz", "mask.nii.gz"))
    )


def stage(case: str) -> Path:
    root = OUTPUT / "staging"
    folder = root / case
    if not (folder / "mr.nii.gz").exists():
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / "mr.part.nii.gz"
        save_nifti(crop_head_top(load(DATA / case / "mr.nii.gz")), tmp)
        tmp.rename(folder / "mr.nii.gz")
    for name in ("ct.nii.gz", "mask.nii.gz"):
        link = folder / name
        if not link.exists():
            link.symlink_to((DATA / case / name).resolve())
    return root


def checked_model(seal: dict[str, Any]) -> Any:
    if sha256(MODEL) != seal.get("model_sha256"):
        raise SystemExit("Inner-skull model differs from the one recorded in the v3.1 seal")
    return pickle.loads(MODEL.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--aggregate", action="store_true")
    args = parser.parse_args()
    seal = require_frozen_protocol(PROTOCOL, FREEZE)
    model = checked_model(seal)
    safe_local_output(OUTPUT)
    SUBJECTS.mkdir(parents=True, exist_ok=True)
    if args.case:
        if args.case not in test_cases():
            raise SystemExit("Unknown test case")
        evaluate(args.case, stage(args.case), SUBJECTS, OUTPUT, model, fs_env())
        return
    if not args.aggregate:
        raise SystemExit("Pass --case or --aggregate")
    if (OUTPUT / "cohort-summary.json").exists():
        raise SystemExit("Test cohort already scored; a rerun needs a new protocol version")
    cases = test_cases()
    results, failures = [], []
    for case in cases:
        done = OUTPUT / "cases" / case / "skull-v3-metrics.json"
        failed = OUTPUT / "cases" / case / "FAILED.json"
        if done.exists():
            results.append(json.loads(done.read_text()))
        elif failed.exists():
            failures.append({"case": case, **json.loads(failed.read_text())})
        else:
            raise SystemExit(f"Case {case} not finished; aggregate refused")
    summary = summarize(results, SEED) if results else None
    if summary:
        summary["decision"]["scope"] = "v3.1: head crop + watershed + offsets + learned inner skull"
    write_json(
        OUTPUT / "cohort-summary.json",
        {
            "protocol_seal": seal,
            "soma_version": version("soma-neuro"),
            "dataset": "SynthRAD2025 Task 1 head-and-neck (CC BY-NC 4.0); aggregates only",
            "requested": len(cases),
            "completed_cases": len(results),
            "failures": failures,
            "mri_qc_failures": sum(1 for r in results if r["flags"]["mri_qc"]["flag"]),
            "cohort": summary,
        },
    )


if __name__ == "__main__":
    main()
