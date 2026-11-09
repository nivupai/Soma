"""Prespecified, resumable large-cohort replication with thin per-run checkpoints."""

import hashlib
import json
import shutil
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.core.provenance import manifest, sha256
from soma.experiments.cache import canonical_id, software_identity
from soma.experiments.config import CohortConfig, config_from_dict, read_config, scientific_dict
from soma.experiments.records import cached_record, input_identity
from soma.experiments.sensitivity import sensitivity_design
from soma.resources import protocol_document_sha256
from soma.simulations.calibration import atomic_json
from soma.statistics.hierarchical import holm, sign_flip_pvalue, subject_contrasts
from soma.statistics.inference import InferenceConfig, infer_mean
from soma.statistics.robustness import (
    KEYS,
    current_generation,
    influence_tables,
    weighting_summaries,
)

OUTCOMES = {
    "absolute_power_v2": "V^2",
    "log_absolute_power": "natural_log_ratio",
    "erd_percent": "percentage_points",
    "log_power_ratio": "natural_log_ratio",
}


def protocol_digest(values: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def load_protocol(path: Path) -> tuple[dict[str, Any], str]:
    values = read_config(path)
    digest = protocol_digest(values)
    checksum = path.with_suffix(".sha256")
    if not checksum.is_file() or checksum.read_text().strip() != digest:
        raise ValueError("Protocol seal is missing or the frozen configuration changed")
    receipt = path.with_name(path.stem + "-freeze.json")
    if receipt.exists():
        info = json.loads(receipt.read_text())
        if info["protocol_sha256"] != digest or info.get(
            "configuration_file_sha256", sha256(path)
        ) != sha256(path):
            raise ValueError("Protocol freeze receipt does not match the configuration")
        if path.name == "replication.yaml" and "document_sha256" in info:
            if protocol_document_sha256("REPLICATION_PROTOCOL.md") != info["document_sha256"]:
                raise ValueError("Frozen protocol document changed")
    config_from_dict(values["cohort"])
    minimum = values["eligibility"]["minimum_paired_runs"]
    if values["eligibility"]["minimum_trials_per_condition_per_run"] < 1:
        raise ValueError("Minimum trial count must be positive")
    if not isinstance(minimum, int) or minimum < 1:
        raise ValueError("minimum_paired_runs must be positive")
    return values, digest


def _inference_config(protocol: dict[str, Any]) -> InferenceConfig:
    names = ("confidence", "n_resamples", "seed", "max_invalid_studentized_fraction", "missing")
    return InferenceConfig(**{k: protocol["inference"][k] for k in names})


def _receipt_valid(folder: Path, fingerprint: str) -> bool:
    path = folder / "checkpoint.json"
    if not path.exists():
        return False
    info = json.loads(path.read_text())
    if info["input_fingerprint"] != fingerprint or info["status"] != "complete":
        return False
    for name, digest in info["files"].items():
        if Path(name).name != name or sha256(folder / name) != digest:
            raise ValueError(f"Replication checkpoint checksum mismatch: {folder / name}")
    return True


def _stream_tables(paths: list[Path], destination: Path) -> None:
    with destination.open("x") as target:
        header = None
        for path in paths:
            with path.open() as source:
                line = source.readline()
                if header is None:
                    header = line
                    target.write(line)
                elif line != header:
                    raise ValueError(f"Incompatible table schema: {path}")
                shutil.copyfileobj(source, target, 1024 * 1024)


def eligible_effects(
    features: pd.DataFrame, cfg: CohortConfig, minimum_runs: int, minimum_trials: int = 1
) -> tuple[pd.DataFrame, pd.DataFrame]:
    runs, subjects = subject_contrasts(features)
    if minimum_trials < 1:
        raise ValueError("minimum_trials must be positive")
    if minimum_trials > 1 and not features.empty:
        imagery = features[features.kind == "imagery"].copy()
        imagery["log_absolute_power"] = np.log(
            imagery.absolute_power_v2.where(imagery.absolute_power_v2 > 0)
        )
        for outcome in OUTCOMES:
            counts = (
                imagery.groupby(["subject", "run", "channel", "band", "condition"])[outcome]
                .count()
                .unstack("condition")
            )
            good = (counts.get("left hand imagery", 0) >= minimum_trials) & (
                counts.get("right hand imagery", 0) >= minimum_trials
            )
            allowed = set(counts.index[good])
            selected = runs.outcome == outcome
            for index, row in runs[selected].iterrows():
                if (row["subject"], row["run"], row["channel"], row["band"]) not in allowed:
                    runs.loc[index, "contrast"] = np.nan
        subjects = (
            runs.groupby(["subject", *KEYS])
            .agg(
                contrast=("contrast", "mean"),
                n_runs=("contrast", "count"),
                run_sd=("contrast", "std"),
            )
            .reset_index()
        )
    expected = pd.DataFrame(
        [
            {"subject": s, "channel": c, "band": b, "outcome": o, "units": u}
            for s in cfg.subjects
            for c in cfg.motor.channels
            for b in ("mu", "beta")
            for o, u in OUTCOMES.items()
        ]
    )
    subjects = expected.merge(subjects, on=["subject", *KEYS], how="left")
    subjects["n_runs"] = pd.to_numeric(subjects.n_runs).fillna(0).astype(int)
    subjects["contrast"] = pd.to_numeric(subjects.contrast).astype(float)
    subjects["run_sd"] = pd.to_numeric(subjects.run_sd).astype(float)
    subjects["unrestricted_contrast"] = subjects.contrast
    subjects["included"] = subjects.n_runs >= minimum_runs
    subjects["exclusion_reason"] = np.where(subjects.included, "", "insufficient_paired_runs")
    subjects.loc[~subjects.included, "contrast"] = np.nan
    return runs, subjects


def _infer_table(subjects: pd.DataFrame, protocol: dict[str, Any]) -> pd.DataFrame:
    rows = []
    config = _inference_config(protocol)
    for key, frame in subjects.groupby(KEYS, sort=True):
        if frame.subject.duplicated().any():
            raise ValueError("Duplicate subject effects in replication")
        values = frame.sort_values("subject").contrast.to_numpy(float)
        for result in infer_mean(values, tuple(protocol["inference"]["methods"]), config):
            row = {**dict(zip(KEYS, key, strict=True)), **result}
            row["warnings"] = "; ".join(result["warnings"])
            row["p_sign_flip"] = np.nan
            primary = (
                key[0] in protocol["primary"]["channels"]
                and key[1] == protocol["primary"]["band"]
                and key[2] == protocol["primary"]["outcome"]
                and result["method"] == protocol["primary"]["interval"]
            )
            available = values[np.isfinite(values)]
            if primary and protocol["inference"].get("sign_flip") and len(available) >= 2:
                row["p_sign_flip"] = sign_flip_pvalue(
                    available, config.seed, protocol["inference"]["n_permutations"]
                )
            rows.append(row)
    population = pd.DataFrame(rows)
    population["p_holm_primary"] = np.nan
    tested = population.p_sign_flip.notna()
    if tested.any():
        observed = population.loc[tested, "p_sign_flip"].to_numpy(float)
        # Unavailable outcomes stay in the prespecified family; they cannot
        # make the remaining comparison less conservative.
        unavailable = len(protocol["primary"]["channels"]) - len(observed)
        family = np.r_[observed, np.ones(unavailable)]
        population.loc[tested, "p_holm_primary"] = holm(family)[: len(observed)]
    return population


def _initial_comparison(
    initial: Path | None, population: pd.DataFrame, protocol: dict[str, Any], cfg: CohortConfig
) -> pd.DataFrame:
    if initial is None or not (current_generation(initial) / "features.csv").exists():
        return pd.DataFrame(
            columns=[
                "cohort",
                "channel",
                "band",
                "outcome",
                "estimate",
                "ci_low",
                "ci_high",
                "n_subjects",
            ]
        )
    folder = current_generation(initial)
    feature = pd.read_csv(folder / "features.csv")
    old_cfg = replace(cfg, subjects=tuple(sorted(feature.subject.unique().tolist())))
    _, subjects = eligible_effects(feature, old_cfg, protocol["eligibility"]["minimum_paired_runs"])
    old = _infer_table(subjects, protocol)
    old["cohort"] = "initial_1_to_5"
    new = population.copy()
    new["cohort"] = "replication"
    return pd.concat([old, new], ignore_index=True)


def robustness_flags(
    population: pd.DataFrame,
    influences: pd.DataFrame,
    protocol: dict[str, Any],
    coverage: dict[str, float],
    configuration_effects: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rules = protocol["robustness"]
    rows = []
    for channel in protocol["primary"]["channels"]:
        target = population[
            (population.channel == channel)
            & (population.band == protocol["primary"]["band"])
            & (population.outcome == protocol["primary"]["outcome"])
        ]
        primary = target[target.method == protocol["primary"]["interval"]]
        if primary.empty:
            continue
        item = primary.to_dict("records")[0]
        channel_coverage = dict(coverage)
        channel_coverage["subject_fraction"] = (
            item["n_subjects"] / item["n_requested"] if item["n_requested"] else 0.0
        )
        channel_coverage["missing_reference_fraction"] = coverage.get(
            f"missing_reference_{channel}_mu", coverage["missing_reference_fraction"]
        )
        reasons = []
        for key, threshold in (
            ("subject_fraction", "minimum_subject_fraction"),
            ("record_fraction", "minimum_record_fraction"),
            ("trial_retention", "minimum_trial_retention"),
        ):
            if channel_coverage[key] < rules[threshold]:
                reasons.append(key + "_below_declared_threshold")
        if target.status.ne("ok").any():
            reasons.append("one_or_more_interval_procedures_failed")
        own = (
            influences[
                (influences.channel == channel)
                & (influences.band == protocol["primary"]["band"])
                & (influences.outcome == protocol["primary"]["outcome"])
            ]
            if not influences.empty
            else pd.DataFrame()
        )
        agreement = float(own.sign_agrees.mean()) if len(own) else np.nan
        if (
            not np.isfinite(agreement)
            or agreement < rules["minimum_leave_one_subject_sign_agreement"]
        ):
            reasons.append("leave_one_subject_sign_instability")
        config_agreement = np.nan
        if configuration_effects is not None:
            changes = configuration_effects[
                (configuration_effects.channel == channel)
                & (configuration_effects.band == protocol["primary"]["band"])
                & (configuration_effects.outcome == protocol["primary"]["outcome"])
                & (configuration_effects.method == protocol["primary"]["interval"])
            ]
            estimates = changes.estimate.to_numpy(float)
            valid = np.isfinite(estimates)
            config_agreement = (
                float(
                    np.sum(valid & (np.sign(estimates) == np.sign(item["estimate"])))
                    / len(estimates)
                )
                if len(estimates)
                else np.nan
            )
            if (
                not np.isfinite(config_agreement)
                or config_agreement < rules["minimum_configuration_sign_agreement"]
            ):
                reasons.append("configuration_sign_instability")
            if not valid.all() or len(changes) != len(protocol["sensitivity_variants"]):
                reasons.append("incomplete_configuration_evidence")
            ref = changes[changes.variant.isin(["reference_none", "reference_fz_pz"])]
            if np.any(np.sign(ref.estimate.to_numpy(float)) != np.sign(item["estimate"])):
                reasons.append("reference_dependent_sign")
        if (
            channel_coverage["missing_reference_fraction"]
            > rules["maximum_missing_reference_fraction"]
        ):
            reasons.append("insufficient_reference_data")
        status = (
            "sensitive_or_insufficient"
            if reasons
            else "sensitivity_not_yet_evaluated"
            if configuration_effects is None
            else "passes_declared_descriptive_checks"
        )
        rows.append(
            {
                "channel": channel,
                "band": protocol["primary"]["band"],
                "estimate": item["estimate"],
                "status": status,
                "flags": ";".join(reasons),
                "leave_subject_sign_agreement": agreement,
                "configuration_sign_agreement": config_agreement,
                **channel_coverage,
                "interpretation": (
                    "operational diagnostics; no guarantee of physiological validity or invariance"
                ),
            }
        )
    return pd.DataFrame(rows)


def replicate(
    root: Path,
    output: Path,
    protocol_path: Path,
    *,
    subjects: tuple[int, ...] | None = None,
    runs: tuple[int, ...] | None = None,
    cache_root: Path = Path("data/derived/cohort-cache"),
    resume: bool = False,
    variant: str = "primary",
    plots: bool = True,
    initial: Path | None = Path("reports/milestone3-committed/cohort"),
) -> dict[str, Any]:
    protocol, digest = load_protocol(protocol_path)
    cfg = config_from_dict(protocol["cohort"])
    cfg = replace(cfg, subjects=subjects or cfg.subjects, runs=runs or cfg.runs, plots=False)
    design = sensitivity_design(cfg)
    if variant not in protocol["sensitivity_variants"] or variant not in design:
        raise ValueError("Variant is not in the frozen protocol")
    cfg = design[variant][1]
    software = software_identity()
    identity = {
        "protocol_sha256": digest,
        "selection": scientific_dict(cfg),
        "variant": variant,
        "software": software,
    }
    if output.exists():
        if not resume:
            raise FileExistsError(output)
        if json.loads((output / "identity.json").read_text()) != json.loads(json.dumps(identity)):
            raise ValueError("Replication resume protocol/configuration/code/environment mismatch")
    else:
        output.mkdir(parents=True)
        atomic_json(output / "identity.json", identity)
        atomic_json(output / "protocol.json", protocol)
    started = time.perf_counter()
    records = output / "records"
    records.mkdir(exist_ok=True)
    attempts = output / "attempts"
    attempts.mkdir(exist_ok=True)
    ledger = []
    channel_set: set[str] | None = None
    sampling: float | None = None
    reused = 0
    for subject in sorted(cfg.subjects):
        for run in sorted(cfg.runs):
            record = records / f"S{subject:03d}R{run:02d}"
            row: dict[str, Any] = {
                "subject": subject,
                "run": run,
                "status": "failed",
                "resumed": False,
            }
            tick = time.perf_counter()
            try:
                source = input_identity(root, subject, run, cfg)
                fingerprint = canonical_id(source)
                if resume and _receipt_valid(record, fingerprint):
                    row = json.loads((record / "checkpoint.json").read_text())["record"]
                    metadata = json.loads((record / "metadata.json").read_text())
                    row["resumed"] = True
                    reused += 1
                else:
                    if record.exists():
                        archive = attempts / (
                            record.name + f"-{len(list(attempts.glob(record.name + '-*'))) + 1:03d}"
                        )
                        record.rename(archive)
                    record.mkdir()
                    cache, metadata, hit = cached_record(
                        root, subject, run, cfg, cache_root, software
                    )
                    for name in (
                        "features.csv",
                        "events.csv",
                        "trials.csv",
                        "metadata.json",
                        "cache.json",
                    ):
                        shutil.copy2(cache / name, record / name)
                    task_count = sum(
                        1
                        for a in metadata["source"].get("annotations", [])
                        if a["description"] in ("T1", "T2")
                    )
                    notes = list(metadata.get("ingest_processing_warnings", []))
                    if cfg.synthetic_seed is None and task_count != 15:
                        notes.append(f"nonstandard task count: {task_count}; retained with warning")
                    row.update(
                        status="complete",
                        input_fingerprint=fingerprint,
                        cache_key=cache.name,
                        cache_hit=hit,
                        fs_hz=metadata["fs_hz"],
                        n_samples=metadata["source"].get("n_samples"),
                        warnings=notes,
                        profile=metadata["profile"],
                        counts=metadata["quality"]["trial_counts"],
                    )
                channels = set(metadata["preprocessing"]["channels"])
                fs = float(metadata["fs_hz"])
                if (channel_set is not None and channels != channel_set) or (
                    sampling is not None and fs != sampling
                ):
                    raise ValueError("Cross-run EEG channel or sampling-rate inconsistency")
                channel_set, sampling = channels, fs
                row["elapsed_seconds"] = time.perf_counter() - tick
                checksums = {
                    p.name: sha256(p)
                    for p in record.iterdir()
                    if p.is_file() and p.name != "checkpoint.json"
                }
                atomic_json(
                    record / "checkpoint.json",
                    {
                        "status": "complete",
                        "input_fingerprint": fingerprint,
                        "files": checksums,
                        "record": row,
                    },
                )
            except Exception as exc:
                row.update(
                    status="failed",
                    error_type=type(exc).__name__,
                    error=str(exc),
                    warnings=getattr(exc, "record_warnings", []),
                    elapsed_seconds=time.perf_counter() - tick,
                )
                record.mkdir(exist_ok=True)
                atomic_json(record / "failure.json", row)
            ledger.append(row)
            atomic_json(
                output / "progress.json",
                {
                    "identity": canonical_id(identity),
                    "records": ledger,
                    "updated_utc": datetime.now(UTC).isoformat(),
                },
            )
    generations = output / "generations"
    generations.mkdir(exist_ok=True)
    generation = generations / f"{len(list(generations.iterdir())) + 1:04d}"
    generation.mkdir()
    valid = [row for row in ledger if row["status"] == "complete"]
    for table in ("features", "events", "trials"):
        paths = [
            records / f"S{row['subject']:03d}R{row['run']:02d}" / (table + ".csv") for row in valid
        ]
        if paths:
            _stream_tables(paths, generation / (table + ".csv"))
    if valid:
        features = pd.read_csv(generation / "features.csv")
    else:
        from soma.experiments.cohort import FEATURE_COLUMNS

        features = pd.DataFrame(columns=FEATURE_COLUMNS)
        features.to_csv(generation / "features.csv", index=False)
    if features.duplicated(
        ["subject", "run", "recording", "trial_index", "kind", "channel", "band"]
    ).any():
        raise ValueError("Duplicate trial identities during incremental aggregation")
    minimum = protocol["eligibility"]["minimum_paired_runs"]
    run_effects, subject_effects = eligible_effects(
        features, cfg, minimum, protocol["eligibility"]["minimum_trials_per_condition_per_run"]
    )
    population = _infer_table(subject_effects, protocol)
    tables = {
        "features": features,
        "run_contrasts": run_effects,
        "subject_contrasts": subject_effects,
        "population": population,
        "subject_exclusions": subject_effects[~subject_effects.included],
    }
    tables.update(
        influence_tables(
            subject_effects, run_effects, minimum, protocol["robustness"]["trimmed_fraction"]
        )
    )
    tables["weighting_summary"] = weighting_summaries(features, subject_effects, run_effects)
    tables["initial_comparison"] = _initial_comparison(initial, population, protocol, cfg)
    for name, frame in tables.items():
        if name != "features":
            frame.to_csv(generation / (name + ".csv"), index=False)
    quality = []
    for subject in sorted(cfg.subjects):
        own = [row for row in ledger if row["subject"] == subject]
        successes = [row for row in own if row["status"] == "complete"]
        included = subject_effects[
            (subject_effects.subject == subject)
            & (subject_effects.outcome == protocol["primary"]["outcome"])
            & subject_effects.channel.isin(protocol["primary"]["channels"])
            & (subject_effects.band == protocol["primary"]["band"])
        ]
        quality.append(
            {
                "subject": subject,
                "requested_runs": len(own),
                "complete_runs": len(successes),
                "failed_runs": len(own) - len(successes),
                "imagery_proposed": sum(row["counts"]["analysis"]["proposed"] for row in successes),
                "imagery_accepted": sum(row["counts"]["analysis"]["accepted"] for row in successes),
                "any_primary_outcome_eligible": bool(included.included.any()),
                "record_warnings": sum(len(row.get("warnings", [])) for row in own),
            }
        )
    q = pd.DataFrame(quality)
    q.to_csv(generation / "quality_subject.csv", index=False)
    pd.DataFrame(
        [{k: v for k, v in row.items() if k not in ("profile", "counts")} for row in ledger]
    ).to_csv(generation / "quality_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "subject": row["subject"],
                "run": row["run"],
                "resumed": row["resumed"],
                **row.get("profile", {}),
            }
            for row in ledger
        ]
    ).to_csv(generation / "profiling_run.csv", index=False)
    imagery = features[features.kind == "imagery"]
    coverage = {
        "subject_fraction": float(q.any_primary_outcome_eligible.mean()),
        "record_fraction": len(valid) / len(ledger),
        "trial_retention": float(q.imagery_accepted.sum() / q.imagery_proposed.sum())
        if q.imagery_proposed.sum()
        else 0.0,
        "missing_reference_fraction": float(imagery.erd_percent.isna().mean())
        if len(imagery)
        else 1.0,
    }
    for channel in protocol["primary"]["channels"]:
        cells = imagery[
            (imagery.channel == channel) & (imagery.band == protocol["primary"]["band"])
        ]
        coverage[f"missing_reference_{channel}_mu"] = (
            float(cells.erd_percent.isna().mean()) if len(cells) else 1.0
        )
    robustness_flags(population, tables["leave_one_subject_out"], protocol, coverage).to_csv(
        generation / "robustness.csv", index=False
    )
    experiment_id = canonical_id(
        {
            "identity": identity,
            "inputs": [row.get("input_fingerprint", "unavailable") for row in ledger],
        }
    )
    atomic_json(
        generation / "coverage.json",
        {
            "records": ledger,
            "complete": len(valid),
            "failed": len(ledger) - len(valid),
            "requested_subjects": list(cfg.subjects),
            "requested_runs": list(cfg.runs),
            "coverage_metrics": coverage,
        },
    )
    atomic_json(
        generation / "manifest.json",
        manifest(
            {
                "dataset": cfg.dataset,
                "record_inputs": [
                    {
                        "subject": r["subject"],
                        "run": r["run"],
                        "fingerprint": r.get("input_fingerprint"),
                        "error": r.get("error"),
                    }
                    for r in ledger
                ],
            },
            {
                "experiment_id": experiment_id,
                **identity,
                "eligibility": protocol["eligibility"],
                "primary": protocol["primary"],
                "inference": protocol["inference"],
                "initial_features_sha256": sha256(current_generation(initial) / "features.csv")
                if initial is not None and (current_generation(initial) / "features.csv").exists()
                else None,
            },
            {
                "output": str(output.resolve()),
                "data_root": str(root.resolve()),
                "cache_root": str(cache_root.resolve()),
            },
            protocol["inference"]["seed"],
        ),
    )
    atomic_json(
        generation / "profiling.json",
        {
            "wall_seconds": time.perf_counter() - started,
            "records_requested": len(ledger),
            "records_resumed": reused,
            "cache_hits": sum(bool(row.get("cache_hit")) for row in ledger if not row["resumed"]),
            "incremental_policy": (
                "one raw recording at a time; CSV streaming; only spectral features aggregated"
            ),
        },
    )
    if plots and valid:
        from soma.visualization.replication import plot_replication

        plot_replication(generation)
    primary = population[
        (population.outcome == protocol["primary"]["outcome"])
        & population.channel.isin(protocol["primary"]["channels"])
        & (population.band == protocol["primary"]["band"])
    ]
    report = [
        "# Prespecified EEG replication",
        "",
        f"Protocol SHA-256: {digest}.",
        f"Records complete: {len(valid)}/{len(ledger)}; selected subjects {cfg.subjects}.",
        f"Variant: {variant}; fixed primary interval: {protocol['primary']['interval']}.",
        "",
        "```csv",
        primary.to_csv(index=False),
        "```",
        "",
        "Excluded subjects/outcomes and failed records retain identities and reasons.",
        "Inference is subject balanced; run/trial weighted targets are separately labeled.",
        "T intervals assume independent normal subjects or a finite-variance CLT.",
        "Interval failures are explicit; no method substitutes for another.",
        "Initial-five-informed hypotheses remain exploratory; coordinates are templates.",
        "Operational robustness flags are diagnostics, not proof of physiological validity.",
    ]
    (generation / "report.md").write_text("\n".join(report) + "\n")
    atomic_json(
        output / "current.json",
        {
            "generation": str(generation.relative_to(output)),
            "experiment_id": experiment_id,
            "updated_utc": datetime.now(UTC).isoformat(),
        },
    )
    return {
        "status": "complete" if len(valid) == len(ledger) else "partial" if valid else "failed",
        "complete": len(valid),
        "failed": len(ledger) - len(valid),
        "resumed": reused,
        "generation": str(generation),
        "experiment_id": experiment_id,
        "output": str(output),
    }


def replication_sensitivity(
    root: Path,
    output: Path,
    protocol_path: Path,
    *,
    subjects: tuple[int, ...] | None = None,
    runs: tuple[int, ...] | None = None,
    cache_root: Path = Path("data/derived/cohort-cache"),
    resume: bool = False,
    plots: bool = True,
) -> dict[str, Any]:
    protocol, digest = load_protocol(protocol_path)
    identity = {
        "protocol_sha256": digest,
        "subjects": subjects,
        "runs": runs,
        "software": software_identity(),
    }
    if output.exists():
        if not resume or json.loads((output / "identity.json").read_text()) != json.loads(
            json.dumps(identity)
        ):
            raise ValueError("Sensitivity output exists or resume identity mismatch")
    else:
        output.mkdir(parents=True)
        atomic_json(output / "identity.json", identity)
    results, effects, subject_frames, retention, missing = [], [], [], [], []
    for variant in protocol["sensitivity_variants"]:
        destination = output / variant
        result = replicate(
            root,
            destination,
            protocol_path,
            subjects=subjects,
            runs=runs,
            cache_root=cache_root,
            resume=resume and destination.exists(),
            variant=variant,
            plots=False,
        )
        results.append({"variant": variant, **result})
        folder = Path(result["generation"])
        table = pd.read_csv(folder / "population.csv")
        table["variant"] = variant
        effects.append(table)
        frame = pd.read_csv(folder / "subject_contrasts.csv")
        frame["variant"] = variant
        subject_frames.append(frame)
        quality = pd.read_csv(folder / "quality_subject.csv")
        quality["variant"] = variant
        retention.append(quality)
        cov = json.loads((folder / "coverage.json").read_text())["coverage_metrics"]
        missing.append(
            {
                "variant": variant,
                **cov,
                "records_complete": result["complete"],
                "records_failed": result["failed"],
            }
        )
    generations = output / "generations"
    generations.mkdir(exist_ok=True)
    generation = generations / f"{len(list(generations.iterdir())) + 1:04d}"
    generation.mkdir()
    table = pd.concat(effects, ignore_index=True)
    keys = [*KEYS, "method"]
    primary = table[table.variant == "primary"][keys + ["estimate"]].rename(
        columns={"estimate": "primary_estimate"}
    )
    table = table.merge(primary, on=keys, how="left")
    table["effect_change"] = table.estimate - table.primary_estimate
    table["relative_change"] = table.effect_change / table.primary_estimate.abs().where(
        table.primary_estimate != 0
    )
    table["sign_consistent"] = np.where(
        table.estimate.notna() & table.primary_estimate.notna(),
        np.sign(table.estimate) == np.sign(table.primary_estimate),
        np.nan,
    )
    subject_table = pd.concat(subject_frames, ignore_index=True)
    base_subjects = subject_table[subject_table.variant == "primary"][
        ["subject", *KEYS, "contrast"]
    ].rename(columns={"contrast": "primary_contrast"})
    subject_table = subject_table.merge(base_subjects, on=["subject", *KEYS], how="left")
    subject_table["subject_effect_change"] = subject_table.contrast - subject_table.primary_contrast
    paired = (
        subject_table.groupby(["variant", *KEYS])
        .agg(
            paired_subject_change=("subject_effect_change", "mean"),
            paired_subject_count=("subject_effect_change", "count"),
        )
        .reset_index()
    )
    table = table.merge(paired, on=["variant", *KEYS], how="left")
    table.to_csv(generation / "sensitivity_effects.csv", index=False)
    subject_table.to_csv(generation / "sensitivity_subject_effects.csv", index=False)
    pd.concat(retention, ignore_index=True).to_csv(
        generation / "sensitivity_retention.csv", index=False
    )
    pd.DataFrame(missing).to_csv(generation / "sensitivity_missingness.csv", index=False)
    primary_folder = current_generation(output / "primary")
    primary_population = pd.read_csv(primary_folder / "population.csv")
    influence = pd.read_csv(primary_folder / "leave_one_subject_out.csv")
    cov = json.loads((primary_folder / "coverage.json").read_text())["coverage_metrics"]
    robustness_flags(primary_population, influence, protocol, cov, table).to_csv(
        generation / "robustness.csv", index=False
    )
    atomic_json(
        generation / "manifest.json",
        manifest(
            {"dataset": "eegmmidb"},
            {
                "protocol_sha256": digest,
                "variants": protocol["sensitivity_variants"],
                "results": results,
            },
            {"output": str(output.resolve())},
            protocol["inference"]["seed"],
        ),
    )
    if plots:
        from soma.visualization.replication import plot_replication_sensitivity

        plot_replication_sensitivity(generation)
    (generation / "report.md").write_text(
        "# Frozen-protocol replication sensitivity\n\n"
        + "All prespecified one-factor variants are retained. No configuration is promoted. "
        + "robustness.csv applies the declared coverage, influence and sign-consistency criteria. "
        + "Sensitivity includes trial selection; paired-subject contrasts control membership.\n"
    )
    atomic_json(
        output / "current.json",
        {"generation": str(generation.relative_to(output)), "protocol_sha256": digest},
    )
    return {
        "status": "complete" if all(r["failed"] == 0 for r in results) else "partial",
        "record_analyses_complete": sum(r["complete"] for r in results),
        "record_analyses_failed": sum(r["failed"] for r in results),
        "variants": len(results),
        "output": str(output),
        "generation": str(generation),
    }
