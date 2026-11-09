"""Backend-neutral tissue segmentation, no implicit tool installation or weights."""

import time
from importlib.metadata import version
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from soma.benchmarks.segmentation import intensity_baseline
from soma.core.provenance import sha256
from soma.imaging.nifti import load_nifti
from soma.imaging.segmentation import require_labels
from soma.imaging.volumes import Volume


class SegmentationBackend(Protocol):
    cache_version: str

    def segment(
        self, image: Volume, *, subject: str, parameters: dict[str, Any]
    ) -> tuple[Volume, dict[str, Any]]: ...


class MultiOtsu:
    cache_version = "soma-multiotsu-v1"

    def segment(
        self, image: Volume, *, subject: str, parameters: dict[str, Any]
    ) -> tuple[Volume, dict[str, Any]]:
        start = time.perf_counter()
        labels = intensity_baseline(image)
        return labels, {
            "backend": "Soma multi-Otsu",
            "version": version("soma-neuro"),
            "model": "none",
            "input_contrast": "T1w",
            "parameters": labels.metadata,
            "ontology": "CSF1/GM2/WM3",
            "mapping": {0: 0, 1: 1, 2: 2, 3: 3},
            "native_geometry": labels.geometry(),
            "runtime_s": time.perf_counter() - start,
            "warnings": ["limited intensity baseline; no anatomical certification"],
            "reference_used": False,
            "subject": subject,
        }


class Precomputed:
    cache_version = "precomputed-import-v1"

    def segment(
        self, image: Volume, *, subject: str, parameters: dict[str, Any]
    ) -> tuple[Volume, dict[str, Any]]:
        start = time.perf_counter()
        required = [
            "path",
            "subject",
            "tool",
            "version",
            "model",
            "mapping",
            "input_sha256",
            "reference_used",
        ]
        if (
            any(k not in parameters for k in required)
            or parameters["subject"] != subject
            or parameters["reference_used"] is not False
        ):
            raise ValueError(
                "Independent precomputed segmentation needs matched subject and complete provenance"
            )
        if parameters["input_sha256"] != image.metadata.get("source_sha256"):
            raise ValueError("Precomputed segmentation input MRI identity differs")
        path = Path(parameters["path"])
        labels = load_nifti(path, kind="labels")
        if not labels.same_grid(image):
            raise ValueError("Imported labels and image geometry differ; no automatic resampling")
        values = require_labels(labels)
        mapping = {int(k): int(v) for k, v in parameters["mapping"].items()}
        if not set(np.unique(values)).issubset(mapping) or not set(mapping.values()).issubset(
            {0, 1, 2, 3}
        ):
            raise ValueError("Unknown/incompatible precomputed label ontology")
        data = np.zeros(labels.shape, dtype=np.uint8)
        for source, target in mapping.items():
            data[values == source] = target
        result = Volume(data, labels.affine_m, "labels", {"pipeline_subject": subject})
        return result, {
            "backend": parameters["tool"],
            "version": parameters["version"],
            "model": parameters["model"],
            "input_contrast": "T1w",
            "parameters": parameters,
            "ontology": "CSF1/GM2/WM3",
            "mapping": mapping,
            "native_geometry": labels.geometry(),
            "runtime_s": time.perf_counter() - start,
            "warnings": [],
            "reference_used": False,
            "source_output_sha256": sha256(path),
            "subject": subject,
        }


BACKENDS: dict[str, SegmentationBackend] = {"multiotsu": MultiOtsu(), "import": Precomputed()}


def register_backend(name: str, backend: SegmentationBackend) -> None:
    if not getattr(backend, "cache_version", None):
        raise ValueError("External backend must declare cache_version for software/model identity")
    if not name or name in BACKENDS:
        raise ValueError("Backend names are explicit and cannot replace registered implementations")
    BACKENDS[name] = backend


def backend_identity(name: str) -> dict[str, Any]:
    import inspect

    backend = BACKENDS.get(name)
    if backend is None:
        raise ValueError("Unknown backend; register it explicitly")
    path = inspect.getsourcefile(type(backend))
    return {
        "name": name,
        "cache_version": backend.cache_version,
        "implementation_sha256": sha256(Path(path)) if path and Path(path).exists() else None,
        "module": type(backend).__module__,
        "class": type(backend).__qualname__,
    }
