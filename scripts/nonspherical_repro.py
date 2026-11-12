"""Tiny cross-platform physical BEM reference; excludes the large study."""

import argparse
import json
import platform
import tempfile
from pathlib import Path

import numpy as np

from soma.anatomy.synthetic import sphere_mesh
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.noise import average_projector
from soma.source.nonspherical import protocol
from soma.source.nonspherical_solver import solve


def run():
    u, _ = sphere_mesh(0, 1)
    v, f = sphere_mesh(2, 0.09)
    ss = u * 0.09
    exact = average_projector(len(u)) @ (3 / (4 * np.pi * 0.33 * 0.09**3) * ss)
    with tempfile.TemporaryDirectory() as root:
        g, d = solve(
            [Mesh(Points(v, Frame.MRI), f)], np.zeros((1, 3)), ss, [0.33], Path(root) / "solver"
        )
    error = float(np.linalg.norm(g - exact) / np.linalg.norm(exact))
    assert error < 0.04 and d["algebraic_residual_relative"] < 1e-8
    return dict(
        schema="soma.nonspherical.repro/1",
        environment=dict(
            system=platform.system(), machine=platform.machine(), python=platform.python_version()
        ),
        protocol=protocol().protocol.fingerprint,
        solver_version=d["solver_version"],
        error=error,
        lead=g.tolist(),
        scope="homogeneous analytic limiting reference only; not head/anatomical portability",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(run(), indent=2) + "\n")
