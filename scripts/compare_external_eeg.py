"""Compare four actual synthetic external transfer reports, never human replication."""

import argparse
import json
from pathlib import Path

from compare_human_identity import compare

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
r = compare(a.root, filename="external-eeg-synthetic.json")
r["schema"] = "soma.external-eeg.synthetic-comparison/1"
r["claim"] = (
    "fictional sessions and frozen-state prediction parity; "
    "no human replication or cache interchange"
)
a.output.write_text(json.dumps(r, indent=2) + "\n")
