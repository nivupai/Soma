"""Repeatable cost and uncertainty experiments; no absolute-time pass/fail gates."""

import os
import platform
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from soma.core.provenance import manifest, output_directory, write_json
from soma.experiments.cohort import run_cohort
from soma.experiments.config import CohortConfig, scientific_dict
from soma.experiments.sensitivity import run_sensitivity
from soma.statistics.hierarchical import ResamplingConfig, subject_bootstrap


def benchmark(output: Path, seed: int = 42) -> dict[str, Any]:
    output_directory(output)
    cfg = CohortConfig(subjects=(1, 2), runs=(4, 8), synthetic_seed=seed, plots=False)
    cache = output / "cache"
    rows = []
    for label in ("cold", "warm"):
        start = time.perf_counter()
        result = run_cohort(Path("data/raw"), output / label, cfg, cache)
        profile = pd.read_csv(output / label / "profiling.csv")
        rows.append(
            {
                "phase": label,
                "wall_seconds": time.perf_counter() - start,
                "records_complete": result["complete"],
                "cache_hits": int(profile.cache_hit.sum()),
                "cache_misses": int((~profile.cache_hit).sum()),
                "mean_tfr_compute_seconds_on_original_misses": float(profile.tfr_seconds.mean()),
                "maximum_peak_traced_mib_on_original_misses": float(profile.peak_traced_mib.max()),
            }
        )
    start = time.perf_counter()
    values: dict[str, Any] = {
        "cohort": scientific_dict(replace(cfg, subjects=(1,), runs=(4,))),
        "variants": ["primary", "reference_none", "qc_strict"],
    }
    values["cohort"]["plots"] = False
    run_sensitivity(Path("data/raw"), output / "sweep", values, cache)
    rows.append({"phase": "three_variant_sweep", "wall_seconds": time.perf_counter() - start})
    pd.DataFrame(rows).to_csv(output / "benchmark.csv", index=False)
    context = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "memory_note": (
            "tracemalloc peak per run; native allocations may be incomplete; "
            "RSS is process high-water, not per-stage delta"
        ),
    }
    result = manifest(
        {"dataset": "synthetic-cohort"}, context, {"output": str(output.resolve())}, seed
    )
    write_json(output / "manifest.json", result)
    return {"output": str(output), "measurements": rows, "context": context}


def uncertainty_validation(
    output: Path,
    seed: int = 42,
    repetitions: int = 200,
    n_subjects: int = 40,
    n_bootstrap: int = 1000,
) -> dict[str, Any]:
    if repetitions < 20 or n_subjects < 5:
        raise ValueError("Coverage laboratory needs >=20 replications and >=5 subjects")
    output_directory(output)
    rng = np.random.default_rng(seed)
    rows = []
    truth = 0.5
    for repetition in range(repetitions):
        values = rng.normal(truth, 1, n_subjects)
        cfg = ResamplingConfig(seed=seed + repetition + 1, n_bootstrap=n_bootstrap)
        summary = subject_bootstrap(values, cfg)
        low, high = summary["ci_low"], summary["ci_high"]
        rows.append(
            {
                "repetition": repetition,
                **summary,
                "true_mean": truth,
                "covered": bool(low is not None and high is not None and low <= truth <= high),
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(output / "coverage.csv", index=False)
    count = int(table.covered.sum())
    interval = binomtest(count, repetitions).proportion_ci(confidence_level=0.95)
    result = {
        "repetitions": repetitions,
        "n_subjects": n_subjects,
        "nominal_confidence": 0.95,
        "observed_coverage": count / repetitions,
        "coverage_binomial_ci": [float(interval.low), float(interval.high)],
        "interpretation": (
            "Repeated independent normal-subject simulations; diagnostic of "
            "percentile coverage, not a single seeded regression or universal "
            "guarantee"
        ),
    }
    write_json(output / "results.json", result)
    write_json(
        output / "manifest.json",
        manifest(
            {"dataset": "normal-subject-contrast-simulation"},
            {**result, "n_bootstrap": n_bootstrap, "true_mean": truth, "subject_sd": 1},
            {"output": str(output.resolve())},
            seed,
        ),
    )
    return result
