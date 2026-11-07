"""Measured decoding stages and simulation geometry figures, never extrapolated timings."""

import platform
import resource
import sys
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from soma.core.provenance import manifest
from soma.decoding.config import identity, read_protocol
from soma.decoding.covariance import TrialCovariances
from soma.decoding.csp import TrainingCSP
from soma.decoding.evaluation import evaluate
from soma.decoding.features import build_bank
from soma.decoding.riemannian import TrainingTangentSpace, riemannian_distance, riemannian_mean
from soma.decoding.synthetic import simulate_decoding
from soma.simulations.calibration import atomic_json


def benchmark(
    output: Path, config: Path = Path("configs/decoding.yaml"), seed: int = 42
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    protocol, checksum = read_protocol(config)
    dataset, truth = simulate_decoding(seed=seed)
    rows = []

    def measure(name: str, function: Callable[[], Any]) -> Any:
        wall, cpu = time.perf_counter(), time.process_time()
        tracemalloc.start()
        with threadpool_limits(limits=1):
            result = function()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rows.append(
            {
                "stage": name,
                "wall_seconds": time.perf_counter() - wall,
                "cpu_seconds": time.process_time() - cpu,
                "peak_traced_mib": peak / 2**20,
                "process_high_water_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                / (2**20 if sys.platform == "darwin" else 1024.0),
            }
        )
        return result

    bank = measure("PSD_and_burst_context", lambda: build_bank(dataset))
    cov = measure("OAS_covariances", lambda: TrialCovariances().fit_transform(dataset.X))
    measure("MNE_CSP_fit", lambda: TrainingCSP(4, 0.1).fit(dataset.X, dataset.y))
    measure(
        "Riemannian_100_distances",
        lambda: [riemannian_distance(cov[i], cov[i + 1]) for i in range(100)],
    )
    tangent = measure("training_tangent_fit", lambda: TrainingTangentSpace().fit(cov))
    features = measure("tangent_mapping", lambda: tangent.transform(cov))
    measure("logistic_fit", lambda: LogisticRegression(max_iter=1000).fit(features, dataset.y))
    measure(
        "nested_cross_subject",
        lambda: evaluate(
            bank,
            protocol,
            "cross-subject",
            output / "cross-subject",
            models=("csp_lda", "riemann_mdm", "tangent_lr"),
            plots=False,
        ),
    )
    pd.DataFrame(rows).to_csv(output / "timings.csv", index=False)
    atomic_json(output / "truth.json", truth)
    means = np.stack([cov[dataset.y == c].mean(axis=0) for c in (0, 1)])
    geometric = np.stack([riemannian_mean(cov[dataset.y == c]) for c in (0, 1)])
    np.savez_compressed(
        output / "geometry.npz", covariances=cov, euclidean_means=means, riemannian_means=geometric
    )
    first = cov[:20]
    distances = np.asarray([[riemannian_distance(a, b) for a in first] for b in first])
    euclidean = np.asarray([[np.linalg.norm(a - b) for a in first] for b in first])
    np.savez_compressed(output / "distances.npz", riemannian=distances, euclidean=euclidean)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for ax, values, title in zip(
        axes,
        (distances, euclidean),
        ("Affine-invariant distance (dimensionless)", "Euclidean Frobenius distance (µV²)"),
        strict=True,
    ):
        image = ax.imshow(values, cmap="viridis")
        ax.set(title=title, xlabel="Synthetic trial", ylabel="Synthetic trial")
        fig.colorbar(image, ax=ax)
    fig.savefig(output / "geometry_distances.png", dpi=160)
    plt.close(fig)
    # Recover known source variances for one subject, middle run (unit run scale).
    indices = np.flatnonzero((dataset.metadata.subject == 1) & (dataset.metadata.run == 8))
    empirical = TrialCovariances("empirical", relative_floor=0).fit_transform(dataset.X[indices])
    mixing = np.asarray(truth["subject_mixing"]["1"])
    inverse = np.linalg.inv(mixing)
    recovered = inverse[None] @ empirical @ inverse.T[None] / (truth["scale_v"] * 1e6) ** 2
    recovery: list[dict[str, Any]] = []
    for label in (0, 1):
        expected = np.full(9, 0.4**2 + (truth["noise"] * (1 + 1 / 60)) ** 2)
        expected[:2] += (
            np.asarray(
                [1 + truth["effect"] * (2 * label - 1), 1 - truth["effect"] * (2 * label - 1)]
            )
            - 0.4**2
        )
        observed = np.diag(recovered[dataset.y[indices] == label].mean(axis=0))
        recovery.extend(
            {
                "class": label,
                "source": c,
                "expected_variance": float(expected[c]),
                "recovered_variance": float(observed[c]),
            }
            for c in range(9)
        )
    recovery_table = pd.DataFrame(recovery)
    recovery_table.to_csv(output / "source_covariance_recovery.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for label, ax in enumerate(axes):
        data = recovery_table[recovery_table["class"] == label]
        ax.bar(data.source - 0.15, data.expected_variance, width=0.3, label="known model")
        ax.bar(data.source + 0.15, data.recovered_variance, width=0.3, label="empirical recovery")
        ax.set(
            title=f"Synthetic class {label}; subject 1 run 8",
            xlabel="Known simulated source",
            ylabel="Variance in source amplitude units",
        )
        ax.legend()
    fig.savefig(output / "synthetic_covariance_recovery.png", dpi=160)
    plt.close(fig)
    atomic_json(
        output / "manifest.json",
        manifest(
            {"synthetic_truth": truth},
            {
                "protocol_sha256": checksum,
                "software": identity(),
                "hardware": platform.platform(),
                "fit_threads": 1,
                "units": "volts externally; covariance in µV² internally",
            },
            {"output": str(output.resolve())},
            seed,
        ),
    )
    return {"status": "complete", "output": str(output), "stages": rows, "features": bank.profile}
