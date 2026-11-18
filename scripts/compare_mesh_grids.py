"""Require four real CI environments and bounded numerical physical agreement."""

import argparse
import json
from pathlib import Path

import numpy as np


def compare(root):
    paths = sorted(Path(root).glob("*/mesh-grid-synthetic.json"))
    if len(paths) != 4:
        raise ValueError("Four independent platform reports required")
    reports = [json.loads(p.read_text()) for p in paths]
    environments = {
        (
            r["environment"]["system"],
            r["environment"]["machine"],
            ".".join(r["environment"]["python"].split(".")[:2]),
        )
        for r in reports
    }
    if environments != {
        (os, m, py)
        for os, m in [("Linux", "x86_64"), ("Darwin", "arm64")]
        for py in ["3.11", "3.12"]
    }:
        raise ValueError("Wrong environment coverage")
    baseline = reports[0]
    for r in reports:
        if r["schema"] != "soma.mesh-grid.repro/1" or r["protocol"] != baseline["protocol"]:
            raise ValueError("Identity drift")
        if np.asarray(r["lead"]).shape != (32, 6):
            raise ValueError("Incomplete paired field report")
        if not np.isfinite(r["lead"]).all() or not 0 < r["relative"] < 0.15:
            raise ValueError("Invalid reference result")
        if r["boundary_coordinate_max_m"] > 1e-12 or r["min_mean_ratio"] < 0.01:
            raise ValueError("Invalid physical mesh")
        if not np.allclose(
            r["nearest_mm"], baseline["nearest_mm"], rtol=1e-12, atol=1e-12
        ) or not np.allclose(
            r["tissue_volumes_m3"], baseline["tissue_volumes_m3"], rtol=1e-10, atol=1e-14
        ):
            raise ValueError("Physical geometry/grid disagreement")
        if not np.allclose(r["lead"], baseline["lead"], rtol=0.02, atol=0.01):
            raise ValueError("Cross-platform field disagreement")
    return dict(
        schema="soma.mesh-grid.comparison/1",
        all_passed=True,
        reports=4,
        rtol=0.02,
        atol_V_per_Am=0.01,
        scope=baseline["scope"],
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.write_text(json.dumps(compare(a.root), indent=2) + "\n")
