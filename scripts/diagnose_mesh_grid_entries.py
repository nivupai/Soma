"""Audit the original comparator's elementwise failures; no gate substitution."""

import argparse
import csv
import itertools
import json
from pathlib import Path

import numpy as np


def entries(actual, reference):
    a, b = np.asarray(actual, float), np.asarray(reference, float)
    if a.shape != (32, 6) or b.shape != a.shape or not np.isfinite([a, b]).all():
        raise ValueError("Complete finite 32x6 lead fields required")
    delta = np.abs(a - b)
    tolerance = 0.01 + 0.02 * np.abs(b)  # np.allclose(actual, reference), unchanged.
    return [
        dict(
            sensor_index=int(i),
            source_index=int(j // 3),
            orientation="XYZ"[j % 3],
            actual_V_per_Am=float(a[i, j]),
            reference_V_per_Am=float(b[i, j]),
            absolute_difference_V_per_Am=float(delta[i, j]),
            relative_difference=None if b[i, j] == 0 else float(delta[i, j] / abs(b[i, j])),
            applied_tolerance_V_per_Am=float(tolerance[i, j]),
            reference_magnitude_V_per_Am=float(abs(b[i, j])),
            reference_below_1_V_per_Am=bool(abs(b[i, j]) < 1),
            failed=bool(delta[i, j] > tolerance[i, j]),
        )
        for i, j in np.ndindex(a.shape)
    ]


def diagnose(root, output):
    paths = sorted(root.glob("*/mesh-grid-synthetic.json"))
    if len(paths) != 4:
        raise ValueError("All four original platform reports required")
    reports = [(p.parent.name, json.loads(p.read_text())) for p in paths]
    all_rows, pairs = [], []
    for (name_b, b), (name_a, a) in itertools.combinations(reports, 2):
        rows = entries(a["lead"], b["lead"])
        for row in rows:
            row.update(
                actual_platform=name_a,
                actual_python=a["environment"]["python"],
                reference_platform=name_b,
                reference_python=b["environment"]["python"],
                original_comparator_pair=name_b == reports[0][0],
            )
        all_rows.extend(rows)
        x, y = np.asarray(a["lead"]), np.asarray(b["lead"])
        failed = [r for r in rows if r["failed"]]
        pairs.append(
            dict(
                actual=name_a,
                reference=name_b,
                aggregate_relative=float(np.linalg.norm(x - y) / np.linalg.norm(y)),
                entries=len(rows),
                failed_entries=len(failed),
                failed_reference_magnitudes=[r["reference_magnitude_V_per_Am"] for r in failed],
                all_median_reference_magnitude=float(np.median(np.abs(y))),
                failed_median_reference_magnitude=None
                if not failed
                else float(np.median([r["reference_magnitude_V_per_Am"] for r in failed])),
                failed_below_1=sum(r["reference_below_1_V_per_Am"] for r in failed),
            )
        )
    output.mkdir(parents=True, exist_ok=True)
    for name, selected in [
        ("all-entries.csv", all_rows),
        ("failing-entries.csv", [r for r in all_rows if r["failed"]]),
        (
            "original-comparator-failures.csv",
            [r for r in all_rows if r["failed"] and r["original_comparator_pair"]],
        ),
    ]:
        with (output / name).open("w") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0]))
            w.writeheader()
            w.writerows(selected)
    (output / "entry-summary.json").write_text(
        json.dumps(
            dict(
                rtol=0.02,
                atol_V_per_Am=0.01,
                relative_denominator="absolute reference entry; undefined at zero",
                small_magnitude_cutoff_V_per_Am=1,
                pairs=pairs,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    diagnose(a.root, a.output)
