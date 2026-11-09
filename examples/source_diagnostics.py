"""Identity toy forward: lambda²=.1 gives diagonal resolution 1/1.1.

Dimensionless toy units, no anatomy, scalp or localization validation.
"""

import json

import numpy as np

from soma.sdk.source import Resolution, Tikhonov


def run():
    forward = np.eye(3)
    inverse = Tikhonov(forward, 0.1)
    truth = np.array([1.0, 0.0, 0.0])
    estimate = inverse.solve(forward @ truth)
    resolution = Resolution(inverse.kernel, forward)
    assert np.allclose(estimate, truth / 1.1)
    assert np.allclose(resolution.diagonal, 1 / 1.1)
    return {
        "estimate": estimate.tolist(),
        "resolution_diagonal": resolution.diagonal.tolist(),
        "diagnostics": inverse.diagnostics(truth, truth),
        "units": "dimensionless toy",
    }


if __name__ == "__main__":
    print(json.dumps(run(), allow_nan=False))
