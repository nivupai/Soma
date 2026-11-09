"""Workflow records and dependency contracts; geometry remains in soma.imaging."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from soma.core.provenance import sha256
from soma.geometry import Frame, Transform


@dataclass(frozen=True)
class InputRecord:
    image: Path
    subject: str
    session: str | None = None
    dataset_type: str = "standalone"
    source_root: Path | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    legacy: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch("[a-zA-Z0-9]+", self.subject) or (
            self.session is not None and not re.fullmatch("[a-zA-Z0-9]+", self.session)
        ):
            raise ValueError("BIDS subject/session entities must be alphanumeric")
        if self.dataset_type not in ("bids", "legacy", "standalone") or (
            self.dataset_type == "legacy" and not self.legacy
        ):
            raise ValueError("Explicit BIDS or legacy origin required")
        if (
            self.dataset_type == "legacy"
            and self.legacy
            and self.legacy.get("dataset") == "mrbrains13"
            and self.legacy.get("partition") != "external"
        ):
            raise ValueError("MRBrainS bridge permits labeled training external partition only")

        if self.dataset_type == "bids":
            if (
                self.source_root is None
                or not (self.source_root / "dataset_description.json").is_file()
            ):
                raise ValueError("Original BIDS origin requires an inspected dataset root")
            if not self.image.resolve().is_relative_to(
                self.source_root.resolve()
            ) or not self.image.name.startswith("sub-" + self.subject):
                raise ValueError("BIDS source path/subject identity mismatch")

    @property
    def key(self) -> str:
        return "sub-" + self.subject + ("_ses-" + self.session if self.session else "")

    def receipt(self) -> dict[str, Any]:
        result = {
            "image": str(self.image.resolve()),
            "sha256": sha256(self.image),
            "subject": self.subject,
            "session": self.session,
            "dataset_type": self.dataset_type,
            "source_root": str((self.source_root or self.image.parent).resolve()),
            "entities": self.entities,
            "metadata": self.metadata,
            "legacy": self.legacy,
        }
        if self.legacy:
            result["auxiliary_sha256"] = {
                k: sha256(Path(self.legacy[k]))
                for k in ("reference", "testing_style_reference")
                if k in self.legacy
            }
        return result


@dataclass(frozen=True)
class StageSpec:
    name: str
    dependencies: tuple[str, ...]
    inputs: dict[str, str]
    outputs: dict[str, str]
    parameters: dict[str, Any] = field(default_factory=dict)
    frames: tuple[str, ...] = ("RAS",)
    units: str = "m"
    software: tuple[str, ...] = ("numpy", "nibabel")
    failure_conditions: tuple[str, ...] = ("invalid input type/geometry/content",)


def ordered_graph(stages: list[StageSpec], initial: set[str]) -> list[StageSpec]:
    names = [s.name for s in stages]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate stage name")
    if any(set(s.dependencies) - set(names) for s in stages):
        raise ValueError("Missing stage dependency")
    outputs = set(initial)
    for stage in stages:
        if outputs & set(stage.outputs):
            raise ValueError("Duplicate artifact name")
        outputs.update(stage.outputs)
    remaining = {s.name: s for s in stages}
    done: set[str] = set()
    available = set(initial)
    result = []
    while remaining:
        ready = [s for s in remaining.values() if set(s.dependencies) <= done]
        if not ready:
            raise ValueError("Pipeline dependency cycle")
        for s in ready:
            if not set(s.inputs) <= available:
                raise ValueError("Artifact dependency absent or not ordered")
            result.append(s)
            done.add(s.name)
            available.update(s.outputs)
            del remaining[s.name]
    return result


def transform_receipt(
    transform: Transform,
    source_grid: dict[str, Any],
    reference_grid: dict[str, Any],
    *,
    interpolation: str,
    provenance: str,
) -> dict[str, Any]:
    if not provenance or transform.source != Frame.RAS or transform.destination != Frame.RAS:
        raise ValueError("Resampling transform must explicitly map reference RAS to source RAS")
    return {
        "type": "affine",
        "source_frame": transform.source.value,
        "destination_frame": transform.destination.value,
        "direction": "reference_world_to_source_world",
        "matrix": transform.matrix.tolist(),
        "units": "m",
        "rigid": transform.rigid,
        "interpolation": interpolation,
        "source_grid": source_grid,
        "reference_grid": reference_grid,
        "composition": [],
        "provenance": provenance,
    }


def read_transform(value: dict[str, Any]) -> Transform:
    if (
        value.get("type") != "affine"
        or value.get("units") != "m"
        or value.get("direction") != "reference_world_to_source_world"
    ):
        raise ValueError(
            "Only explicit affine reference-to-source "
            "metre transforms supported; no nonlinear coercion"
        )
    return Transform(
        Frame(value["source_frame"]),
        Frame(value["destination_frame"]),
        np.array(value["matrix"]),
        bool(value["rigid"]),
    )
