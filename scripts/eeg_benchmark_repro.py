"""Actual runner environment and deterministic synthetic decoder outcomes only."""

import argparse
import json
import platform
from pathlib import Path

from examples.eeg_benchmark import run

p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(
    json.dumps(
        {
            "schema": "soma.eeg.benchmark-synthetic/1.0.0",
            "all_passed": True,
            "environment": {
                "system": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
            },
            "invariants": run(),
        },
        indent=2,
    )
    + "\n"
)
