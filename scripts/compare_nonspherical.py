"""Require four real CI environments and bounded numerical physical agreement."""

import argparse
import json
from pathlib import Path

import numpy as np


def compare(root):
    paths = sorted(Path(root).glob("*/nonspherical-synthetic.json"))
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
        if (
            r["schema"] != "soma.nonspherical.repro/1"
            or r["protocol"] != baseline["protocol"]
            or r["solver_version"] != "2.6.0"
        ):
            raise ValueError("Identity drift")
        if not np.isfinite(r["lead"]).all() or not 0 < r["error"] < 0.04:
            raise ValueError("Invalid reference result")
        if not np.allclose(r["lead"], baseline["lead"], rtol=1e-8, atol=1e-7):
            raise ValueError("Cross-platform field disagreement")
    return dict(
        schema="soma.nonspherical.comparison/1",
        all_passed=True,
        reports=4,
        rtol=1e-8,
        atol_V_per_Am=1e-7,
        scope=baseline["scope"],
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.write_text(json.dumps(compare(a.root), indent=2) + "\n")
