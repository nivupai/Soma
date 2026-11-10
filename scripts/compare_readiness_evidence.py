"""Reuse M20's actual four-runner equality validator for M21 fictional invariants."""

import argparse
import json
from pathlib import Path

from compare_human_identity import compare

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
r = compare(a.root, filename="readiness-evidence.json")
r["schema"] = "soma.readiness.synthetic-repro-comparison/1.0.0"
r["claim"] = (
    "fictional immutable evidence, session relations, registration schemas and readiness gates only"
)
a.output.write_text(json.dumps(r, indent=2) + "\n")
