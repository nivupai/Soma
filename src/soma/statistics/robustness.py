"""Influence diagnostics and explicitly distinct weighting targets."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.core.provenance import manifest
from soma.simulations.calibration import atomic_json
from soma.statistics.inference import robust_locations

KEYS = ["channel", "band", "outcome", "units"]


def current_generation(path: Path) -> Path:
    if not (path / "current.json").exists():
        return path
    import json

    relative = Path(json.loads((path / "current.json").read_text())["generation"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Generation pointer must stay inside its experiment directory")
    return path / relative


def influence_tables(
    subjects: pd.DataFrame, runs: pd.DataFrame, minimum_paired_runs: int = 1, trim: float = 0.2
) -> dict[str, pd.DataFrame]:
    subject_rows, run_rows, locations = [], [], []
    for key, frame in subjects.groupby(KEYS, sort=True):
        data = frame[np.isfinite(frame.contrast)].copy()
        if data.subject.duplicated().any():
            raise ValueError("Influence requires unique subject/outcome rows")
        values = data.contrast.to_numpy(float)
        identity = dict(zip(KEYS, key, strict=True))
        root = float(values.mean()) if len(values) else np.nan
        locations.append(
            {
                **identity,
                **robust_locations(values, trim),
                "fraction_positive": float(np.mean(values > 0)) if len(values) else np.nan,
                "fraction_negative": float(np.mean(values < 0)) if len(values) else np.nan,
                "run_pair_rule": minimum_paired_runs,
            }
        )
        if not len(values):
            continue
        sem = float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else np.nan
        group_runs = runs.copy()
        for name, value in identity.items():
            group_runs = group_runs[group_runs[name] == value]
        for row in data.to_dict("records"):
            subject = int(row["subject"])
            rest = data[data.subject != subject].contrast.to_numpy(float)
            estimate = float(np.mean(rest)) if len(rest) else np.nan
            delta = estimate - root
            subject_rows.append(
                {
                    **identity,
                    "excluded_subject": subject,
                    "n_remaining": len(rest),
                    "primary_estimate": root,
                    "estimate": estimate,
                    "change": delta,
                    "absolute_change": abs(delta),
                    "change_over_subject_sem": delta / sem if sem > 0 else np.nan,
                    "sign_agrees": bool(np.sign(estimate) == np.sign(root))
                    if np.isfinite(estimate)
                    else None,
                }
            )
            subject_runs = group_runs[(group_runs.subject == subject) & group_runs.contrast.notna()]
            for run in subject_runs.run:
                remaining = subject_runs[subject_runs.run != run].contrast.to_numpy(float)
                eligible = len(remaining) >= minimum_paired_runs
                candidate = np.r_[rest, np.mean(remaining)] if eligible else rest
                changed = float(candidate.mean()) if len(candidate) else np.nan
                run_rows.append(
                    {
                        **identity,
                        "excluded_subject": subject,
                        "excluded_run": int(run),
                        "remaining_subject_runs": len(remaining),
                        "subject_still_eligible": eligible,
                        "n_subjects": len(candidate),
                        "primary_estimate": root,
                        "estimate": changed,
                        "change": changed - root,
                        "absolute_change": abs(changed - root),
                    }
                )
    leave_subject = pd.DataFrame(
        subject_rows,
        columns=[
            *KEYS,
            "excluded_subject",
            "n_remaining",
            "primary_estimate",
            "estimate",
            "change",
            "absolute_change",
            "change_over_subject_sem",
            "sign_agrees",
        ],
    )
    leave_subject["influence_rank"] = pd.Series(dtype=float)
    if not leave_subject.empty:
        leave_subject["influence_rank"] = leave_subject.groupby(KEYS).absolute_change.rank(
            method="min", ascending=False
        )
    return {
        "leave_one_subject_out": leave_subject,
        "leave_one_run_out": pd.DataFrame(
            run_rows,
            columns=[
                *KEYS,
                "excluded_subject",
                "excluded_run",
                "remaining_subject_runs",
                "subject_still_eligible",
                "n_subjects",
                "primary_estimate",
                "estimate",
                "change",
                "absolute_change",
            ],
        ),
        "robust_locations": pd.DataFrame(locations),
    }


def weighting_summaries(
    features: pd.DataFrame, subjects: pd.DataFrame, runs: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    for (channel, band), frame in features[features.kind == "imagery"].groupby(["channel", "band"]):
        valid_subjects = subjects[
            (subjects.channel == channel)
            & (subjects.band == band)
            & (subjects.outcome == "log_absolute_power")
            & subjects.contrast.notna()
        ]
        allowed = set(valid_subjects.subject)
        trial = frame[frame.subject.isin(allowed)].copy()
        trial["value"] = np.log(trial.absolute_power_v2.where(trial.absolute_power_v2 > 0))
        condition = trial.groupby("condition").value.mean()
        run = runs[
            (runs.channel == channel)
            & (runs.band == band)
            & (runs.outcome == "log_absolute_power")
            & runs.subject.isin(allowed)
        ]
        means = {
            "subject_balanced": float(valid_subjects.contrast.mean()),
            "observed_run_weighted": float(run.contrast.mean()),
            "observed_trial_weighted": float(
                condition.get("left hand imagery", np.nan)
                - condition.get("right hand imagery", np.nan)
            ),
        }
        for label, value in means.items():
            rows.append(
                {
                    "channel": channel,
                    "band": band,
                    "estimand": label,
                    "estimate": value,
                    "n_subjects": len(allowed),
                    "n_observed_runs": int(run.contrast.notna().sum()),
                    "n_trials": len(trial),
                    "population_sampling_unit": "subject",
                    "interpretation": (
                        "different observed-data weighting targets; trial count is not population n"
                    ),
                }
            )
    return pd.DataFrame(rows)


def run_influence(
    input_path: Path, output: Path, minimum_paired_runs: int | None = None
) -> dict[str, Any]:
    folder = current_generation(input_path)
    if minimum_paired_runs is None:
        import json

        saved = json.loads((folder / "manifest.json").read_text())
        minimum_paired_runs = (
            saved.get("parameters", {}).get("eligibility", {}).get("minimum_paired_runs", 1)
        )
    if minimum_paired_runs < 1:
        raise ValueError("minimum_paired_runs must be positive")
    output.mkdir(parents=True, exist_ok=False)
    subjects = pd.read_csv(folder / "subject_contrasts.csv")
    runs = pd.read_csv(folder / "run_contrasts.csv")
    tables = influence_tables(subjects, runs, minimum_paired_runs)
    for name, table in tables.items():
        table.to_csv(output / (name + ".csv"), index=False)
    if (folder / "features.csv").exists():
        weighting_summaries(pd.read_csv(folder / "features.csv"), subjects, runs).to_csv(
            output / "weighting_summary.csv", index=False
        )
    atomic_json(
        output / "manifest.json",
        manifest(
            {"dataset": "saved-subject-run-effects"},
            {"minimum_paired_runs": minimum_paired_runs, "trim": 0.2},
            {"input": str(folder.resolve()), "output": str(output.resolve())},
        ),
    )
    from soma.visualization.replication import plot_influence

    plot_influence(output)
    return {"status": "complete", "input": str(folder), "output": str(output)}
