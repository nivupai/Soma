"""Binary metrics with explicit positive class and subject-level comparison units."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    roc_auc_score,
)

from soma.statistics.hierarchical import holm, sign_flip_pvalue
from soma.statistics.inference import InferenceConfig, infer_mean


def classification_metrics(
    y: Any, prediction: Any, score: Any = None, probability: Any = None
) -> dict[str, Any]:
    y, prediction = np.asarray(y), np.asarray(prediction)
    if y.shape != prediction.shape or y.ndim != 1 or not len(y) or not np.isin(y, [0, 1]).all():
        raise ValueError("Aligned binary labels/predictions required")
    tn, fp, fn, tp = confusion_matrix(y, prediction, labels=[0, 1]).ravel()
    both = len(np.unique(y)) == 2
    result = {
        "n_trials": len(y),
        "n_left": int(np.sum(y == 0)),
        "n_right": int(np.sum(y == 1)),
        "positive_class": "right_hand_imagery",
        "accuracy": float(accuracy_score(y, prediction)),
        "balanced_accuracy": float(balanced_accuracy_score(y, prediction)) if both else np.nan,
        "sensitivity": float(tp / (tp + fn)) if tp + fn else np.nan,
        "specificity": float(tn / (tn + fp)) if tn + fp else np.nan,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "roc_auc": float(roc_auc_score(y, score)) if score is not None and both else np.nan,
        "brier": float(brier_score_loss(y, probability)) if probability is not None else np.nan,
        "log_loss": float(
            log_loss(y, np.column_stack([1 - probability, probability]), labels=[0, 1])
        )
        if probability is not None
        else np.nan,
        "metric_status": "ok" if both else "test_single_class",
    }
    return result


def subject_scores(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, subject, run, count), frame in predictions.groupby(
        ["model", "subject", "run", "calibration_trials"], sort=True
    ):
        probability = frame.probability.to_numpy(float) if frame.probability.notna().all() else None
        score = frame.score.to_numpy(float) if frame.score.notna().all() else None
        rows.append(
            {
                "model": model,
                "subject": subject,
                "run": run,
                "calibration_trials": count,
                **classification_metrics(frame.label, frame.prediction, score, probability),
            }
        )
    return pd.DataFrame(rows)


def compare_models(
    subjects: pd.DataFrame, protocol: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries, influence = [], []
    for count, group in subjects.groupby("calibration_trials"):
        mean = group.pivot_table(
            index=["subject", "run"], columns="model", values="balanced_accuracy"
        )
        for first, second in protocol["primary_comparisons"]:
            if first not in mean or second not in mean:
                continue
            paired = (mean[first] - mean[second]).dropna().groupby(level="subject").mean()
            x = paired.to_numpy(float)
            base = {
                "first": first,
                "second": second,
                "calibration_trials": int(str(count)),
                "n_matched_subjects": len(x),
            }
            config = InferenceConfig(
                confidence=protocol["confidence"],
                n_resamples=protocol["n_resamples"],
                seed=protocol["seed"],
            )
            for row in infer_mean(x, ("t", "percentile"), config):
                summaries.append(
                    {
                        **base,
                        **row,
                        "warnings": ";".join(row["warnings"]),
                        "p_sign_flip": sign_flip_pvalue(x, protocol["seed"], 19999)
                        if len(x) >= 2
                        else np.nan,
                    }
                )
            for subject in paired.index:
                rest = paired.drop(subject)
                influence.append(
                    {
                        **base,
                        "excluded_subject": int(subject),
                        "estimate": float(rest.mean()),
                        "change": float(rest.mean() - paired.mean()),
                    }
                )
    table = pd.DataFrame(summaries)
    if len(table):
        table["p_holm"] = np.nan
        for _key, indices in table.groupby(["calibration_trials", "method"]).groups.items():
            observed = table.loc[indices, "p_sign_flip"].to_numpy(float)
            family = np.r_[
                np.nan_to_num(observed, nan=1.0),
                np.ones(len(protocol["primary_comparisons"]) - len(observed)),
            ]
            corrected = holm(family)[: len(observed)]
            table.loc[indices, "p_holm"] = np.where(np.isfinite(observed), corrected, np.nan)
    return table, pd.DataFrame(influence)
