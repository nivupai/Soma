"""Bounded postprocessing on recorded forwards; no new fitting/physical simulation."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from soma.geometry import Frame, Points
from soma.source.nonspherical import (
    cases,
    head_parameters,
    meshes,
    native_forward,
    pose,
    radial_projection,
    sensor_targets,
    source_grid,
)
from soma.source.resolution import Resolution
from soma.source.uncertainty import electrode_positions, kernels, physical_forward, transform


def run(root, output):
    rows = []
    fields = []
    grid = source_grid()
    sphere = physical_forward(grid, electrode_positions(), transform()).matrix
    for head in range(6):
        p = head_parameters(head)
        fine = np.load(root / f"head-{head}/fine/result/lead.npy", allow_pickle=False)[:, :144]
        fields.append(
            dict(
                head=head,
                case="sphere-vs-nonspherical-fine",
                total_relative=float(np.linalg.norm(sphere - fine) / np.linalg.norm(fine)),
                scope="geometry + sensor layout + different formulation; not isolated shape effect",
            )
        )
        scale = float(np.linalg.norm(fine, 2))
        base = np.load(root / f"head-{head}/mesh-2/result/lead.npy", allow_pickle=False)
        for case in cases():
            path = root / f"head-{head}" / case["id"] / "result/lead.npy"
            if not path.exists():
                continue
            g = np.load(path, allow_pickle=False)
            b = meshes(p, case["level"], case)
            t = pose(case)
            ss, _ = radial_projection(
                b[-1], t.apply(Points(sensor_targets(p, case), Frame.HEAD)).xyz
            )
            fw = native_forward(g, grid, t.inverse().apply(Points(ss, Frame.MRI)).xyz, t)
            ops, _ = kernels(fw, scale)
            fields.append(
                dict(
                    head=head,
                    case=case["id"],
                    total_relative=float(np.linalg.norm(g - fine) / np.linalg.norm(fine)),
                    mismatch_at_fixed_mesh_relative=float(
                        np.linalg.norm(g - base) / np.linalg.norm(base)
                    ),
                    orientation_column_norm_min=float(np.linalg.norm(g, axis=0).min()),
                    orientation_column_norm_max=float(np.linalg.norm(g, axis=0).max()),
                    rank=int(np.linalg.matrix_rank(g)),
                )
            )
            for method, k in ops.items():
                resolution = Resolution(k, fw.matrix)
                # Cartesian orientations separately; magnitude follows the linear PSF.
                for seed in range(48):
                    psfs = resolution.psf(list(range(3 * seed, 3 * seed + 3)))
                    for orientation in range(3):
                        amplitude = np.linalg.norm(psfs[:, orientation].reshape(-1, 3), axis=1)
                        distance = np.linalg.norm(grid.xyz - grid.xyz[seed], axis=1) * 1000
                        energy = amplitude**2
                        rows.append(
                            dict(
                                head=head,
                                case=case["id"],
                                method=method,
                                source=seed,
                                orientation=orientation,
                                peak_error_mm=float(distance[np.argmax(amplitude)]),
                                dispersion_mm=float(np.sqrt(energy @ distance**2 / energy.sum())),
                                self_gain=float(amplitude[seed]),
                                units="1/(A*m)" if method == "dSPM" else "1",
                            )
                        )
    pd.DataFrame(rows).to_csv(output / "resolution.csv", index=False)
    pd.DataFrame(fields).to_csv(output / "field-attribution.csv", index=False)
    manifest = json.loads((output / "manifest.json").read_text())
    import hashlib

    for p in output.rglob("*"):
        if p.is_file() and p.name != "manifest.json":
            manifest[str(p.relative_to(output))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.root, a.output)
