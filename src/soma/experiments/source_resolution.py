"""Bounded cortical PSFs, CTFs and mesh geodesics over a fixed lambda grid."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.source.inverse import CorticalInverse
from soma.source.resolution import Resolution, cortical_distances, spatial_metrics
from soma.source.workflow import RunReport, sealed_config, study_forward, synthetic_covariance


def analyze_resolution(config_path: Path, output: Path) -> dict[str, Any]:
    config = sealed_config(config_path)
    forward = study_forward()
    report = RunReport(output, config, forward, 20261107)
    noise, covariance = synthetic_covariance(
        forward, seed=20261107, std=config["noise_std_v"], correlation=config["noise_correlation"]
    )
    indices = np.linspace(
        0, forward.matrix.shape[1] - 1, config["selected_columns"], dtype=int
    ).tolist()
    geodesic = cortical_distances(forward.native_free["src"], indices)
    rows = []
    arrays: dict[str, Any] = {"indices": indices, "geodesic_m": geodesic}
    for iteration, lambda2 in enumerate(config["lambda2_grid"]):
        inv = CorticalInverse(forward, covariance, lambda2=lambda2, depth=config["depth"])
        resolution = Resolution(inv.kernel, forward.matrix)
        psf, ctf = resolution.psf(indices), resolution.ctf(indices)
        arrays[f"psf_{iteration}"] = psf
        arrays[f"ctf_{iteration}"] = ctf
        arrays[f"diagonal_{iteration}"] = resolution.diagonal
        for column, index in enumerate(indices):
            rows.append(
                {
                    "lambda2": lambda2,
                    **spatial_metrics(
                        psf[:, column], index, forward.coordinates.points.xyz, geodesic[column]
                    ),
                }
            )
    np.savez_compressed(output / "selected-resolution.npz", **arrays)
    pd.DataFrame(rows).to_csv(output / "resolution.csv", index=False)
    from soma.visualization.source import resolution_figure

    resolution_figure(output, forward, arrays["psf_2"][:, 0], indices[0])
    return report.finish(
        {
            "status": "complete",
            "selected_sources": indices,
            "columns_per_lambda": len(indices),
            "lambda2_grid": config["lambda2_grid"],
            "noise": noise.diagnostics(),
            "distance": (
                "Euclidean head metres and within-hemisphere white-mesh edge shortest paths"
            ),
            "full_dense_resolution_allocated": False,
            "mean_peak_euclidean_m": float(np.mean([r["peak_euclidean_m"] for r in rows])),
        }
    )
