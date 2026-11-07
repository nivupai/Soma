"""Conservative labels/masks and measurements, without a clinical tissue model."""

from typing import Any

import numpy as np
from scipy import ndimage
from skimage.filters import threshold_otsu

from soma.imaging.volumes import Volume


def require_labels(volume: Volume) -> np.ndarray[Any, Any]:
    data = volume.array()
    if volume.kind != "labels" or data.dtype.kind not in "biu" or np.any(data < 0):
        raise ValueError("Nonnegative integer anatomical labels are required")
    return data


def agreement(a: Volume, b: Volume, *, label: int = 1) -> dict[str, float]:
    if not a.same_grid(b):
        raise ValueError("Segmentation comparison requires the same physical grid")
    x, y = require_labels(a) == label, require_labels(b) == label
    intersection, union = int(np.sum(x & y)), int(np.sum(x | y))
    denominator = int(x.sum() + y.sum())
    return {
        "dice": 2 * intersection / denominator if denominator else 1.0,
        "jaccard": intersection / union if union else 1.0,
    }


def region_volumes(volume: Volume) -> dict[int, float]:
    labels, counts = np.unique(require_labels(volume), return_counts=True)
    voxel = abs(float(np.linalg.det(volume.affine_m[:3, :3])))
    return {int(label): float(count * voxel) for label, count in zip(labels, counts, strict=True)}


def process_mask(
    volume: Volume,
    *,
    closing_iterations: int = 0,
    fill_holes: bool = False,
    largest_component: bool = False,
) -> Volume:
    data = require_labels(volume)
    if not set(np.unique(data)) <= {0, 1} or closing_iterations < 0:
        raise ValueError("Binary masks and nonnegative morphology iterations required")
    mask = data.astype(bool)
    if closing_iterations:
        mask = ndimage.binary_closing(mask, iterations=closing_iterations)
    if fill_holes:
        mask = ndimage.binary_fill_holes(mask)
    components, count = ndimage.label(mask)
    sizes = np.bincount(components.ravel())
    if largest_component and count:
        sizes[0] = 0
        mask = components == int(np.argmax(sizes))
    return Volume(
        mask.astype(np.uint8),
        volume.affine_m,
        "labels",
        {
            **volume.metadata,
            "morphology": {
                "closing_iterations_voxels": closing_iterations,
                "fill_holes": fill_holes,
                "largest_component": largest_component,
                "input_components": count,
                "changed_voxels": int(np.sum(mask != data.astype(bool))),
            },
        },
    )


def threshold_mask(volume: Volume, *, threshold: float | None = None) -> Volume:
    data = volume.array()
    if volume.kind != "intensity" or not np.isfinite(data).all() or np.ptp(data) == 0:
        raise ValueError("Threshold baseline requires finite nonconstant intensities")
    value = float(threshold_otsu(data)) if threshold is None else float(threshold)
    return Volume(
        (data > value).astype(np.uint8),
        volume.affine_m,
        "labels",
        {
            **volume.metadata,
            "segmentation": {
                "source": "automatic_intensity_threshold_baseline",
                "threshold": value,
                "reference_annotation": False,
                "clinical_tissue_segmentation": False,
            },
        },
    )


def validate_mask(mask: Volume, image: Volume) -> None:
    data = require_labels(mask)
    if not mask.same_grid(image) or not set(np.unique(data)) <= {0, 1}:
        raise ValueError("Binary mask must share the image's physical grid")


def components(mask: Volume, *, label: int = 1) -> tuple[Volume, dict[str, Any]]:
    data = require_labels(mask)
    labels, count = ndimage.label(data == label)
    counts = np.bincount(labels.ravel())
    output = Volume(
        labels.astype(np.int32),
        mask.affine_m,
        "labels",
        {"component_source": mask.metadata, "connectivity": 6},
    )
    return output, {
        "count": count,
        "component_voxels": counts[1:].tolist(),
        "component_volumes_m3": (counts[1:] * abs(np.linalg.det(mask.affine_m[:3, :3]))).tolist(),
    }
