"""Subjects, not trials, are the independent resampling units."""

from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray


@dataclass(frozen=True)
class ResamplingConfig:
    seed: int = 42
    n_bootstrap: int = 2000
    confidence: float = 0.95
    sign_flip: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.n_bootstrap, int)
            or self.n_bootstrap < 100
            or not isinstance(self.seed, int)
            or self.seed < 0
            or not 0 < self.confidence < 1
        ):
            raise ValueError("Use at least 100 bootstrap draws and confidence in (0,1)")


DEFAULT_RESAMPLING = ResamplingConfig()


def subject_bootstrap(
    values: NDArray[np.float64], cfg: ResamplingConfig = DEFAULT_RESAMPLING
) -> dict[str, float | int | None]:
    """Percentile CI for the equal-subject mean; no CI for fewer than 2 subjects."""
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Bootstrap requires a finite 1D subject contrast vector")
    n = len(values)
    result: dict[str, float | int | None] = {
        "n_subjects": n,
        "estimate": float(np.mean(values)) if n else None,
        "ci_low": None,
        "ci_high": None,
        "sd_subjects": float(np.std(values, ddof=1)) if n > 1 else None,
    }
    if n < 2:
        return result
    rng = np.random.default_rng(cfg.seed)
    # Chunking bounds memory while preserving a reproducible subject-resampling sequence.
    samples = np.concatenate(
        [
            np.mean(values[rng.integers(0, n, (min(256, cfg.n_bootstrap - i), n))], axis=1)
            for i in range(0, cfg.n_bootstrap, 256)
        ]
    )
    alpha = (1 - cfg.confidence) / 2
    result.update(
        ci_low=float(np.quantile(samples, alpha)), ci_high=float(np.quantile(samples, 1 - alpha))
    )
    return result


def sign_flip_pvalue(
    values: NDArray[np.float64], seed: int = 42, n_permutations: int = 10000
) -> float:
    """Two-sided paired subject sign flips under symmetric independent null contrasts."""
    if values.ndim != 1 or not np.isfinite(values).all() or len(values) < 2:
        raise ValueError("Sign flips require >=2 finite independent subject contrasts")
    n = len(values)
    tolerance = (
        8 * np.finfo(float).eps * max(float(np.max(np.abs(values))), abs(float(np.mean(values))))
    )
    if n <= 16:
        signs = np.asarray(list(product((-1, 1), repeat=n)))
        null = np.abs(np.mean(signs * values, axis=1))
        return float(np.mean(null >= abs(np.mean(values)) - tolerance))
    if n_permutations < 100:
        raise ValueError("Use at least 100 sign-flip samples")
    signs = np.random.default_rng(seed).choice([-1, 1], (n_permutations, n))
    return float(
        (1 + np.sum(np.abs(np.mean(signs * values, axis=1)) >= abs(np.mean(values)) - tolerance))
        / (n_permutations + 1)
    )


def holm(pvalues: NDArray[np.float64]) -> NDArray[np.float64]:
    if pvalues.ndim != 1 or not np.isfinite(pvalues).all() or np.any((pvalues < 0) | (pvalues > 1)):
        raise ValueError("Holm correction requires finite p-values in [0,1]")
    order = np.argsort(pvalues)
    adjusted = np.maximum.accumulate(pvalues[order] * np.arange(len(pvalues), 0, -1))
    result = np.empty_like(pvalues)
    result[order] = np.minimum(adjusted, 1)
    return result


def subject_contrasts(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pair conditions within each run, then equally average complete run pairs per subject."""
    base_columns = ["subject", "run", "channel", "band", "outcome", "units", "contrast"]
    if features.empty:
        runs = pd.DataFrame(columns=base_columns)
        return runs, pd.DataFrame(
            columns=[
                "subject",
                "channel",
                "band",
                "outcome",
                "units",
                "contrast",
                "n_runs",
                "run_sd",
            ]
        )
    imagery = features[features.kind == "imagery"].copy()
    imagery["log_absolute_power"] = np.log(
        imagery.absolute_power_v2.where(imagery.absolute_power_v2 > 0)
    )
    outcomes = {
        "absolute_power_v2": "V^2",
        "log_absolute_power": "natural_log_ratio",
        "erd_percent": "percentage_points",
        "log_power_ratio": "natural_log_ratio",
    }
    frames = []
    for outcome, units in outcomes.items():
        means = (
            imagery.groupby(["subject", "run", "channel", "band", "condition"])[outcome]
            .mean()
            .unstack("condition")
        )
        left = means.get("left hand imagery", pd.Series(np.nan, index=means.index))
        right = means.get("right hand imagery", pd.Series(np.nan, index=means.index))
        frame = (left - right).rename("contrast").reset_index()
        frame["outcome"], frame["units"] = outcome, units
        frames.append(frame)
    runs = pd.concat(frames, ignore_index=True)[base_columns]
    subjects = (
        runs.groupby(["subject", "channel", "band", "outcome", "units"], dropna=False)
        .agg(
            contrast=("contrast", "mean"), n_runs=("contrast", "count"), run_sd=("contrast", "std")
        )
        .reset_index()
    )
    return runs, subjects


def population_summary(
    subjects: pd.DataFrame, cfg: ResamplingConfig = DEFAULT_RESAMPLING
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, exclusions = [], []
    for key, frame in subjects.groupby(["channel", "band", "outcome", "units"], sort=True):
        available = frame[np.isfinite(frame.contrast)].sort_values("subject")
        if available.subject.duplicated().any():
            raise ValueError("One contrast per subject/outcome is required before resampling")
        values = available.contrast.to_numpy(dtype=float)
        row = dict(zip(("channel", "band", "outcome", "units"), key, strict=True))
        row.update(subject_bootstrap(values, cfg))
        sd = float(np.std(values, ddof=1)) if len(values) > 1 else np.nan
        row["standardized_mean_contrast"] = float(np.mean(values) / sd) if sd > 0 else np.nan
        row.update(
            n_missing_subjects=int(len(frame) - len(available)),
            confidence=cfg.confidence,
            ci_method="percentile subject bootstrap",
            seed=cfg.seed,
        )
        row["p_sign_flip"] = (
            sign_flip_pvalue(values, cfg.seed) if cfg.sign_flip and len(values) >= 2 else np.nan
        )
        rows.append(row)
        for subject in available.subject:
            kept = available[available.subject != subject].contrast
            exclusions.append(
                {
                    **dict(zip(("channel", "band", "outcome", "units"), key, strict=True)),
                    "excluded_subject": int(subject),
                    "n_remaining": len(kept),
                    "estimate": float(kept.mean()) if len(kept) else np.nan,
                }
            )
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary["p_holm"] = np.nan
        valid = summary.p_sign_flip.notna()
        if valid.any():
            # One explicit family: every channel×band×outcome tested in this execution.
            summary.loc[valid, "p_holm"] = holm(summary.loc[valid, "p_sign_flip"].to_numpy(float))
    return summary, pd.DataFrame(exclusions)


def lateralization_contrasts(features: pd.DataFrame) -> pd.DataFrame:
    """Left-hand contra=C4, right-hand contra=C3; these are sensor-label conventions."""
    rows = []
    if features.empty:
        return pd.DataFrame(columns=["subject", "run", "band", "metric", "units", "value"])
    imagery = features[features.kind == "imagery"]
    grouped = imagery.groupby(
        ["subject", "run", "band", "condition", "channel"]
    ).absolute_power_v2.mean()
    for (subject, run, band), _frame in imagery.groupby(["subject", "run", "band"]):

        def power(
            condition: str,
            channel: str,
            subject_id: Any = subject,
            run_id: Any = run,
            band_name: Any = band,
        ) -> float:
            return float(grouped.get((subject_id, run_id, band_name, condition, channel), np.nan))

        l3, l4 = (power("left hand imagery", c) for c in ("C3", "C4"))
        r3, r4 = (power("right hand imagery", c) for c in ("C3", "C4"))
        values = {
            "left_contra_minus_ipsi": l4 - l3,
            "right_contra_minus_ipsi": r3 - r4,
            "condition_by_sensor_interaction": (l4 - l3) - (r4 - r3),
            "right_C4_minus_left_C3": r4 - l3,
        }
        for metric, value in values.items():
            rows.append(
                {
                    "subject": subject,
                    "run": run,
                    "band": band,
                    "metric": metric,
                    "units": "V^2",
                    "value": value,
                }
            )
        if min(l3, l4, r3, r4) > 0 and np.isfinite([l3, l4, r3, r4]).all():
            for metric, value in {
                "left_log_contra_over_ipsi": np.log(l4 / l3),
                "right_log_contra_over_ipsi": np.log(r3 / r4),
                "log_condition_by_sensor_interaction": np.log(l4 / l3) - np.log(r4 / r3),
            }.items():
                rows.append(
                    {
                        "subject": subject,
                        "run": run,
                        "band": band,
                        "metric": metric,
                        "units": "natural_log_ratio",
                        "value": float(value),
                    }
                )
    return pd.DataFrame(rows)


def burst_contrasts(summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Within-run paired burst contrasts, then equal-run subject means."""
    columns = ["subject", "run", "channel", "band", "outcome", "units", "contrast"]
    if summary.empty:
        return pd.DataFrame(columns=columns), pd.DataFrame(
            columns=[
                "subject",
                "channel",
                "band",
                "outcome",
                "units",
                "contrast",
                "n_runs",
                "run_sd",
            ]
        )
    metrics = {
        "occupancy": "fraction",
        "rate_hz": "Hz",
        "mean_complete_duration_s": "s",
        "mean_burst_amplitude_v": "V",
    }
    frames = []
    for strategy, data in summary.groupby("strategy"):
        for metric, units in metrics.items():
            means = data.pivot(
                index=["subject", "run", "channel", "band"], columns="condition", values=metric
            )
            left = means.get("left hand imagery", pd.Series(np.nan, index=means.index))
            right = means.get("right hand imagery", pd.Series(np.nan, index=means.index))
            frame = (left - right).rename("contrast").reset_index()
            frame["outcome"] = f"burst_{strategy}_{metric}"
            frame["units"] = units
            frames.append(frame)
    runs = pd.concat(frames, ignore_index=True)[columns]
    subjects = (
        runs.groupby(["subject", "channel", "band", "outcome", "units"])
        .agg(
            contrast=("contrast", "mean"), n_runs=("contrast", "count"), run_sd=("contrast", "std")
        )
        .reset_index()
    )
    return runs, subjects
