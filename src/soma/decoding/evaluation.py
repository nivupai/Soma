"""Fresh fold-local pipelines, subject-balanced nested selection and audit receipts."""

import gzip
import json
import os
import platform
import resource
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from soma.core.provenance import manifest
from soma.decoding.config import digest, identity
from soma.decoding.features import FeatureBank, covariance_parameters
from soma.decoding.metrics import compare_models, subject_scores
from soma.decoding.models import make_pipeline, parameter_grid, require_unfitted
from soma.decoding.splits import Fold, inner_splits, outer_splits, validate_split
from soma.simulations.calibration import atomic_json
from soma.statistics.inference import InferenceConfig, infer_mean


class FitAudit:
    def __init__(self) -> None:
        self.partitions: dict[str, dict[str, Any]] = {}
        self.fits: list[dict[str, Any]] = []
        self.patterns: list[dict[str, Any]] = []
        self.states: list[dict[str, Any]] = []
        self.projection: list[dict[str, Any]] = []

    def partition(self, bank: FeatureBank, fold: Fold) -> str:
        record = validate_split(bank.dataset, fold)
        key = record["membership_sha256"]
        self.partitions[key] = record
        return str(key)

    def save(self, path: Path) -> None:
        atomic_json(path / "partitions.json", self.partitions)
        with gzip.open(path / "fits.json.gz", "wt") as stream:
            json.dump(self.fits, stream, allow_nan=False)
        atomic_json(path / "fitted_states.json", self.states)
        pd.DataFrame(self.projection).to_csv(path / "tangent_projection.csv", index=False)
        pd.DataFrame(
            self.patterns, columns=["fold", "component", "channel", "pattern", "filter"]
        ).to_csv(path / "csp_patterns.csv", index=False)


def fit_fold(
    bank: FeatureBank,
    model: str,
    protocol: dict[str, Any],
    fold: Fold,
    params: dict[str, Any],
    audit: FitAudit,
    *,
    phase: str,
    labels: Any = None,
) -> tuple[Pipeline, Any, Any, Any]:
    membership = audit.partition(bank, fold)
    if not isinstance(model, str):
        raise ValueError("Only decoder names are accepted; external/prefitted models are forbidden")
    if bank.covariance_parameters != covariance_parameters(protocol):
        raise ValueError("Trial covariance bank parameters disagree with the protocol")
    pipeline = make_pipeline(model, protocol, params, precomputed_covariance=True)
    require_unfitted(pipeline)
    y = bank.dataset.y if labels is None else np.asarray(labels)
    if y.shape != bank.dataset.y.shape or y.dtype.kind not in "iu" or not np.isin(y, [0, 1]).all():
        raise ValueError("Replacement labels must align identified integer binary trials")
    if set(np.unique(y[fold.train])) != {0, 1}:
        raise ValueError("Training partition lacks one binary class")
    X = bank.input(model)
    tick, cpu = time.perf_counter(), time.process_time()
    try:
        with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=1):
            warnings.simplefilter("always")
            pipeline.fit(X[fold.train], y[fold.train])
            fit_s = time.perf_counter() - tick
            predict = pipeline.predict(X[fold.test])
            score = pipeline.decision_function(X[fold.test])
            probability = (
                pipeline.predict_proba(X[fold.test])[:, 1]
                if hasattr(pipeline, "predict_proba")
                else None
            )
        if (
            not np.isfinite(score).all()
            or not np.isin(predict, [0, 1]).all()
            or (
                probability is not None
                and (
                    not np.isfinite(probability).all()
                    or np.any((probability < 0) | (probability > 1))
                )
            )
        ):
            raise ValueError("Nonfinite/invalid model predictions")
    except Exception as exc:
        audit.fits.append(
            {
                "model": model,
                "phase": phase,
                "partition": membership,
                "params": params,
                "status": "failed",
                "error": str(exc),
                "fit_and_predict_seconds": time.perf_counter() - tick,
            }
        )
        raise
    record = {
        "model": model,
        "phase": phase,
        "partition": membership,
        "params": params,
        "fit_seconds": fit_s,
        "fit_and_predict_seconds": time.perf_counter() - tick,
        "cpu_seconds": time.process_time() - cpu,
        "n_train": len(fold.train),
        "n_test": len(fold.test),
        "train_class_counts": np.bincount(y[fold.train], minlength=2).tolist(),
        "training_labels_sha256": digest(y[fold.train].tolist()),
        "warnings": [str(w.message) for w in caught],
    }
    audit.fits.append(record)
    if phase in ("outer", "adaptation", "heldout"):
        state: dict[str, Any] = {"model": model, "fold": fold.name, "partition": membership}
        if "scale" in pipeline.named_steps:
            state["scaler_training_mean"] = pipeline.named_steps["scale"].mean_.tolist()
        if "bursts" in pipeline.named_steps:
            state["training_burst_median_v"] = pipeline.named_steps[
                "bursts"
            ].threshold_reference_.tolist()
        if "tangent" in pipeline.named_steps:
            state["training_tangent_reference"] = pipeline.named_steps[
                "tangent"
            ].reference_.tolist()
            covariance = pipeline.named_steps["covariance"].transform(X[fold.test])
            mapped = pipeline.named_steps["tangent"].transform(covariance)
            audit.projection.extend(
                {
                    "fold": fold.name,
                    "subject": int(bank.dataset.metadata.iloc[index].subject),
                    "trial_id": bank.dataset.metadata.iloc[index].trial_id,
                    "label": int(y[index]),
                    "coordinate_0": float(mapped[i, 0]),
                    "coordinate_1": float(mapped[i, 1]),
                }
                for i, index in enumerate(fold.test)
            )
        if "covariance" in pipeline.named_steps:
            state["test_trial_covariance_diagnostics"] = [
                bank.covariance_diagnostics[i] for i in fold.test
            ]
        audit.states.append(state)
        if "csp" in pipeline.named_steps:
            csp = pipeline.named_steps["csp"]
            for component in range(csp.n_components):
                for c, channel in enumerate(bank.dataset.channels):
                    audit.patterns.append(
                        {
                            "fold": fold.name,
                            "component": component,
                            "channel": channel,
                            "pattern": float(csp.patterns_[component, c]),
                            "filter": float(csp.filters_[component, c]),
                        }
                    )
    return pipeline, predict, score, probability


def choose_parameters(
    bank: FeatureBank,
    model: str,
    protocol: dict[str, Any],
    training: Any,
    outer_test: Any,
    audit: FitAudit,
    labels: Any = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    training, outer_test = (
        np.asarray(training, dtype=np.int64),
        np.asarray(outer_test, dtype=np.int64),
    )
    if np.intersect1d(training, outer_test).size:
        raise ValueError("Outer test trials supplied to hyperparameter selection")
    y = bank.dataset.y if labels is None else np.asarray(labels)
    candidates: list[dict[str, Any]] = []
    for candidate, params in enumerate(parameter_grid(model, protocol, True)):
        scores, errors = [], []
        for fold in inner_splits(bank.dataset, training, protocol["inner_subject_folds"]):
            if (
                np.intersect1d(fold.train, outer_test).size
                or np.intersect1d(fold.test, outer_test).size
            ):
                raise ValueError("Outer participant entered inner model selection")
            try:
                _, predictions, _, _ = fit_fold(
                    bank, model, protocol, fold, params, audit, phase="inner", labels=y
                )
                groups = bank.dataset.metadata.iloc[fold.test].subject.to_numpy()
                for subject in np.unique(groups):
                    mask = groups == subject
                    if len(np.unique(y[fold.test][mask])) == 2:
                        scores.append(
                            float(balanced_accuracy_score(y[fold.test][mask], predictions[mask]))
                        )
                    else:
                        errors.append("inner subject lacks a test class")
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        candidates.append(
            {
                "model": model,
                "candidate": candidate,
                "params": params,
                "mean_subject_balanced_accuracy": float(np.mean(scores))
                if scores and not errors
                else None,
                "n_subject_scores": len(scores),
                "errors": errors,
                "training_membership_sha256": digest(
                    bank.dataset.metadata.iloc[training].trial_id.tolist()
                ),
            }
        )
    valid = [row for row in candidates if row["mean_subject_balanced_accuracy"] is not None]
    if not valid:
        raise ValueError(f"All inner candidates failed: {candidates}")
    best = max(valid, key=lambda row: row["mean_subject_balanced_accuracy"])
    return dict(best["params"]), candidates


def prediction_rows(
    bank: FeatureBank,
    fold: Fold,
    model: str,
    prediction: Any,
    score: Any,
    probability: Any,
    count: int = 0,
    labels: Any = None,
) -> list[dict[str, Any]]:
    y = bank.dataset.y if labels is None else labels
    result = []
    for i, index in enumerate(fold.test):
        row = bank.dataset.metadata.iloc[index]
        result.append(
            {
                "model": model,
                "fold": fold.name,
                "subject": int(row.subject),
                "run": int(row.run),
                "trial_id": row.trial_id,
                "label": int(y[index]),
                "prediction": int(prediction[i]),
                "score": float(score[i]),
                "probability": float(probability[i]) if probability is not None else np.nan,
                "calibration_trials": count,
            }
        )
    return result


def evaluate(
    bank: FeatureBank,
    protocol: dict[str, Any],
    mode: str,
    output: Path,
    *,
    models: tuple[str, ...] | None = None,
    labels: Any = None,
    frozen_params: dict[str, dict[str, Any]] | None = None,
    training_subjects: tuple[int, ...] | None = None,
    plots: bool = True,
) -> dict[str, Any]:
    if mode not in ("within-subject", "cross-subject"):
        raise ValueError("Use a separate within-subject, cross-subject or adaptation workflow")
    if frozen_params is not None and mode != "cross-subject":
        raise ValueError("Frozen transfer parameters require cross-subject mode")
    output.mkdir(parents=True, exist_ok=False)
    tick, cpu = time.perf_counter(), time.process_time()
    chosen_models = tuple(protocol["models"]) if models is None else models
    if not set(chosen_models) <= set(protocol["models"]):
        raise ValueError("Decoder subset is not prespecified")
    dataset = bank.dataset
    audit = FitAudit()
    predictions, failures, selection = [], [], []
    if frozen_params is not None:
        if training_subjects is None:
            raise ValueError("Frozen transfer requires explicit development training subjects")
        training = np.flatnonzero(dataset.metadata.subject.isin(training_subjects))
        tests = np.flatnonzero(~dataset.metadata.subject.isin(training_subjects))
        folds = [Fold("prospective-transfer", training, tests, "cross-subject")]
    else:
        folds = outer_splits(dataset, mode, protocol["outer_subject_folds"])
    candidates: list[dict[str, Any]]
    for fold in folds:
        for model in chosen_models:
            try:
                if frozen_params is not None:
                    params, candidates = frozen_params[model], []
                elif mode == "cross-subject":
                    params, candidates = choose_parameters(
                        bank, model, protocol, fold.train, fold.test, audit, labels
                    )
                else:
                    params, candidates = {}, []
                selection.append(
                    {"fold": fold.name, "model": model, "params": params, "candidates": candidates}
                )
                _, pred, score, proba = fit_fold(
                    bank,
                    model,
                    protocol,
                    fold,
                    params,
                    audit,
                    phase="heldout" if frozen_params is not None else "outer",
                    labels=labels,
                )
                predictions.extend(
                    prediction_rows(bank, fold, model, pred, score, proba, labels=labels)
                )
            except Exception as exc:
                failures.append(
                    {
                        "fold": fold.name,
                        "model": model,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
        atomic_json(
            output / "progress.json",
            {
                "last_completed_fold": fold.name,
                "completed_fits": len(audit.fits),
                "failed_cells": len(failures),
                "outer_folds_planned": len(folds),
            },
        )
        try:
            validate_split(dataset, fold)
            # A simple dummy uses only the training class prior and no test statistics.
            y = dataset.y if labels is None else labels
            majority = int(np.argmax(np.bincount(y[fold.train], minlength=2)))
            prior = float(np.mean(y[fold.train]))
            predictions.extend(
                prediction_rows(
                    bank,
                    fold,
                    "dummy",
                    np.full(len(fold.test), majority),
                    np.full(len(fold.test), prior),
                    np.full(len(fold.test), prior),
                    labels=labels,
                )
            )
        except Exception as exc:
            failures.append({"fold": fold.name, "model": "dummy", "error": str(exc)})
    return save_evaluation(
        bank, protocol, mode, output, predictions, failures, selection, audit, tick, cpu, plots
    )


def save_evaluation(
    bank: FeatureBank,
    protocol: dict[str, Any],
    mode: str,
    output: Path,
    predictions: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    selection: list[dict[str, Any]],
    audit: FitAudit,
    tick: float,
    cpu: float,
    plots: bool,
) -> dict[str, Any]:
    predicted = pd.DataFrame(
        predictions,
        columns=[
            "model",
            "fold",
            "subject",
            "run",
            "trial_id",
            "label",
            "prediction",
            "score",
            "probability",
            "calibration_trials",
        ],
    )
    if predicted.empty:
        predicted.to_csv(output / "predictions.csv", index=False)
        atomic_json(output / "failures.json", failures)
        atomic_json(output / "selection.json", selection)
        audit.save(output)
        atomic_json(
            output / "manifest.json",
            manifest(
                {"dataset_fingerprint": bank.dataset.fingerprint},
                {
                    "protocol_sha256": digest(protocol),
                    "software": identity(),
                    "mode": mode,
                    "status": "failed_no_predictions",
                },
                {"output": str(output.resolve())},
                protocol["seed"],
            ),
        )
        return {
            "status": "failed",
            "output": str(output),
            "fits": len(audit.fits),
            "failures": len(failures),
        }
    predicted.to_csv(output / "predictions.csv", index=False)
    scores = subject_scores(predicted)
    scores.to_csv(output / "metrics_run.csv", index=False)
    subjects = scores.groupby(["model", "subject", "calibration_trials"], as_index=False).agg(
        balanced_accuracy=("balanced_accuracy", "mean"),
        accuracy=("accuracy", "mean"),
        n_runs=("run", "count"),
        n_trials=("n_trials", "sum"),
    )
    subjects.to_csv(output / "metrics_subject.csv", index=False)
    comparisons, influence = compare_models(scores, protocol)
    comparisons.to_csv(output / "comparisons.csv", index=False)
    influence.to_csv(output / "comparison_influence.csv", index=False)
    summary = []
    for (model, count), group in subjects.groupby(["model", "calibration_trials"]):
        values = group.balanced_accuracy.to_numpy(float)
        for row in infer_mean(
            values,
            ("t",),
            InferenceConfig(n_resamples=protocol["n_resamples"], seed=protocol["seed"]),
        ):
            summary.append(
                {
                    "model": model,
                    "calibration_trials": int(str(count)),
                    **row,
                    "warnings": ";".join(row["warnings"]),
                    "estimand": "equal-subject mean balanced accuracy; equal observed runs",
                }
            )
    pd.DataFrame(summary).to_csv(output / "summary.csv", index=False)
    reliability = []
    for (model, calibration_count), rows in predicted[predicted.probability.notna()].groupby(
        ["model", "calibration_trials"]
    ):
        for a, b in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:], strict=True):
            chosen = rows[
                (rows.probability >= a)
                & ((rows.probability < b) | ((b == 1) & (rows.probability == 1)))
            ]
            if len(chosen):
                reliability.append(
                    {
                        "model": model,
                        "calibration_trials": int(str(calibration_count)),
                        "lower": a,
                        "upper": b,
                        "n_trials": len(chosen),
                        "mean_probability": chosen.probability.mean(),
                        "fraction_right": chosen.label.mean(),
                        "interpretation": "descriptive correlated trials; no independent-trial CI",
                    }
                )
    pd.DataFrame(reliability).to_csv(output / "reliability.csv", index=False)
    atomic_json(output / "failures.json", failures)
    atomic_json(output / "selection.json", selection)
    audit.save(output)
    profile = {
        "wall_seconds": time.perf_counter() - tick,
        "cpu_seconds": time.process_time() - cpu,
        "process_high_water_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (2**20 if sys.platform == "darwin" else 1024.0),
        "hardware": platform.platform(),
        "logical_cpus": os.cpu_count(),
        "fit_threads": 1,
        "fits": len(audit.fits),
        "failures": len(failures),
        **bank.profile,
    }
    atomic_json(output / "profiling.json", profile)
    atomic_json(
        output / "manifest.json",
        manifest(
            {
                "dataset": "identified-decoding-trials",
                "trial_dataset_fingerprint": bank.dataset.fingerprint,
                "provenance": bank.dataset.provenance,
            },
            {
                "protocol_sha256": digest(protocol),
                "protocol": protocol,
                "mode": mode,
                "software": identity(),
                "positive_class": "right_hand_imagery",
                "statistical_unit": "subject; descriptive CV intervals; overlapping training",
                "analysis_labels_sha256": digest(
                    predicted[["trial_id", "label"]].drop_duplicates().to_dict("records")
                ),
            },
            {"output": str(output.resolve())},
            protocol["seed"],
        ),
    )
    if plots:
        from soma.visualization.decoding import plot_evaluation

        plot_evaluation(output, bank)
    (output / "report.md").write_text(
        f"# {mode} decoding\n\n"
        + f"{len(audit.fits)} fits; {len(failures)} failed model/fold cells. "
        "All trial predictions, grouped partitions and training-only choices are saved. "
        "Subject means, not trial counts, determine population uncertainty. "
        "Sensor filters do not locate anatomical sources.\n"
    )
    return {
        "status": "complete" if not failures else "partial",
        "mode": mode,
        "output": str(output),
        **profile,
    }


def adaptation(
    bank: FeatureBank,
    protocol: dict[str, Any],
    output: Path,
    *,
    frozen_params: dict[str, dict[str, Any]] | None = None,
    training_subjects: tuple[int, ...] | None = None,
    plots: bool = True,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    tick, cpu = time.perf_counter(), time.process_time()
    audit = FitAudit()
    predictions, failures, selection = [], [], []
    dataset = bank.dataset
    if frozen_params is not None:
        if training_subjects is None:
            raise ValueError("Frozen adaptation requires development subjects")
        train = np.flatnonzero(dataset.metadata.subject.isin(training_subjects))
        test = np.flatnonzero(~dataset.metadata.subject.isin(training_subjects))
        folds = [Fold("prospective-adaptation", train, test, "cross-subject")]
    else:
        folds = outer_splits(dataset, "cross-subject", protocol["outer_subject_folds"])
    for outer in folds:
        for model in protocol["adaptation_models"]:
            try:
                params, candidates = (
                    (frozen_params[model], [])
                    if frozen_params is not None
                    else choose_parameters(bank, model, protocol, outer.train, outer.test, audit)
                )
                selection.append(
                    {"fold": outer.name, "model": model, "params": params, "candidates": candidates}
                )
            except Exception as exc:
                failures.append({"fold": outer.name, "model": model, "error": str(exc)})
                continue
            for subject in sorted(dataset.metadata.iloc[outer.test].subject.unique()):
                proposals = dataset.metadata[
                    (dataset.metadata.subject == subject)
                    & (dataset.metadata.run == protocol["adaptation_run"])
                ].sort_values("start_sample")
                target_test = np.flatnonzero(
                    (dataset.metadata.subject == subject)
                    & dataset.metadata.run.isin(protocol["adaptation_test_runs"])
                )
                for count in protocol["adaptation_trial_counts"]:
                    try:
                        selected = [
                            i
                            for label in (0, 1)
                            for i in proposals[proposals.label == label].index[: count // 2]
                        ]
                        if len(selected) != count:
                            raise ValueError(
                                "Insufficient labeled calibration trials; count not reduced"
                            )
                        train = np.r_[outer.train, np.asarray(selected, dtype=np.int64)]
                        fold = Fold(
                            f"{outer.name}-S{subject:03d}-k{count}",
                            train,
                            target_test,
                            "adaptation",
                        )
                        _, pred, score, proba = fit_fold(
                            bank, model, protocol, fold, params, audit, phase="adaptation"
                        )
                        predictions.extend(
                            prediction_rows(bank, fold, model, pred, score, proba, count)
                        )
                    except Exception as exc:
                        failures.append(
                            {
                                "subject": int(subject),
                                "model": model,
                                "calibration_trials": count,
                                "error": str(exc),
                            }
                        )
    return save_evaluation(
        bank,
        protocol,
        "adaptation",
        output,
        predictions,
        failures,
        selection,
        audit,
        tick,
        cpu,
        plots,
    )
