"""Resumable Monte Carlo grid with deterministic per-replication streams and bounded tasks."""

import json
import os
import platform
import resource
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from soma.core.provenance import manifest, sha256
from soma.experiments.cache import canonical_id, software_identity
from soma.simulations.hierarchical import SCENARIOS, SimulationConfig, simulate
from soma.statistics.inference import METHODS, InferenceConfig, infer_mean


@dataclass(frozen=True)
class CalibrationConfig:
    scenarios: tuple[str, ...] = SCENARIOS
    subject_counts: tuple[int, ...] = (5, 10, 20, 30, 50, 100)
    methods: tuple[str, ...] = METHODS
    repetitions: int = 2000
    n_resamples: int = 1999
    seed: int = 20261106
    confidence: float = 0.95
    chunk_size: int = 25

    def __post_init__(self) -> None:
        if (
            not self.scenarios
            or len(set(self.scenarios)) != len(self.scenarios)
            or set(self.scenarios) - set(SCENARIOS)
            or not self.subject_counts
            or len(set(self.subject_counts)) != len(self.subject_counts)
            or min(self.subject_counts) < 2
            or not self.methods
            or len(set(self.methods)) != len(self.methods)
            or set(self.methods) - set(METHODS)
            or self.repetitions < 20
            or self.chunk_size < 1
        ):
            raise ValueError(
                "Invalid calibration scenarios, subject counts, methods or replication/chunk counts"
            )
        InferenceConfig(confidence=self.confidence, n_resamples=self.n_resamples, seed=self.seed)


DEFAULT_CALIBRATION = CalibrationConfig()


def atomic_json(path: Path, value: Any) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def calibration_identity(cfg: CalibrationConfig) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    relevant = [
        "statistics/inference.py",
        "simulations/hierarchical.py",
        "simulations/calibration.py",
    ]
    software = software_identity()
    software.pop("source_digest")
    return {
        "config": asdict(cfg),
        "software": software,
        "code": {name: sha256(root / name) for name in relevant},
    }


def _chunk(task: tuple[CalibrationConfig, str, int, int, int]) -> list[dict[str, Any]]:
    cfg, scenario, n, start, stop = task
    rows = []
    for replication in range(start, stop):
        stream = np.random.SeedSequence([cfg.seed, SCENARIOS.index(scenario), n, replication])
        data_seed, inference_seed = [int(x.generate_state(1)[0]) for x in stream.spawn(2)]
        simulated = simulate(SimulationConfig(scenario=scenario, n_subjects=n), data_seed)
        effects = simulated["subject_effects"]
        inference = InferenceConfig(
            confidence=cfg.confidence, n_resamples=cfg.n_resamples, seed=inference_seed
        )
        for result in infer_mean(effects, cfg.methods, inference):
            low, high = result["ci_low"], result["ci_high"]
            estimate = result["estimate"]
            target = simulated["target_mean"]
            truth = simulated["structural_truth"]
            rows.append(
                {
                    "scenario": scenario,
                    "n_requested": n,
                    "replication": replication,
                    "method": result["method"],
                    "n_effective": result["n_subjects"],
                    "estimate": estimate,
                    "target_mean": target,
                    "structural_truth": truth,
                    "status": result["status"],
                    "ci_low": low,
                    "ci_high": high,
                    "width": high - low if result["status"] == "ok" else None,
                    "covered_target": bool(low <= target <= high)
                    if result["status"] == "ok"
                    else False,
                    "covered_structural": bool(low <= truth <= high)
                    if result["status"] == "ok"
                    else False,
                    "invalid_pivot_fraction": result["invalid_pivot_fraction"],
                    "warning_count": len(result["warnings"]),
                }
            )
    return rows


def _publish_chunk(
    task: tuple[CalibrationConfig, str, int, int, int], rows: list[dict[str, Any]], folder: Path
) -> None:
    _, scenario, n, start, stop = task
    name = f"{scenario}-n{n:03d}-{start:06d}-{stop:06d}"
    path = folder / (name + ".csv")
    temporary = folder / (name + ".tmp")
    pd.DataFrame(rows).to_csv(temporary, index=False)
    temporary.replace(path)
    atomic_json(folder / (name + ".json"), {"sha256": sha256(path), "rows": len(rows)})


def _chunk_valid(task: tuple[CalibrationConfig, str, int, int, int], folder: Path) -> bool:
    _, scenario, n, start, stop = task
    name = f"{scenario}-n{n:03d}-{start:06d}-{stop:06d}"
    path = folder / (name + ".csv")
    receipt = folder / (name + ".json")
    if not path.exists() or not receipt.exists():
        return False
    info = json.loads(receipt.read_text())
    if sha256(path) != info["sha256"]:
        raise ValueError(f"Calibration checkpoint checksum mismatch: {path}")
    return True


def _summarize(folder: Path, cfg: CalibrationConfig) -> pd.DataFrame:
    output = []
    # One scenario/sample-size cell at a time bounds aggregation memory.
    for scenario in cfg.scenarios:
        for n in cfg.subject_counts:
            files = sorted(folder.glob(f"{scenario}-n{n:03d}-*.csv"))
            table = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
            for method, group in table.groupby("method"):
                if group.replication.nunique() != cfg.repetitions:
                    raise ValueError("Incomplete or duplicated Monte Carlo replications")
                successes = group.status == "ok"
                coverage = float(group.covered_target.mean())
                ci = binomtest(int(group.covered_target.sum()), len(group)).proportion_ci()
                estimate = group.estimate.to_numpy(float)
                target = group.target_mean.to_numpy(float)
                output.append(
                    {
                        "scenario": scenario,
                        "n_requested": n,
                        "method": method,
                        "replications": len(group),
                        "n_resamples": cfg.n_resamples,
                        "mean_n_effective": float(group.n_effective.mean()),
                        "target_mean": float(target[0]),
                        "structural_truth": float(group.structural_truth.iloc[0]),
                        "bias": float(np.nanmean(estimate - target)),
                        "variance": float(np.nanvar(estimate, ddof=1)),
                        "rmse": float(np.sqrt(np.nanmean((estimate - target) ** 2))),
                        "structural_bias": float(
                            np.nanmean(estimate - group.structural_truth.to_numpy(float))
                        ),
                        "coverage": coverage,
                        "coverage_conditional_success": float(
                            group.loc[successes, "covered_target"].mean()
                        )
                        if successes.any()
                        else np.nan,
                        "structural_coverage": float(group.covered_structural.mean()),
                        "coverage_mcse": float(np.sqrt(coverage * (1 - coverage) / len(group))),
                        "coverage_mc_ci_low": float(ci.low),
                        "coverage_mc_ci_high": float(ci.high),
                        "nominal_confidence": cfg.confidence,
                        "mean_width": float(group.width.mean()),
                        "failure_rate": float(1 - successes.mean()),
                        "warning_rate": float((group.warning_count > 0).mean()),
                    }
                )
    return pd.DataFrame(output)


def calibrate(
    output: Path,
    cfg: CalibrationConfig = DEFAULT_CALIBRATION,
    *,
    workers: int = 1,
    resume: bool = False,
    plots: bool = True,
) -> dict[str, Any]:
    if not isinstance(workers, int) or not 1 <= workers <= min(8, os.cpu_count() or 1):
        raise ValueError("Use 1–8 bounded workers within the available logical CPU count")
    identity = calibration_identity(cfg)
    experiment_id = canonical_id(identity)
    if output.exists():
        if not resume:
            raise FileExistsError(output)
        if json.loads((output / "identity.json").read_text()) != json.loads(json.dumps(identity)):
            raise ValueError("Calibration resume configuration/code/environment mismatch")
    else:
        output.mkdir(parents=True)
        atomic_json(output / "identity.json", identity)
    chunks = output / "chunks"
    chunks.mkdir(exist_ok=True)
    tasks = [
        (cfg, s, n, a, min(a + cfg.chunk_size, cfg.repetitions))
        for s in cfg.scenarios
        for n in cfg.subject_counts
        for a in range(0, cfg.repetitions, cfg.chunk_size)
    ]
    pending = [task for task in tasks if not _chunk_valid(task, chunks)]
    started = time.perf_counter()
    if workers == 1:
        for task in pending:
            _publish_chunk(task, _chunk(task), chunks)
    else:
        # At most workers futures in flight; scheduling cannot change per-replication streams.
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for start in range(0, len(pending), workers):
                block = pending[start : start + workers]
                futures = [pool.submit(_chunk, task) for task in block]
                for task, future in zip(block, futures, strict=True):
                    _publish_chunk(task, future.result(), chunks)
    generations = output / "generations"
    generations.mkdir(exist_ok=True)
    generation = generations / f"{len(list(generations.iterdir())) + 1:04d}"
    generation.mkdir()
    summary = _summarize(chunks, cfg)
    summary.to_csv(generation / "calibration.csv", index=False)
    elapsed = time.perf_counter() - started
    profile = {
        "wall_seconds": elapsed,
        "workers": workers,
        "chunks_requested": len(tasks),
        "chunks_computed": len(pending),
        "chunks_reused": len(tasks) - len(pending),
        "process_high_water_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (2**20 if platform.system() == "Darwin" else 1024),
        "child_high_water_rss_mib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        / (2**20 if platform.system() == "Darwin" else 1024),
        "hardware": platform.platform(),
        "logical_cpus": os.cpu_count(),
    }
    atomic_json(generation / "profiling.json", profile)
    atomic_json(
        generation / "manifest.json",
        manifest(
            {"dataset": "hierarchical-statistical-simulation"},
            {
                "experiment_id": experiment_id,
                **identity,
                "coverage_denominator": (
                    "all independent replications; failed intervals count noncoverage"
                ),
                "seed_scheme": (
                    "SeedSequence(global, scenario_index, N, replication); "
                    "child streams for data/inference"
                ),
            },
            {"output": str(output.resolve())},
            cfg.seed,
        ),
    )
    if plots:
        from soma.visualization.calibration import plot_calibration

        plot_calibration(generation)
    report = [
        "# Statistical calibration",
        "",
        f"Experiment {experiment_id}.",
        f"{len(summary)} scenario/N/method cells; {cfg.repetitions} independent datasets per cell.",
        f"{cfg.n_resamples} bootstrap draws per dataset.",
        "",
        "Coverage uncertainty is Monte Carlo binomial uncertainty, not EEG-effect uncertainty.",
        "Failure rates and conditional-success coverage are separate; no method is replaced.",
        "MNAR/preprocessing targets differ explicitly from structural truth.",
        "No universal interval-method winner is asserted.",
    ]
    (generation / "report.md").write_text("\n".join(report) + "\n")
    atomic_json(
        output / "current.json",
        {
            "generation": str(generation.relative_to(output)),
            "experiment_id": experiment_id,
            "completed_at_utc": datetime.now(UTC).isoformat(),
        },
    )
    return {
        "experiment_id": experiment_id,
        "output": str(output),
        "generation": str(generation),
        "status": "complete",
        "cells": len(summary),
        **profile,
    }
