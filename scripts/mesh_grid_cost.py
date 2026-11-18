"""Isolated post-run inverse-cost measurement; same frozen operators/settings."""

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

from soma.source.bem_discrepancy import sensors
from soma.source.mesh_replication import candidate_grid
from soma.source.nonspherical import native_forward, pose, source_grid
from soma.source.uncertainty import kernels

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("head", type=int)
    p.add_argument("spacing", type=int)
    p.add_argument("solver")
    p.add_argument("output", type=Path)
    a = p.parse_args()
    g = np.loadtxt(a.root / f"grid-{a.head}-{a.spacing}-{a.solver}-V_per_Am.csv", delimiter=",")
    fine = np.loadtxt(a.root / f"F-{a.head}-3-0-V_per_Am.csv", delimiter=",")
    grid = source_grid()
    grid = (
        type(grid)(grid.xyz[np.r_[0:6, 24:30]], grid.frame)
        if a.spacing == 0
        else candidate_grid(a.spacing)
    )
    started = time.perf_counter()
    ops, _ = kernels(
        native_forward(g, grid, sensors(a.head), pose({})), float(np.linalg.norm(fine[:, :36], 2))
    )
    norms = {name: float(np.linalg.norm(k @ g)) for name, k in ops.items()}
    r = dict(
        head=a.head,
        spacing_mm=a.spacing,
        candidates=len(grid.xyz),
        solver=a.solver,
        seconds=time.perf_counter() - started,
        peak_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
        scope="post-run isolated kernel/resolution cost; imports included in peak RSS",
        resolution_norms=norms,
    )
    a.output.write_text(json.dumps(r, indent=2) + "\n")
