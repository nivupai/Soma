"""Private single-process component timings; no machine-specific assertions."""

import resource
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import numpy as np

from soma.benchmarks.segmentation import intensity_baseline
from soma.benchmarks.topology import topology
from soma.core.provenance import sha256, write_json
from soma.imaging.nifti import load_nifti, save_nifti
from soma.imaging.resampling import resample
from soma.imaging.surfaces import extract_surface
from soma.imaging.volumes import Volume
from soma.pipeline.cache import source_hash
from soma.pipeline.stages import intensity_qc, preprocess

T = TypeVar("T")


def main() -> None:
    root = Path("reports/milestone12-component-performance-acceptance")
    root.mkdir(parents=True, exist_ok=False)
    times: dict[str, float] = {}

    def timed(name: str, operation: Callable[[], T]) -> T:
        start = time.perf_counter()
        value = operation()
        times[name] = time.perf_counter() - start
        return value

    path = Path("data/derived/milestone12/synthetic-bids-acceptance/sub-01/anat/sub-01_T1w.nii.gz")

    def loading() -> Volume:
        volume = load_nifti(path)
        volume.array()
        return volume

    image = timed("load_and_materialize_s", loading)
    corrected, _ = timed(
        "n4_s",
        lambda: preprocess(
            image,
            {
                "n4": {"enabled": True, "iterations": [2], "shrink_factor": 1},
                "resampling": {"enabled": False},
            },
        ),
    )
    labels = timed("segmentation_s", lambda: intensity_baseline(corrected))
    reference = Volume(np.zeros((23, 23, 23), np.float32), np.diag([0.0011] * 3 + [1.0]))
    timed("resampling_s", lambda: resample(image, reference))
    mesh = timed("surface_generation_s", lambda: extract_surface(labels, label=3))
    timed("intensity_qc_s", lambda: intensity_qc(image))
    mesh_qc = timed("topology_qc_s", lambda: topology(mesh))
    timed("nifti_serialization_s", lambda: save_nifti(labels, root / "labels.nii.gz"))
    write_json(
        root / "performance.json",
        {
            "scope": "single synthetic 25 cubed image; no cache, no figures; not human timings",
            "shape": image.shape,
            "times": times,
            "topology_status": mesh_qc.get("status"),
            "peak_RSS_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**2 if sys.platform == "darwin" else 1024),
            "memory_scope": "whole process high-water including imported libraries",
            "source_tree_sha256": source_hash(),
            "orchestration_sha256": sha256(Path(__file__)),
        },
    )


if __name__ == "__main__":
    main()
