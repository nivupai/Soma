"""Synthetic coordinate/domain SDK example; no human validation claim."""

import numpy as np

from soma.sdk.source import SourceDomain, SourcePrior


def run():
    domain = SourceDomain(np.ones((2, 2, 2), dtype=bool), np.diag([0.001, 0.001, 0.001, 1.0]))
    p = domain.centers()[[0, 7]]
    prior = SourcePrior.create(p, "cell_volume", domain=domain)
    return dict(
        synthetic_only=True,
        voxels=8,
        volume_m3=domain.volume_m3,
        prior_scale=prior.diagonal.tolist(),
        human_accuracy=False,
    )
