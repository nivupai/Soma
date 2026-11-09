"""Stage serialization over existing content-addressed Soma physical caches."""

import hashlib
import json
import shutil
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from soma.anatomy.cache import cached_object, fingerprint
from soma.core.provenance import sha256
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.imaging.volumes import Volume


def source_hash() -> str:
    root = Path(__file__).resolve().parents[1]
    return hashlib.sha256(
        b"".join(
            str(p.relative_to(root)).encode() + p.read_bytes() for p in sorted(root.rglob("*.py"))
        )
    ).hexdigest()


def encode(value: Any, arrays: dict[str, Any], aliases: dict[str, Any]) -> Any:
    if isinstance(value, Volume):
        for key, parent in aliases.items():
            if value is parent:
                return {"__alias__": key}
        key = "a" + str(len(arrays))
        arrays[key] = value.array()
        return {
            "__volume__": key,
            "affine": value.affine_m.tolist(),
            "kind": value.kind,
            "metadata": value.metadata,
        }
    if isinstance(value, Mesh):
        return {
            "__mesh__": True,
            "vertices": encode(value.vertices.xyz, arrays, aliases),
            "faces": encode(value.faces, arrays, aliases),
            "frame": value.vertices.frame.value,
            "metadata": value.metadata,
        }
    if isinstance(value, np.ndarray):
        key = "a" + str(len(arrays))
        arrays[key] = value
        return {"__array__": key}
    if isinstance(value, dict):
        return {str(k): encode(v, arrays, aliases) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v, arrays, aliases) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def decode(value: Any, arrays: Any, aliases: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        if "__alias__" in value:
            return aliases[value["__alias__"]]
        if "__volume__" in value:
            return Volume(
                arrays[value["__volume__"]],
                np.array(value["affine"]),
                value["kind"],
                value["metadata"],
            )
        if "__array__" in value:
            return arrays[value["__array__"]]
        if "__mesh__" in value:
            return Mesh(
                Points(decode(value["vertices"], arrays, aliases), Frame(value["frame"])),
                decode(value["faces"], arrays, aliases),
                value["metadata"],
            )
        return {k: decode(v, arrays, aliases) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v, arrays, aliases) for v in value]
    return value


def artifact_hash(value: Any) -> str:
    arrays: dict[str, Any] = {}
    metadata = encode(value, arrays, {})
    digest = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )
    for k, v in arrays.items():
        x = np.ascontiguousarray(v)
        digest.update(k.encode() + str(x.shape).encode() + str(x.dtype).encode() + x.tobytes())
    return digest.hexdigest()


class StageCache:
    def __init__(self, root: Path, *, repair: bool = False, recover: bool = False) -> None:
        self.root, self.repair, self.recover = root, repair, recover
        self.implementation = source_hash()
        self.versions = {
            n: version(n)
            for n in [
                "soma-neuro",
                "numpy",
                "scipy",
                "nibabel",
                "SimpleITK",
                "scikit-image",
                "pybids",
            ]
        }

    def run(
        self,
        name: str,
        inputs: dict[str, Any],
        parameters: dict[str, Any],
        build: Callable[[], dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        identity = {
            "inputs": {k: artifact_hash(v) for k, v in inputs.items()},
            "parameters": parameters,
            "implementation": self.implementation,
            "software": self.versions,
            "frame": "RAS",
            "units": "m",
        }
        identity = json.loads(json.dumps(identity, sort_keys=True, allow_nan=False))
        key = fingerprint(identity)
        path = self.root / f"{name}-{key}.npz"
        receipt = path.with_suffix(".npz.json")
        recovery = None
        if path.exists() or receipt.exists():
            incomplete = not (path.exists() and receipt.exists())
            bad = incomplete
            if not incomplete:
                try:
                    m = json.loads(receipt.read_text())
                    bad = m["parameters"] != identity or m["sha256"] != sha256(path)
                except (ValueError, KeyError):
                    bad = True
            if bad:
                if not (self.repair or (incomplete and self.recover)):
                    raise ValueError(
                        "Cache integrity failure; use explicit "
                        "repair or incomplete-publication recovery"
                    )
                quarantine = self.root / ".quarantine" / f"{name}-{key}-{time.time_ns()}"
                quarantine.mkdir(parents=True, exist_ok=False)
                for p in [path, receipt]:
                    if p.exists():
                        shutil.move(str(p), quarantine / p.name)
                recovery = {
                    "reason": "incomplete publication" if incomplete else "corrupt committed cache",
                    "quarantine": str(quarantine),
                }

        def read(p: Path) -> Any:
            with np.load(p, allow_pickle=False) as a:
                return decode(json.loads(str(a["manifest"].item())), a, inputs)

        def write(p: Path, value: Any) -> None:
            arrays: dict[str, Any] = {}
            metadata = encode(value, arrays, inputs)
            np.savez_compressed(p, manifest=json.dumps(metadata, allow_nan=False), **arrays)

        result, report = cached_object(self.root, name, identity, ".npz", build, read, write)
        report["recovery"] = recovery
        return dict(result), report
