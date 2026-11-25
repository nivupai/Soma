"""M33 v3 development: learned inner-skull refinement, leave-one-centre-out, development only.

    python -m scripts.dev_m33_inner_skull extract --fs-subjects DIR [--cases ...]
    python -m scripts.dev_m33_inner_skull evaluate --fs-subjects DIR [--cases ...]

``extract`` writes per-case MRI features and CT targets; ``evaluate`` trains on the other two
centres' development cases, refines the held-in case's inner skull and scores it against CT.
"""

import argparse
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from scripts.dev_m33_skull import DATA, OUT, SPLIT, SYNTHSEG_CACHE
from scripts.run_m33_skull_v2 import OFFSETS_MM
from soma.anatomy.fs_skull import load_watershed, offset_mesh, voxelize
from soma.anatomy.inner_skull_refine import apply_correction, features, targets
from soma.anatomy.t1_skull import mask_volume, pad
from soma.benchmarks.ct_skull import CTSkullParameters, RegionRule, ct_truth, score_case
from soma.core.provenance import write_json
from soma.imaging.nifti import load_nifti
from soma.pipeline.synthseg import load_synthseg, to_native_grid

SEED = 11042


def development() -> list[str]:
    return sorted(json.loads(SPLIT.read_text())["development"])


def calibrated(subjects: Path, case: str) -> dict[str, Any]:
    return {
        b: offset_mesh(m, OFFSETS_MM[b]) for b, m in load_watershed(subjects / case, case).items()
    }


def load_case(case: str) -> tuple[Any, Any, Any, Any]:
    t1 = load_nifti(DATA / case / "mr.nii.gz")
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    synth, _ = to_native_grid(load_synthseg(SYNTHSEG_CACHE / case / "synthseg.nii.gz"), t1)
    return t1, ct, mask, synth


def extract(case: str, subjects: Path) -> None:
    out = OUT / case / "refine-features.npz"
    if out.exists():
        return
    t1, ct, mask, synth = load_case(case)
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    inner = calibrated(subjects, case)["inner_skull"]
    x = features(inner, t1, synth)
    y = targets(inner, truth.masks["inner_skull"])
    keep = region.contains_mm(inner.vertices.xyz * 1000)
    np.savez_compressed(out, x=x, y=y, region=keep)


def train(cases: list[str]) -> Any:
    from sklearn.ensemble import HistGradientBoostingRegressor

    xs, ys = [], []
    for case in cases:
        d = np.load(OUT / case / "refine-features.npz")
        # Train on region vertices; clip extreme targets (watershed failures) to stay robust.
        xs.append(d["x"][d["region"]])
        ys.append(np.clip(d["y"][d["region"]], -12, 12))
    model = HistGradientBoostingRegressor(
        loss="absolute_error",
        max_iter=300,
        learning_rate=0.08,
        max_leaf_nodes=31,
        random_state=SEED,
    )
    model.fit(np.vstack(xs), np.concatenate(ys))
    return model


def evaluate(case: str, subjects: Path, model: Any) -> dict[str, Any]:
    out = OUT / case / "refined-metrics.json"
    if out.exists():
        return dict(json.loads(out.read_text()))
    t1, ct, mask, synth = load_case(case)
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    meshes = calibrated(subjects, case)
    x = np.load(OUT / case / "refine-features.npz")["x"]
    meshes["inner_skull"] = apply_correction(meshes["inner_skull"], model.predict(x))
    like = pad(t1, CTSkullParameters().padding_voxels)
    masks = {b: mask_volume(voxelize(m, like), like, boundary=b) for b, m in meshes.items()}
    result = {"case": case, "scores": score_case(meshes, masks, truth, region)}
    write_json(out, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["extract", "evaluate"])
    parser.add_argument("--fs-subjects", type=Path, required=True)
    parser.add_argument("--cases", nargs="*")
    args = parser.parse_args()
    dev = development()
    cases = args.cases or dev
    if not set(cases) <= set(dev):
        raise SystemExit("Development only")
    if args.step == "extract":
        for case in cases:
            try:
                extract(case, args.fs_subjects)
                print("done", case, flush=True)
            except Exception as exc:
                print("FAIL", case, type(exc).__name__, exc, flush=True)
        return
    models: dict[str, Any] = {}
    for centre in sorted({c[2] for c in cases}):
        path = OUT / f"refine-model-loco-{centre}.pkl"
        if path.exists():
            models[centre] = pickle.loads(path.read_bytes())
        else:
            models[centre] = train([c for c in dev if c[2] != centre])
            path.write_bytes(pickle.dumps(models[centre]))
    for case in cases:
        try:
            evaluate(case, args.fs_subjects, models[case[2]])
            print("done", case, flush=True)
        except Exception as exc:
            print("FAIL", case, type(exc).__name__, exc, flush=True)


if __name__ == "__main__":
    main()
