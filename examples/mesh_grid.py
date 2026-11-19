"""Core-only grid geometry; full external mesher study remains opt-in."""

import numpy as np

from soma.sdk.source import convergence_grid, mesh_grid_design, mesh_grid_protocol
from soma.source.mesh_replication import nearest_distances


def run():
    c = mesh_grid_design()
    counts = [len(convergence_grid(s).xyz) for s in c["grid"]["spacing_mm"]]
    assert counts == c["grid"]["counts"]
    distances = [
        float(nearest_distances(convergence_grid(s).xyz, np.array([[0.012, 0.023, 0.034]]))[0])
        for s in c["grid"]["spacing_mm"]
    ]
    return dict(
        synthetic_only=True,
        counts=counts,
        nearest_mm=distances,
        protocol=mesh_grid_protocol().protocol.fingerprint,
        scope="grid geometry, not source-localization validation",
    )
