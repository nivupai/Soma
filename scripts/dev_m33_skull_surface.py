"""M33 inner skull: surface taken straight from the 3D network, plus an MRI-only per-case choice.

Development pools only (180 SynthRAD2023 cases, leave-one-centre-out). Nothing here touches
CERMEP.

- ``worst``: diagnosis of the 10 cases with the largest error after the improved
  gradient-boosted model ("ideas"): how far the starting watershed surface is from the CT inner
  skull, and how much of it lies beyond the 12 mm correction clip. CT is read for diagnosis only.
- ``score``: the network surface. Starting from the calibrated watershed inner skull, every
  vertex is walked onto the zero level of the network's predicted distance map (several small
  steps along the map's gradient, smoothed over the mesh), so the result is no longer limited
  by the 12 mm clip. The mesh keeps its ico-5 topology. The same case also records an MRI-only
  disagreement between this surface and the ideas surface (no CT).
- ``aggregate``: the per-case choice. For each held-out centre, a disagreement threshold is
  picked on the other two centres; a held-out case uses the network surface when its
  disagreement is above that threshold, else the ideas surface. Compared with v3.2 and ideas.

    python -m scripts.dev_m33_skull_surface worst
    python -m scripts.dev_m33_skull_surface score --case 1BA001
    python -m scripts.dev_m33_skull_surface aggregate
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

OUT = Path("reports/milestone33/skull-surface")
NAME = "netsurf-metrics.json"
CHOICE = "surface-choice.json"
CENTRES = "ABC"
SEED = 11042
STEPS = 12
STEP_MM = 3.0
SMOOTH = 3
FINAL_SMOOTH = 2
THRESHOLDS_MM = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 1e9)
NAMES = {
    "v32": "refined180-metrics.json",
    "ideas": "ideas-metrics.json",
    "net": "net-metrics.json",
    "netsurf": NAME,
}


def pool() -> list[str]:
    from scripts.dev_m33_skull_net import pool as net_pool

    return list(net_pool())


# ---------------------------------------------------------------- the network surface
def smooth_vectors(faces: np.ndarray, n: int, vec: np.ndarray, iterations: int) -> np.ndarray:
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.vstack([edges, edges[:, ::-1]])
    degree = np.maximum(np.bincount(edges[:, 0], minlength=n), 1).astype(float)
    v = vec.astype(float).copy()
    for _ in range(iterations):
        total = np.stack(
            [np.bincount(edges[:, 0], weights=v[edges[:, 1], k], minlength=n) for k in range(3)],
            axis=1,
        )
        v = 0.5 * v + 0.5 * total / degree[:, None]
    return v


def project_to_zero(
    xyz_m: np.ndarray,
    faces: np.ndarray,
    sdf_mm: np.ndarray,
    affine: np.ndarray,
    *,
    steps: int = STEPS,
    step_mm: float = STEP_MM,
    smooth: int = SMOOTH,
    final_smooth: int = FINAL_SMOOTH,
) -> np.ndarray:
    """Walk vertices onto the zero level of a signed distance map (mm, + outside).

    Each step moves a vertex by ``-clip(d, ±step_mm)`` along the unit gradient of the map, with
    the displacement field smoothed over the mesh so neighbouring vertices move together.
    """
    from scripts.dev_m33_skull_net import sample_grid

    spacing_mm = np.abs(np.diag(affine[:3, :3])) * 1000.0
    grads = np.gradient(sdf_mm.astype(np.float32), *spacing_mm)
    x = xyz_m.copy()
    n = len(x)
    for _ in range(steps):
        d = sample_grid(sdf_mm, affine, x)
        g = np.stack([sample_grid(gk, affine, x) for gk in grads], axis=1)
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
        move_mm = -np.clip(d, -step_mm, step_mm)[:, None] * g
        x = x + smooth_vectors(faces, n, move_mm, smooth) / 1000.0
    if final_smooth:
        x = _laplacian(x, faces, final_smooth)
    return x


def _laplacian(x: np.ndarray, faces: np.ndarray, iterations: int) -> np.ndarray:
    """Taubin smoothing (no shrink) of vertex positions."""
    n = len(x)
    for _ in range(iterations):
        for lam in (0.5, -0.53):
            avg = smooth_vectors(faces, n, x, 1) * 2 - x  # neighbour mean
            x = x + lam * (avg - x)
    return x


# ---------------------------------------------------------------- per case
def _case_data(case: str) -> dict[str, Any]:
    from scripts.dev_m33_crop import prepared
    from scripts.dev_m33_skull import fs_env

    _, _, (meshes,) = prepared(case, fs_env())
    return dict(meshes)


def _truth(case: str) -> tuple[Any, Any, Any]:
    from scripts.dev_m33_skull import DATA
    from soma.anatomy.t1_skull import pad
    from soma.benchmarks.ct_skull import CTSkullParameters, RegionRule, ct_truth
    from soma.imaging.nifti import load_nifti

    full = load_nifti(DATA / case / "mr.nii.gz")
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    like = pad(full, CTSkullParameters().padding_voxels)
    return truth, region, like


def score(case: str) -> None:
    from scripts.dev_m33_crop import ROOT
    from scripts.dev_m33_skull_net import predict_grid
    from scripts.dev_m33_skull_score_ideas import PARAMS
    from scripts.dev_m33_skull_score_ideas import predict as ideas_predict
    from soma.anatomy.fs_skull import voxelize
    from soma.anatomy.inner_skull_refine import apply_correction
    from soma.anatomy.t1_skull import mask_volume
    from soma.benchmarks.ct_skull import score_case
    from soma.core.provenance import write_json
    from soma.geometry import Points
    from soma.imaging.surfaces import Mesh

    out = ROOT / "cases" / case / NAME
    choice = ROOT / "cases" / case / CHOICE
    if out.exists() and choice.exists():
        return
    meshes = _case_data(case)
    inner = meshes["inner_skull"]
    faces = np.asarray(inner.faces)
    pred, affine = predict_grid(case)
    xyz = project_to_zero(inner.vertices.xyz, faces, pred, affine)
    net_mesh = Mesh(Points(xyz, inner.vertices.frame), faces, {**inner.metadata, "net_surface": 1})
    ideas_mesh = apply_correction(inner, ideas_predict(case), PARAMS)
    # MRI-only disagreement between the two candidate surfaces (same vertex order).
    gap_mm = np.linalg.norm(net_mesh.vertices.xyz - ideas_mesh.vertices.xyz, axis=1) * 1000.0
    moved_mm = np.linalg.norm(xyz - inner.vertices.xyz, axis=1) * 1000.0
    write_json(
        choice,
        {
            "case": case,
            "mri_only": True,
            "gap_mean_mm": float(gap_mm.mean()),
            "gap_p95_mm": float(np.percentile(gap_mm, 95)),
            "gap_frac_over_5mm": float((gap_mm > 5).mean()),
            "net_moved_max_mm": float(moved_mm.max()),
            "net_residual_mean_mm": float(np.abs(_sample_pred(pred, affine, xyz)).mean()),
        },
    )
    truth, region, like = _truth(case)
    m = dict(meshes)
    m["inner_skull"] = net_mesh
    masks = {b: mask_volume(voxelize(v, like), like, boundary=b) for b, v in m.items()}
    write_json(out, {"case": case, "scores": score_case(m, masks, truth, region)})


def _sample_pred(pred: np.ndarray, affine: np.ndarray, xyz: np.ndarray) -> np.ndarray:
    from scripts.dev_m33_skull_net import sample_grid

    return sample_grid(pred, affine, xyz)


# ---------------------------------------------------------------- diagnosis of the worst cases
def _scores(case: str) -> dict[str, float] | None:
    from scripts.dev_m33_crop import ROOT

    row: dict[str, float] = {}
    for k, name in NAMES.items():
        f = ROOT / "cases" / case / name
        if not f.exists():
            if k == "netsurf":
                continue
            return None
        row[k] = json.loads(f.read_text())["scores"]["boundaries"]["inner_skull"]["mean_abs_mm"]
    return row


def worst() -> None:
    from soma.anatomy.inner_skull_refine import targets

    rows = {c: r for c in pool() if (r := _scores(c)) is not None}
    ranked = sorted(rows, key=lambda c: rows[c]["ideas"], reverse=True)
    out: dict[str, Any] = {
        "note": "development only; CT read for diagnosis; no case IDs",
        "cases_scored": len(rows),
        "ideas_mean_all_mm": float(np.mean([r["ideas"] for r in rows.values()])),
        "ideas_mean_without_worst10_mm": float(np.mean([rows[c]["ideas"] for c in ranked[10:]])),
        "worst": [],
    }
    for rank, case in enumerate(ranked[:10], 1):
        truth, _, _ = _truth(case)
        inner = _case_data(case)["inner_skull"]
        t = targets(inner, truth.masks["inner_skull"])
        out["worst"].append(
            {
                "rank": rank,
                "centre": case[2],
                "ideas_mm": rows[case]["ideas"],
                "net_mm": rows[case]["net"],
                "v32_mm": rows[case]["v32"],
                "watershed_start_mean_abs_mm": float(np.abs(t).mean()),
                "watershed_start_p95_abs_mm": float(np.percentile(np.abs(t), 95)),
                "watershed_frac_beyond_12mm": float((np.abs(t) > 12).mean()),
                "watershed_mostly_outside": bool(np.median(t) > 0),
            }
        )
        print(json.dumps(out["worst"][-1]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "worst10.json").write_text(json.dumps(out, indent=1))


# ---------------------------------------------------------------- per-case choice and summary
def _boot(diff: np.ndarray, rng: np.random.Generator) -> list[float]:
    boots = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
    return [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]


def aggregate() -> None:
    from scripts.dev_m33_crop import ROOT

    rows: dict[str, dict[str, float]] = {}
    for c in pool():
        r = _scores(c)
        f = ROOT / "cases" / c / CHOICE
        if r is None or "netsurf" not in r or not f.exists():
            continue
        r["gap"] = json.loads(f.read_text())["gap_mean_mm"]
        rows[c] = r

    def chosen(c: str, tau: float) -> float:
        return rows[c]["netsurf"] if rows[c]["gap"] > tau else rows[c]["ideas"]

    thresholds: dict[str, float] = {}
    for centre in CENTRES:
        train = [c for c in rows if c[2] != centre]
        if not train:
            continue
        thresholds[centre] = min(
            THRESHOLDS_MM, key=lambda t: float(np.mean([chosen(c, t) for c in train]))
        )
    for c in rows:
        tau = thresholds.get(c[2], 1e9)
        rows[c]["choice"] = chosen(c, tau)
        rows[c]["used_net"] = float(rows[c]["gap"] > tau)
    rng = np.random.default_rng(SEED)
    summary: dict[str, Any] = {
        "boundary": "inner_skull",
        "scheme": "leave-one-centre-out, 180 SynthRAD2023 cases, development only",
        "models": {
            "v32": "gradient-boosted refinement, 180-case retrain",
            "ideas": "improved gradient-boosted model (recommended so far)",
            "net": "3D U-Net, one clipped correction step",
            "netsurf": "3D U-Net zero surface (iterative projection, no 12 mm clip)",
            "choice": "netsurf where the MRI-only gap to ideas exceeds a threshold picked on "
            "the other two centres, else ideas",
        },
        "thresholds_mm": {k: (None if v >= 1e8 else v) for k, v in thresholds.items()},
    }
    for group in ("all", *CENTRES):
        keys = [c for c in rows if group == "all" or c[2] == group]
        if not keys:
            continue
        entry: dict[str, Any] = {
            "cases": len(keys),
            "cases_using_net": int(sum(rows[c]["used_net"] for c in keys)),
        }
        v32 = np.array([rows[c]["v32"] for c in keys])
        ideas = np.array([rows[c]["ideas"] for c in keys])
        for k in ("v32", "ideas", "net", "netsurf", "choice"):
            a = np.array([rows[c][k] for c in keys])
            entry[k] = {"mean_abs_mm": float(a.mean()), "mean_abs_mm_median": float(np.median(a))}
            if k != "v32":
                entry[k]["change_vs_v32_mm"] = float((a - v32).mean())
                entry[k]["change_vs_v32_95ci_mm"] = _boot(a - v32, rng)
                entry[k]["cases_improved_vs_v32"] = int((a < v32).sum())
            if k in ("netsurf", "choice"):
                entry[k]["change_vs_ideas_mm"] = float((a - ideas).mean())
                entry[k]["change_vs_ideas_95ci_mm"] = _boot(a - ideas, rng)
                entry[k]["cases_improved_vs_ideas"] = int((a < ideas).sum())
        summary[group] = entry
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["worst", "score", "aggregate"])
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.step == "worst":
        worst()
    elif args.step == "score":
        if args.case not in pool():
            raise SystemExit("Development pool only")
        score(args.case)
        print("done", args.case, flush=True)
    else:
        aggregate()


if __name__ == "__main__":
    main()
