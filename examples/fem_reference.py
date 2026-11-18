"""Core-only concentric physical reference; full FEM requires the optional extra."""

import numpy as np

from soma.sdk.source import fem_reference_design, fem_reference_protocol, layered_sphere_reference
from soma.source.bem_discrepancy import homogeneous_series, sensors
from soma.source.noise import average_projector


def run():
    c = fem_reference_design()
    ss = sensors(None)
    p = np.array([[0.0, 0.0, 0.0], [0.035, 0.0, 0.0]])
    g, d = layered_sphere_reference(p, ss, c["radii_m"], [0.33] * 4)
    expected = average_projector(32) @ homogeneous_series(p, ss)
    error = float(np.linalg.norm(g - expected) / np.linalg.norm(expected))
    assert error < 1e-12
    return dict(
        synthetic_only=True,
        human_subjects=0,
        protocol=fem_reference_protocol().protocol.fingerprint,
        homogeneous_identity_relative=error,
        transmission=d,
        full_four_layer_status="consult study; analytical identity is not FEM validation",
    )
