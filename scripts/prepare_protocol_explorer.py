"""Explicit operator action: register real synthetic records, never execute from a GET."""

import argparse
import json
from pathlib import Path

from soma.protocol.examples import demonstrations
from soma.protocol.model import SealedProtocol, canonical, write_seal
from soma.protocol.replay import read_execution


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--base", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "source/execution-5/result.json").exists():
        demonstrations(root)
    config = json.loads(args.base.read_text()) if args.base else {"roots": {}, "entries": []}
    config["roots"]["protocol-histories"] = str(root)
    for family in ["eeg", "mri", "fmri", "source"]:
        for i in range(1, 6 if family == "source" else 5):
            relative = f"{family}/execution-{i}/result.json"
            execution = read_execution(root / relative)
            seal_path = root / family / f"seal-{i}.json"
            if not seal_path.exists():
                write_seal(SealedProtocol(canonical(execution.record()["protocol"])), seal_path)
            for kind, suffix in [("execution", relative), ("protocol", f"{family}/seal-{i}.json")]:
                identity = f"research-{family}-{kind}-{i}"
                if not any(e["id"] == identity for e in config["entries"]):
                    config["entries"].append(
                        {
                            "id": identity,
                            "kind": kind,
                            "label": f"{family.upper()} {kind} {i}",
                            "root": "protocol-histories",
                            "file": suffix,
                            "synthetic": True,
                        }
                    )
    args.config.parent.mkdir(parents=True, exist_ok=True)
    args.config.write_text(json.dumps(config, indent=2) + "\n")
    print({"registered_records": len(config["entries"])})


if __name__ == "__main__":
    main()
