"""Compare actual synthetic outputs across all four required platform executions."""

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path

import numpy as np

from soma.sdk.results import load_result


def compare(directory):
    paths = sorted(directory.rglob("cross-platform.json"))
    if len(paths) != 4:
        raise ValueError("Four actual platform/Python reports are required")
    reports = [load_result(p)[0]["payload"]["values"] for p in paths]
    expected = {(os, py) for os in ["Linux", "Darwin"] for py in ["3.11", "3.12"]}
    observed = {(r["platform"], ".".join(r["python"].split(".")[:2])) for r in reports}
    if observed != expected:
        raise ValueError("Actual runner matrix does not match required evidence")
    protocol_bytes = (
        files("soma.resources").joinpath("reproducibility-tolerances-v1.json").read_bytes()
    )
    protocol = json.loads(protocol_bytes)
    for report in reports:
        if (
            report.get("tolerance_protocol_sha256") != hashlib.sha256(protocol_bytes).hexdigest()
            or report.get("benchmark") != "soma.synthetic-reproducibility-v1"
            or not report.get("all_passed")
        ):
            raise ValueError("Unknown/failed benchmark or tolerance protocol")
        cases = {c["case"]: c for c in report["cases"]}
        if set(cases) != set(protocol):
            raise ValueError("Incomplete benchmark cases")
        for name, c in cases.items():
            if not c["passed"] or {k: c[k] for k in ["atol", "rtol"]} != protocol[name]:
                raise ValueError("Changed tolerance or failed case")
    rows = []
    baseline = reports[0]
    for other in reports[1:]:
        if other["benchmark"] != baseline["benchmark"] or not other["all_passed"]:
            raise ValueError("Unsupported or failed numerical report")
        a = {c["case"]: c for c in baseline["cases"]}
        b = {c["case"]: c for c in other["cases"]}
        if set(a) != set(b):
            raise ValueError("Case inventories differ")
        for name, left in a.items():
            right = b[name]
            x = np.asarray(left["actual_values"])
            y = np.asarray(right["actual_values"])
            if x.shape != y.shape:
                raise ValueError("Numerical result axes differ")
            # Triangle inequality: each run is bounded relative to the same oracle.
            atol = 2 * max(left["atol"], right["atol"])
            rtol = 2 * max(left["rtol"], right["rtol"])
            passed = bool(np.allclose(x, y, atol=atol, rtol=rtol))
            row = {
                "case": name,
                "left": [baseline["platform"], baseline["python"]],
                "right": [other["platform"], other["python"]],
                "maximum_absolute_difference": float(np.max(np.abs(x - y))),
                "atol": atol,
                "rtol": rtol,
                "passed": passed,
            }
            rows.append(row)
            if not passed:
                raise ValueError("Cross-platform numerical disagreement: " + json.dumps(row))
    return {
        "platforms": [
            {
                k: r[k]
                for k in [
                    "platform",
                    "architecture",
                    "python",
                    "dependencies",
                    "numerical_backends",
                ]
            }
            for r in reports
        ],
        "pairwise_comparisons": rows,
        "all_passed": all(r["passed"] for r in rows),
        "input_hash_identity": {
            key: len({r["input_hashes"][key] for r in reports}) == 1
            for key in baseline["input_hashes"]
        },
        "scope": (
            "same declared generators and within-case analytical references; "
            "exact input-byte identity reported separately"
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    result = compare(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
