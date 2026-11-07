"""Content-bound physical caches: staged file, atomic checksum receipt, fail closed."""

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256
from soma.simulations.calibration import atomic_json


def fingerprint(parameters: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()[:24]


def cached_object(
    root: Path,
    kind: str,
    parameters: dict[str, Any],
    suffix: str,
    build: Callable[[], Any],
    read: Callable[[Path], Any],
    write: Callable[[Path, Any], None],
) -> tuple[Any, dict[str, Any]]:
    import time

    started = time.perf_counter()
    root.mkdir(parents=True, exist_ok=True)
    identity = fingerprint(parameters)
    path = root / f"{kind}-{identity}{suffix}"
    receipt = path.with_suffix(path.suffix + ".json")
    if path.exists() or receipt.exists():
        if not path.exists() or not receipt.exists():
            raise ValueError("Incomplete physical cache publication")
        metadata = json.loads(receipt.read_text())
        if metadata["parameters"] != parameters or metadata["sha256"] != sha256(path):
            raise ValueError("Physical cache fingerprint/checksum mismatch")
        obj = read(path)
        hit = True
    else:
        obj = build()
        with tempfile.TemporaryDirectory(dir=root, prefix=".physical-") as temporary:
            pending = Path(temporary) / ("object" + suffix)
            write(pending, obj)
            os.replace(pending, path)
        atomic_json(receipt, {"parameters": parameters, "sha256": sha256(path)})
        # Always read the serialized object, so fresh/cache-hit precision is identical.
        obj = read(path)
        hit = False
    return obj, {
        "cache_key": identity,
        "path": str(path),
        "sha256": sha256(path),
        "hit": hit,
        "wall_s": time.perf_counter() - started,
        "parameters": parameters,
    }
