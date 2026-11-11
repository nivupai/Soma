"""Existing fold-local Soma decoders, explicit source selection and target evaluation."""

import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.core.signal import Signal
from soma.decoding.config import identity
from soma.decoding.covariance import TrialCovariances
from soma.decoding.data import TrialDataset
from soma.decoding.evaluation import FitAudit, choose_parameters, fit_fold
from soma.decoding.features import FeatureBank, covariance_parameters
from soma.decoding.metrics import classification_metrics
from soma.decoding.splits import Fold, validate_split
from soma.eeg_benchmark.protocol import MODELS
from soma.results.contracts import create_result
from soma.results.io import inspect_result, save_result
from soma.signal.spectral import WelchConfig, welch
from soma.workflow.model import digest
from soma.workflow.runtime import environment


@lru_cache(maxsize=1)
def environment_snapshot() -> dict[str, Any]:
    return environment()


def bank(dataset: TrialDataset, p: dict[str, Any]) -> FeatureBank:
    powers = np.empty((*dataset.X.shape[:2], 2))
    tick = time.perf_counter()
    for i, trial in enumerate(dataset.X):
        for c, ch in enumerate(dataset.channels):
            spec = welch(
                Signal(trial[c], dataset.fs, ch),
                WelchConfig(round(dataset.fs), round(dataset.fs) // 2),
            )
            powers[i, c] = [spec.band_power(*band) for band in p["bands"]]
    if np.any(powers <= 0):
        raise ValueError("Nonpositive power cannot be logged")
    cov = TrialCovariances(**covariance_parameters(p))
    mat = cov.fit_transform(dataset.X)
    return FeatureBank(
        dataset,
        np.log(powers),
        np.empty((0,)),
        {
            "feature_seconds": time.perf_counter() - tick,
            "bank_mib": (dataset.X.nbytes + powers.nbytes + mat.nbytes) / 2**20,
        },
        mat,
        covariance_parameters(p),
        cov.last_diagnostics_,
    )


def select(
    bank: FeatureBank,
    p: dict[str, Any],
    sources: list[int],
    targets: list[int],
    labels: Any = None,
    models: tuple[str, ...] = MODELS[1:],
) -> tuple[dict[str, dict[str, Any]], FitAudit, list[dict[str, Any]]]:
    frame = bank.dataset.metadata
    training = np.flatnonzero(frame.subject.isin(sources))
    testing = np.flatnonzero(frame.subject.isin(targets))
    if set(sources) & set(targets) or not len(training) or not len(testing):
        raise ValueError("Source/target leakage or missing partition")
    audit = FitAudit()
    selected = {}
    tried = []
    for model in models:
        if p["normalization"] == "center_only" and model in ("multiband_lr", "tangent_lr"):
            # Source search must use the same prespecified normalization as final fitting.
            # Reuse the existing source CV with the override included in every candidate.
            chosen, rows = select_centered(bank, model, p, training, testing, audit, labels)
        else:
            chosen, rows = choose_parameters(bank, model, p, training, testing, audit, labels)
        selected[model] = chosen
        tried.extend(rows)
    return selected, audit, tried


def select_centered(
    bank: FeatureBank,
    model: str,
    p: dict[str, Any],
    training: Any,
    testing: Any,
    audit: FitAudit,
    labels: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from soma.decoding.models import parameter_grid
    from soma.decoding.splits import inner_splits

    y = bank.dataset.y if labels is None else np.asarray(labels)
    rows: list[dict[str, Any]] = []
    for params in parameter_grid(model, p, True):
        params = {**params, "scale__with_std": False}
        scores = []
        for fold in inner_splits(bank.dataset, training, p["inner_subject_folds"]):
            if np.intersect1d(testing, np.r_[fold.train, fold.test]).size:
                raise ValueError("Target entered selection")
            _, pred, _, _ = fit_fold(bank, model, p, fold, params, audit, phase="inner", labels=y)
            for subject in bank.dataset.metadata.iloc[fold.test].subject.unique():
                mask = bank.dataset.metadata.iloc[fold.test].subject.to_numpy() == subject
                scores.append(
                    classification_metrics(y[fold.test][mask], pred[mask])["balanced_accuracy"]
                )
        rows.append(
            {
                "model": model,
                "params": params,
                "mean_subject_balanced_accuracy": float(np.mean(scores)),
                "n_subject_scores": len(scores),
                "errors": [],
            }
        )
    return dict(max(rows, key=lambda r: r["mean_subject_balanced_accuracy"])["params"]), rows


def folds(
    dataset: TrialDataset, p: dict[str, Any], sources: list[int], targets: list[int], mode: str
) -> list[Fold]:
    frame = dataset.metadata
    result = []
    if set(sources) & set(targets):
        raise ValueError("Subject-disjoint transfer required")
    if mode == "cross-subject":
        result = [
            Fold(
                "zero-shot",
                np.flatnonzero(frame.subject.isin(sources)),
                np.flatnonzero(frame.subject.isin(targets) & frame.run.isin(p["evaluation_runs"])),
                mode,
            )
        ]
    elif mode == "within-subject":
        for subject in targets:
            for run in p["evaluation_runs"]:
                result.append(
                    Fold(
                        f"S{subject:03}-R{run:02}",
                        np.flatnonzero((frame.subject == subject) & (frame.run != run)),
                        np.flatnonzero((frame.subject == subject) & (frame.run == run)),
                        mode,
                    )
                )
    else:
        raise ValueError("Unknown benchmark mode")
    for fold in result:
        validate_split(dataset, fold)
    return result


def native(
    record: dict[str, Any], output: Path, *, computation: str = "eeg-benchmark-cell"
) -> None:
    e = create_result(
        "experiment.manifest",
        {
            "computation": computation,
            "inputs": {},
            "environment": environment_snapshot(),
            "assumptions": ["subject-level descriptive analysis"],
            "validation": {"scope": "frozen benchmark"},
            "limitations": ["historically reused data; no confirmatory or clinical claim"],
        },
        values=record,
        provenance={},
        method={"id": "soma.eeg.benchmark", "version": "1"},
        parameters={},
        units={},
        dataset_identity="eegmmidb-1.0.0",
        subject_identity=None,
        statistical_estimand="equal target subject/run balanced accuracy",
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(e, {}, output)


def read_native(path: Path) -> dict[str, Any]:
    e = inspect_result(path)["envelope"]
    if e["method"] != {"id": "soma.eeg.benchmark", "version": "1"} or e["payload"]["arrays"]:
        raise ValueError("Not a metadata-only benchmark receipt")
    return dict(e["payload"]["values"])


def evaluate(
    bank: FeatureBank,
    p: dict[str, Any],
    sources: list[int],
    targets: list[int],
    selected: dict[str, dict[str, Any]],
    output: Path,
    protocol_fingerprint: str,
    *,
    labels: Any = None,
    modes: tuple[str, ...] = ("within-subject", "cross-subject"),
    models: tuple[str, ...] = MODELS,
) -> tuple[pd.DataFrame, list[dict[str, Any]], FitAudit]:
    dataset = bank.dataset
    y = dataset.y if labels is None else np.asarray(labels)
    if y.shape != dataset.y.shape or set(np.unique(y)) != {0, 1}:
        raise ValueError("Invalid analysis labels")
    audit = FitAudit()
    rows = []
    cells = []
    data_fingerprint = dataset.fingerprint
    software = identity()
    label_fingerprint = digest(y.tolist())
    for mode in modes:
        for fold in folds(dataset, p, sources, targets, mode):
            for model in models:
                key = digest(
                    {
                        "protocol": protocol_fingerprint,
                        "data": data_fingerprint,
                        "configuration": p,
                        "labels": label_fingerprint,
                        "model": model,
                        "fold": {"train": fold.train.tolist(), "test": fold.test.tolist()},
                        "parameters": selected.get(model, {}),
                        "software": software,
                    }
                )
                destination = output / "cells" / key
                if (destination / "result.json").exists():
                    cell = read_native(destination / "result.json")
                    if cell["identity"] != key:
                        raise ValueError("Corrupted or incompatible cached cell")
                else:
                    tick = time.perf_counter()
                    try:
                        if model == "dummy":
                            validate_split(dataset, fold)
                            prior = float(y[fold.train].mean())
                            prediction = np.full(len(fold.test), int(prior > 0.5))
                            score = np.full(len(fold.test), prior)
                            probability = score
                        else:
                            params = selected[model]
                            _, prediction, score, probability = fit_fold(
                                bank, model, p, fold, params, audit, phase="outer", labels=y
                            )
                        predictions = []
                        for j, index in enumerate(fold.test):
                            row = dataset.metadata.iloc[index]
                            predictions.append(
                                {
                                    "subject": int(row.subject),
                                    "run": int(row.run),
                                    "trial_id": row.trial_id,
                                    "label": int(y[index]),
                                    "prediction": int(prediction[j]),
                                    "score": float(score[j]),
                                    "probability": float(probability[j])
                                    if probability is not None
                                    else None,
                                    "model": model,
                                    "mode": mode,
                                    "fold": fold.name,
                                }
                            )
                        cell = {
                            "identity": key,
                            "status": "COMPLETE",
                            "mode": mode,
                            "model": model,
                            "fold": fold.name,
                            "train_subjects": sorted(
                                map(int, dataset.metadata.iloc[fold.train].subject.unique())
                            ),
                            "test_subjects": sorted(
                                map(int, dataset.metadata.iloc[fold.test].subject.unique())
                            ),
                            "train_trial_ids": dataset.metadata.iloc[fold.train].trial_id.tolist(),
                            "test_trial_ids": dataset.metadata.iloc[fold.test].trial_id.tolist(),
                            "parameters": selected.get(model, {}),
                            "predictions": predictions,
                            "seconds": time.perf_counter() - tick,
                        }
                    except (ValueError, RuntimeError, KeyError) as exc:
                        cell = {
                            "identity": key,
                            "status": "FAILED",
                            "mode": mode,
                            "model": model,
                            "fold": fold.name,
                            "predictions": [],
                            "reason": type(exc).__name__ + ": " + str(exc),
                            "seconds": time.perf_counter() - tick,
                        }
                    native(cell, destination)
                cells.append(cell)
                rows.extend(cell["predictions"])
    return pd.DataFrame(rows), cells, audit


def adaptation(
    bank: FeatureBank,
    p: dict[str, Any],
    sources: list[int],
    targets: list[int],
    selected: dict[str, dict[str, Any]],
) -> tuple[pd.DataFrame, list[dict[str, Any]], FitAudit]:
    dataset = bank.dataset
    frame = dataset.metadata
    audit = FitAudit()
    rows = []
    cells = []
    for subject in targets:
        test = np.flatnonzero(
            (frame.subject == subject) & frame.run.isin(p["adaptation_test_runs"])
        )
        calibration = frame[
            (frame.subject == subject) & (frame.run == p["adaptation_run"])
        ].sort_values("start_sample")
        for count in p["adaptation_counts"]:
            for model in p["adaptation_models"]:
                try:
                    ids = [
                        i
                        for label in (0, 1)
                        for i in calibration[calibration.label == label].index[: count // 2]
                    ]
                    if len(ids) != count or not len(test):
                        raise ValueError("Insufficient fixed adaptation/evaluation data")
                    if np.intersect1d(ids, test).size:
                        raise ValueError("Adaptation/test contamination")
                    train = np.r_[
                        np.flatnonzero(frame.subject.isin(sources)), np.asarray(ids, dtype=np.int64)
                    ]
                    fold = Fold(f"adapt-S{subject:03}-k{count}", train, test, "adaptation")
                    _, pred, score, proba = fit_fold(
                        bank, model, p, fold, selected[model], audit, phase="adaptation"
                    )
                    for j, index in enumerate(test):
                        row = frame.iloc[index]
                        rows.append(
                            {
                                "subject": subject,
                                "run": int(row.run),
                                "trial_id": row.trial_id,
                                "label": int(dataset.y[index]),
                                "prediction": int(pred[j]),
                                "score": float(score[j]),
                                "probability": float(proba[j]) if proba is not None else None,
                                "model": model,
                                "mode": "adaptation",
                                "fold": fold.name,
                                "calibration_trials": count,
                            }
                        )
                    cells.append(
                        {
                            "subject": subject,
                            "model": model,
                            "calibration_trials": count,
                            "status": "COMPLETE",
                            "adaptation_trial_ids": frame.iloc[ids].trial_id.tolist(),
                            "test_trial_ids": frame.iloc[test].trial_id.tolist(),
                        }
                    )
                except (ValueError, RuntimeError) as exc:
                    cells.append(
                        {
                            "subject": subject,
                            "model": model,
                            "calibration_trials": count,
                            "status": "FAILED",
                            "reason": str(exc),
                        }
                    )
    return pd.DataFrame(rows), cells, audit
