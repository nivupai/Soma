"""Compare all four actual synthetic benchmark artifacts; no human replication claim."""

import argparse
import json
from pathlib import Path

from compare_human_identity import compare

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
r = compare(a.root, filename="eeg-benchmark-synthetic.json")
r["schema"] = "soma.eeg.benchmark-synthetic-comparison/1.0.0"
r["claim"] = (
    "known-mixture synthetic decoding and metadata only; no human cross-platform replication"
)
a.output.write_text(json.dumps(r, indent=2) + "\n")
