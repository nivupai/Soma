"""Prespecified individual-model parameters and immutable protocol receipt."""

import json
from pathlib import Path
from typing import Any

import yaml

from soma.core.provenance import sha256


def frozen_config(path: Path) -> dict[str, Any]:
    receipt_path = Path("configs/individual-head-model-freeze.json")
    receipt = json.loads(receipt_path.read_text())
    for filename, digest in receipt["files_sha256"].items():
        if sha256(Path(filename)) != digest:
            raise ValueError(f"Individual head-model protocol freeze mismatch: {filename}")
    if not any(path.resolve() == Path(name).resolve() for name in receipt["files_sha256"]):
        raise ValueError("Configuration is not part of the frozen individual protocol")
    config = dict(yaml.safe_load(path.read_text()))
    amendment = json.loads(Path("configs/individual-head-model-amendment.json").read_text())
    if sha256(Path(amendment["amendment_document"])) != amendment["sha256"]:
        raise ValueError("Individual protocol amendment checksum mismatch")
    config["_protocol_amendment"] = amendment
    if "anatomy" in config:
        config["_original_surface_origin"] = config["anatomy"]["surface_origin"]
        config["anatomy"]["surface_origin"] = amendment["resolved_surface_origin"]
    return config
