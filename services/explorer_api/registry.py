"""Explicit local allowlist, resolved on every access to reject symlink escapes."""

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from .models import Strict


class Entry(Strict):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    kind: Literal[
        "eeg",
        "mri",
        "source",
        "fmri",
        "experiment",
        "workflow",
        "protocol",
        "execution",
        "human-audit",
        "human-readiness",
    ]
    label: str = Field(max_length=120)
    root: str
    file: str
    subject: str = "local"
    session: str = "unspecified"
    run: str = "1"
    frame: str = "unspecified"
    units: str = "unspecified"
    synthetic: bool = False
    provenance: str = "Operator-selected local research artifact; no anatomical certification"
    segmentation: str | None = None
    geometry: str | None = None
    operators: str | None = None
    surface: str | None = None
    surface_root: str | None = None
    metadata_file: str | None = None
    manifest: str | None = None
    figures: list[str] = Field(default_factory=list, max_length=8)
    design: str | None = None
    events: str | None = None
    role: Literal["effect", "bold"] = "effect"
    spatial_units_override: Literal["mm", "meter", "micron"] | None = None
    # Deliberate identity/estimand declarations, never inferred from filenames.
    compatibility: dict[str, str] = {}


class Configuration(Strict):
    roots: dict[str, str] = {}
    entries: list[Entry] = []


class Registry:
    def __init__(self, config: Configuration | None = None) -> None:
        if config is None:
            name = os.environ.get("SOMA_EXPLORER_CONFIG")
            config = (
                Configuration.model_validate_json(Path(name).read_text())
                if name
                else Configuration()
            )
        self.roots = {key: Path(path).resolve(strict=True) for key, path in config.roots.items()}
        self.entries = {entry.id: entry for entry in config.entries}
        if len(self.entries) != len(config.entries):
            raise ValueError("Duplicate dataset identity")
        if any(e.id.startswith("demo-") for e in config.entries):
            raise ValueError("Synthetic demo identities are reserved")
        for entry in config.entries:
            self.path(entry)

    def path(self, entry: Entry, field: str = "file") -> Path:
        relative = getattr(entry, field)
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise ValueError("Invalid configured relative resource")
        return self.resolve(entry, relative, entry.surface_root if field == "surface" else None)

    def resolve(self, entry: Entry, relative: str, root_key: str | None = None) -> Path:
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Invalid configured relative resource")
        root = self.roots[root_key or entry.root]
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Resource outside allowed root")
        if path.stat().st_size > 1024**3:
            raise ValueError("Resource exceeds 1 GiB limit")
        return path

    def get(self, identity: str, kind: str | None = None) -> Entry:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", identity):
            raise KeyError("Unknown identity")
        entry = self.entries[identity]
        if kind and kind != entry.kind:
            raise ValueError("Incompatible resource kind")
        self.path(entry)
        return entry


def sanitize(value: Any) -> Any:
    """Suppress path/identity fields without truncating scientific metrics or rows."""
    if isinstance(value, dict):
        private = {
            "path",
            "paths",
            "file",
            "files",
            "filename",
            "filenames",
            "subject",
            "subjects",
            "subject_id",
            "subject_identity",
            "participant_identity",
            "participant",
            "participants",
            "participant_id",
        }
        return {
            k: sanitize(v)
            for k, v in value.items()
            if k.lower() not in private
            and not k.lower().endswith(
                ("_path", "_paths", "_file", "_files", "_filename", "_filenames")
            )
        }
    if isinstance(value, list):
        # The input JSON is already capped at4MiB. Never silently drop result rows.
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        if (
            "/Users/" in value
            or "/home/" in value
            or value.startswith(("/", "file:", "data/", "reports/", "derivatives/"))
            or re.match(r"^[A-Za-z]:[\\/]", value)
        ):
            return "[private resource]"
        return value
    if value is None or isinstance(value, (float, int, bool)):
        return value
    return str(value)[:100]


def read_json(path: Path) -> Any:
    if path.stat().st_size > 4 * 1024**2:
        raise ValueError("Metadata exceeds 4 MiB")

    def reject(value: str) -> Any:
        raise ValueError("Nonfinite JSON number")

    return json.loads(path.read_text(), parse_constant=reject)
