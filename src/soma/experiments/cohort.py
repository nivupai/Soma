"""Sequential, failure-aware repeated-measures experiments using the existing EEG engine."""

import json
import platform
import resource
import shutil
import time
import tracemalloc
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.core.provenance import manifest, output_directory, sha256, write_json
from soma.datasets.eegbci import load_recording, recording_path
from soma.datasets.registry import REGISTRY
from soma.eeg.motor_imagery import analyze_run
from soma.experiments.cache import (
    canonical_id,
    publish_cache,
    software_identity,
    staging_directory,
    validate_cache,
)
from soma.experiments.config import CohortConfig, scientific_dict
from soma.signal.bursts import analyze_bursts
from soma.signal.cohort_synthetic import cohort_recording
from soma.statistics.hierarchical import (
    burst_contrasts,
    lateralization_contrasts,
    population_summary,
    subject_contrasts,
)

DEFAULT_COHORT = CohortConfig()
TABLES = (
    "events",
    "trials",
    "features",
    "summary",
    "burst_features",
    "burst_events",
    "burst_dynamics",
)
FEATURE_COLUMNS = [
    "subject",
    "run",
    "recording",
    "trial_index",
    "condition",
    "kind",
    "channel",
    "band",
    "absolute_power_v2",
    "reference_power_v2",
    "erd_percent",
    "log_power_ratio",
    "power_difference_v2",
    "baseline",
]


def _compute(
    raw: Any, source: dict[str, Any], subject: int, run: int, cfg: CohortConfig, staging: Path
) -> None:
    started = time.perf_counter()
    own_trace = not tracemalloc.is_tracing()
    if own_trace:
        tracemalloc.start()
    try:
        result = analyze_run(
            raw, subject, run, str(source["file_identifier"]), replace(cfg.motor, plots=False)
        )
        burst_started = time.perf_counter()
        bursts = analyze_bursts(
            result["processed"],
            result["trials"],
            subject,
            run,
            str(source["file_identifier"]),
            cfg.bursts,
        )
        burst_seconds = time.perf_counter() - burst_started
        peak = tracemalloc.get_traced_memory()[1] / 2**20 if own_trace else None
    finally:
        if own_trace:
            tracemalloc.stop()
    for name in ("events", "trials", "features", "summary"):
        result[name].to_csv(staging / f"{name}.csv", index=False)
    bursts["features"].to_csv(staging / "burst_features.csv", index=False)
    bursts["events"].to_csv(staging / "burst_events.csv", index=False)
    bursts["dynamics"].to_csv(staging / "burst_dynamics.csv", index=False)
    np.save(staging / "processed.npy", result["processed"].data, allow_pickle=False)
    np.savez(
        staging / "tfr_mean.npz",
        mean_over_valid_time=result["tfr"].reference_mean(),
        trial_indices=np.asarray([t.event.index for t in result["context"].trials]),
        conditions=np.asarray([t.event.label for t in result["context"].trials]),
        times=result["tfr"].times,
        frequencies=result["tfr"].frequencies,
        valid=result["tfr"].valid,
        channels=np.asarray(result["tfr"].channels),
    )
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write_json(
        staging / "metadata.json",
        {
            "source": source,
            "geometry": result["geometry"],
            "preprocessing": result["preprocessing"],
            "quality": result["quality"],
            "burst_calibration": bursts["calibration"],
            "burst_config": bursts["config"],
            "profile": {
                **result["profile"],
                "burst_seconds": burst_seconds,
                "run_compute_seconds": time.perf_counter() - started,
                "peak_traced_mib": peak,
                "process_high_water_rss_mib": rss
                / (2**20 if platform.system() == "Darwin" else 1024),
            },
            "fs_hz": result["processed"].fs,
            "channels": list(result["processed"].channels),
        },
    )


def _aggregate_bursts(table: pd.DataFrame) -> pd.DataFrame:
    if table.empty:
        return pd.DataFrame(
            columns=[
                "subject",
                "run",
                "channel",
                "band",
                "strategy",
                "condition",
                "valid_observation_s",
                "occupancy",
                "rate_hz",
                "mean_complete_duration_s",
                "mean_burst_amplitude_v",
            ]
        )
    keys = ["subject", "run", "channel", "band", "strategy", "condition"]
    sums = (
        table.groupby(keys)
        .agg(
            valid_observation_s=("valid_observation_s", "sum"),
            burst_observation_s=("burst_observation_s", "sum"),
            onset_count=("onset_count", "sum"),
            complete_count=("complete_count", "sum"),
            complete_duration_sum_s=("complete_duration_sum_s", "sum"),
            amplitude_sum_v=("amplitude_sum_v", "sum"),
            burst_samples=("burst_samples", "sum"),
            n_windows=("trial_index", "size"),
        )
        .reset_index()
    )
    sums["occupancy"] = sums.burst_observation_s / sums.valid_observation_s.where(
        sums.valid_observation_s > 0
    )
    sums["rate_hz"] = sums.onset_count / sums.valid_observation_s.where(
        sums.valid_observation_s > 0
    )
    sums["mean_complete_duration_s"] = sums.complete_duration_sum_s / sums.complete_count.where(
        sums.complete_count > 0
    )
    sums["mean_burst_amplitude_v"] = sums.amplitude_sum_v / sums.burst_samples.where(
        sums.burst_samples > 0
    )
    return sums


def burst_power_associations(
    features: pd.DataFrame, burst_summary: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match same run/channel/band condition contrasts; correlations use subject means."""
    if features.empty or burst_summary.empty:
        return pd.DataFrame(), pd.DataFrame()
    power = (
        features[features.kind == "imagery"]
        .groupby(["subject", "run", "channel", "band", "condition"])
        .absolute_power_v2.mean()
        .rename("power_v2")
    )
    merged = burst_summary.merge(
        power.reset_index(), on=["subject", "run", "channel", "band", "condition"], how="inner"
    )
    keys = ["subject", "run", "channel", "band", "strategy"]
    outcomes = [
        "power_v2",
        "occupancy",
        "rate_hz",
        "mean_complete_duration_s",
        "mean_burst_amplitude_v",
    ]
    rows = []
    for key, group in merged.groupby(keys):
        indexed = group.set_index("condition")
        if not {"left hand imagery", "right hand imagery"} <= set(indexed.index):
            continue
        row = dict(zip(keys, key, strict=True))
        for outcome in outcomes:
            paired_values = (
                indexed[outcome]
                .reindex(["left hand imagery", "right hand imagery"])
                .to_numpy(dtype=float)
            )
            row[outcome + "_left_minus_right"] = float(paired_values[0] - paired_values[1])
        rows.append(row)
    contrasts = pd.DataFrame(rows)
    if contrasts.empty:
        return contrasts, pd.DataFrame()
    subject = (
        contrasts.groupby(["subject", "channel", "band", "strategy"])
        .mean(numeric_only=True)
        .reset_index()
    )
    associations = []
    for key, group in subject.groupby(["channel", "band", "strategy"]):
        for metric in outcomes[1:]:
            pair = group[["power_v2_left_minus_right", metric + "_left_minus_right"]].dropna()
            corr = (
                float(pair.corr().to_numpy(dtype=float)[0, 1])
                if len(pair) >= 3 and (pair.std() > 0).all()
                else np.nan
            )
            associations.append(
                dict(zip(["channel", "band", "strategy"], key, strict=True))
                | {
                    "metric": metric,
                    "n_subjects": len(pair),
                    "pearson_r": corr,
                    "interpretation": "descriptive subject-level association, not causal",
                }
            )
    return contrasts, pd.DataFrame(associations)


def run_cohort(
    root: Path,
    output: Path,
    cfg: CohortConfig = DEFAULT_COHORT,
    cache_root: Path = Path("data/derived/cohort-cache"),
) -> dict[str, Any]:
    """Load only selected cached EDFs; process one run at a time; record all failures."""
    output_directory(output)
    software = software_identity()
    experiment_id = canonical_id({"science": scientific_dict(cfg), "software": software})
    rows: list[dict[str, Any]] = []
    frames: dict[str, list[pd.DataFrame]] = {name: [] for name in TABLES}
    reference_channels: set[str] | None = None
    reference_fs: float | None = None
    for subject in sorted(cfg.subjects):
        for run in sorted(cfg.runs):
            started = time.perf_counter()
            raw = None
            staging = None
            row: dict[str, Any] = {
                "subject": subject,
                "run": run,
                "status": "failed",
                "cache_hit": False,
            }
            try:
                if cfg.synthetic_seed is None:
                    path = recording_path(root, subject, run)
                    if not path.is_file():
                        raise FileNotFoundError(f"Missing explicitly selected EDF: {path}")
                    fingerprint = sha256(path)
                    source = {
                        "dataset": cfg.dataset,
                        "file_identifier": path.name,
                        "subject": subject,
                        "run": run,
                        "sha256": fingerprint,
                        "dataset_source": REGISTRY[cfg.dataset].source,
                    }
                else:
                    source = {
                        "dataset": "synthetic-cohort",
                        "file_identifier": f"synthetic-S{subject:03d}R{run:02d}",
                        "subject": subject,
                        "run": run,
                        "seed": cfg.synthetic_seed,
                        "missing": cfg.synthetic_missing,
                        "artifacts": cfg.synthetic_artifacts,
                    }
                    fingerprint = canonical_id(source)
                parameters = {
                    "source": json.loads(json.dumps(source)),
                    "fingerprint": fingerprint,
                    "motor": asdict(replace(cfg.motor, plots=False)),
                    "bursts": asdict(cfg.bursts),
                    "software": software,
                }
                row["input_fingerprint"] = fingerprint
                key = canonical_id(parameters)
                cache = cache_root / key
                hit = validate_cache(cache, key)
                if not hit:
                    if cfg.synthetic_seed is None:
                        raw, loaded = load_recording(root, subject, run)
                        source.update(loaded)
                    else:
                        raw, truth = cohort_recording(
                            subject,
                            run,
                            cfg.synthetic_seed,
                            missing=cfg.synthetic_missing,
                            artifacts=cfg.synthetic_artifacts,
                        )
                        source["truth"] = truth
                    staging = staging_directory(cache_root)
                    _compute(raw, source, subject, run, cfg, staging)
                    publish_cache(staging, cache, key, parameters)
                    staging = None
                metadata = json.loads((cache / "metadata.json").read_text())
                fs = float(metadata["fs_hz"])
                channels = set(metadata["preprocessing"]["channels"])
                if reference_channels is not None and channels != reference_channels:
                    raise ValueError("Incompatible EEG channel sets across cohort recordings")
                if reference_fs is not None and fs != reference_fs:
                    raise ValueError(f"Inconsistent sampling frequency: {fs} vs {reference_fs} Hz")
                reference_channels, reference_fs = channels, fs
                folder = output / f"subject-{subject:03d}" / f"run-{run:02d}"
                folder.mkdir(parents=True)
                tables = {}
                for name in TABLES:
                    tables[name] = pd.read_csv(cache / f"{name}.csv")
                # Commit a run to the cohort only after all artifacts validate/read successfully.
                for name in tables:
                    shutil.copy2(cache / f"{name}.csv", folder / f"{name}.csv")
                for name in ("metadata.json", "tfr_mean.npz", "cache.json"):
                    shutil.copy2(cache / name, folder / name)
                for name, table in tables.items():
                    frames[name].append(table)
                row.update(
                    status="complete",
                    cache_hit=hit,
                    cache_key=key,
                    input_fingerprint=fingerprint,
                    fs_hz=fs,
                    n_eeg_channels=len(channels),
                    source=metadata["source"],
                    counts=metadata["quality"]["trial_counts"],
                    profile=metadata["profile"],
                )
            except Exception as exc:
                row.update(
                    error_type=type(exc).__name__,
                    error=str(exc),
                    category="missing"
                    if isinstance(exc, FileNotFoundError)
                    else "validation_or_processing",
                )
            finally:
                if raw is not None:
                    raw.close()
                if staging is not None:
                    shutil.rmtree(staging, ignore_errors=True)
            row["elapsed_seconds"] = time.perf_counter() - started
            rows.append(row)
    experiment_id = canonical_id(
        {
            "science": scientific_dict(cfg),
            "software": software,
            "inputs": [
                {
                    "subject": row["subject"],
                    "run": row["run"],
                    "fingerprint": row.get("input_fingerprint", "unavailable"),
                }
                for row in rows
            ],
        }
    )
    combined: dict[str, pd.DataFrame] = {}
    for name, values in frames.items():
        nonempty = [table for table in values if not table.empty]
        combined[name] = (
            pd.concat(nonempty, ignore_index=True)
            if nonempty
            else values[0].iloc[:0].copy()
            if values
            else pd.DataFrame()
        )
    if combined["features"].empty:
        combined["features"] = pd.DataFrame(columns=FEATURE_COLUMNS)
    for name, table in combined.items():
        table.to_csv(output / f"{name}.csv", index=False)
    coverage = pd.DataFrame(
        [{k: v for k, v in row.items() if k not in ("source", "profile", "counts")} for row in rows]
    )
    coverage.to_csv(output / "coverage.csv", index=False)
    write_json(
        output / "coverage.json",
        {
            "requested_subjects": list(cfg.subjects),
            "requested_runs": list(cfg.runs),
            "records": rows,
            "complete": sum(r["status"] == "complete" for r in rows),
            "failed": sum(r["status"] != "complete" for r in rows),
        },
    )
    runs, subjects = subject_contrasts(combined["features"])
    if not subjects.empty:
        keys = subjects[["channel", "band", "outcome", "units"]].drop_duplicates()
        expected = pd.DataFrame({"subject": list(cfg.subjects)}).merge(keys, how="cross")
        subjects = expected.merge(
            subjects, on=["subject", "channel", "band", "outcome", "units"], how="left"
        )
        subjects["n_runs"] = subjects.n_runs.fillna(0).astype(int)
    population, exclusions = population_summary(subjects, cfg.statistics)
    laterality = lateralization_contrasts(combined["features"])
    if not laterality.empty:
        lateral_subject = (
            laterality.groupby(["subject", "band", "metric", "units"]).value.mean().reset_index()
        )
        lateral_subject = lateral_subject.rename(columns={"value": "contrast", "metric": "outcome"})
        lateral_subject["channel"] = "C3_C4_sensor_convention"
        lateral_population, _ = population_summary(
            lateral_subject, replace(cfg.statistics, sign_flip=False)
        )
    else:
        lateral_subject, lateral_population = pd.DataFrame(), pd.DataFrame()
    burst_summary = _aggregate_bursts(combined["burst_features"])
    burst_runs, burst_subjects = burst_contrasts(burst_summary)
    burst_population, _ = population_summary(
        burst_subjects, replace(cfg.statistics, sign_flip=False)
    )
    associations, correlations = burst_power_associations(combined["features"], burst_summary)
    for name, table in {
        "run_contrasts": runs,
        "subject_contrasts": subjects,
        "population": population,
        "leave_one_subject_out": exclusions,
        "lateralization": laterality,
        "lateralization_subject": lateral_subject,
        "lateralization_population": lateral_population,
        "burst_condition_summary": burst_summary,
        "burst_power_contrasts": associations,
        "burst_power_associations": correlations,
        "burst_run_contrasts": burst_runs,
        "burst_subject_contrasts": burst_subjects,
        "burst_population": burst_population,
    }.items():
        table.to_csv(output / f"{name}.csv", index=False)
    retention = []
    for row in rows:
        if row["status"] == "complete":
            for stage, counts in row["counts"].items():
                retention.append(
                    {"subject": row["subject"], "run": row["run"], "stage": stage, **counts}
                )
    pd.DataFrame(
        retention, columns=["subject", "run", "stage", "proposed", "accepted", "rejected"]
    ).to_csv(output / "retention.csv", index=False)
    profile = [
        {
            "subject": r["subject"],
            "run": r["run"],
            "cache_hit": r["cache_hit"],
            "elapsed_seconds": r["elapsed_seconds"],
            **(r.get("profile") or {}),
        }
        for r in rows
    ]
    pd.DataFrame(profile).to_csv(output / "profiling.csv", index=False)
    result = manifest(
        {
            "dataset": cfg.dataset if cfg.synthetic_seed is None else "synthetic-cohort",
            "recordings": [
                r.get(
                    "source", {"subject": r["subject"], "run": r["run"], "failure": r.get("error")}
                )
                for r in rows
            ],
        },
        {
            "experiment_id": experiment_id,
            "cohort": scientific_dict(cfg),
            "cache_software": software,
            "statistical_unit": (
                "subject; pair within run, equal run average, then equal subject mean"
            ),
            "ci": "pointwise percentile subject bootstrap; descriptive, not simultaneous",
            "sign_flip_assumptions": (
                "independent symmetric subject contrast null; optional Holm family"
                " over all tested outcomes"
            ),
        },
        {
            "data_root": str(root.resolve()),
            "output": str(output.resolve()),
            "cache_root": str(cache_root.resolve()),
        },
        cfg.synthetic_seed,
    )
    write_json(output / "manifest.json", result)
    if cfg.plots and not subjects.empty:
        from soma.visualization.cohort import plot_cohort

        plot_cohort(output)
    complete = sum(r["status"] == "complete" for r in rows)
    report = [
        "# Cohort replication",
        "",
        f"Experiment {experiment_id}.",
        f"Records complete: {complete}/{len(rows)}; subjects {cfg.subjects}; runs {cfg.runs}.",
        "",
        "Recordings were processed separately. coverage.json lists failures and anomalies.",
        "retention.csv and trials.csv preserve stage counts and rejection reasons.",
        "No external subject exclusion list was applied.",
        "",
        "Primary: C3/C4 mu left-minus-right log absolute power, equal paired-run weight",
        "within subject, then equal subject weight. Beta, Cz and bursts are exploratory.",
        "Nominal bootstrap CIs resample subjects; they are pointwise, not simultaneous.",
        "Percentile intervals can under-cover at five subjects; inspect the coverage laboratory.",
        "",
        "```csv",
        population.to_csv(index=False),
        "```",
        "",
        "Burst amplitude is Hilbert amplitude in volts. Thresholds use accepted rest.",
        "Rates use actual valid exposure; complete durations exclude censored fragments.",
        "Zero occupancy can mean no bursts; missing calibration/exposure is unavailable.",
        "Burst-power correlations use subject contrasts and do not establish causality.",
        "",
        "Template coordinates are not measured digitization. Small samples, QC, references,",
        "noncausal smoothing, missing records and threshold choices limit generalization.",
        "See docs/PROTOCOL.md and docs/METHODS.md for definitions and assumptions.",
    ]
    (output / "report.md").write_text("\n".join(report) + "\n")
    return {
        "experiment_id": experiment_id,
        "complete": complete,
        "failed": len(rows) - complete,
        "output": str(output),
        "status": "complete" if complete == len(rows) else ("partial" if complete else "failed"),
    }
