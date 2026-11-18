"""Small native external-mesher platform control, not the full M30 study."""

import argparse
import json
import platform
from pathlib import Path

import numpy as np

from soma.experiments.mesh_grid import protocol
from soma.source.bem_discrepancy import homogeneous_series, sensors
from soma.source.fem_reference import full_subtraction
from soma.source.mesh_replication import boundaries, candidate_grid, gmsh_mesh, nearest_distances
from soma.source.noise import average_projector


def run():
    v, t, labels, q = gmsh_mesh(boundaries(None, 1), sensors(None), 0.025)
    p = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0]])
    g, d = full_subtraction(v, t, labels, p, sensors(None), [0.33] * 4, quadrature=8)
    exact = average_projector(32) @ homogeneous_series(p, sensors(None))
    error = float(np.linalg.norm(g - exact) / np.linalg.norm(exact))
    assert error < 0.15 and d["relative_residual"] < 1e-10
    return dict(
        schema="soma.mesh-grid.repro/1",
        environment=dict(
            system=platform.system(), machine=platform.machine(), python=platform.python_version()
        ),
        protocol=protocol().protocol.fingerprint,
        lead=g.tolist(),
        relative=error,
        tissue_volumes_m3=q["tissue_volumes_m3"],
        min_mean_ratio=q["min_mean_ratio"],
        boundary_coordinate_max_m=q["boundary_coordinate_max_m"],
        nearest_mm=[
            float(nearest_distances(candidate_grid(s).xyz, np.array([[0.012, 0.023, 0.034]]))[0])
            for s in [30, 20, 15]
        ],
        scope="small native Gmsh/P1 numerical check; no bitwise mesh or cache identity claim",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(run(), indent=2) + "\n")
