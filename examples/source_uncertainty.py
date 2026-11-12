"""Small physical compatibility control; the full frozen sweep uses the CLI."""

import numpy as np

from soma.sdk.source import uncertainty_design, uncertainty_protocol
from soma.source.uncertainty import (
    candidate_grid,
    electrode_positions,
    kernels,
    physical_forward,
    transform,
)


def run():
    points = candidate_grid()
    electrodes = electrode_positions()
    base = physical_forward(points, electrodes, transform())
    sigmas = list(uncertainty_design()["conductivities_S_m"])
    sigmas[2] = 0.01
    changed = physical_forward(points, electrodes, transform(), sigmas=sigmas)
    operators, numerical = kernels(base, float(np.linalg.norm(base.matrix, 2)))
    assert set(operators) == {"Tikhonov", "MNE", "dSPM"}
    assert np.linalg.norm(changed.matrix - base.matrix) / np.linalg.norm(base.matrix) > 0.01
    assert numerical["normal_equation_residual_relative"] < 1e-10
    return {
        "synthetic_only": True,
        "conductivity_aware": True,
        "physical_units": "V/(A m)",
        "protocol": uncertainty_protocol().protocol.fingerprint,
        "methods": sorted(operators),
        "human_subjects": 0,
    }
