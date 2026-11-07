"""Single-pass pull resampling: reference RAS points map into moving RAS points."""

from typing import Any

import numpy as np
from scipy.ndimage import affine_transform

from soma.geometry import Frame, Transform
from soma.imaging.volumes import Volume


def resample(
    source: Volume,
    reference: Volume,
    *,
    reference_to_source: Transform | None = None,
    order: int = 1,
    cval: float = 0,
    allow_repeated: bool = False,
) -> Volume:
    if order not in (0, 1, 3):
        raise ValueError("Supported interpolation orders are nearest=0, linear=1, cubic=3")
    if source.kind == "labels" and order != 0:
        raise ValueError("Anatomical labels require nearest-neighbor interpolation")
    if source.metadata.get("resampling") and not allow_repeated:
        raise ValueError("Repeated resampling requires explicit allow_repeated=True")
    transform = reference_to_source or Transform(Frame.RAS, Frame.RAS, np.eye(4))
    if transform.source != Frame.RAS or transform.destination != Frame.RAS:
        raise ValueError("Resampling transform must map reference RAS metres to source RAS metres")
    pull = np.linalg.solve(source.affine_m, transform.matrix @ reference.affine_m)
    data = source.array()
    if source.kind == "labels" and (data.dtype.kind not in "biu" or cval != int(cval)):
        raise ValueError("Label data and background must be integers")
    if source.kind == "labels":
        if np.any(data < 0) or cval < 0:
            raise ValueError("Anatomical label identities/background must be nonnegative")
        maximum = 1 if data.dtype.kind == "b" else np.iinfo(data.dtype).max
        if cval > maximum:
            raise ValueError("Label background cannot be represented by the stored dtype")
    if not np.isfinite(data).all() or not np.isfinite(cval):
        raise ValueError("Resampling requires finite intensities and background")
    # Preserve intensity precision, but do not round interpolated integer intensities.
    dtype = data.dtype if order == 0 or data.dtype.kind == "f" else np.dtype("float64")
    output = affine_transform(
        data,
        pull[:3, :3],
        pull[:3, 3],
        output_shape=reference.shape,
        order=order,
        output=dtype,
        mode="constant",
        cval=cval,
        prefilter=order > 1,
    )
    metadata: dict[str, Any] = {
        **source.metadata,
        "resampling": {
            "source_grid": source.geometry(),
            "reference_grid": reference.geometry(),
            "reference_to_source_RAS_m": transform.matrix.tolist(),
            "pull_voxel_matrix": pull.tolist(),
            "order": order,
            "background": cval,
            "one_pass": True,
        },
    }
    return Volume(output, reference.affine_m, source.kind, metadata)
