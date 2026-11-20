"""Synthetic concentric-shell head phantom on an LPS voxel grid (no participant data)."""

from typing import Any

import numpy as np

from soma.imaging.volumes import Volume

VOXEL_MM = 2.0
SHAPE = (80, 80, 80)
# Radii (mm): brain, extracerebral CSF (= inner skull), outer skull, scalp.
BRAIN, INNER, OUTER, SCALP = 46.0, 50.0, 56.0, 62.0


def affine(voxel_mm: float, shape: tuple[int, int, int]) -> Any:
    """LPS storage like SynthRAD2023: +i → left, +j → posterior, +k → superior."""
    a = np.diag([-voxel_mm, -voxel_mm, voxel_mm, 1.0])
    a[:3, 3] = -a[:3, :3] @ ((np.asarray(shape) - 1) / 2)
    a[:3] /= 1000
    a[3, 3] = 1.0
    return a


def radius_mm(shape: tuple[int, int, int], voxel_mm: float) -> Any:
    index = np.indices(shape).astype(float)
    centre = (np.asarray(shape) - 1) / 2
    return np.sqrt(sum(((index[i] - centre[i]) * voxel_mm) ** 2 for i in range(3)))


def phantom(
    *,
    outer: float = OUTER,
    scalp: float = SCALP,
    voxel_mm: float = VOXEL_MM,
    shape: tuple[int, int, int] = SHAPE,
) -> dict[str, Volume]:
    r = radius_mm(shape, voxel_mm)
    a = affine(voxel_mm, shape)
    t1 = np.zeros(shape, np.float32)
    t1[r < scalp] = 0.8
    t1[r < outer] = 0.05
    t1[r < INNER] = 0.2
    t1[r < BRAIN] = 0.6
    ct = np.full(shape, -1000.0, np.float32)
    ct[r < scalp] = 40.0
    ct[r < outer] = 1200.0
    ct[r < INNER] = 15.0
    ct[r < BRAIN] = 35.0
    head = (r < scalp + 4).astype(np.uint8)
    labels = np.zeros(shape, np.int16)
    labels[r < INNER] = 24
    labels[r < BRAIN] = 3
    meta = {"source_sha256": "synthetic", "subject": "phantom"}
    return {
        "t1": Volume(t1, a, "intensity", meta),
        "ct": Volume(ct, a, "intensity", meta),
        "mask": Volume(head, a, "labels", meta),
        "synthseg": Volume(labels, a, "labels", meta),
    }
