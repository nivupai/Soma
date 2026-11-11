"""Bounded, resumable evaluation with M19 seals, M18 record caches and M17 receipts."""

import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from soma.core.provenance import sha256
from soma.eeg_benchmark.data import inventory, load_dataset
from soma.eeg_benchmark.evaluation import (
    adaptation,
    bank,
    environment_snapshot,
    evaluate,
    native,
    read_native,
    select,
)
from soma.eeg_benchmark.protocol import configuration, inspect_protocol
from soma.eeg_benchmark.statistics import (
    bootstrap,
    null_diagnostic,
    permuted_labels,
    subject_table,
    summarize,
)
from soma.human.permissions import PermissionEvidence, check_permission
from soma.pipeline.cache import source_hash
from soma.protocol.model import SealedProtocol
from soma.simulations.calibration import atomic_json
from soma.workflow.model import digest


def safe_locations(root: Path, output: Path, cache: Path) -> None:
    from soma.datasets.human_mri import safe_local_output

    safe_local_output(output)
    safe_local_output(cache)
    if output.resolve().is_relative_to(root.resolve()) or cache.resolve().is_relative_to(
        root.resolve()
    ):
        raise ValueError("Benchmark outputs must not modify raw inputs")


def run_benchmark(
    sealed: SealedProtocol,
    inv: dict[str, Any],
    root: Path,
    permission: PermissionEvidence,
    source: Path,
    key: bytes,
    output: Path,
    cache: Path,
) -> dict[str, Any]:
    safe_locations(root, output, cache)
    value = inspect_protocol(sealed)
    current = inventory(root, value, key)
    if (
        current["fingerprint"] != inv["fingerprint"]
        or sealed.protocol.document()["optional_metadata"]["inventory_fingerprint"]
        != inv["fingerprint"]
    ):
        raise ValueError("Cohort/input snapshot changed after seal")
    allowed = check_permission(
        permission,
        dataset="eegmmidb",
        version="1.0.0",
        purpose="methods_research",
        action="analyze",
        source_content=source.read_bytes(),
    )
    if not allowed["allowed"]:
        raise ValueError("Data-use evidence blocks benchmark")
    code = source_hash()
    identity = digest(
        {
            "protocol": sealed.protocol.fingerprint,
            "inventory": inv["fingerprint"],
            "permission": permission.fingerprint,
            "implementation": code,
            "environment": environment_snapshot(),
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    lock = output / "identity.local.json"
    if lock.exists() and json.loads(lock.read_text())["identity"] != identity:
        raise ValueError("Incompatible resumed benchmark")
    atomic_json(
        lock,
        {
            "identity": identity,
            "protocol": sealed.record(),
            "inventory": inv,
            "permission": permission.document(),
        },
    )
    results = []
    tick = time.perf_counter()
    cpu = time.process_time()
    for variant in value["variants"]:
        if source_hash() != code:
            raise ValueError("Code changed during frozen evaluation; explicit amendment required")
        destination = output / variant
        if (destination / "summary/result.json").is_file():
            completed = read_native(destination / "summary/result.json")
            if completed["identity"] != identity or completed["variant"] != variant:
                raise ValueError("Changed variant receipt")
            # Verify all sealed stage/cell artifacts even when resuming a completed variant.
            for relative, checksum in completed["files"].items():
                path = (destination / relative).resolve(strict=True)
                if not path.is_relative_to(destination.resolve()) or sha256(path) != checksum:
                    raise ValueError("Corrupt resumed output")
            results.append(completed)
            continue
        started = time.perf_counter()
        p = configuration(value, variant)
        destination.mkdir(parents=True, exist_ok=True)
        with threadpool_limits(limits=1):
            dataset, coverage = load_dataset(
                root,
                inv,
                p,
                permission,
                source,
                cache,
                coverage_path=destination / "coverage.local.json",
            )
            atomic_json(destination / "coverage.local.json", coverage)
            features = bank(dataset, p)
            eligible = set(map(int, dataset.metadata.subject.unique()))
            sources = [s for s in inv["source_subjects"][: p["source_limit"]] if s in eligible]
            targets = [s for s in inv["target_subjects"] if s in eligible]
            if len(sources) < 3 or len(targets) < 2:
                raise ValueError("Insufficient prespecified eligible subjects; no replacements")
            selected, audit, tried = select(features, p, sources, targets)
            atomic_json(
                destination / "selection.local.json",
                {"selected": selected, "all_candidates": tried, "target_used_for_selection": False},
            )
            (destination / "selection-audit").mkdir(exist_ok=True)
            audit.save(destination / "selection-audit")
            predicted, cells, fit_audit = evaluate(
                features, p, sources, targets, selected, destination, sealed.protocol.fingerprint
            )
            predicted.to_csv(destination / "predictions.local.csv", index=False)
            (destination / "fit-audit").mkdir(exist_ok=True)
            fit_audit.save(destination / "fit-audit")
            rows = subject_table(predicted, inv["target_subjects"], p["evaluation_runs"])
            atomic_json(destination / "subjects.local.json", rows)
            summary = summarize(rows, p)
            if variant == "primary":
                adapted, adapt_cells, adapt_audit = adaptation(
                    features, p, sources, targets, selected
                )
                adapted.to_csv(destination / "adaptation.local.csv", index=False)
                (destination / "adaptation-audit").mkdir(exist_ok=True)
                adapt_audit.save(destination / "adaptation-audit")
                atomic_json(destination / "adaptation-cells.local.json", adapt_cells)
                adapt_summary = []
                for count in p["adaptation_counts"]:
                    subset = (
                        adapted[adapted.calibration_trials == count]
                        if len(adapted)
                        else pd.DataFrame()
                    )
                    for model in p["adaptation_models"]:
                        selected_rows = (
                            subset[subset.model == model].copy() if len(subset) else pd.DataFrame()
                        )
                        if len(selected_rows):
                            selected_rows["mode"] = "cross-subject"
                        metrics = subject_table(
                            selected_rows,
                            inv["target_subjects"],
                            p["adaptation_test_runs"],
                            ("cross-subject",),
                        )
                        vals = [
                            r["balanced_accuracy"]
                            for r in metrics
                            if r["model"] == model and r["status"] == "COMPLETE"
                        ]
                        adapt_summary.append(
                            {
                                "model": model,
                                "labeled_target_trials": count,
                                "n_subjects": len(vals),
                                "balanced_accuracy": bootstrap(
                                    vals, seed=p["seed"], resamples=p["bootstrap_resamples"]
                                )
                                if len(vals) >= 2
                                else None,
                                "target_supervised": count > 0,
                                "test_runs": p["adaptation_test_runs"],
                                "test_data_used_for_fitting": False,
                            }
                        )
                summary["adaptation"] = adapt_summary
                nulls: dict[str, list[float]] = {model: [] for model in p["null_models"]}
                for repetition in range(p["null_repetitions"]):
                    folder = destination / "nulls" / str(repetition)
                    if (folder / "summary/result.json").exists():
                        record = read_native(folder / "summary/result.json")
                    else:
                        labels = permuted_labels(
                            dataset.y, dataset.metadata, p["seed"] + repetition + 1
                        )
                        choice, null_audit, candidates = select(
                            features, p, sources, targets, labels, tuple(p["null_models"])
                        )
                        pred, null_cells, _ = evaluate(
                            features,
                            p,
                            sources,
                            targets,
                            choice,
                            folder,
                            sealed.protocol.fingerprint,
                            labels=labels,
                            modes=("cross-subject",),
                            models=tuple(p["null_models"]),
                        )
                        scores = subject_table(
                            pred, targets, p["evaluation_runs"], ("cross-subject",)
                        )
                        record = {
                            "repetition": repetition,
                            "identity": identity,
                            "statistics": {},
                            "source_selection_refit": True,
                            "failed_cells": sum(c["status"] != "COMPLETE" for c in null_cells),
                            "all_candidates": candidates,
                        }
                        for model in p["null_models"]:
                            vals = [
                                r["balanced_accuracy"]
                                for r in scores
                                if r["model"] == model and r["status"] == "COMPLETE"
                            ]
                            if len(vals) != len(targets):
                                raise ValueError("Incomplete null; do not manufacture p-value")
                            record["statistics"][model] = float(np.mean(vals))
                        native(record, folder / "summary")
                    if record["identity"] != identity:
                        raise ValueError("Changed resumed null identity")
                    for model in nulls:
                        nulls[model].append(record["statistics"][model])
                summary["null_diagnostics"] = {
                    model: null_diagnostic(
                        next(
                            r["balanced_accuracy"]["mean"]
                            for r in summary["methods"]
                            if r["mode"] == "cross-subject" and r["model"] == model
                        ),
                        vals,
                        exchangeability_attested=p["exchangeability_attested"],
                    )
                    for model, vals in nulls.items()
                }
        summary.update(
            schema="soma.eeg.benchmark-summary/1.0.0",
            identity=identity,
            variant=variant,
            protocol_fingerprint=sealed.protocol.fingerprint,
            source_subjects=len(sources),
            planned_source_subjects=p["source_limit"],
            target_subjects=len(targets),
            planned_target_subjects=value["target_count"],
            recordings_planned=len(coverage),
            recordings_eligible=sum(r["status"] == "ELIGIBLE" for r in coverage),
            trials_retained=len(dataset.y),
            trials_proposed=sum(r["n_proposed"] for r in coverage),
            trials_rejected_or_unavailable=sum(r["n_proposed"] for r in coverage) - len(dataset.y),
            failed_model_cells=sum(c["status"] != "COMPLETE" for c in cells),
            wall_seconds=time.perf_counter() - started,
            selected_parameters=selected,
            process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (2**20 if sys.platform == "darwin" else 1024),
            leakage_checks={
                "source_target_disjoint": True,
                "selection_source_only": True,
                "outer_runs_disjoint": True,
                "fitted_transforms_training_only": True,
                "trial_covariance": "fixed per-trial feature; no target population reference",
                "within_parameters": (
                    "selected on independent source-role participants, fixed before fitting targets"
                ),
            },
            files={
                f.relative_to(destination).as_posix(): sha256(f)
                for f in sorted(destination.rglob("*"))
                if f.is_file()
            },
        )
        native(summary, destination / "summary")
        results.append(summary)
        atomic_json(
            output / "progress.local.json",
            {"identity": identity, "completed_variants": [r["variant"] for r in results]},
        )
    if source_hash() != code:
        raise ValueError("Frozen code changed")
    result = {
        "schema": "soma.eeg.benchmark-execution/1.0.0",
        "identity": identity,
        "protocol_fingerprint": sealed.protocol.fingerprint,
        "variants": results,
        "status": "PARTIAL"
        if any(
            r["failed_model_cells"]
            or r["source_subjects"] < r["planned_source_subjects"]
            or any(m["missing_subjects"] for m in r["methods"])
            for r in results
        )
        else "COMPLETE",
        "wall_seconds": time.perf_counter() - tick,
        "cpu_seconds": time.process_time() - cpu,
        "new_external_evidence": "NOT_AVAILABLE",
        "external_replication": False,
        "confirmatory_claim_allowed": False,
    }
    if (output / "execution/result.json").exists():
        return read_native(output / "execution/result.json")
    native(result, output / "execution")
    return result
