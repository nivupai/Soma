"""Closed tetrahedron: area in m², volume exactly 1e-6/6 m³."""

import json

import numpy as np

from soma.sdk.imaging import Frame, Mesh, Points, mesh_quality


def mesh():
    return Mesh(
        Points(np.array([[0.0, 0, 0], [0.01, 0, 0], [0, 0.01, 0], [0, 0, 0.01]]), Frame.RAS),
        np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]]),
    )


def run():
    result = mesh_quality(mesh())
    assert result["geometrically_valid_under_checks"]
    assert np.isclose(result["enclosed_volume_m3"], 1e-6 / 6, rtol=1e-12, atol=0)
    return {k: result[k] for k in ["euler_characteristic", "surface_area_m2", "enclosed_volume_m3"]}


if __name__ == "__main__":
    print(json.dumps(run(), allow_nan=False))
