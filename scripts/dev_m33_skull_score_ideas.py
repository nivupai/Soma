"""M33 inner-skull refinement: full mesh scoring of the best training ideas (development only).

Candidate (chosen from ``experiments-all.json``, per-vertex proxy): extra MRI features +
equal case weights + per-scan normalisation + location prior ("combo_rich"), a second-pass
model on top ("cascade"), and lighter mesh smoothing (5 iterations, clip 12 mm). It is scored
with the same mesh pipeline as ``scripts.dev_m33_crop`` (``score_case`` against CT) under
leave-one-centre-out on the 180 SynthRAD2023 cases, and compared case by case with the v3.2
retrain (``refined180-metrics.json``). Nothing here touches CERMEP.

    python -m scripts.dev_m33_skull_score_ideas train            # three fold models
    python -m scripts.dev_m33_skull_score_ideas score --case 1BA001
    python -m scripts.dev_m33_skull_score_ideas aggregate
"""

import argparse
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from scripts.dev_m33_crop import ROOT, SPLIT_FILE, prepared
from scripts.dev_m33_skull import DATA, fs_env
from scripts.dev_m33_skull_improve import CENTRES, OUT, design, fit, load, location_prior, stack
from soma.anatomy.fs_skull import voxelize
from soma.anatomy.inner_skull_refine import RefineParameters, apply_correction
from soma.anatomy.t1_skull import mask_volume, pad
from soma.benchmarks.ct_skull import CTSkullParameters, RegionRule, ct_truth, score_case
from soma.core.provenance import write_json
from soma.imaging.nifti import load_nifti

VARIANT = {"weighted", "casenorm", "location", "rich"}
PARAMS = RefineParameters(smoothing_iterations=5, max_correction_mm=12.0)
MODELS = OUT / "models"
NAME = "ideas-metrics.json"
BASELINE = "refined180-metrics.json"


def pool() -> list[str]:
    split = json.loads(SPLIT_FILE.read_text())
    return sorted(split["development"] + split["held_out"])


def model_path(centre: str) -> Path:
    return MODELS / f"ideas-fold-{centre}.pkl"


def train() -> None:
    cases = pool()
    data = load(cases)
    MODELS.mkdir(parents=True, exist_ok=True)
    for centre in CENTRES:
        path = model_path(centre)
        if path.exists():
            continue
        train_cases = [c for c in cases if c[2] != centre and c in data]
        prior = location_prior(data, train_cases)
        oof_x, oof_y, oof_w = [], [], []
        for inner in sorted({c[2] for c in train_cases}):
            a = [c for c in train_cases if c[2] != inner]
            b = [c for c in train_cases if c[2] == inner]
            m1 = fit(*stack(data, a, VARIANT, prior))
            xb, yb, wb = stack(data, b, VARIANT, prior)
            oof_x.append(np.hstack([xb, m1.predict(xb)[:, None]]))
            oof_y.append(yb)
            oof_w.append(wb)
        stage1 = fit(*stack(data, train_cases, VARIANT, prior))
        stage2 = fit(np.vstack(oof_x), np.concatenate(oof_y), np.concatenate(oof_w))
        path.write_bytes(pickle.dumps({"stage1": stage1, "stage2": stage2, "prior": prior}))
        print("trained fold", centre, flush=True)
    (MODELS / "ideas-folds.done").write_text("ok\n")


def predict(case: str) -> np.ndarray:
    fold = pickle.loads(model_path(case[2]).read_bytes())
    data = load([case])
    x = design(data, case, VARIANT, fold["prior"], every_vertex=True)
    return np.asarray(fold["stage2"].predict(np.hstack([x, fold["stage1"].predict(x)[:, None]])))


def score(case: str) -> None:
    out = ROOT / "cases" / case / NAME
    if out.exists():
        return
    _, _, (meshes,) = prepared(case, fs_env())
    meshes["inner_skull"] = apply_correction(meshes["inner_skull"], predict(case), PARAMS)
    full = load_nifti(DATA / case / "mr.nii.gz")
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    like = pad(full, CTSkullParameters().padding_voxels)
    masks = {b: mask_volume(voxelize(m, like), like, boundary=b) for b, m in meshes.items()}
    write_json(out, {"case": case, "scores": score_case(meshes, masks, truth, region)})


def aggregate() -> None:
    rows = []
    for case in pool():
        a, b = ROOT / "cases" / case / BASELINE, ROOT / "cases" / case / NAME
        if not (a.exists() and b.exists()):
            continue
        old = json.loads(a.read_text())["scores"]["boundaries"]["inner_skull"]
        new = json.loads(b.read_text())["scores"]["boundaries"]["inner_skull"]
        rows.append((case, old["mean_abs_mm"], new["mean_abs_mm"], old["HD95_mm"], new["HD95_mm"]))
    summary: dict[str, Any] = {
        "candidate": "combo_rich + cascade, smoothing 5, clip 12 mm",
        "baseline": "v3.2 retrain (refined180-metrics.json)",
        "boundary": "inner_skull",
        "scheme": "leave-one-centre-out, 180 SynthRAD2023 cases, development only",
    }
    rng = np.random.default_rng(11042)
    for name in ("all", *CENTRES):
        sel = [r for r in rows if name == "all" or r[0][2] == name]
        if not sel:
            continue
        arr = np.array([r[1:] for r in sel], dtype=float)
        diff = arr[:, 1] - arr[:, 0]
        boots = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
        summary[name] = {
            "cases": len(sel),
            "v32_mean_abs_mm": float(arr[:, 0].mean()),
            "ideas_mean_abs_mm": float(arr[:, 1].mean()),
            "v32_mean_abs_mm_median": float(np.median(arr[:, 0])),
            "ideas_mean_abs_mm_median": float(np.median(arr[:, 1])),
            "v32_HD95_mm": float(arr[:, 2].mean()),
            "ideas_HD95_mm": float(arr[:, 3].mean()),
            "mean_abs_change_mm": float(diff.mean()),
            "mean_abs_change_95ci_mm": [
                float(np.percentile(boots, 2.5)),
                float(np.percentile(boots, 97.5)),
            ],
            "cases_improved": int((diff < 0).sum()),
        }
    path = OUT / "full-mesh-summary.json"
    path.write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["train", "score", "aggregate"])
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.step == "train":
        train()
    elif args.step == "score":
        if args.case not in pool():
            raise SystemExit("Development pool only")
        score(args.case)
        print("done", args.case, flush=True)
    else:
        aggregate()


if __name__ == "__main__":
    main()
