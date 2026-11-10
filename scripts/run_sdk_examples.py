"""Execute all examples and write only explicitly requested synthetic results."""

import argparse
import importlib
import json
from pathlib import Path

NAMES = (
    "mri_geometry",
    "segmentation",
    "surface_qc",
    "eeg_analysis",
    "source_diagnostics",
    "fmri_contrast",
    "provenance",
    "explorer",
    "result_schemas",
    "workflow_provenance",
    "research_protocol",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = {name: importlib.import_module("examples." + name).run() for name in NAMES}
    text = json.dumps(results, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
