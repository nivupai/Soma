"""Prespecified M10 settings, independent of historical protocol seals."""

import json
from pathlib import Path
from typing import Any

import yaml

from soma.core.provenance import sha256


def configuration(path: Path) -> dict[str, Any]:
    receipt = json.loads(Path("configs/milestone10-freeze.json").read_text())
    for name, digest in receipt["files_sha256"].items():
        if sha256(Path(name)) != digest:
            raise ValueError(f"M10 freeze mismatch: {name}")
    if path.suffix != ".yaml" or not any(
        path.resolve() == Path(name).resolve() for name in receipt["files_sha256"]
    ):
        raise ValueError("Unsealed M10 configuration")
    return dict(yaml.safe_load(path.read_text()))
