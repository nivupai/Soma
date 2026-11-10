"""Explicit local native readiness allowlist; no human data needed by demo/CI."""

import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--pilots", type=Path, required=True)
p.add_argument("--base", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
d = json.loads(a.base.read_text())
d["roots"]["readiness-pilots"] = str(a.pilots.resolve(strict=True))
for dataset in ["eegmmidb", "ibsr-v2", "ds000114"]:
    d["entries"].append(
        {
            "id": "readiness-" + dataset,
            "kind": "human-readiness",
            "label": dataset + " readiness evidence",
            "root": "readiness-pilots",
            "file": f"readiness/{dataset}/result.json",
            "synthetic": False,
        }
    )
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(d, indent=2) + "\n")
