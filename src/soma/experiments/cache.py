"""Content-addressed, checksummed run artifacts; no pickled executable objects."""

import hashlib
import json
import platform
import shutil
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256, write_json


def canonical_id(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()[:24]


def software_identity() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    return {
        "application": version("soma-neuro"),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "byteorder": sys.byteorder,
        "libraries": {
            name: version(name)
            for name in ("numpy", "scipy", "mne", "neurodsp", "pandas", "PyYAML")
        },
        "source_digest": canonical_id(
            {str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob("*.py"))}
        ),
    }


def validate_cache(folder: Path, key: str) -> bool:
    if not folder.is_dir():
        return False
    info = json.loads((folder / "cache.json").read_text())
    if info["key"] != key or not info["files"]:
        raise ValueError(f"Invalid cache identity: {folder}")
    for name, digest in info["files"].items():
        # Cache metadata is data, never permission to read outside its artifact directory.
        if (
            Path(name).name != name
            or not (folder / name).is_file()
            or sha256(folder / name) != digest
        ):
            raise ValueError(f"Corrupt cache artifact: {folder / name}")
    return True


def publish_cache(staging: Path, destination: Path, key: str, parameters: dict[str, Any]) -> None:
    files = {p.name: sha256(p) for p in staging.iterdir() if p.is_file()}
    write_json(
        staging / "cache.json",
        {"schema_version": 1, "key": key, "parameters": parameters, "files": files},
    )
    if destination.exists():
        # Another producer must have published a complete identical identity.
        validate_cache(destination, key)
        shutil.rmtree(staging)
    else:
        staging.rename(destination)


def staging_directory(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".building-", dir=root))
