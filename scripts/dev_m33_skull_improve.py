"""M33 inner-skull refinement: training-improvement experiments (development data only).

Reads the per-case features already written by ``scripts.dev_m33_crop prepare``
(``reports/milestone33/skull-dev-crop/cases/<case>/refine-features.npz``) and compares training
variants under leave-one-centre-out. Nothing here touches CERMEP or any sealed test set, and
nothing is sealed or written to configs.

    python -m scripts.dev_m33_skull_improve --pool dev   # 60 development cases
    python -m scripts.dev_m33_skull_improve --pool all   # 180 once the retrain has features

Metric is a fast per-vertex proxy: |CT signed distance - predicted correction| on region
vertices, before mesh smoothing and clipping. It ranks variants; the winner must still be
scored with the full mesh pipeline (``score_case``) before any claim.

Variants:
- base: the v3.1 model exactly (MAE loss, 300 iters, lr 0.08, 31 leaves).
- weighted: every case counts equally (sample weight 1 / region vertices of that case).
- casenorm: T1 profile and gradient columns robust-scaled per case (median / IQR over that
  case's vertices) to reduce scanner and centre intensity differences.
- location: adds a vertex-location prior. Watershed meshes are deformed ico-5 spheres (10242
  vertices) so a vertex index means roughly the same place on every head; the feature is that
  index's mean outward direction over the training cases (MRI-only).
- combo: weighted + casenorm + location.
- rich / combo_rich: adds ``refine-features2.npz`` (``scripts.dev_m33_skull_features2``).
- cascade: the best single-stage variant, plus a second model on combo features + out-of-fold stage-1 prediction.
- thick: the best variant (without the extra features) with 3 mm degraded copies of the
  training centres' cases added (``scripts.dev_m33_skull_thick``), scored on 1 mm and 3 mm.
- smoothing grid: mesh smoothing iterations x correction clip for the best variant.
- quantile: the best variant trained at the 10th / 50th / 90th percentile; reports how often the CT truth
  falls in the 10-90 range per centre, the range width, and whether wider ranges mark larger
  errors (Spearman); then the same after conformal calibration (CQR) fitted on the training
  centres only, which widens the range by a fixed margin to reach 80 % coverage.
"""

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path("reports/milestone33/skull-dev-crop")
SPLIT_FILE = Path("configs/m33-skull-v2-split.json")
OUT = Path("reports/milestone33/skull-improve")
THICK = Path("reports/milestone33/skull-dev-thick")
SEED = 11042
CLIP = 12.0
N_PROFILE = 21
PROFILE_COLS = slice(0, 2 * N_PROFILE - 1)  # T1 profile (21) + gradient (20)
DIRECTION_COLS = slice(3 * N_PROFILE - 1, 3 * N_PROFILE + 2)  # 62:65
CENTRES = "ABC"


def gbm(loss: str = "absolute_error", quantile: float | None = None) -> Any:
    from sklearn.ensemble import HistGradientBoostingRegressor

    kw: dict[str, Any] = {"loss": loss}
    if quantile is not None:
        kw = {"loss": "quantile", "quantile": quantile}
    return HistGradientBoostingRegressor(
        **kw, max_iter=300, learning_rate=0.08, max_leaf_nodes=31, random_state=SEED
    )


def load(cases: list[str], root: Path = ROOT) -> dict[str, dict[str, np.ndarray]]:
    data = {}
    for case in cases:
        path = root / "cases" / case / "refine-features.npz"
        if not path.exists():
            continue
        d = np.load(path)
        data[case] = {"x": d["x"].astype(np.float32), "y": d["y"], "region": d["region"]}
        extra = root / "cases" / case / "refine-features2.npz"
        if extra.exists():
            e = np.load(extra)
            data[case]["x2"] = e["x2"].astype(np.float32)
            data[case]["faces"] = e["faces"]
    return data


def casenorm(x: np.ndarray) -> np.ndarray:
    x = x.copy()
    block = x[:, PROFILE_COLS]
    med = np.median(block, axis=0)
    iqr = np.subtract(*np.percentile(block, [75, 25], axis=0))
    x[:, PROFILE_COLS] = (block - med) / np.maximum(iqr, 1e-3)
    return x


def location_prior(data: dict[str, dict[str, np.ndarray]], cases: list[str]) -> np.ndarray | None:
    sizes = {len(data[c]["x"]) for c in cases}
    if len(sizes) != 1:
        return None  # meshes not in vertex correspondence; skip the prior
    mean = np.mean([data[c]["x"][:, DIRECTION_COLS] for c in cases], axis=0)
    return np.asarray(mean / np.maximum(np.linalg.norm(mean, axis=1, keepdims=True), 1e-9))


def design(
    data: dict[str, dict[str, np.ndarray]],
    case: str,
    variant: set[str],
    prior: Any,
    every_vertex: bool = False,
) -> np.ndarray:
    x = data[case]["x"]
    if "casenorm" in variant:
        x = casenorm(x)
    if "location" in variant and prior is not None and len(prior) == len(x):
        x = np.hstack([x, prior.astype(np.float32)])
    if "rich" in variant:
        x = np.hstack([x, data[case]["x2"]])
    return np.asarray(x if every_vertex else x[data[case]["region"]])


def smooth(faces: np.ndarray, values: np.ndarray, iterations: int) -> np.ndarray:
    """Same neighbour averaging as soma.anatomy.inner_skull_refine.smooth_on_mesh."""
    n = len(values)
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.vstack([edges, edges[:, ::-1]])
    degree = np.bincount(edges[:, 0], minlength=n).astype(float)
    v = values.astype(float).copy()
    for _ in range(iterations):
        total = np.bincount(edges[:, 0], weights=v[edges[:, 1]], minlength=n)
        v = 0.5 * v + 0.5 * total / np.maximum(degree, 1)
    return v


def stack(
    data: dict[str, dict[str, np.ndarray]], cases: list[str], variant: set[str], prior: Any
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    xs, ys, ws = [], [], []
    for c in cases:
        x = design(data, c, variant, prior)
        xs.append(x)
        ys.append(np.clip(data[c]["y"][data[c]["region"]], -CLIP, CLIP))
        ws.append(np.full(len(x), 1.0 / len(x) if "weighted" in variant else 1.0))
    w = np.concatenate(ws)
    return np.vstack(xs), np.concatenate(ys), w / w.mean()


def fit(x: np.ndarray, y: np.ndarray, w: np.ndarray, **kw: Any) -> Any:
    return gbm(**kw).fit(x, y, sample_weight=w)


def case_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    yc = np.clip(y, -CLIP, CLIP)
    r = np.abs(yc - pred)
    return {
        "mean_abs_mm": float(r.mean()),
        "p95_abs_mm": float(np.percentile(r, 95)),
        "uncorrected_mean_abs_mm": float(np.abs(yc).mean()),
    }


def summarise(per_case: dict[str, dict[str, float]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    groups = {"all": list(per_case)} | {c: [k for k in per_case if k[2] == c] for c in CENTRES}
    for name, keys in groups.items():
        if not keys:
            continue
        m = np.array([per_case[k]["mean_abs_mm"] for k in keys])
        p = np.array([per_case[k]["p95_abs_mm"] for k in keys])
        out[name] = {
            "cases": len(keys),
            "mean_abs_mm_median": float(np.median(m)),
            "mean_abs_mm_mean": float(m.mean()),
            "p95_abs_mm_median": float(np.median(p)),
        }
    return out


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def thick_augmentation(
    data: dict[str, dict[str, np.ndarray]], cases: list[str], variant: set[str]
) -> dict[str, Any] | None:
    """Add 3 mm degraded copies of the training centres' cases to training.

    Scores the held-out centre's original 1 mm cases and its 3 mm copies, with and without the
    copies in training. Copies of held-out cases are never used for training.
    """
    thick = {f"{c}#thick": d for c, d in load(cases, THICK).items()}
    if len(thick) < len(cases) // 2:
        return None
    every = {**data, **thick}
    per: dict[str, dict[str, dict[str, float]]] = {
        k: {} for k in ("1mm_without", "1mm_with", "3mm_without", "3mm_with")
    }
    for centre in CENTRES:
        train = [c for c in cases if c[2] != centre]
        test = [c for c in cases if c[2] == centre]
        if not train or not test:
            continue
        prior = location_prior(data, train)
        plain = fit(*stack(every, train, variant, prior))
        augmented = fit(
            *stack(every, train + [f"{c}#thick" for c in train if f"{c}#thick" in thick],
                   variant, prior)
        )
        for c in test:
            for tag, key in (("1mm", c), ("3mm", f"{c}#thick")):
                if key not in every:
                    continue
                y = every[key]["y"][every[key]["region"]]
                x = design(every, key, variant, prior)
                per[f"{tag}_without"][c] = case_metrics(y, plain.predict(x))
                per[f"{tag}_with"][c] = case_metrics(y, augmented.predict(x))
    return {
        "thick_cases": len(thick),
        "summary": {k: summarise(v).get("all", {}) for k, v in per.items()},
        "by_centre": {k: summarise(v) for k, v in per.items()},
    }


def smoothing_grid(
    data: dict[str, dict[str, np.ndarray]], cases: list[str], variant: set[str]
) -> dict[str, Any]:
    """Proxy for the mesh step: smooth predictions over the whole mesh, clip, score region."""
    preds: dict[str, np.ndarray] = {}
    for centre in CENTRES:
        train = [c for c in cases if c[2] != centre]
        test = [c for c in cases if c[2] == centre]
        if not train or not test:
            continue
        prior = location_prior(data, train)
        model = fit(*stack(data, train, variant, prior))
        for c in test:
            preds[c] = model.predict(design(data, c, variant, prior, every_vertex=True))
    grid: dict[str, Any] = {}
    for iters in (0, 5, 10, 20, 40):
        for clip in (4.0, 6.0, 8.0, 12.0):
            scores = []
            for c, p in preds.items():
                q = np.clip(smooth(data[c]["faces"], p, iters), -clip, clip)
                r = data[c]["region"]
                scores.append(case_metrics(data[c]["y"][r], q[r])["mean_abs_mm"])
            grid[f"smooth{iters}_clip{clip:g}"] = float(np.median(scores))
    key = min(grid, key=grid.__getitem__)
    return {
        "median_mean_abs_mm": grid,
        "best": {key: grid[key]},
        "current_v31": grid["smooth10_clip6"],
    }


def run(pool: str) -> dict[str, Any]:
    split = json.loads(SPLIT_FILE.read_text())
    cases = sorted(split["development"] + (split["held_out"] if pool == "all" else []))
    data = load(cases)
    cases = sorted(data)
    variants = {
        "base": set(),
        "weighted": {"weighted"},
        "casenorm": {"casenorm"},
        "location": {"location"},
        "combo": {"weighted", "casenorm", "location"},
    }
    rich_ready = all("x2" in data[c] for c in cases)
    if rich_ready:
        variants["rich"] = {"rich"}
        variants["combo_rich"] = {"weighted", "casenorm", "location", "rich"}
    results: dict[str, Any] = {
        "pool": pool,
        "cases": len(cases),
        "metric": "per-vertex |CT signed distance - prediction| on region vertices, "
        f"targets clipped to +/-{CLIP} mm, before smoothing; proxy for ranking only",
        "variants": {},
    }
    per_variant: dict[str, dict[str, dict[str, float]]] = {}
    for name, variant in variants.items():
        t0 = time.time()
        per_case: dict[str, dict[str, float]] = {}
        for centre in CENTRES:
            train = [c for c in cases if c[2] != centre]
            test = [c for c in cases if c[2] == centre]
            if not train or not test:
                continue
            prior = location_prior(data, train)
            model = fit(*stack(data, train, variant, prior))
            for c in test:
                pred = model.predict(design(data, c, variant, prior))
                per_case[c] = case_metrics(data[c]["y"][data[c]["region"]], pred)
        per_variant[name] = per_case
        results["variants"][name] = summarise(per_case) | {"seconds": round(time.time() - t0)}
        print(name, json.dumps(results["variants"][name].get("all")), flush=True)

    best = min(
        results["variants"], key=lambda k: results["variants"][k]["all"]["mean_abs_mm_median"]
    )
    results["best_single_stage"] = best
    if rich_ready:
        results["smoothing_grid"] = smoothing_grid(data, cases, variants[best])
        print("smoothing", json.dumps(results["smoothing_grid"]["best"]), flush=True)

    thick_results = thick_augmentation(data, cases, variants[best] - {"rich"})
    if thick_results:
        results["thick_augmentation"] = thick_results
        print("thick", json.dumps(thick_results["summary"]), flush=True)

    # Cascade on the best single-stage variant: stage-1 out-of-fold within the training
    # centres, then stage 2 on features + stage-1 prediction.
    combo = variants[best]
    results["cascade_and_quantile_variant"] = best
    per_case = {}
    for centre in CENTRES:
        train = [c for c in cases if c[2] != centre]
        test = [c for c in cases if c[2] == centre]
        if not train or not test:
            continue
        prior = location_prior(data, train)
        oof_x, oof_y, oof_w = [], [], []
        for inner in sorted({c[2] for c in train}):
            a = [c for c in train if c[2] != inner]
            b = [c for c in train if c[2] == inner]
            if not a:
                continue
            m1 = fit(*stack(data, a, combo, prior))
            xb, yb, wb = stack(data, b, combo, prior)
            oof_x.append(np.hstack([xb, m1.predict(xb)[:, None]]))
            oof_y.append(yb)
            oof_w.append(wb)
        stage1 = fit(*stack(data, train, combo, prior))
        if not oof_x:
            continue  # only one training centre: no out-of-fold stage 1 to learn from
        stage2 = fit(np.vstack(oof_x), np.concatenate(oof_y), np.concatenate(oof_w))
        for c in test:
            x = design(data, c, combo, prior)
            pred = stage2.predict(np.hstack([x, stage1.predict(x)[:, None]]))
            per_case[c] = case_metrics(data[c]["y"][data[c]["region"]], pred)
    per_variant["cascade"] = per_case
    results["variants"]["cascade"] = summarise(per_case)
    print("cascade", json.dumps(results["variants"]["cascade"].get("all")), flush=True)

    # Quantile error ranges on the best single-stage variant.
    cover: dict[str, list[float]] = {c: [] for c in CENTRES}
    width: dict[str, list[float]] = {c: [] for c in CENTRES}
    rho: dict[str, list[float]] = {c: [] for c in CENTRES}
    cover_cal: dict[str, list[float]] = {c: [] for c in CENTRES}
    width_cal: dict[str, list[float]] = {c: [] for c in CENTRES}
    margins: dict[str, float] = {}
    for centre in CENTRES:
        train = [c for c in cases if c[2] != centre]
        test = [c for c in cases if c[2] == centre]
        if not train or not test:
            continue
        prior = location_prior(data, train)
        xt, yt, wt = stack(data, train, combo, prior)
        lo, mid, hi = (fit(xt, yt, wt, quantile=q) for q in (0.1, 0.5, 0.9))
        # Conformal calibration (CQR) using only the training centres: fit the range on all but
        # one training centre, score how far that centre's truth falls outside, and widen by
        # the median over its cases of each case's 80th-percentile miss.
        case_q: list[float] = []
        for inner in sorted({c[2] for c in train}):
            a = [c for c in train if c[2] != inner]
            b = [c for c in train if c[2] == inner]
            if not a:
                continue
            xa, ya, wa = stack(data, a, combo, prior)
            ilo, ihi = (fit(xa, ya, wa, quantile=q) for q in (0.1, 0.9))
            for c in b:
                xb = design(data, c, combo, prior)
                yb = np.clip(data[c]["y"][data[c]["region"]], -CLIP, CLIP)
                miss = np.maximum(ilo.predict(xb) - yb, yb - ihi.predict(xb))
                case_q.append(float(np.percentile(miss, 80)))
        margin = float(np.median(case_q)) if case_q else 0.0
        margins[centre] = margin
        for c in test:
            x = design(data, c, combo, prior)
            y = np.clip(data[c]["y"][data[c]["region"]], -CLIP, CLIP)
            ql, qm, qh = lo.predict(x), mid.predict(x), hi.predict(x)
            cover[centre].append(float(np.mean((y >= ql) & (y <= qh))))
            width[centre].append(float(np.median(qh - ql)))
            rho[centre].append(spearman(qh - ql, np.abs(y - qm)))
            cl, ch = ql - margin, qh + margin
            cover_cal[centre].append(float(np.mean((y >= cl) & (y <= ch))))
            width_cal[centre].append(float(np.median(ch - cl)))
    results["quantile_10_90"] = {
        "nominal_coverage": 0.8,
        **{
            c: {
                "coverage_median": float(np.median(cover[c])),
                "coverage_min": float(np.min(cover[c])),
                "width_mm_median": float(np.median(width[c])),
                "width_vs_error_spearman_median": float(np.median(rho[c])),
                "calibration_margin_mm": margins[c],
                "calibrated_coverage_median": float(np.median(cover_cal[c])),
                "calibrated_coverage_min": float(np.min(cover_cal[c])),
                "calibrated_width_mm_median": float(np.median(width_cal[c])),
            }
            for c in CENTRES
            if cover[c]
        },
    }
    print("quantile", json.dumps(results["quantile_10_90"]), flush=True)
    results["per_case"] = per_variant  # case IDs stay local (reports/ is not published)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", choices=["dev", "all"], default="dev")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    result = run(args.pool)
    path = OUT / f"experiments-{args.pool}.json"
    path.write_text(json.dumps(result, indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
