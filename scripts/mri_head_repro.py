"""Small synthetic MRI-frame/voxel-prior fixture, never human-anatomy evidence."""

import argparse
import json
import platform
from pathlib import Path

import nibabel as nib
import numpy as np

from soma.anatomy.head_models import MRIFrameChain
from soma.geometry import Frame, Transform
from soma.source.domains import SourceDomain
from soma.source.noise import NoiseModel, average_projector
from soma.source.prior_calibration import PriorInverse, SourcePrior


def run():
    image = nib.MGHImage(np.zeros((4, 6, 8), np.float32), np.diag([1.0, 2.0, 3.0, 1.0]))
    chain = MRIFrameChain.from_mgh(image, Transform(Frame.HEAD, Frame.MRI, np.eye(4)))
    coordinates = chain.apply(
        np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]), "voxel_centers", "MRI_surface_RAS_m"
    )
    np.testing.assert_allclose(
        coordinates, [[0.002, -0.012, 0.006], [0.001, -0.003, 0.002]], atol=1e-15
    )
    mask = np.ones((3, 3, 3), bool)
    mask[0, :2, :2] = False
    affine = np.diag([0.002, 0.002, 0.002, 1.0])
    affine[:3, 3] = [0.08, -0.002, -0.002]
    domain = SourceDomain(mask, affine)
    p = domain.centers()[[0, 10, 22]]
    prior = SourcePrior.create(p, "cell_volume", domain=domain)
    proj = average_projector(5)
    g = proj @ np.sin(np.arange(45).reshape(5, 9) + 0.3) * 100
    noise = NoiseModel((5e-8) ** 2 * proj, tuple("abcde"), proj)
    kernel = PriorInverse(g, p, prior, noise, "MNE").kernel(0.1)
    return dict(
        schema="soma.mri-head-model.repro/1",
        synthetic_only=True,
        environment=dict(
            system=platform.system(), machine=platform.machine(), python=platform.python_version()
        ),
        coordinates_m=coordinates.tolist(),
        volume_m3=domain.volume_m3,
        weights_m3=domain.weights(p).tolist(),
        kernel=kernel.tolist(),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.write_text(json.dumps(run(), indent=2, allow_nan=False) + "\n")
