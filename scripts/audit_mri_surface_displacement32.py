"""Descriptive decimation QC against provided FLASH surfaces, never ground truth."""

import argparse
from pathlib import Path

import mne
import numpy as np
import pandas as pd

from soma.anatomy.surfaces import distance_to_surface
from soma.datasets.human_mri import safe_local_output
from soma.datasets.matched import SampleAssets
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh


def run(local, output):
    safe_local_output(local)
    rows = []
    assets = SampleAssets()
    for i, name in enumerate(["inner_skull", "outer_skull", "outer_skin"]):
        vertices, faces = mne.read_surface(
            assets.subject_dir / "bem" / (name + ".surf"), verbose=False
        )
        native = Mesh(Points(vertices * 0.001, Frame.MRI), faces)
        for level in [2, 3, 4]:
            with np.load(local / f"geometry-{level}/geometry.npz", allow_pickle=False) as z:
                decimated = Mesh(Points(z[f"v{i}"], Frame.MRI), z[f"f{i}"])
            a = distance_to_surface(native.vertices, decimated) * 1000
            b = distance_to_surface(decimated.vertices, native) * 1000
            rows.append(
                dict(
                    level=level,
                    boundary=name,
                    symmetric_vertex_sample_mean_mm=(a.mean() + b.mean()) / 2,
                    pooled_vertex_sample_HD95_mm=np.percentile(np.r_[a, b], 95),
                    vertex_sample_max_mm=max(a.max(), b.max()),
                    reference="provided FLASH boundary, not independent truth",
                    definition="bidirectional vertex-to-triangle samples; not area-integrated ASSD",
                )
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("local", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.local, a.output)
