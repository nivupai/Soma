"""M33 skull v2 development: calibrated watershed offsets, leave-one-centre-out.

Development cases only. For each centre, the per-surface normal offset is minus the median
signed bias of the watershed surfaces on the OTHER two centres' development cases; the held-
in centre's cases are then re-scored with that offset. This estimates how a single offset,
fitted on development data, generalises to an unseen centre.

    python -m scripts.tune_m33_skull --fs-subjects /Volumes/X/fs-subjects [--cases ...]
"""

import argparse
import glob
import json
from pathlib import Path
from typing import Any

import numpy as np

from scripts.dev_m33_skull import DATA, OUT, SPLIT
from soma.anatomy.fs_skull import load_watershed, offset_mesh, voxelize
from soma.anatomy.t1_skull import mask_volume, pad
from soma.benchmarks.ct_skull import CTSkullParameters, RegionRule, ct_truth, score_case
from soma.core.provenance import write_json
from soma.imaging.nifti import load_nifti

BOUNDARIES = ("inner_skull", "outer_skull", "outer_scalp")


def raw_results() -> list[dict[str, Any]]:
    paths = sorted(glob.glob(str(OUT / "*" / "dev-metrics.json")))
    return [json.loads(Path(p).read_text()) for p in paths]


def loco_offsets(results: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    offsets = {}
    for centre in "ABC":
        train = [r for r in results if r["case"][2] != centre]
        offsets[centre] = {
            b: -float(
                np.median(
                    [r["methods"]["watershed"]["boundaries"][b]["signed_mean_mm"] for r in train]
                )
            )
            for b in BOUNDARIES
        }
    return offsets


def loco_synthseg_inner(results: list[dict[str, Any]]) -> dict[str, float]:
    return {
        centre: -float(
            np.median(
                [
                    r["methods"]["t1_baseline"]["boundaries"]["inner_skull"]["signed_mean_mm"]
                    for r in results
                    if r["case"][2] != centre
                ]
            )
        )
        for centre in "ABC"
    }


def rescore(
    case: str, subjects: Path, offsets: dict[str, float], synth_inner_mm: float | None = None
) -> dict[str, Any]:
    name = "calibrated-metrics.json" if synth_inner_mm is None else "hybrid-metrics.json"
    return rescore_generic(case, subjects, offsets, name, synth_inner_mm)


def rescore_generic(
    case: str,
    subjects: Path,
    offsets: dict[str, float],
    name: str,
    synth_inner_mm: float | None = None,
) -> dict[str, Any]:
    out = OUT / case / name
    if out.exists():
        return dict(json.loads(out.read_text()))
    t1 = load_nifti(DATA / case / "mr.nii.gz")
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    like = pad(t1, CTSkullParameters().padding_voxels)
    meshes = {
        b: offset_mesh(m, offsets[b]) for b, m in load_watershed(subjects / case, case).items()
    }
    if synth_inner_mm is not None:
        # Hybrid: inner skull from the SynthSeg intracranial surface, calibrated offset.
        from scripts.dev_m33_skull import SYNTHSEG_CACHE
        from soma.anatomy.t1_skull import T1SkullParameters, estimate_t1_skull
        from soma.pipeline.synthseg import load_synthseg

        base = estimate_t1_skull(
            t1,
            load_synthseg(SYNTHSEG_CACHE / case / "synthseg.nii.gz"),
            parameters=T1SkullParameters(),
        )
        meshes["inner_skull"] = offset_mesh(base.meshes["inner_skull"], synth_inner_mm)
    masks = {b: mask_volume(voxelize(m, like), like, boundary=b) for b, m in meshes.items()}
    result = {
        "case": case,
        "offsets_mm": offsets,
        "synthseg_inner_offset_mm": synth_inner_mm,
        "scores": score_case(meshes, masks, truth, region),
    }
    write_json(out, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fs-subjects", type=Path, required=True)
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--hybrid", action="store_true")
    args = parser.parse_args()
    development = set(json.loads(SPLIT.read_text())["development"])
    results = raw_results()
    if {r["case"] for r in results} != development:
        raise SystemExit("Need raw watershed results for every development case first")
    offsets = loco_offsets(results)
    if not (OUT / "loco-offsets.json").exists():
        write_json(OUT / "loco-offsets.json", offsets)
    cases = args.cases or sorted(development)
    if not set(cases) <= development:
        raise SystemExit("Tuning refuses held-out cases")
    for case in cases:
        try:
            synth = loco_synthseg_inner(results)[case[2]] if args.hybrid else None
            rescore(case, args.fs_subjects, offsets[case[2]], synth)
            print("done", case, flush=True)
        except Exception as exc:
            print("FAIL", case, type(exc).__name__, exc, flush=True)


if __name__ == "__main__":
    main()
