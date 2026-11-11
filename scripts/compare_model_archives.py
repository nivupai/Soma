"""Compare synthetic release checks, never interchange human model artifacts."""

import argparse
import json
from pathlib import Path

from compare_human_identity import compare

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
r = compare(a.root, filename="model-archive-synthetic.json")
r["schema"] = "soma.model-archive.synthetic-comparison/1"
r["claim"] = "four actual independent source fits and reloads; no universal artifact portability"
a.output.write_text(json.dumps(r, indent=2) + "\n")
