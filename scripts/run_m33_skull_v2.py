"""M33 skull protocol v2: calibrated FreeSurfer watershed vs CT on the 120 held-out cases.

Refuses to score until docs/MILESTONE33_SKULL_PROTOCOL_V2.md is sealed by the owner in
configs/m33-skull-v2-freeze.json (``python -m scripts.seal_m33_skull_v2``). Held-out cases
are scored once; finished cases resume from their cached metrics. Development cases are
refused. Per-case outputs stay in ignored local storage.

    python -m scripts.run_m33_skull_v2 --fs-subjects /Volumes/X/fs-subjects \
        --output reports/milestone33/skull-v2
"""

import argparse
import json
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from scripts.dev_m33_skull import DATA, SPLIT, SYNTHSEG_CACHE, build_watershed, fs_env
from scripts.run_m33_segmentation import run_synthseg
from scripts.run_m33_skull_validation import (
    SEED,
    centre,
    require_frozen_protocol,
    summarize,
)
from soma.anatomy.fs_skull import load_watershed, offset_mesh, voxelize
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
from soma.core.provenance import write_json
from soma.datasets.human_mri import safe_local_output
from soma.imaging.nifti import load_nifti
from soma.pipeline.synthseg import load_synthseg

PROTOCOL = Path("docs/MILESTONE33_SKULL_PROTOCOL_V2.md")
FREEZE = Path("configs/m33-skull-v2-freeze.json")
# Fixed before held-out scoring: minus the median signed bias on the 60 development cases.
OFFSETS_MM = {"inner_skull": -3.28, "outer_skull": -3.63, "outer_scalp": -0.95}
# MRI-only quality check (no CT): watershed inner-skull volume / SynthSeg intracranial volume.
QC_RATIO_RANGE = (0.80, 1.80)
SYNTHSEG_CMD = (
    str(Path.home()) + "/soma-tools/run-synthseg.sh --i {input} --o {output} --robust --threads 4"
)


def mesh_volume_ml(mesh: Any) -> float:
    t = mesh.vertices.xyz[mesh.faces] * 1000
    return float(abs(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()) / 6 / 1000)


def evaluate(case: str, subjects: Path, output: Path, env: dict[str, str]) -> dict[str, Any]:
    cache = output / "cases" / case
    done = cache / "skull-v2-metrics.json"
    if done.exists():
        return dict(json.loads(done.read_text()))
    cache.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    t1 = load_nifti(DATA / case / "mr.nii.gz")
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    subject = build_watershed(case, subjects, env)
    raw = load_watershed(subject, case)
    synth_path = SYNTHSEG_CACHE / case / "synthseg.nii.gz"
    if not synth_path.exists():
        synth_path = run_synthseg(SYNTHSEG_CMD, DATA / case / "mr.nii.gz", cache)
    synth = load_synthseg(synth_path)
    icv_ml = float((synth.array() > 0).sum() * np.prod(synth.spacing_m * 1000) / 1000)
    ratio = mesh_volume_ml(raw["inner_skull"]) / icv_ml
    qc = {
        "watershed_inner_over_synthseg_icv": ratio,
        "range": list(QC_RATIO_RANGE),
        "pass": QC_RATIO_RANGE[0] <= ratio <= QC_RATIO_RANGE[1],
    }
    like = pad(t1, CTSkullParameters().padding_voxels)
    meshes = {b: offset_mesh(m, OFFSETS_MM[b]) for b, m in raw.items()}
    masks = {b: mask_volume(voxelize(m, like), like, boundary=b) for b, m in meshes.items()}
    truths = {
        hu: ct_truth(ct, mask, parameters=CTSkullParameters(bone_hu=hu))
        for hu in (PRIMARY_BONE_HU, *SENSITIVITY_BONE_HU)
    }
    primary = truths[PRIMARY_BONE_HU]
    region = RegionRule().fit(primary.masks["inner_skull"])
    flags = exclusion_flags(ct, mask, primary, region, t1=t1, thresholds=FLAGS_V2)
    # The MRI-only QC failure is a flag too: such a head would be labelled NOT_READY on its own.
    flags["mri_qc"] = {"flag": not qc["pass"], **qc}
    flags["any"] = bool(flags["any"] or not qc["pass"])
    scores: dict[str, Any] = {}
    for hu, truth in truths.items():
        try:
            scores[str(hu)] = score_case(meshes, masks, truth, region, seed=SEED)
        except ValueError as exc:  # a failed sensitivity threshold never drops the case
            scores[str(hu)] = {"error": str(exc)}
    result = {
        "case": case,
        "centre": centre(case),
        "offsets_mm": OFFSETS_MM,
        "flags": flags,
        "scores": {k: v for k, v in scores.items() if "error" not in v},
        "score_errors": {k: v["error"] for k, v in scores.items() if "error" in v},
        "wall_s": time.perf_counter() - t0,
    }
    write_json(done, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fs-subjects", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--aggregate", action="store_true", help="write the cohort summary")
    args = parser.parse_args()
    seal = require_frozen_protocol(PROTOCOL, FREEZE)
    safe_local_output(args.output)
    held_out = json.loads(SPLIT.read_text())["held_out"]
    cases = args.cases or held_out
    if not set(cases) <= set(held_out):
        raise SystemExit("v2 scoring is for held-out cases only")
    if (args.output / "cohort-summary.json").exists():
        raise SystemExit("Held-out cohort already scored; a rerun needs a new protocol version")
    env = fs_env()
    results, failures = [], []
    for case in cases:
        try:
            results.append(evaluate(case, args.fs_subjects, args.output, env))
            print("done", case, flush=True)
        except Exception as exc:  # every failure is reported per case
            failures.append({"case": case, "reason": f"{type(exc).__name__}: {exc}"})
            print("FAIL", case, exc, flush=True)
    if args.aggregate:
        if set(cases) != set(held_out):
            raise SystemExit("Aggregate only over the full held-out set")
        summary = summarize(results, SEED) if results else None
        if summary:
            summary["decision"]["scope"] = (
                "FreeSurfer watershed BEM, fixed development-calibrated offsets; this method only"
            )
        write_json(
            args.output / "cohort-summary.json",
            {
                "protocol_seal": seal,
                "soma_version": version("soma-neuro"),
                "dataset": "SynthRAD2023 Task 1 brain (CC BY-NC 4.0); aggregates only",
                "requested": len(cases),
                "completed_cases": len(results),
                "failures": failures,
                "mri_qc_failures": sum(1 for r in results if r["flags"]["mri_qc"]["flag"]),
                "cohort": summary,
            },
        )


if __name__ == "__main__":
    main()
