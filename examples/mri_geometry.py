"""Run: python -m examples.mri_geometry. Expected RAS+ and 2 mm spacing."""

import json
import tempfile
from pathlib import Path

import numpy as np

from soma.sdk.imaging import load_nifti, save_nifti, validate_volume
from soma.sdk.synthetic import asymmetric


def run():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic.nii.gz"
        save_nifti(asymmetric(), path)
        volume = load_nifti(path)
        report = validate_volume(volume)
        indices = np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]])
        world = volume.grid.to_world(indices)
        assert np.allclose(volume.grid.to_voxel(world), indices)
        assert np.allclose(volume.spacing_m, 0.002)
        assert report["geometry"]["axis_codes"] == ["R", "A", "S"]
        return {
            "spacing_mm": (volume.spacing_m * 1000).tolist(),
            "world_m": world.xyz.tolist(),
            "roundtrip_voxels": report["voxel_roundtrip_max_voxels"],
            "synthetic": True,
        }


if __name__ == "__main__":
    print(json.dumps(run(), allow_nan=False))
