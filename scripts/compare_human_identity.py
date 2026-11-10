"""Require actual four-platform metadata evidence; no real-data access equivalence claim."""

import argparse
import json
from pathlib import Path

from soma.results.io import read_json


def compare(root, filename="human-identity.json"):
    reports = [read_json(p) for p in sorted(root.rglob(filename))]
    if len(reports) != 4:
        raise ValueError("Exactly four actual runner reports required")
    assert {
        (r["environment"]["system"], r["environment"]["machine"], r["environment"]["python"][:4])
        for r in reports
    } == {
        (s, a, p) for s, a in [("Darwin", "arm64"), ("Linux", "x86_64")] for p in ["3.11", "3.12"]
    }
    assert all(r["all_passed"] and r["invariants"] == reports[0]["invariants"] for r in reports)
    return {
        "schema": "soma.human.synthetic-repro-comparison/1.0.0",
        "environments": [r["environment"] for r in reports],
        "all_passed": True,
        "invariants_identical": True,
        "actual_human_data_accessed": False,
        "claim": (
            "fictional metadata serialization, identity scopes, permissions, "
            "protocol, registration schema and declared lineage only"
        ),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.write_text(json.dumps(compare(args.root), indent=2) + "\n")
