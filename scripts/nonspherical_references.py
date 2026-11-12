"""Bounded physical limiting reference; no cohort localization outcomes."""

import argparse
import json
from pathlib import Path

import numpy as np

from soma.anatomy.synthetic import sphere_mesh
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.noise import average_projector
from soma.source.nonspherical import design
from soma.source.nonspherical_solver import solve
from soma.source.uncertainty import fibonacci, physical_forward, transform


def run(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    c = design()
    u, _ = sphere_mesh(0, 1)
    sensors = u * 0.09
    exact = average_projector(len(u)) @ (3 / (4 * np.pi * 0.33 * 0.09**3) * sensors)
    rows = []
    for level in range(4):
        v, f = sphere_mesh(level, 0.09)
        b = [Mesh(Points(v, Frame.MRI), f, {"synthetic": True})]
        g, d = solve(b, np.zeros((1, 3)), sensors, [0.33], output / f"homogeneous-{level}")
        error = float(np.linalg.norm(g - exact) / np.linalg.norm(exact))
        rows.append(dict(reference="A-exact-homogeneous-central", level=level, error=error, **d))
    truth = Points(fibonacci(4, 0.1) * 0.05, Frame.MRI)
    semi = physical_forward(truth, Points(sensors, Frame.HEAD), transform()).matrix
    for level in range(4):
        b = []
        for radius in c["radii_mm"]:
            v, f = sphere_mesh(level, radius / 1000)
            b.append(Mesh(Points(v, Frame.MRI), f, {"synthetic": True}))
        g, d = solve(
            b, truth.xyz, sensors, c["conductivities_S_m"], output / f"heterogeneous-{level}"
        )
        error = float(np.linalg.norm(g - semi) / np.linalg.norm(semi))
        rows.append(dict(reference="A-MNE-semi-analytic-four-shell", level=level, error=error, **d))
    report = dict(
        homogeneous_acceptance=c["sphere_reference_rtol"],
        homogeneous_status="PASS" if rows[3]["error"] <= c["sphere_reference_rtol"] else "FAIL",
        rows=rows,
        C_four_layer="NOT_ESTABLISHED",
        FEM="NOT_PERFORMED",
        D="PHANTOM_NOT_AVAILABLE",
    )
    (output / "references.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
