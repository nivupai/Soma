"""Small numerical prior gate; full M31 experiment is deliberately outside CI."""

import argparse
import json
import platform
from pathlib import Path

import numpy as np

from soma.source.noise import NoiseModel, average_projector
from soma.source.prior_calibration import PriorInverse, SourcePrior


def run():
    p = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0], [-0.02, 0.0, 0.0]])
    proj = average_projector(5)
    g = proj @ np.sin(np.arange(45).reshape(5, 9) + 0.3) * 100
    noise = NoiseModel((5e-8) ** 2 * proj, tuple("abcde"), proj)
    data = []
    for kind in ["unweighted", "cell_volume", "total_variance"]:
        prior = SourcePrior.create(p, kind)
        for method in ["Tikhonov", "MNE", "dSPM"]:
            inv = PriorInverse(g, p, prior, noise, method)
            data.append(
                dict(
                    prior=kind,
                    method=method,
                    kernel=inv.kernel(0.1).tolist(),
                    diagnostics=inv.diagnostics(0.1),
                )
            )
    return dict(
        schema="soma.inverse-prior.repro/1",
        design_sha256="abb24125e39c51438197e4e7301b3f7079bdb4820bdd6257069348594d6468bc",
        environment=dict(
            system=platform.system(), machine=platform.machine(), python=platform.python_version()
        ),
        synthetic_only=True,
        data=data,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.write_text(json.dumps(run(), indent=2, allow_nan=False) + "\n")
