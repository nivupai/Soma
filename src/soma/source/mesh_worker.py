"""Optional external mesher process; no Gmsh library is bundled with Soma."""

import argparse
import json
import resource
import sys
from pathlib import Path

import numpy as np

from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.mesh_replication import gmsh_mesh

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    a = p.parse_args()
    request = json.loads((a.root / "request.local.json").read_text())
    with np.load(a.root / "surfaces.npz", allow_pickle=False) as z:
        surfaces = [
            Mesh(Points(z[f"v{i}"], Frame.MRI), z[f"f{i}"], {"synthetic": True}) for i in range(4)
        ]
        ss = z["sensors"]
    v, t, labels, q = gmsh_mesh(surfaces, ss, request["max_size_m"])
    if len(v) > 18000 or len(t) > 100000 or q["min_mean_ratio"] < 0.01:
        raise ValueError("Frozen mesh size/quality gate")
    q["peak_mesher_MiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        1024**2 if sys.platform == "darwin" else 1024
    )
    np.savez_compressed(a.root / "mesh.npz", vertices=v, tetrahedra=t, labels=labels)
    (a.root / "mesh-audit.json").write_text(json.dumps(q, indent=2) + "\n")
