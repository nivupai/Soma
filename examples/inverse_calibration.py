"""Small core-only moment-prior example; not anatomical validation."""

import numpy as np

from soma.sdk.source import NoiseModel, PriorInverse, SourcePrior, average_projector


def run():
    grid = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0], [-0.02, 0.0, 0.0]])
    p = average_projector(5)
    g = p @ np.random.default_rng(31).normal(size=(5, 9)) * 100
    noise = NoiseModel((5e-8) ** 2 * p, tuple("abcde"), p)
    prior = SourcePrior.create(grid, "cell_volume")
    inv = PriorInverse(g, grid, prior, noise, "MNE")
    result = inv.diagnostics(1 / 9)
    assert 0 < result["EDF"] < 4
    return dict(synthetic_only=True, units="A*m", **result)
