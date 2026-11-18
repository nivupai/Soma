"""Tiny homogeneous FEM physical control for the actual platform matrix."""

import argparse
import json
import platform
from pathlib import Path

import numpy as np

from soma.anatomy.synthetic import sphere_mesh
from soma.experiments.fem_reference import protocol
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.bem_discrepancy import homogeneous_series, sensors
from soma.source.fem_reference import full_subtraction, radial_mesh
from soma.source.noise import average_projector


def run():
    bs = []
    for radius in [0.081, 0.0828, 0.0873, 0.09]:
        v, f = sphere_mesh(1, radius)
        bs.append(Mesh(Points(v, Frame.MRI), f, {}))
    v, t, labels, q = radial_mesh(bs, 1)
    p = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0]])
    g, d = full_subtraction(v, t, labels, p, sensors(None), [0.33] * 4, quadrature=8)
    exact = average_projector(32) @ homogeneous_series(p, sensors(None))
    error = float(np.linalg.norm(g - exact) / np.linalg.norm(exact))
    assert error < 0.15 and d["relative_residual"] < 1e-10
    return dict(
        schema="soma.fem-reference.repro/1",
        environment=dict(
            system=platform.system(), machine=platform.machine(), python=platform.python_version()
        ),
        protocol=protocol().protocol.fingerprint,
        lead=g.tolist(),
        relative=error,
        mesh=q,
        algebraic_residual=d["relative_residual"],
        scope="coarse homogeneous FEM software reproducibility; not full four-layer acceptance",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(run(), indent=2) + "\n")
