"""Predeclared one-factor-at-a-time comparisons; never select a best-looking result."""

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.core.provenance import manifest, output_directory, write_json
from soma.experiments.cache import canonical_id, software_identity
from soma.experiments.cohort import run_cohort
from soma.experiments.config import CohortConfig, config_from_dict, scientific_dict


def sensitivity_design(primary: CohortConfig) -> dict[str, tuple[str, CohortConfig]]:
    """Ten fixed configurations; each comparator changes one scientific factor."""
    motor = primary.motor
    qc = motor.quality
    return {
        "primary": ("prespecified primary", primary),
        "reference_none": (
            "reference only: acquisition reference",
            replace(
                primary,
                motor=replace(
                    motor,
                    preprocessing=replace(
                        motor.preprocessing, reference="none", reference_channels=()
                    ),
                ),
            ),
        ),
        "reference_fz_pz": (
            "reference only: arithmetic Fz/Pz pair; not claimed neutral",
            replace(
                primary,
                motor=replace(
                    motor,
                    preprocessing=replace(
                        motor.preprocessing, reference="channels", reference_channels=("Fz", "Pz")
                    ),
                ),
            ),
        ),
        "filter_05_40": (
            "high-pass only: 0.5 Hz",
            replace(
                primary,
                motor=replace(motor, preprocessing=replace(motor.preprocessing, highpass_hz=0.5)),
            ),
        ),
        "filter_1_45": (
            "low-pass only: 45 Hz",
            replace(
                primary,
                motor=replace(motor, preprocessing=replace(motor.preprocessing, lowpass_hz=45)),
            ),
        ),
        "normalization_none": (
            "normalization only: absolute powers retained",
            replace(primary, motor=replace(motor, baseline="none")),
        ),
        "normalization_matched": (
            "normalization only: supported trial-matched rest",
            replace(primary, motor=replace(motor, baseline="matched_rest")),
        ),
        "qc_strict": (
            "QC policy only: half amplitude ceilings; flat threshold unchanged",
            replace(
                primary,
                motor=replace(
                    motor,
                    quality=replace(
                        qc,
                        channel_ptp_v=qc.channel_ptp_v * 0.5,
                        trial_ptp_v=qc.trial_ptp_v * 0.5,
                        excursion_v=qc.excursion_v * 0.5,
                    ),
                ),
            ),
        ),
        "qc_permissive": (
            "QC policy only: 1.5 times amplitude ceilings",
            replace(
                primary,
                motor=replace(
                    motor,
                    quality=replace(
                        qc,
                        channel_ptp_v=qc.channel_ptp_v * 1.5,
                        trial_ptp_v=qc.trial_ptp_v * 1.5,
                        excursion_v=qc.excursion_v * 1.5,
                    ),
                ),
            ),
        ),
        "burst_high_25": (
            "burst high threshold only: 2.5 times rest median",
            replace(primary, bursts=replace(primary.bursts, high_multiplier=2.5)),
        ),
    }


def run_sensitivity(
    root: Path,
    output: Path,
    values: dict[str, Any],
    cache_root: Path = Path("data/derived/cohort-cache"),
) -> dict[str, Any]:
    allowed = {"cohort", "variants"}
    if set(values) - allowed or "cohort" not in values:
        raise ValueError("Sensitivity config requires cohort and optional explicit variant names")
    cfg = config_from_dict(values["cohort"])
    design = sensitivity_design(cfg)
    names = values.get("variants", list(design))
    if (
        not isinstance(names, list)
        or not names
        or names[0] != "primary"
        or len(set(names)) != len(names)
        or set(names) - design.keys()
    ):
        raise ValueError("Unique predefined variants beginning with primary are required")
    output_directory(output)
    manifests, frames, retention, missing, bursts, subject_frames, burst_effects = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for name in names:
        reason, variant = design[name]
        result = run_cohort(root, output / name, variant, cache_root)
        manifests.append({"variant": name, "reason": reason, **result})
        population = (
            pd.read_csv(output / name / "population.csv")
            if (output / name / "population.csv").stat().st_size > 1
            else pd.DataFrame()
        )
        if not population.empty:
            population["variant"] = name
            frames.append(population)
        subject_frame = pd.read_csv(output / name / "subject_contrasts.csv")
        subject_frame["variant"] = name
        subject_frames.append(subject_frame)
        burst_population_path = output / name / "burst_population.csv"
        if burst_population_path.stat().st_size > 1:
            burst_population = pd.read_csv(burst_population_path)
            burst_population["variant"] = name
            burst_effects.append(burst_population)
        table = pd.read_csv(output / name / "retention.csv")
        table["variant"] = name
        retention.append(table)
        features = pd.read_csv(output / name / "features.csv")
        imagery = features[features.kind == "imagery"]
        missing.append(
            {
                "variant": name,
                "imagery_feature_cells": len(imagery),
                "missing_reference_cells": int(imagery.erd_percent.isna().sum()),
                "missing_reference_fraction": float(imagery.erd_percent.isna().mean())
                if len(imagery)
                else None,
                "subjects_retained": int(imagery.subject.nunique()),
                "records_complete": result["complete"],
            }
        )
        burst = pd.read_csv(output / name / "burst_condition_summary.csv")
        burst["variant"] = name
        bursts.append(burst)
    effects = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not effects.empty:
        keys = ["channel", "band", "outcome", "units"]
        primary = effects[effects.variant == "primary"][keys + ["estimate"]].rename(
            columns={"estimate": "primary_estimate"}
        )
        effects = effects.merge(primary, on=keys, how="left")
        effects["effect_change"] = effects.estimate - effects.primary_estimate
        finite = effects.estimate.notna() & effects.primary_estimate.notna()
        effects["sign_consistent"] = pd.Series(pd.NA, index=effects.index, dtype="boolean")
        effects.loc[finite, "sign_consistent"] = (
            np.sign(effects.loc[finite, "estimate"])
            == np.sign(effects.loc[finite, "primary_estimate"])
        ).to_numpy()
        effects["relative_change"] = effects.effect_change / effects.primary_estimate.abs().where(
            effects.primary_estimate.abs() > 0
        )
        # Explicitly distinguish missing/unavailable normalization from a zero effect.
    paired_subjects = pd.concat(subject_frames, ignore_index=True)
    if not paired_subjects.empty:
        keys = ["subject", "channel", "band", "outcome", "units"]
        primary_subjects = paired_subjects[paired_subjects.variant == "primary"][
            keys + ["contrast"]
        ].rename(columns={"contrast": "primary_contrast"})
        paired_subjects = paired_subjects.merge(primary_subjects, on=keys, how="left")
        paired_subjects["subject_effect_change"] = (
            paired_subjects.contrast - paired_subjects.primary_contrast
        )
        valid = paired_subjects.contrast.notna() & paired_subjects.primary_contrast.notna()
        paired_subjects["subject_sign_consistent"] = np.where(
            valid,
            (np.sign(paired_subjects.contrast) == np.sign(paired_subjects.primary_contrast)).astype(
                float
            ),
            np.nan,
        )
        paired_summary = (
            paired_subjects.groupby(["variant", "channel", "band", "outcome", "units"])
            .agg(
                n_paired_subjects=("subject_effect_change", "count"),
                paired_subject_mean_change=("subject_effect_change", "mean"),
                subject_sign_consistency=("subject_sign_consistent", "mean"),
            )
            .reset_index()
        )
        effects = effects.merge(
            paired_summary, on=["variant", "channel", "band", "outcome", "units"], how="left"
        )
    paired_subjects.to_csv(output / "sensitivity_subject_effects.csv", index=False)
    burst_effect_table = (
        pd.concat(burst_effects, ignore_index=True) if burst_effects else pd.DataFrame()
    )
    if not burst_effect_table.empty:
        keys = ["channel", "band", "outcome", "units"]
        primary_bursts = burst_effect_table[burst_effect_table.variant == "primary"][
            keys + ["estimate"]
        ].rename(columns={"estimate": "primary_estimate"})
        burst_effect_table = burst_effect_table.merge(primary_bursts, on=keys, how="left")
        burst_effect_table["effect_change"] = (
            burst_effect_table.estimate - burst_effect_table.primary_estimate
        )
    burst_effect_table.to_csv(output / "sensitivity_burst_effects.csv", index=False)
    effects.to_csv(output / "sensitivity_effects.csv", index=False)
    pd.concat(retention, ignore_index=True).to_csv(
        output / "sensitivity_retention.csv", index=False
    )
    pd.DataFrame(missing).to_csv(output / "sensitivity_missingness.csv", index=False)
    pd.concat(bursts, ignore_index=True).to_csv(output / "sensitivity_bursts.csv", index=False)
    experiment_id = canonical_id(
        {
            "primary": scientific_dict(cfg),
            "variants": names,
            "software": software_identity(),
            "input_experiments": [(item["variant"], item["experiment_id"]) for item in manifests],
        }
    )
    write_json(
        output / "design.json",
        {
            "experiment_id": experiment_id,
            "variants": {
                name: {"reason": design[name][0], "configuration": asdict(design[name][1])}
                for name in names
            },
            "records": manifests,
            "design": "one factor at a time; no Cartesian search or configuration selection",
        },
    )
    write_json(
        output / "manifest.json",
        manifest(
            {"dataset": cfg.dataset, "cohort": list(cfg.subjects)},
            {"experiment_id": experiment_id, "design": names, "primary": scientific_dict(cfg)},
            {
                "output": str(output.resolve()),
                "data_root": str(root.resolve()),
                "cache_root": str(cache_root.resolve()),
            },
            cfg.statistics.seed,
        ),
    )
    if cfg.plots and not effects.empty:
        from soma.visualization.cohort import plot_sensitivity

        plot_sensitivity(output)
    report = [
        "# Prespecified sensitivity analysis",
        "",
        "One factor at a time; every variant is retained and none selected as confirmatory.",
        "Complete configurations and rationales: design.json.",
        "",
        "Effect changes and sign consistency: sensitivity_effects.csv. Relative changes",
        "are unavailable for an exactly zero primary estimate; near-zero ratios can be unstable.",
        "Check retention and missing references alongside effects. Absolute log contrasts",
        "should be invariant",
        "to normalization when trial pairs remain identical. QC or matched references",
        "can change the usable trial sets.",
        "",
        "Burst comparisons: sensitivity_bursts.csv and per-variant tables. Percentile CIs",
        "are pointwise descriptions, not evidence that a favored configuration is true.",
    ]
    (output / "report.md").write_text("\n".join(report) + "\n")
    completed = sum(item["complete"] for item in manifests)
    failed = sum(item["failed"] for item in manifests)
    return {
        "experiment_id": experiment_id,
        "variants": len(names),
        "output": str(output),
        "records_complete": completed,
        "records_failed": failed,
        "status": "complete" if not failed else ("partial" if completed else "failed"),
    }
