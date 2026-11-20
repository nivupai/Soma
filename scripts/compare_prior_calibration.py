"""Mandatory four-environment gate for the new bounded inverse-prior reference."""

import argparse
import json
from pathlib import Path

import numpy as np


def compare(root):
    paths = sorted(root.glob("*/inverse-prior-synthetic.json"))
    if len(paths) != 4:
        raise ValueError("Four inverse-prior reports required")
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
        raise ValueError("Inverse-prior environment coverage mismatch")
    for r in reports:
        if (
            r["schema"] != "soma.inverse-prior.repro/1"
            or r["design_sha256"]
            != "abb24125e39c51438197e4e7301b3f7079bdb4820bdd6257069348594d6468bc"
            or r["synthetic_only"] is not True
            or len(r["data"]) != 9
        ):
            raise ValueError("Invalid inverse-prior report identity")
        for b, a in zip(reports[0]["data"], r["data"], strict=True):
            if (a["prior"], a["method"]) != (b["prior"], b["method"]):
                raise ValueError("Inverse-prior comparison pairing mismatch")
            x, y = np.asarray(a["kernel"]), np.asarray(b["kernel"])
            if (
                x.shape != (9, 5)
                or not np.isfinite(x).all()
                or not np.allclose(x, y, rtol=1e-9, atol=1e-11)
            ):
                raise ValueError("Inverse-prior numerical kernel disagreement")
            if set(a["diagnostics"]) != set(b["diagnostics"]):
                raise ValueError("Incomplete inverse-prior diagnostics")
            if not np.allclose(
                list(a["diagnostics"].values()),
                list(b["diagnostics"].values()),
                rtol=1e-9,
                atol=1e-11,
            ):
                raise ValueError("Inverse-prior diagnostic disagreement")
    return dict(
        schema="soma.inverse-prior.comparison/1",
        reports=4,
        all_passed=True,
        rtol=1e-9,
        atol=1e-11,
        scope="bounded analytical prior regression, not human validation",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.write_text(json.dumps(compare(a.root), indent=2) + "\n")
