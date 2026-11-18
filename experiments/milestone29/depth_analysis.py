"""Supplemental POST_OUTCOME_DESCRIPTIVE depth audit; no acceptance gate changes.

Reproduce: python experiments/milestone29/depth_analysis.py
The primary tables explicitly report source radius, not cortical depth. This
supplement computes distance to the actual finest polyhedral brain boundary.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.experiments.nonspherical import known_truth
from soma.imaging.mesh_quality import _point_triangle, contains
from soma.source.nonspherical import head_parameters, meshes


def run(root: Path) -> None:
    fields = pd.read_csv(root / "source-fields.csv")
    fields = fields[
        fields.label.str.startswith("C-") & (fields.level == 3) & fields.independent_draw
    ]
    rows = []
    for head in range(6):
        brain = meshes(head_parameters(head), 3)[0]
        points, _ = known_truth(head)
        assert contains(brain, points.xyz).all()
        triangles = brain.vertices.xyz[brain.faces]
        for source, point in enumerate(points.xyz):
            distance = float(
                _point_triangle(np.broadcast_to(point, (len(triangles), 3)), triangles).min()
            )
            assert 0 < distance <= np.linalg.norm(brain.vertices.xyz - point, axis=1).min()
            field = fields[(fields["head"] == head) & (fields.source == source + 12)]
            assert len(field) == 1
            rows.append(
                dict(
                    head=head,
                    source=source,
                    brain_boundary_distance_mm=distance * 1000,
                    source_radius_mm=float(np.linalg.norm(point) * 1000),
                    relative=float(field.relative.iloc[0]),
                    analysis_status="POST_OUTCOME_DESCRIPTIVE",
                )
            )
    table = pd.DataFrame(rows)
    table.to_csv(root / "source-depth-audit.csv", index=False)
    for head, group in table.groupby("head"):
        plt.scatter(group.brain_boundary_distance_mm, group.relative, label=f"head {head}", s=18)
    plt.xlabel("Distance to finest polyhedral brain boundary (mm)")
    plt.ylabel("OM/FEM combined XYZ relative field difference (1)")
    plt.title("Geometric depth — synthetic\nPost-outcome descriptive supplement")
    plt.legend()
    plt.tight_layout()
    path = root / "figures/13-geometric-depth-supplement.svg"
    plt.savefig(path)
    plt.close()
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


if __name__ == "__main__":
    run(Path(__file__).resolve().parent)
