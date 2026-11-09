"""Explicit local-only human reference reproduction; outputs must be new/ignored.

Run after activating Soma's environment. Never downloads, reads MRBrainS test
payloads, or emits participant information into the repository's tracked trees.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256, write_json
from soma.datasets.human_mri import safe_local_output


def source_hash() -> str:
    return hashlib.sha256(
        b"".join(str(p).encode() + p.read_bytes() for p in sorted(Path("src/soma").rglob("*.py")))
    ).hexdigest()


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "reports/milestone11-human-reproduction")
    safe_local_output(root)
    root.mkdir(parents=True, exist_ok=False)
    env = {
        **os.environ,
        "MPLBACKEND": "Agg",
        "OPENBLAS_NUM_THREADS": "1",
        "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": "1",
    }
    cfg = "configs/human-tissues.yaml"
    inventory = root / "inventory"
    development = root / "development"
    external = root / "external"
    commands = [
        ["mri", "inventory-human", "--config", cfg, "--output", str(inventory)],
        [
            "mri",
            "benchmark-human-tissues",
            "--config",
            cfg,
            "--inventory",
            str(inventory / "inventory.json"),
            "--phase",
            "development",
            "--output",
            str(development),
        ],
        [
            "mri",
            "benchmark-human-tissues",
            "--config",
            cfg,
            "--inventory",
            str(inventory / "inventory.json"),
            "--phase",
            "external",
            "--output",
            str(external),
        ],
    ]
    frozen: dict[str, Any] = {}
    for index, args in enumerate(commands):
        if index == 2:
            summary = json.loads((development / "summary.json").read_text())
            manifest = json.loads((development / "manifest.json").read_text())
            if summary["status"] != "complete" or manifest["source_tree_sha256"] != source_hash():
                raise ValueError(
                    "Complete development and unchanged executed code "
                    "required before external evaluation"
                )
            frozen = {
                "before_external_utc": datetime.now(UTC).isoformat(),
                "source_tree_sha256": source_hash(),
                "development_manifest_sha256": sha256(development / "manifest.json"),
                "inventory_sha256": sha256(inventory / "inventory.json"),
                "protocol_sha256": sha256(Path("configs/human-tissues-freeze.json")),
            }
            write_json(root / "external-freeze.json", frozen)
        with (root / f"command-{index + 1}.log").open("x") as stream:
            subprocess.run(
                [sys.executable, "-c", "from soma.cli import app; app()", *args],
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
            )
    if source_hash() != frozen["source_tree_sha256"]:
        raise ValueError("Scientific source changed during external evaluation")
    print("Local human-reference reports complete. Read ignored summaries; no data published.")


if __name__ == "__main__":
    main()
