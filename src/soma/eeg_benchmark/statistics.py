"""Subject-cluster uncertainty and explicitly conditional, nonconfirmatory null diagnostics."""

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import beta, rankdata

from soma.decoding.metrics import classification_metrics
from soma.eeg_benchmark.protocol import MODELS


def subject_table(
    predictions: pd.DataFrame,
    targets: list[int],
    runs: list[int],
    modes: tuple[str, ...] = ("within-subject", "cross-subject"),
) -> list[dict[str, Any]]:
    rows = []
    for mode in modes:
        for model in MODELS:
            for subject in targets:
                selected = (
                    predictions[
                        (predictions["mode"] == mode)
                        & (predictions.model == model)
                        & (predictions.subject == subject)
                    ]
                    if len(predictions)
                    else pd.DataFrame()
                )
                metrics = []
                for run in runs:
                    frame = selected[selected.run == run] if len(selected) else pd.DataFrame()
                    if not len(frame):
                        continue
                    if frame.trial_id.duplicated().any():
                        raise ValueError("Repeated evaluation trials")
                    proba = (
                        frame.probability.to_numpy(float)
                        if frame.probability.notna().all()
                        else None
                    )
                    metrics.append(
                        classification_metrics(frame.label, frame.prediction, frame.score, proba)
                    )
                complete = len(metrics) == len(runs) and all(
                    m["metric_status"] == "ok" for m in metrics
                )
                result = {
                    "subject": subject,
                    "model": model,
                    "mode": mode,
                    "status": "COMPLETE" if complete else "MISSING_OR_FAILED",
                    "n_runs": len(metrics),
                    "n_trials": sum(m["n_trials"] for m in metrics),
                }
                for metric in [
                    "balanced_accuracy",
                    "accuracy",
                    "sensitivity",
                    "specificity",
                    "roc_auc",
                    "brier",
                    "log_loss",
                ]:
                    values = [float(m[metric]) for m in metrics]
                    result[metric] = (
                        float(np.mean(values)) if complete and np.isfinite(values).all() else None
                    )
                result["confusion"] = [
                    [sum(m["tn"] for m in metrics), sum(m["fp"] for m in metrics)],
                    [sum(m["fn"] for m in metrics), sum(m["tp"] for m in metrics)],
                ]
                rows.append(result)
    return rows


def bootstrap(values: Any, *, seed: int = 22042, resamples: int = 1999) -> dict[str, Any]:
    x = np.asarray(values, float)
    if x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all() or resamples < 99:
        raise ValueError("Finite independent subject scores and >=99 resamples required")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(x), size=(resamples, len(x)))
    estimates = x[indices].mean(axis=1)
    lo, hi = np.quantile(estimates, [0.025, 0.975])
    return {
        "mean": float(x.mean()),
        "median": float(np.median(x)),
        "lower": float(lo),
        "upper": float(hi),
        "n_subjects": len(x),
        "resamples": resamples,
        "unit": "subject",
        "confidence": 0.95,
        "assumptions": (
            "conditional on fitted source; fixed sampled coho"
            "rt; pointwise, not training-population refitting"
        ),
    }


def summarize(rows: list[dict[str, Any]], p: dict[str, Any]) -> dict[str, Any]:
    result = []
    pairs = []
    influence = []
    frame = pd.DataFrame(rows)
    for mode in sorted(frame["mode"].unique()):
        for model in MODELS:
            subset = frame[(frame["mode"] == mode) & (frame.model == model)]
            valid = subset[subset.status == "COMPLETE"]
            b = (
                bootstrap(
                    valid.balanced_accuracy, seed=p["seed"], resamples=p["bootstrap_resamples"]
                )
                if len(valid) >= 2
                else None
            )
            metrics = {
                metric: float(valid[metric].mean())
                if len(valid) and valid[metric].notna().all()
                else None
                for metric in [
                    "accuracy",
                    "sensitivity",
                    "specificity",
                    "roc_auc",
                    "brier",
                    "log_loss",
                ]
            }
            confusion = (
                np.sum(np.asarray(valid.confusion.tolist(), int), axis=0).tolist()
                if len(valid)
                else [[0, 0], [0, 0]]
            )
            result.append(
                {
                    "mode": mode,
                    "model": model,
                    "planned_subjects": len(subset),
                    "complete_subjects": len(valid),
                    "missing_subjects": len(subset) - len(valid),
                    "balanced_accuracy": b,
                    "metrics": metrics,
                    "confusion": confusion,
                    "subject_distribution": np.histogram(
                        valid.balanced_accuracy, bins=np.linspace(0, 1, 11)
                    )[0].tolist(),
                    "distribution_bin_edges": np.linspace(0, 1, 11).tolist(),
                    "status": "COMPLETE" if len(valid) == len(subset) else "PARTIAL",
                }
            )
        wide = frame[(frame["mode"] == mode) & (frame.status == "COMPLETE")].pivot(
            index="subject", columns="model", values="balanced_accuracy"
        )
        complete = wide.dropna()
        if len(complete):
            ranks = np.asarray(
                [rankdata(-row, method="average") for row in complete[list(MODELS)].to_numpy()]
            )
            for j, model in enumerate(MODELS):
                pairs.append(
                    {
                        "mode": mode,
                        "model": model,
                        "mean_subject_rank": float(ranks[:, j].mean()),
                        "n_matched_subjects": len(complete),
                        "interpretation": "descriptive tied ranks; no superiority claim",
                    }
                )
        for index, first in enumerate(MODELS[1:], start=1):
            for second in MODELS[:index]:
                if first not in wide or second not in wide:
                    continue
                difference = (wide[first] - wide[second]).dropna().to_numpy(float)
                if len(difference) >= 2:
                    pairs.append(
                        {
                            "mode": mode,
                            "first": first,
                            "second": second,
                            "difference": bootstrap(
                                difference, seed=p["seed"], resamples=p["bootstrap_resamples"]
                            ),
                            "p_value": None,
                            "multiplicity": (
                                "ten exploratory paired contrasts per mode; "
                                "pointwise intervals only"
                            ),
                        }
                    )
        for model in MODELS:
            x = frame[
                (frame["mode"] == mode) & (frame.model == model) & (frame.status == "COMPLETE")
            ].balanced_accuracy.to_numpy(float)
            if len(x) >= 3:
                delta = [float(np.delete(x, i).mean() - x.mean()) for i in range(len(x))]
                influence.append(
                    {
                        "mode": mode,
                        "model": model,
                        "maximum_absolute_mean_change": float(np.max(np.abs(delta))),
                        "method": (
                            "leave one evaluation subject out of aggregation; no training refit"
                        ),
                    }
                )
    return {
        "methods": result,
        "comparisons": pairs,
        "subject_inclusion_influence": influence,
        "confirmatory_claim_allowed": False,
        "external_replication": False,
        "interpretation": "historically reused EEGBCI; conditional subject uncertainty",
    }


def permuted_labels(labels: Any, metadata: pd.DataFrame, seed: int) -> np.ndarray[Any, Any]:
    result = np.asarray(labels).copy()
    rng = np.random.default_rng(seed)
    if result.shape != (len(metadata),) or not np.isin(result, [0, 1]).all():
        raise ValueError("Binary identified labels required")
    for indices in metadata.groupby(["subject", "run"], sort=True).indices.values():
        result[indices] = rng.permutation(result[indices])
    return result


def null_diagnostic(
    observed: float, values: list[float], *, exchangeability_attested: bool = False
) -> dict[str, Any]:
    x = np.asarray(values, float)
    if not len(x) or not np.isfinite(x).all():
        raise ValueError("Complete finite permutation diagnostics required")
    count = int(np.sum(x >= observed))
    n = len(x)
    return {
        "null_hypothesis": (
            "no label-signal association conditional on within-subject/run class counts"
        ),
        "scheme": (
            "labels shuffled independently within subject"
            " and run; source selection and model refitted"
        ),
        "permutations": n,
        "test_statistic": "equal target-subject/run mean balanced accuracy",
        "observed": observed,
        "null_mean": float(x.mean()),
        "null_range": [float(x.min()), float(x.max())],
        "exceedances": count,
        "empirical_tail_fraction": float((count + 1) / (n + 1)),
        "monte_carlo_exceedance_interval": [
            float(beta.ppf(0.025, count, n - count + 1)) if count else 0.0,
            float(beta.ppf(0.975, count + 1, n - count)) if count < n else 1.0,
        ],
        "p_value": float((count + 1) / (n + 1)) if exchangeability_attested else None,
        "exchangeability_attested": exchangeability_attested,
        "multiplicity": (
            "two prespecified exploratory diagnostics; no n"
            "ominal human p-values or significance decisions"
        ),
        "limitations": [
            "temporal exchangeability of real instructed imagery trials not established",
            (
                "Monte Carlo interval quantifies diagnostic exc"
                "eedance rate, not biological effect uncertainty"
            ),
        ],
    }
