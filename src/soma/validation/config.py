"""Milestone 11 protocol seal, independent of earlier milestone seals."""

import json
from pathlib import Path
from typing import Any

import yaml

from soma.core.provenance import sha256


def configuration(path: Path) -> dict[str, Any]:
    seal = json.loads(Path("configs/milestone11-freeze.json").read_text())
    for name, digest in seal["files_sha256"].items():
        if sha256(Path(name)) != digest:
            raise ValueError(f"M11 protocol/config checksum mismatch: {name}")
    if path.resolve() not in [
        Path(p).resolve() for p in seal["files_sha256"] if p.endswith(".yaml")
    ]:
        raise ValueError("Unsealed M11 study configuration")
    return dict(yaml.safe_load(path.read_text()))
