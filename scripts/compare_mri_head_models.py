"""Mandatory elementwise MRI software fixture gate, not human validation."""

import argparse
import json
from pathlib import Path

import numpy as np


def compare(root):
    paths = sorted(root.glob("*/mri-head-model-synthetic.json"))
    if len(paths) != 4:
        raise ValueError("Four MRI software reports required")
    reports = [json.loads(p.read_text()) for p in paths]
    env = {
        (
            r["environment"]["system"],
            r["environment"]["machine"],
            ".".join(r["environment"]["python"].split(".")[:2]),
        )
        for r in reports
    }
    if env != {
        (os, arch, py)
        for os, arch in [("Linux", "x86_64"), ("Darwin", "arm64")]
        for py in ["3.11", "3.12"]
    }:
        raise ValueError("MRI environment coverage mismatch")
    expected_keys = {
        "schema",
        "synthetic_only",
        "environment",
        "coordinates_m",
        "volume_m3",
        "weights_m3",
        "kernel",
    }
    for r in reports:
        if (
            set(r) != expected_keys
            or r["schema"] != "soma.mri-head-model.repro/1"
            or r["synthetic_only"] is not True
        ):
            raise ValueError("Invalid MRI fixture identity")
        for k, shape in [
            ("coordinates_m", (2, 3)),
            ("weights_m3", (3,)),
            ("volume_m3", ()),
            ("kernel", (9, 5)),
        ]:
            x, y = np.asarray(r[k]), np.asarray(reports[0][k])
            if (
                x.shape != shape
                or not np.isfinite(x).all()
                or not np.allclose(x, y, rtol=1e-10, atol=1e-12)
            ):
                raise ValueError("MRI elementwise numerical disagreement: " + k)
        np.testing.assert_allclose(
            r["coordinates_m"], [[0.002, -0.012, 0.006], [0.001, -0.003, 0.002]], rtol=0, atol=1e-15
        )
        np.testing.assert_allclose(r["volume_m3"], 23 * 0.002**3, rtol=1e-12, atol=0)
        np.testing.assert_allclose(sum(r["weights_m3"]), r["volume_m3"], rtol=1e-12, atol=0)
    return dict(
        schema="soma.mri-head-model.comparison/1",
        reports=4,
        all_passed=True,
        rtol=1e-10,
        atol=1e-12,
        scope="synthetic analytical frame and MRI voxel-prior software only",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.write_text(json.dumps(compare(a.root), indent=2) + "\n")
