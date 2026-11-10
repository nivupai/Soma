"""Run actual synthetic workflow replay; output is JSON metadata, never human arrays."""

import argparse
import json
from pathlib import Path

from soma.workflow.replay import replay

parser = argparse.ArgumentParser()
parser.add_argument("--cache", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
result = replay(args.cache)
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open("x") as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
print({"all_passed": result["all_passed"], "workflows": list(result["workflows"])})
