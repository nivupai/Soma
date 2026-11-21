"""SynthSeg label import: fixed ontology map and native-grid return, no tool execution here."""

from pathlib import Path
from typing import Any, Literal

import numpy as np

from soma.imaging.nifti import load_nifti
from soma.imaging.resampling import resample
from soma.imaging.segmentation import require_labels
from soma.imaging.volumes import Volume

# Written in docs/MILESTONE33_SEGMENTATION_PROTOCOL.md before any scoring.
SYNTHSEG_CSF = (4, 5, 14, 15, 24, 43, 44)
SYNTHSEG_GM = (3, 8, 10, 11, 12, 13, 17, 18, 26, 28, 42, 47, 49, 50, 51, 52, 53, 54, 58, 60)
SYNTHSEG_WM = (2, 7, 16, 41, 46)
SYNTHSEG_TO_SOMA: dict[int, int] = {
    0: 0,
    **{code: 1 for code in SYNTHSEG_CSF},
    **{code: 2 for code in SYNTHSEG_GM},
    **{code: 3 for code in SYNTHSEG_WM},
}


def map_synthseg(labels: Volume) -> Volume:
    """Map SynthSeg (non-parcellated) codes to Soma CSF1/GM2/WM3; unknown codes are refused."""
    values = require_labels(labels)
    unknown = sorted(set(np.unique(values).tolist()) - set(SYNTHSEG_TO_SOMA))
    if unknown:
        raise ValueError(f"SynthSeg codes outside the frozen ontology map: {unknown}")
    lut = np.zeros(int(values.max()) + 1, dtype=np.uint8)
    for source, target in SYNTHSEG_TO_SOMA.items():
        if source < len(lut):
            lut[source] = target
    return Volume(
        lut[values],
        labels.affine_m,
        "labels",
        {**labels.metadata, "ontology": "CSF1/GM2/WM3", "synthseg_mapping": SYNTHSEG_TO_SOMA},
    )


def to_native_grid(labels: Volume, native: Volume) -> tuple[Volume, dict[str, Any]]:
    """Return mapped labels on the native image grid by one nearest-neighbour pass."""
    if labels.same_grid(native):
        return labels, {"resampled": False}
    out = resample(labels, native, order=0)
    return out, {"resampled": True, "order": 0, "resampling": out.metadata["resampling"]}


def intracranial_mask(labels: Volume, *, dilation_voxels: int = 1) -> Volume:
    """Non-background SynthSeg region, dilated; never derived from a reference label."""
    from scipy.ndimage import binary_dilation

    if dilation_voxels < 0:
        raise ValueError("Dilation must be nonnegative")
    mask = require_labels(labels) > 0
    if dilation_voxels:
        mask = binary_dilation(mask, iterations=dilation_voxels)
    return Volume(
        mask.astype(np.uint8),
        labels.affine_m,
        "labels",
        {"mask": "synthseg-nonbackground", "dilation_voxels": dilation_voxels},
    )


def load_synthseg(path: Path) -> Volume:
    """Load SynthSeg output; it works in mm, and inherits 'unknown' units from IBSR headers."""
    import nibabel as nib

    image: Any = nib.load(path)
    unit = image.header.get_xyzt_units()[0]
    override = "mm" if unit == "unknown" else None
    # SynthSeg copies the input's coded transform: sform for IBSR/MRBrainS, qform-only for
    # SynthRAD2023. Use whichever is coded, preferring sform.
    policy: Literal["sform", "qform"] = "sform" if image.get_sform(coded=True)[1] else "qform"
    return load_nifti(path, policy=policy, units_override=override, kind="labels")
