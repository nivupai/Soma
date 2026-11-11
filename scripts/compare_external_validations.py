"""Compare four fictional frozen evaluation reports, never human/cache portability."""

import argparse
import json
from pathlib import Path

from compare_human_identity import compare

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
r = compare(a.root, filename="external-validation-synthetic.json")
r["schema"] = "soma.external-validation.synthetic-comparison/1"
r["claim"] = (
    "fictional independent target draws; no human external replication or cache interchange"
)
a.output.write_text(json.dumps(r, indent=2) + "\n")
