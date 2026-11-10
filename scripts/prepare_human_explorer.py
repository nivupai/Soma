"""Register existing private pilot artifacts explicitly; never run pilots from an API read."""

import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pilots", type=Path, required=True)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    config = json.loads(args.base.read_text())
    root = args.pilots.resolve()
    config["roots"]["human-pilots"] = str(root)
    for dataset in ["eegmmidb", "ibsr-v2", "mrbrains13", "ds000114"]:
        file = f"executions/{dataset}/result.json"
        if not (root / file).is_file():
            raise ValueError("Existing native pilot artifact required")
        config["entries"].append(
            {
                "id": "human-" + dataset,
                "kind": "human-audit",
                "label": dataset + " permission/identity audit",
                "root": "human-pilots",
                "file": file,
                "synthetic": False,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n")


if __name__ == "__main__":
    main()
