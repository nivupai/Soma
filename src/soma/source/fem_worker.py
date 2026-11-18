"""Bounded isolated optional FEM solve; numerical packets stay local."""

import argparse
import json
import resource
import sys
from pathlib import Path

import numpy as np

from soma.source.fem_reference import full_subtraction

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    a = p.parse_args()
    request = json.loads((a.root / "request.local.json").read_text())
    with np.load(a.root / "input.npz", allow_pickle=False) as z:
        v, t, labels, sources, sensors = [
            z[k] for k in ["vertices", "tetrahedra", "labels", "sources", "sensors"]
        ]
    if len(t) > 100000 or len(v) > 18000:
        raise MemoryError("Frozen FEM mesh budget exceeded")
    lead, d = full_subtraction(
        v, t, labels, sources, sensors, request["sigmas"], quadrature=request["quadrature"]
    )
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        1024**2 if sys.platform == "darwin" else 1024
    )
    d["peak_child_MiB"] = rss
    if rss > 2400:
        raise MemoryError("Frozen child memory budget exceeded")
    np.savetxt(a.root / "lead.csv", lead, delimiter=",")
    (a.root / "diagnostics.json").write_text(json.dumps(d, indent=2) + "\n")
