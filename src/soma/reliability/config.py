"""Immutable prospective reliability settings, separate from M6/M8 seals."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from soma.core.provenance import sha256


def configuration(path: Path) -> dict[str, Any]:
    receipt = json.loads(Path("configs/model-reliability-freeze.json").read_text())
    for name, digest in receipt["files_sha256"].items():
        if sha256(Path(name)) != digest:
            raise ValueError(f"Reliability protocol/configuration changed: {name}")
    if path.suffix != ".yaml" or not any(
        path.resolve() == Path(name).resolve() for name in receipt["files_sha256"]
    ):
        raise ValueError("Unsealed reliability configuration")
    return dict(yaml.safe_load(path.read_text()))


def stream(seed: int, name: int) -> np.random.Generator:
    """Stable independent named streams; never Python's randomized hash()."""
    return np.random.default_rng(np.random.SeedSequence([seed, name]))
