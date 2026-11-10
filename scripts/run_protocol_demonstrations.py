"""Produce actual synthetic histories, references and frozen summary comparisons."""

import argparse
import json
import time
from pathlib import Path

from soma.protocol.examples import demonstrations
from soma.results.reproducibility import run_suite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    result = demonstrations(args.root)
    result["scientific_elapsed_s"] = time.perf_counter() - started
    result["milestone17_oracles"] = run_suite()
    result["supported_result_schemas"] = ["1.0.0", "1.1.0"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print({"all_passed": result["all_passed"], "families": list(result["families"])})


if __name__ == "__main__":
    main()
