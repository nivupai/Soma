"""M33 skull protocol v3: watershed + offsets + learned inner skull vs CT on SynthRAD2025 HN.

Refuses to score until docs/MILESTONE33_SKULL_PROTOCOL_V3.md is sealed by the owner in
configs/m33-skull-v3-freeze.json (``python -m scripts.seal_m33_skull_v3``). The inner-skull
model file must match the SHA256 fixed in the protocol. Every test case is scored once;
finished cases resume from cached metrics. Per-case outputs stay in ignored local storage.

    python -m scripts.run_m33_skull_v3 --data DIR --fs-subjects DIR --model FILE \
        --output reports/milestone33/skull-v3 [--cases ...] [--aggregate]
"""

import argparse
import json
import pickle
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from scripts.dev_m33_skull import build_watershed, fs_env
from scripts.run_m33_segmentation import run_synthseg
from scripts.run_m33_skull_v2 import OFFSETS_MM, QC_RATIO_RANGE, SYNTHSEG_CMD, mesh_volume_ml
from scripts.run_m33_skull_validation import SEED, require_frozen_protocol, summarize
from soma.anatomy.fs_skull import load_watershed, offset_mesh, voxelize
from soma.anatomy.inner_skull_refine import apply_correction, features
from soma.anatomy.t1_skull import mask_volume, pad
from soma.benchmarks.ct_skull import (
    FLAGS_V2,
    PRIMARY_BONE_HU,
    SENSITIVITY_BONE_HU,
    CTSkullParameters,
    RegionRule,
    ct_truth,
    exclusion_flags,
    score_case,
)
from soma.core.provenance import sha256, write_json
from soma.datasets.human_mri import safe_local_output
from soma.imaging.nifti import load_nifti
from soma.pipeline.synthseg import load_synthseg, to_native_grid

PROTOCOL = Path("docs/MILESTONE33_SKULL_PROTOCOL_V3.md")
FREEZE = Path("configs/m33-skull-v3-freeze.json")
MODEL_SHA256 = "9afbbce8bcd3ec15a02aa06a656cd0c895ea95ab79b673fed88f4f2ab0943b5b"


def load(path: Path, kind: str = "intensity") -> Any:
    try:
        return load_nifti(path, kind=kind)  # type: ignore[arg-type]
    except ValueError:
        return load_nifti(path, policy="sform", kind=kind)  # type: ignore[arg-type]


def evaluate(
    case: str, data: Path, subjects: Path, output: Path, model: Any, env: dict[str, str]
) -> dict[str, Any]:
    cache = output / "cases" / case
    done = cache / "skull-v3-metrics.json"
    if done.exists():
        return dict(json.loads(done.read_text()))
    cache.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    t1 = load(data / case / "mr.nii.gz")
    ct = load(data / case / "ct.nii.gz")
    mask = load(data / case / "mask.nii.gz", "labels")
    subject = build_watershed(case, subjects, env, data)
    raw = load_watershed(subject, case)
    synth = load_synthseg(run_synthseg(SYNTHSEG_CMD, data / case / "mr.nii.gz", cache))
    synth_native, _ = to_native_grid(synth, t1)
    icv_ml = float((synth.array() > 0).sum() * np.prod(synth.spacing_m * 1000) / 1000)
    ratio = mesh_volume_ml(raw["inner_skull"]) / icv_ml
    qc_pass = QC_RATIO_RANGE[0] <= ratio <= QC_RATIO_RANGE[1]
    meshes = {b: offset_mesh(m, OFFSETS_MM[b]) for b, m in raw.items()}
    meshes["inner_skull"] = apply_correction(
        meshes["inner_skull"], model.predict(features(meshes["inner_skull"], t1, synth_native))
    )
    like = pad(t1, CTSkullParameters().padding_voxels)
    masks = {b: mask_volume(voxelize(m, like), like, boundary=b) for b, m in meshes.items()}
    truths = {
        hu: ct_truth(ct, mask, parameters=CTSkullParameters(bone_hu=hu))
        for hu in (PRIMARY_BONE_HU, *SENSITIVITY_BONE_HU)
    }
    primary = truths[PRIMARY_BONE_HU]
    region = RegionRule().fit(primary.masks["inner_skull"])
    flags = exclusion_flags(ct, mask, primary, region, t1=t1, thresholds=FLAGS_V2)
    flags["mri_qc"] = {
        "flag": not qc_pass,
        "watershed_inner_over_synthseg_icv": ratio,
        "range": list(QC_RATIO_RANGE),
    }
    flags["any"] = bool(flags["any"] or not qc_pass)
    scores: dict[str, Any] = {}
    for hu, truth in truths.items():
        try:
            scores[str(hu)] = score_case(meshes, masks, truth, region, seed=SEED)
        except ValueError as exc:
            scores[str(hu)] = {"error": str(exc)}
    result = {
        "case": case,
        "centre": case[3],
        "flags": flags,
        "scores": {k: v for k, v in scores.items() if "error" not in v},
        "score_errors": {k: v["error"] for k, v in scores.items() if "error" in v},
        "wall_s": time.perf_counter() - t0,
    }
    write_json(done, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--fs-subjects", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--aggregate", action="store_true")
    args = parser.parse_args()
    seal = require_frozen_protocol(PROTOCOL, FREEZE)
    if sha256(args.model) != MODEL_SHA256:
        raise SystemExit("Inner-skull model differs from the one fixed in the protocol")
    safe_local_output(args.output)
    all_cases = sorted(
        p.name
        for p in args.data.iterdir()
        if (p / "ct.nii.gz").exists() and (p / "mr.nii.gz").exists()
    )
    cases = args.cases or all_cases
    if (args.output / "cohort-summary.json").exists():
        raise SystemExit("Test cohort already scored; a rerun needs a new protocol version")
    model = pickle.loads(args.model.read_bytes())
    env = fs_env()
    results, failures = [], []
    for case in cases:
        try:
            results.append(evaluate(case, args.data, args.fs_subjects, args.output, model, env))
            print("done", case, flush=True)
        except Exception as exc:
            failures.append({"case": case, "reason": f"{type(exc).__name__}: {exc}"})
            print("FAIL", case, exc, flush=True)
    if args.aggregate:
        if set(cases) != set(all_cases):
            raise SystemExit("Aggregate only over every test case")
        summary = summarize(results, SEED) if results else None
        if summary:
            summary["decision"]["scope"] = (
                "watershed + calibrated offsets + learned inner skull (v3); this method only"
            )
        write_json(
            args.output / "cohort-summary.json",
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
