"""Small physical cross-platform control; no full ensemble in CI."""

import argparse
import json
import platform
import tempfile
from pathlib import Path

import numpy as np

from soma.source.bem_discrepancy import (
    field_metrics,
    geometry,
    homogeneous_series,
    match,
    protocol,
    sensors,
    solve,
)


def run():
    ss = sensors(None)
    p = np.array([[0.0, 0.0, 0.0], [0.02, 0.01, 0.01]])
    exact = homogeneous_series(p, ss)
    exact -= exact.mean(axis=0)
    leads = []
    contracts = []
    errors = {}
    with tempfile.TemporaryDirectory() as directory:
        for solver in ["openmeeg", "mne"]:
            g, d = solve(
                geometry(None, [1] * 3), p, ss, [0.33] * 3, Path(directory) / solver, solver=solver
            )
            leads.append(g.tolist())
            contracts.append(d["contracts"])
            errors[solver] = field_metrics(g, exact)["relative"]
            assert errors[solver] < 0.4
        match(*contracts)
    return dict(
        schema="soma.bem-diagnostic.repro/1",
        environment=dict(
            system=platform.system(), machine=platform.machine(), python=platform.python_version()
        ),
        protocol=protocol().protocol.fingerprint,
        lead=leads,
        errors=errors,
        pair_relative=field_metrics(np.asarray(leads[0]), np.asarray(leads[1]))["relative"],
        scope="coarse homogeneous physical contract; not .10 scientific gate or human validation",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(run(), indent=2) + "\n")
