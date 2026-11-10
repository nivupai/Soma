"""Compare actual four-runner evidence using unmodified frozen protocol tolerances."""

import argparse
import json
from pathlib import Path

import numpy as np

from soma.pipeline.cache import source_hash
from soma.protocol.binding import example_protocol
from soma.protocol.replay import Execution
from soma.protocol.replay import compare as compare_executions
from soma.results.io import read_json


def compare(root):
    paths = sorted(root.rglob("protocol-replay.json"))
    if len(paths) != 4:
        raise ValueError("Exactly four actual protocol runner reports required")
    reports = [read_json(p) for p in paths]
    environments = [r["families"]["source"]["environment"] for r in reports]
    assert {(e["system"], e["machine"], e["python"][:4]) for e in environments} == {
        (s, m, p) for s, m in [("Darwin", "arm64"), ("Linux", "x86_64")] for p in ["3.11", "3.12"]
    }
    rows = []
    for report in reports:
        assert report["all_passed"] and report["milestone17_oracles"]["all_passed"]
        assert report["supported_result_schemas"] == ["1.0.0", "1.1.0"]
        for family, right in report["families"].items():
            protocol = example_protocol(family)
            left = reports[0]["families"][family]
            assessment = compare_executions(
                Execution.from_dict(left["baseline_execution"]),
                Execution.from_dict(right["baseline_execution"]),
                mode="CONTROLLED",
            )
            assert assessment["authorized"], assessment
            bounds = protocol.document()["tolerances"]
            assert right["baseline_execution"]["implementation_fingerprint"] == source_hash()
            assert right["protocol_fingerprint"] == protocol.fingerprint
            assert right["scientific_fingerprint"] == protocol.scientific_fingerprint
            assert right["tolerances"] == bounds == left["tolerances"]
            assert right["baseline_workflow_semantics"] == left["baseline_workflow_semantics"]
            assert (
                right["baseline_numerical_summaries"].keys()
                == left["baseline_numerical_summaries"].keys()
            )
            for unit, values in left["baseline_numerical_summaries"].items():
                a, b = np.asarray(values), np.asarray(right["baseline_numerical_summaries"][unit])
                assert a.shape == b.shape == (len(bounds["axes"]),)
                assert np.isfinite(a).all() and np.isfinite(b).all()
                equivalent = bool(np.allclose(a, b, atol=bounds["atol"], rtol=bounds["rtol"]))
                row = {
                    "family": family,
                    "controlled_replay_assessment": assessment,
                    "unit": unit,
                    "environment": right["environment"],
                    "maximum_absolute_difference": float(np.max(np.abs(a - b))),
                    "numerically_identical": bool(np.array_equal(a, b)),
                    "numerically_equivalent": equivalent,
                    "artifact_bytes_identical": left["baseline_file_fingerprints"]
                    == right["baseline_file_fingerprints"],
                    "artifact_content_identical": left["baseline_artifact_fingerprints"]
                    == right["baseline_artifact_fingerprints"],
                    "input_content_identical": left["baseline_input_fingerprints"]
                    == right["baseline_input_fingerprints"],
                    "tolerance": bounds,
                }
                rows.append(row)
                assert equivalent, row
    return {
        "schema": "soma.protocol.platform-comparison/1.0.0",
        "comparisons": rows,
        "all_passed": True,
        "cache_interchangeability": False,
        "confirmatory_replication_authorized": False,
        "scope": "selected synthetic summaries only; not full study equivalence",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print({"all_passed": result["all_passed"], "comparisons": len(result["comparisons"])})
