"""Analytic sphere truth vs independently thresholded noisy radial intensity.

No reference labels enter prediction. Expected 0 < Dice < 1, positive HD95.
The 10 voxel radius and 0.2 threshold are fixed demonstration parameters.
"""

import json

import numpy as np

from soma.sdk.imaging import LabelVolume, Volume, score


def inputs():
    radius = np.linalg.norm(np.indices((32, 32, 32)).transpose(1, 2, 3, 0) - 15.5, axis=-1)
    truth = (radius <= 10).astype(np.uint8)
    intensity = 10 - radius + np.random.default_rng(16042).normal(0, 0.8, radius.shape)
    prediction = (intensity >= 0.2).astype(np.uint8)
    affine = np.diag([0.002, 0.002, 0.002, 1.0])
    reference = LabelVolume(
        Volume(truth, affine, "labels"),
        "synthetic",
        "analytic-RAS",
        {1: "sphere"},
        {"source": "analytic radius <= 10 voxels"},
    )
    predicted = LabelVolume(
        Volume(prediction, affine, "labels"),
        "synthetic",
        "analytic-RAS",
        {1: "sphere"},
        {"source": "thresholded noisy intensity", "seed": 16042, "truth_used": False},
    )
    return predicted, reference


def run():
    prediction, reference = inputs()
    row = score(prediction, reference)["labels"][0]
    assert 0 < row["Dice"] < 1 and row["HD95_mm"] > 0
    return {k: row[k] for k in ["Dice", "Jaccard", "ASSD_mm", "HD95_mm", "signed_volume_error_mm3"]}


if __name__ == "__main__":
    print(json.dumps(run(), allow_nan=False))
