"""v3.1 development check: does cropping the MRI (``crop_head_top``) change the v3 method?

Development cases only. Steps per case: crop the T1, run SynthSeg and the watershed on the crop,
extract refinement features from the crop. Then leave-one-centre-out training and scoring as in
``scripts.dev_m33_inner_skull``, plus a final model trained on all 60 cropped development cases.

    python -m scripts.dev_m33_crop prepare --cases ...
    python -m scripts.dev_m33_crop evaluate
"""

import argparse
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from scripts.dev_m33_inner_skull import development, train
from scripts.dev_m33_skull import DATA, build_watershed, fs_env
from scripts.run_m33_segmentation import run_synthseg
from scripts.run_m33_skull_v2 import OFFSETS_MM, SYNTHSEG_CMD
from soma.anatomy.fs_skull import crop_head_top, load_watershed, offset_mesh, voxelize
from soma.anatomy.inner_skull_refine import apply_correction, features, targets
from soma.anatomy.t1_skull import mask_volume, pad
from soma.benchmarks.ct_skull import CTSkullParameters, RegionRule, ct_truth, score_case
from soma.core.provenance import write_json
from soma.imaging.nifti import load_nifti, save_nifti
from soma.pipeline.synthseg import load_synthseg, to_native_grid

ROOT = Path("reports/milestone33/skull-dev-crop")
SUBJECTS = Path("/Volumes/YOTUO/soma-data/fs-subjects-crop")


def prepared(case: str, env: dict[str, str]) -> tuple[Any, Any, list[Any]]:
    """Cropped T1, SynthSeg on it (native grid), calibrated watershed meshes on it."""
    crop_dir = ROOT / "mri" / case
    path = crop_dir / "mr.nii.gz"
    if not path.exists():
        crop_dir.mkdir(parents=True, exist_ok=True)
        save_nifti(crop_head_top(load_nifti(DATA / case / "mr.nii.gz")), path)
    t1 = load_nifti(path)
    synth = load_synthseg(run_synthseg(SYNTHSEG_CMD, path, ROOT / "synthseg" / case))
    synth_native, _ = to_native_grid(synth, t1)
    subject = build_watershed(case, SUBJECTS, env, ROOT / "mri")
    meshes = {b: offset_mesh(m, OFFSETS_MM[b]) for b, m in load_watershed(subject, case).items()}
    return t1, synth_native, [meshes]


def prepare(case: str, env: dict[str, str]) -> None:
    out = ROOT / "cases" / case / "refine-features.npz"
    if out.exists():
        return
    t1, synth, (meshes,) = prepared(case, env)
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    inner = meshes["inner_skull"]
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        x=features(inner, t1, synth),
        y=targets(inner, truth.masks["inner_skull"]),
        region=region.contains_mm(inner.vertices.xyz * 1000),
    )


def score(case: str, model: Any, env: dict[str, str]) -> dict[str, Any]:
    out = ROOT / "cases" / case / "refined-metrics.json"
    if out.exists():
        return dict(json.loads(out.read_text()))
    _, _, (meshes,) = prepared(case, env)
    x = np.load(ROOT / "cases" / case / "refine-features.npz")["x"]
    meshes["inner_skull"] = apply_correction(meshes["inner_skull"], model.predict(x))
    full = load_nifti(DATA / case / "mr.nii.gz")
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    like = pad(full, CTSkullParameters().padding_voxels)
    masks = {b: mask_volume(voxelize(m, like), like, boundary=b) for b, m in meshes.items()}
    result = {"case": case, "scores": score_case(meshes, masks, truth, region)}
    write_json(out, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["prepare", "evaluate"])
    parser.add_argument("--cases", nargs="*")
    args = parser.parse_args()
    dev = development()
    cases = args.cases or dev
    if not set(cases) <= set(dev):
        raise SystemExit("Development only")
    env = fs_env()
    if args.step == "prepare":
        for case in cases:
            try:
                prepare(case, env)
                print("done", case, flush=True)
            except Exception as exc:
                print("FAIL", case, type(exc).__name__, exc, flush=True)
        return
    import scripts.dev_m33_inner_skull as inner

    inner.OUT = ROOT / "cases"  # type: ignore[attr-defined]  # train() reads features here
    models = {c: train([d for d in dev if d[2] != c]) for c in "ABC"}
    for case in cases:
        try:
            score(case, models[case[2]], env)
            print("done", case, flush=True)
        except Exception as exc:
            print("FAIL", case, type(exc).__name__, exc, flush=True)
    final = ROOT / "refine-model-v3.1-final.pkl"
    final.write_bytes(pickle.dumps(train(dev)))


if __name__ == "__main__":
    main()
