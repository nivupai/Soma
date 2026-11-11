"""Leakage-safe fixed-parameter evaluation and observable shift; no new classifier."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.decoding.data import TrialDataset
from soma.decoding.metrics import classification_metrics
from soma.decoding.models import make_pipeline, require_unfitted
from soma.decoding.riemannian import riemannian_distance, riemannian_mean
from soma.eeg_benchmark.evaluation import bank
from soma.eeg_benchmark.protocol import MODELS
from soma.eeg_benchmark.statistics import bootstrap
from soma.external_eeg.contracts import parameters, validate_plan
from soma.external_eeg.models import freeze, predict
from soma.workflow.model import digest


def split_indices(data: TrialDataset, p: dict[str, Any]) -> tuple[Any, Any]:
    validate_plan(p)
    frame = data.metadata
    if "session" not in frame:
        raise ValueError("Actual session identity required")
    if not frame.session.isin(p["sessions"]).all() or not frame.subject.isin(p["subjects"]).all():
        raise ValueError("Wrong dataset-scoped subject/session pairing")
    for row in frame.itertuples():
        prefix = f"{data.provenance.get('dataset')}/s{row.subject:02}/{row.session}/r{row.run}"
        if row.recording != prefix or not str(row.trial_id).startswith(prefix + "/t"):
            raise ValueError("Wrong subject/session/recording pairing")
    train = np.flatnonzero(
        frame.subject.isin(p["source_subjects"]) & frame.session.isin(p["source_sessions"])
    )
    test = np.flatnonzero(
        frame.subject.isin(p["target_subjects"]) & frame.session.isin(p["target_sessions"])
    )
    if not len(train) or not len(test) or np.intersect1d(train, test).size:
        raise ValueError("Calibration/test or train/test overlap")
    if p["split"] == "subject" and set(frame.iloc[train].subject) & set(frame.iloc[test].subject):
        raise ValueError("Subject leakage")
    if p["split"] == "session":
        if set(frame.iloc[train].session) & set(frame.iloc[test].session):
            raise ValueError("Session leakage")
        if set(frame.iloc[train].subject) != set(frame.iloc[test].subject):
            raise ValueError("Unpaired cross-session subjects")
    if set(data.y[train]) != {0, 1}:
        raise ValueError("Both training classes required")
    return train, test


def shift(data: TrialDataset, train: Any, test: Any) -> dict[str, Any]:
    f = bank(data, parameters())
    reference = riemannian_mean(f.covariances[train])

    def unit_average(indices: Any) -> dict[str, float]:
        rows = []
        for subject in sorted(set(data.metadata.iloc[indices].subject)):
            ix = np.asarray(indices)[data.metadata.iloc[indices].subject.to_numpy() == subject]
            rows.append(
                {
                    "rms_uV": float(np.sqrt(np.mean(data.X[ix] ** 2)) * 1e6),
                    "log_band_power": float(f.logpowers[ix].mean()),
                    "distance_to_source_covariance_mean": float(
                        np.mean([riemannian_distance(c, reference) for c in f.covariances[ix]])
                    ),
                    "right_fraction": float(data.y[ix].mean()),
                }
            )
        return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}

    return {
        "status": "OBSERVED",
        "source": unit_average(train),
        "target": unit_average(test),
        "reference_fitted_on": "source-only",
        "unit": "equal participant weights",
        "interpretation": "observable shift; no physiological or causal attribution",
    }


def evaluate(
    data: TrialDataset,
    p: dict[str, Any],
    output: Path,
    *,
    synthetic: bool,
    model_paths: dict[str, tuple[Path, str]] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    expected_dataset = "synthetic-external-v1" if synthetic else "bnci2014-001"
    if data.provenance.get("dataset") != expected_dataset:
        raise ValueError("Dataset identity or synthetic/human scope mismatch")
    train, test = split_indices(data, p)
    f = bank(data, parameters())
    frame = data.metadata
    contract = data.provenance.get("contract", p["target_contract"])
    output.mkdir(parents=True, exist_ok=True)
    models = {}
    predictions = []
    summary = []
    for model in MODELS:
        if p["mode"] == "EXTERNAL_REFIT":
            pipeline = None
            prior = float(data.y[train].mean())
            if model != "dummy":
                pipeline = make_pipeline(
                    model, parameters(), p["parameters"][model], precomputed_covariance=True
                )
                require_unfitted(pipeline)
                pipeline.fit(f.input(model)[train], data.y[train])
            identity = freeze(
                pipeline,
                model,
                contract,
                {
                    "origin": "SYNTHETIC_SOURCE_FIT" if synthetic else "EXTERNAL_SOURCE_REFIT",
                    "source_membership": digest(frame.iloc[train].trial_id.tolist()),
                    "source_labels": digest(data.y[train].tolist()),
                    "source_X_sha256": __import__("hashlib")
                    .sha256(data.X[train].tobytes())
                    .hexdigest(),
                    "source_dataset": "fictional-external" if synthetic else "bnci2014-001",
                    "parameters": p["parameters"][model],
                },
                output / model,
                prior=prior,
            )
            path = output / model / "result.json"
        else:
            if not model_paths or model not in model_paths:
                raise ValueError("Frozen model missing; no implicit refitting")
            path, identity = model_paths[model]
        models[model] = identity
        pred, score, proba = predict(
            path, identity, contract, data.X[test], f.logpowers[test], f.covariances[test]
        )
        rows = []
        for subject in p["target_subjects"]:
            subset = np.flatnonzero(frame.iloc[test].subject.to_numpy() == subject)
            groups = []
            for session in p["target_sessions"]:
                for run in p["runs"]:
                    ix = subset[
                        (frame.iloc[test].iloc[subset].session.to_numpy() == session)
                        & (frame.iloc[test].iloc[subset].run.to_numpy() == run)
                    ]
                    if len(ix) and set(data.y[test][ix]) == {0, 1}:
                        m = classification_metrics(
                            data.y[test][ix],
                            pred[ix],
                            score[ix],
                            None if proba is None else proba[ix],
                        )
                        groups.append(m)
            complete = len(groups) == len(p["target_sessions"]) * len(p["runs"])
            row = {
                "subject": subject,
                "model": model,
                "status": "COMPLETE" if complete else "MISSING",
                "balanced_accuracy": float(np.mean([m["balanced_accuracy"] for m in groups]))
                if complete
                else None,
            }
            rows.append(row)
        values = [r["balanced_accuracy"] for r in rows if r["status"] == "COMPLETE"]
        metrics = classification_metrics(data.y[test], pred, score, proba)
        summary.append(
            {
                "model": model,
                "planned_subjects": len(rows),
                "complete_subjects": len(values),
                "missing_subjects": len(rows) - len(values),
                "balanced_accuracy": bootstrap(values, seed=p["seed"], resamples=1999)
                if len(values) >= 2
                else None,
                "confusion": [[metrics["tn"], metrics["fp"]], [metrics["fn"], metrics["tp"]]],
                "right_recall": metrics["sensitivity"],
                "left_recall": metrics["specificity"],
                "brier": float(metrics["brier"]) if np.isfinite(metrics["brier"]) else None,
                "log_loss": float(metrics["log_loss"])
                if np.isfinite(metrics["log_loss"])
                else None,
                "trial_weighting": (
                    "confusion/recall/probability metrics pooled; BA equal subject/session/run"
                ),
            }
        )
        (output / f"{model}-subjects.local.json").write_text(
            __import__("json").dumps(rows, indent=2)
        )
        for j, index in enumerate(test):
            predictions.append(
                {
                    "trial_id": frame.iloc[index].trial_id,
                    "model": model,
                    "label": int(data.y[index]),
                    "prediction": int(pred[j]),
                    "score": float(score[j]),
                    "probability": None if proba is None else float(proba[j]),
                }
            )
    return {
        "status": "COMPLETE" if all(m["missing_subjects"] == 0 for m in summary) else "PARTIAL",
        "mode": p["mode"],
        "split": p["split"],
        "synthetic": synthetic,
        "original_m22_model": False,
        "models": models,
        "performance": summary,
        "source_trials": len(train),
        "target_trials": len(test),
        "source_subjects": len(set(frame.iloc[train].subject)),
        "target_subjects": len(set(frame.iloc[test].subject)),
        "domain_shift": shift(data, train, test),
        "p_value": None,
        "confirmatory_claim_allowed": False,
        "independent_external_replication": False,
        "leakage": {
            "subject_disjoint": p["split"] == "subject",
            "session_disjoint": p["split"] == "session",
            "target_labels_used_for_fitting": False,
            "hyperparameter_search": False,
            "calibration": "NONE",
        },
    }, pd.DataFrame(predictions)
