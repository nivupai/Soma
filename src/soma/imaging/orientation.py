"""Array reorientation changes storage and its affine together, not anatomy."""

import nibabel as nib
import numpy as np

from soma.imaging.volumes import Volume


def reorient(volume: Volume, axis_codes: tuple[str, str, str] = ("R", "A", "S")) -> Volume:
    original = nib.orientations.io_orientation(volume.affine_m)
    desired = nib.orientations.axcodes2ornt(axis_codes)
    change = nib.orientations.ornt_transform(original, desired)
    data = nib.orientations.apply_orientation(volume.array(), change)
    affine = volume.affine_m @ nib.orientations.inv_ornt_aff(change, volume.shape)
    return Volume(
        data,
        np.asarray(affine),
        volume.kind,
        {
            **volume.metadata,
            "storage_reorientation": {
                "from": list(nib.aff2axcodes(volume.affine_m)),
                "to": axis_codes,
                "interpolation": "none",
            },
        },
    )
