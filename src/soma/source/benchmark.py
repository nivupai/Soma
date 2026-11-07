"""Independent small-matrix accuracy table and fresh MNE forward timing."""

import time
from pathlib import Path
from typing import Any

import mne
import numpy as np

from soma.core.provenance import manifest, write_json
from soma.datasets.eegbci import load_recording
from soma.source.forward import build_forward
from soma.source.inverse import Tikhonov
from soma.source.template import Template


def numerical_benchmarks() -> list[dict[str, Any]]:
    rng = np.random.default_rng(20261107)
    matrices = {
        "identity": np.eye(3),
        "diagonal": np.diag([1.0, 2, 3]),
        "overdetermined": rng.normal(size=(8, 3)),
        "underdetermined": rng.normal(size=(3, 8)),
        "rank_deficient": np.diag([1.0, 0.5, 0]),
        "ill_conditioned": np.diag([1.0, 1e-8, 1e-12]),
    }
    results = []
    for name, lead in matrices.items():
        truth = rng.normal(size=(lead.shape[1], 10))
        y = lead @ truth
        for lambda2 in (0.0, 1e-8, 1 / 9, 1e8):
            inverse = Tikhonov(lead, lambda2)
            singular = np.linalg.svd(lead, compute_uv=False)
            results.append(
                {
                    "case": name,
                    "lambda2": lambda2,
                    "rank": int(np.linalg.matrix_rank(lead)),
                    "singular_values": singular.tolist(),
                    "condition": float(singular[0] / singular[-1]) if singular[-1] > 0 else None,
                    **inverse.diagnostics(y, truth),
                }
            )
    return results


def benchmark(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    raw, _ = load_recording(Path("data/raw"), 1, 4)
    start = time.perf_counter()
    cpu_start = time.process_time()
    forward = build_forward(Template(), list(raw.ch_names))  # deliberately no forward cache
    seconds = time.perf_counter() - start
    raw.close()
    result = {
        "fresh_bem_forward_runtime_s": seconds,
        "fresh_bem_forward_cpu_s": time.process_time() - cpu_start,
        "forward_shape": list(forward.matrix.shape),
        "forward_matrix_mib": forward.matrix.nbytes / 1024**2,
        "free_matrix_mib": forward.native_free["sol"]["data"].nbytes / 1024**2,
        "numerical_benchmarks": numerical_benchmarks(),
        "mne_version": mne.__version__,
    }
    import resource
    import sys

    result["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        1024**2 if sys.platform == "darwin" else 1024
    )
    write_json(output / "benchmark.json", result)
    write_json(
        output / "manifest.json",
        manifest(
            forward.diagnostics(),
            {"fresh_forward": True, "numerical_lambda2": [0, 1e-8, 1 / 9, 1e8]},
            {"output": str(output)},
            seed=20261107,
        ),
    )
    return result
