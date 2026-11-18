"""Predesigned conditional forward/refinement and paired geometry summaries."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from soma.experiments.nonspherical import hierarchical


def summary(matrix):
    if matrix.shape != (6, 12) or not np.isfinite(matrix).all():
        return dict(status="INCOMPLETE_COVERAGE", mean=None, lower=None, upper=None)
    mean, low, high = hierarchical(matrix)
    return dict(
        status="complete",
        mean=mean,
        lower=low,
        upper=high,
        heads=6,
        sources_per_head=12,
        interval_scope="conditional uncalibrated simulation summary",
    )


def run(root, out):
    forward = pd.read_csv(root / "forward-sources.csv")
    forward = forward[forward.independent_source].copy()
    forward.source -= 12
    rows = []
    for (condition, level), group in forward.groupby(["condition", "level"]):
        if group["head"].notna().sum() == 0:
            continue
        matrix = (
            group.pivot(index="head", columns="source", values="relative")
            .reindex(index=range(6), columns=range(12))
            .to_numpy()
        )
        rows.append(
            dict(
                condition=condition,
                level=int(level),
                estimand="mean offgrid-source combined XYZ relative L2, not aggregate Frobenius",
                **summary(matrix),
            )
        )
    pd.DataFrame(rows).to_csv(out / "forward-hierarchical.csv", index=False)
    rows = []
    for alt, low, high in [(0, 1, 2), (0, 2, 3), (1, 2, 3)]:
        matrix = np.full((6, 12), np.nan)
        for head in range(6):
            a = root / f"F-{head}-{low}-{alt}-V_per_Am.csv"
            b = root / f"F-{head}-{high}-{alt}-V_per_Am.csv"
            if a.exists() and b.exists():
                x = np.loadtxt(a, delimiter=",")[:, 36:].reshape(32, 12, 3)
                y = np.loadtxt(b, delimiter=",")[:, 36:].reshape(32, 12, 3)
                matrix[head] = np.linalg.norm(x - y, axis=(0, 2)) / np.linalg.norm(y, axis=(0, 2))
        rows.append(dict(alternative=bool(alt), low=low, high=high, **summary(matrix)))
    pd.DataFrame(rows).to_csv(out / "refinement-hierarchical.csv", index=False)
    geometry = pd.DataFrame(json.loads((root / "geometry.json").read_text()))
    rows = []
    rng = np.random.default_rng(57042)
    heads = np.concatenate([rng.integers(i, i + 2, (1999, 2)) for i in [0, 2, 4]], axis=1)
    for level, group in geometry[geometry["head"].notna()].groupby("level"):
        a = group.groupby("head").sampled_max_mm.max().reindex(range(6)).to_numpy()
        samples = a[heads].mean(axis=1)
        lo, hi = np.quantile(samples, [0.025, 0.975])
        rows.append(
            dict(
                level=int(level),
                mean_head_sampled_max_mm=float(a.mean()),
                lower=lo,
                upper=hi,
                heads=6,
                scope="head-only stratified bootstrap; sampled distance, not Hausdorff",
            )
        )
    pd.DataFrame(rows).to_csv(out / "geometry-head-uncertainty.csv", index=False)
    inverse = pd.read_csv(root / "inverse.csv")
    keys = ["head", "spacing_mm", "solver", "method", "source", "noise_std_V", "draw"]
    a = inverse[inverse.status == "geometry_truth_sensitivity"]
    b = inverse[
        (inverse.status == "computed")
        & (inverse.spacing_mm == 15)
        & (inverse.noise_std_V == 5e-8)
        & inverse["head"].isin([0, 5])
    ]
    pair = a.merge(b, on=keys, validate="one_to_one", suffixes=("_alternative", "_primary"))
    pair["paired_geometry_truth_delta_mm"] = (
        pair.localization_mm_alternative - pair.localization_mm_primary
    )
    pair[
        keys
        + [
            "localization_mm_alternative",
            "localization_mm_primary",
            "paired_geometry_truth_delta_mm",
        ]
    ].to_csv(out / "geometry-truth-paired.csv", index=False)
    rows = []
    for (head, method, solver), group in pair.groupby(["head", "method", "solver"]):
        means = group.groupby("source").paired_geometry_truth_delta_mm.mean()
        rows.append(
            dict(
                head=int(head),
                method=method,
                solver=solver,
                mean_delta_mm=float(means.mean()),
                min_source_mean_mm=float(means.min()),
                max_source_mean_mm=float(means.max()),
                source_count=len(means),
                scope="head0/head5 sensitivity; no pooled or human interval",
            )
        )
    pd.DataFrame(rows).to_csv(out / "geometry-truth-summary.csv", index=False)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    run(a.root, a.output)
