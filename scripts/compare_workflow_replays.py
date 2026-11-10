"""Inspect actual runner evidence, separating semantic, byte and numerical agreement."""

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path

import numpy as np

from soma.results.io import read_json


def compare(root):
    paths = sorted(root.rglob("workflow-replay.json"))
    if len(paths) != 4:
        raise ValueError("Exactly four actual runner reports required")
    reports = [read_json(p) for p in paths]
    expected = {(os, py) for os in ["Darwin", "Linux"] for py in ["3.11", "3.12"]}
    assert {
        (r["environment"]["system"], r["environment"]["python"][:4]) for r in reports
    } == expected
    protocol = files("soma.resources").joinpath("workflow-tolerances-v1.json").read_bytes()
    bounds = json.loads(protocol)
    for r in reports:
        assert r["tolerance_protocol_sha256"] == hashlib.sha256(protocol).hexdigest()
        assert r["all_passed"] and r["milestone17_oracles"]["all_passed"]
        assert set(r["workflows"]) == set(bounds)
        for family, w in r["workflows"].items():
            assert w["tolerance"] == bounds[family]
            assert all(s["status"] == "COMPLETE" and s["cached"] for s in w["warm"])
    baseline = reports[0]
    rows = []
    for report in reports[1:]:
        for family, left in baseline["workflows"].items():
            right = report["workflows"][family]
            a = np.asarray(left["numerical_summary"])
            b = np.asarray(right["numerical_summary"])
            atol, rtol = 2 * bounds[family]["atol"], 2 * bounds[family]["rtol"]
            assert a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all()
            passed = bool(np.allclose(a, b, atol=atol, rtol=rtol))
            rows.append(
                {
                    "family": family,
                    "left": baseline["environment"]["system"]
                    + " "
                    + baseline["environment"]["python"],
                    "right": report["environment"]["system"]
                    + " "
                    + report["environment"]["python"],
                    "maximum_absolute_difference": float(np.max(np.abs(a - b))),
                    "atol": atol,
                    "rtol": rtol,
                    "passed": passed,
                    "logical_identity_equal": left["logical_keys"] == right["logical_keys"],
                    "content_fingerprints_equal": left["content_fingerprints"]
                    == right["content_fingerprints"],
                    "file_fingerprints_equal": left["file_fingerprints"]
                    == right["file_fingerprints"],
                    "cache_keys_equal": left["cache_keys"] == right["cache_keys"],
                }
            )
            assert passed, rows[-1]
    return {
        "schema": "soma.workflow.replay-comparison/1",
        "environments": [r["environment"] for r in reports],
        "comparisons": rows,
        "all_passed": True,
        "cache_interchangeability": "NOT_AUTHORIZED_BY_REPLAY",
        "tolerance_protocol_sha256": hashlib.sha256(protocol).hexdigest(),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = compare(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print({"comparisons": len(result["comparisons"]), "all_passed": result["all_passed"]})
