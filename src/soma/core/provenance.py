"""JSON-compatible provenance and exclusively-created analysis directories."""

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest(
    source: dict[str, Any],
    parameters: dict[str, Any],
    paths: dict[str, str],
    seed: int | None = None,
) -> dict[str, Any]:
    try:
        repo = Path(__file__).resolve().parents[3]
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, stderr=subprocess.DEVNULL, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    return {
        "schema_version": 1,
        "source": source,
        "parameters": parameters,
        "paths": paths,
        "random_seed": seed,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "application_version": version("soma-neuro"),
        "git_revision": revision,
        "git_dirty": dirty,
        "python": platform.python_version(),
        "libraries": {
            name: version(name)
            for name in ("numpy", "scipy", "mne", "neurodsp", "pandas", "matplotlib", "typer")
        },
    }


def output_directory(path: Path) -> Path:
    # An existing directory is never reused, including a partially completed run.
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json(path: Path, value: Any) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
