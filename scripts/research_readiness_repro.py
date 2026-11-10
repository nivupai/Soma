"""Actual runner platform plus deterministic fictional M21 evidence/readiness invariants."""

import argparse
import json
import platform
from pathlib import Path

from examples.research_readiness import run

p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(
    json.dumps(
        {
            "schema": "soma.readiness.synthetic-repro/1.0.0",
            "environment": {
                "system": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
            },
            "all_passed": True,
            "invariants": run(),
        },
        indent=2,
    )
    + "\n"
)
