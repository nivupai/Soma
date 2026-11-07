"""Physical reference algebra, common-trial comparisons, and reviewable artifact excerpts."""

import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import csd

from soma.core.provenance import manifest, output_directory, sha256
from soma.core.signal import Signal
from soma.datasets.eegbci import load_recording, recording_path, validate_selection
from soma.eeg.epoching import extract_trials
from soma.eeg.events import parse_events
from soma.eeg.geometry import assign_geometry
from soma.eeg.motor_imagery import MotorImageryConfig
from soma.eeg.preprocessing import ProcessedRecording, preprocess
from soma.eeg.timefrequency import trial_spectra
from soma.signal.spectral import BANDS, Spectrum, WelchConfig, welch
from soma.simulations.calibration import atomic_json
from soma.statistics.hierarchical import subject_contrasts

REFERENCES = ("average", "none", "Fz_Pz")
DEFAULT_AUDIT = MotorImageryConfig(plots=False)


def covariance_identity(
    x: np.ndarray[Any, Any], reference: np.ndarray[Any, Any]
) -> dict[str, float]:
    if (
        x.ndim != 1
        or x.size < 2
        or reference.shape != x.shape
        or not np.isfinite(x).all()
        or not np.isfinite(reference).all()
    ):
        raise ValueError("Reference diagnostics require aligned finite continuous voltages")
    original = float(np.var(x))
    variance = float(np.var(reference))
    covariance = float(np.mean((x - x.mean()) * (reference - reference.mean())))
    predicted = original + variance - 2 * covariance
    actual = float(np.var(x - reference))
    return {
        "acquisition_variance_v2": original,
        "reference_variance_v2": variance,
        "covariance_v2": covariance,
        "predicted_referenced_variance_v2": predicted,
        "actual_referenced_variance_v2": actual,
        "identity_error_v2": actual - predicted,
    }


def spectral_identity(
    x: np.ndarray[Any, Any], reference: np.ndarray[Any, Any], fs: float, cfg: WelchConfig
) -> list[dict[str, Any]]:
    original = welch(Signal(x, fs), cfg)
    ref = welch(Signal(reference, fs), cfg)
    transformed = welch(Signal(x - reference, fs), cfg)
    frequency, cross = csd(
        x,
        reference,
        fs=fs,
        window=cfg.window,
        nperseg=cfg.nperseg,
        noverlap=cfg.noverlap,
        detrend="constant",
        scaling="density",
        average="mean",
    )
    real = Spectrum(np.asarray(frequency), np.real(cross), {})
    rows = []
    for band, (low, high) in BANDS.items():
        px, pr, cr, py = (s.band_power(low, high) for s in (original, ref, real, transformed))
        predicted = px + pr - 2 * cr
        rows.append(
            {
                "band": band,
                "acquisition_power_v2": px,
                "reference_power_v2": pr,
                "cross_real_v2": cr,
                "predicted_referenced_power_v2": predicted,
                "actual_referenced_power_v2": py,
                "identity_error_v2": py - predicted,
            }
        )
    return rows


def _features(
    processed: ProcessedRecording, events: Any, cfg: MotorImageryConfig, identity: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    epochs = extract_trials(processed, events, cfg.analysis, qc=cfg.quality)
    spectra = trial_spectra(epochs)
    bands = spectra.bands()
    rows = []
    for t, trial in enumerate(epochs.trials):
        for c, channel in enumerate(epochs.channels):
            for b, band in enumerate(BANDS):
                rows.append(
                    {
                        **identity,
                        "trial_index": trial.event.index,
                        "condition": trial.event.label,
                        "kind": "imagery",
                        "channel": channel,
                        "band": band,
                        "absolute_power_v2": float(bands[t, c, b]),
                        "erd_percent": np.nan,
                        "log_power_ratio": np.nan,
                        "start_sample": trial.start_sample,
                        "stop_sample": trial.stop_sample,
                    }
                )
    columns = [
        *identity,
        "trial_index",
        "condition",
        "kind",
        "channel",
        "band",
        "absolute_power_v2",
        "erd_percent",
        "log_power_ratio",
        "start_sample",
        "stop_sample",
    ]
    quality = [
        {
            **identity,
            "trial_index": trial.event.index,
            "condition": trial.event.label,
            "accepted": trial.accepted,
            "reasons": ";".join(trial.reasons),
            "max_ptp_v": max((row["ptp_v"] or 0 for row in trial.quality), default=0),
        }
        for trial in epochs.log
    ]
    return pd.DataFrame(rows, columns=columns), pd.DataFrame(quality)


def _contrasts_by_reference(features: pd.DataFrame) -> pd.DataFrame:
    tables = []
    for reference, group in features.groupby("reference"):
        _, subjects = subject_contrasts(group)
        subjects = subjects[subjects.outcome == "log_absolute_power"].copy()
        subjects["reference"] = reference
        tables.append(subjects)
    return pd.concat(tables, ignore_index=True)


def audit_reference(
    root: Path,
    output: Path,
    subjects: tuple[int, ...],
    runs: tuple[int, ...],
    cfg: MotorImageryConfig = DEFAULT_AUDIT,
    *,
    plots: bool = True,
) -> dict[str, Any]:
    if (
        not subjects
        or not runs
        or len(set(subjects)) != len(subjects)
        or len(set(runs)) != len(runs)
    ):
        raise ValueError("Explicit unique audit subjects/runs are required")
    for subject in subjects:
        for run in runs:
            validate_selection(subject, run)
            if run not in (4, 8, 12):
                raise ValueError("Reference audit requires unilateral imagery runs 4, 8, 12")
    output_directory(output)
    started = time.perf_counter()
    all_features: list[pd.DataFrame] = []
    quality_frames: list[pd.DataFrame] = []
    variance_rows: list[dict[str, Any]] = []
    spectral_rows: list[dict[str, Any]] = []
    common_rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for subject in sorted(subjects):
        for run in sorted(runs):
            raw = None
            tracked: tuple[list[Any], ...] = (
                all_features,
                quality_frames,
                variance_rows,
                spectral_rows,
                common_rows,
                sources,
            )
            marks = [len(items) for items in tracked]
            try:
                raw, source = load_recording(root, subject, run)
                geometry_raw, geometry = assign_geometry(raw)
                processed = preprocess(
                    geometry_raw,
                    replace(cfg.preprocessing, reference="none", reference_channels=()),
                    qc=cfg.quality,
                )
                events = parse_events(geometry_raw, subject, run, source["file_identifier"])
                channels = processed.channels
                if not {"Fz", "Pz", *cfg.channels} <= set(channels):
                    raise ValueError("Reference audit needs Fz, Pz and all selected motor channels")
                indices = [channels.index(channel) for channel in cfg.channels]
                data = processed.data
                refs = {
                    "average": data.mean(axis=0),
                    "none": np.zeros(data.shape[1]),
                    "Fz_Pz": data[[channels.index("Fz"), channels.index("Pz")]].mean(axis=0),
                }
                covariance = np.cov(data, bias=True)
                eigenvalues = np.linalg.eigvalsh(covariance)
                common_rows.append(
                    {
                        "subject": subject,
                        "run": run,
                        "common_mode_rms_v": float(np.sqrt(np.mean(refs["average"] ** 2))),
                        "common_mode_variance_v2": float(np.var(refs["average"])),
                        "mean_channel_variance_v2": float(np.var(data, axis=1).mean()),
                        "largest_pc_variance_fraction": float(eigenvalues[-1] / eigenvalues.sum()),
                    }
                )
                folder = output / f"S{subject:03d}R{run:02d}"
                folder.mkdir()
                np.savez(
                    folder / "covariance.npz",
                    channels=np.asarray(channels),
                    acquisition=covariance,
                    average=np.cov(data - refs["average"], bias=True),
                    pair=np.cov(data - refs["Fz_Pz"], bias=True),
                )
                local = []
                views = {}
                for reference, voltage in refs.items():
                    selected = data[indices] - voltage[None, :]
                    views[reference] = selected
                    transformed = ProcessedRecording(
                        selected,
                        cfg.channels,
                        processed.fs,
                        processed.edge_samples,
                        processed.summary,
                    )
                    identity = {
                        "subject": subject,
                        "run": run,
                        "recording": source["file_identifier"],
                        "reference": reference,
                    }
                    features, quality = _features(transformed, events, cfg, identity)
                    local.append(features)
                    quality_frames.append(quality)
                    for channel, index in zip(cfg.channels, indices, strict=True):
                        variance_rows.append(
                            {
                                **identity,
                                "channel": channel,
                                **covariance_identity(data[index], voltage),
                            }
                        )
                local_features = pd.concat(local, ignore_index=True)
                all_features.append(local_features)
                id_columns = [
                    "subject",
                    "run",
                    "recording",
                    "trial_index",
                    "condition",
                    "channel",
                    "band",
                ]
                counts = local_features.groupby(id_columns).reference.nunique()
                shared = counts[counts == len(REFERENCES)].reset_index()[id_columns]
                common = local_features.merge(shared, on=id_columns, how="inner")
                # Cross-spectral identity on exactly the shared accepted observation windows.
                for row in common[(common.reference == "average") & (common.band == "mu")].to_dict(
                    "records"
                ):
                    a, b = int(row["start_sample"]), int(row["stop_sample"])
                    channel = str(row["channel"])
                    index = channels.index(channel)
                    for reference, voltage in refs.items():
                        for measures in spectral_identity(
                            data[index, a:b],
                            voltage[a:b],
                            processed.fs,
                            WelchConfig(int(processed.fs), int(processed.fs) // 2),
                        ):
                            spectral_rows.append(
                                {
                                    "subject": subject,
                                    "run": run,
                                    "trial_index": row["trial_index"],
                                    "condition": row["condition"],
                                    "channel": channel,
                                    "reference": reference,
                                    **measures,
                                }
                            )
                if plots:
                    from soma.visualization.reference_audit import (
                        plot_artifact_excerpt,
                        plot_covariance,
                    )

                    plot_covariance(
                        folder, channels, covariance, np.cov(data - refs["average"], bias=True)
                    )
                    local_quality = pd.concat(quality_frames[-len(REFERENCES) :], ignore_index=True)
                    worst = local_quality.sort_values("max_ptp_v", ascending=False).to_dict(
                        "records"
                    )[0]
                    event = events[int(worst["trial_index"])]
                    a = max(0, event.sample)
                    b = min(data.shape[1], event.sample + int(4 * processed.fs))
                    original = raw.get_data(picks=list(cfg.channels), start=a, stop=b)
                    plot_artifact_excerpt(
                        folder,
                        np.arange(a, b) / processed.fs - event.onset_s,
                        original,
                        {name: values[:, a:b] for name, values in views.items()},
                        cfg.channels,
                    )
                    pd.DataFrame(
                        {
                            "time_relative_s": np.arange(a, b) / processed.fs - event.onset_s,
                            **{f"raw_{ch}_v": original[c] for c, ch in enumerate(cfg.channels)},
                            **{
                                f"{name}_{ch}_v": values[c, a:b]
                                for name, values in views.items()
                                for c, ch in enumerate(cfg.channels)
                            },
                        }
                    ).to_csv(folder / "artifact_excerpt.csv", index=False)
                source["sha256"] = sha256(recording_path(root, subject, run))
                sources.append(source)
                atomic_json(
                    folder / "metadata.json",
                    {
                        "source": source,
                        "geometry": geometry,
                        "base_preprocessing": processed.summary,
                        "linear_order_note": (
                            "identical linear filters commute with subtraction; "
                            "QC remains reference-specific"
                        ),
                        "inspection_rule": (
                            "highest peak-to-peak proposal per run; flag, not artifact diagnosis"
                        ),
                    },
                )
            except Exception as exc:
                for items, mark in zip(tracked, marks, strict=True):
                    del items[mark:]
                failures.append(
                    {
                        "subject": subject,
                        "run": run,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            finally:
                if raw is not None:
                    raw.close()
    if not all_features:
        raise ValueError(f"No reference-audit recordings completed: {failures}")
    features = pd.concat(all_features, ignore_index=True)
    keys = ["subject", "run", "recording", "trial_index", "condition", "channel", "band"]
    counts = features.groupby(keys).reference.nunique()
    common = features.merge(
        counts[counts == len(REFERENCES)].reset_index()[keys], on=keys, how="inner"
    )
    retained = _contrasts_by_reference(features)
    shared_effects = _contrasts_by_reference(common)
    base_retained = retained[retained.reference == "average"][
        ["subject", "channel", "band", "contrast"]
    ].rename(columns={"contrast": "primary_retained"})
    base_shared = shared_effects[shared_effects.reference == "average"][
        ["subject", "channel", "band", "contrast"]
    ].rename(columns={"contrast": "primary_shared"})
    accounting = retained.rename(columns={"contrast": "retained_contrast"}).merge(
        shared_effects[["subject", "channel", "band", "reference", "contrast"]].rename(
            columns={"contrast": "shared_contrast"}
        ),
        on=["subject", "channel", "band", "reference"],
        how="outer",
    )
    accounting = accounting.merge(
        base_retained, on=["subject", "channel", "band"], how="left"
    ).merge(base_shared, on=["subject", "channel", "band"], how="left")
    accounting["retained_reference_change"] = (
        accounting.retained_contrast - accounting.primary_retained
    )
    accounting["common_trial_transform_change"] = (
        accounting.shared_contrast - accounting.primary_shared
    )
    accounting["selection_accounting_remainder"] = (
        accounting.retained_reference_change - accounting.common_trial_transform_change
    )
    influence = []
    for key, group in features.groupby(
        ["subject", "run", "channel", "band", "reference", "condition"]
    ):
        values = np.log(group.absolute_power_v2.to_numpy(float))
        n = len(values)
        sign = 1 if key[-1] == "left hand imagery" else -1
        for row, value in zip(group.to_dict("records"), values, strict=True):
            influence.append(
                {
                    **{k: row[k] for k in keys + ["reference"]},
                    "n_condition_trials": n,
                    "centered_log_deviation": float(value - values.mean()),
                    "delete_trial_run_effect_change": float(
                        sign * (values.mean() - value) / (n - 1)
                    )
                    if n > 1
                    else np.nan,
                    "absolute_change": abs(float(sign * (values.mean() - value) / (n - 1)))
                    if n > 1
                    else np.nan,
                }
            )
    pd.DataFrame(influence).to_csv(output / "trial_influence.csv", index=False)
    for name, table in {
        "features": features,
        "common_trial_features": common,
        "retained_effects": retained,
        "common_trial_effects": shared_effects,
        "reference_accounting": accounting,
        "trial_quality": pd.concat(quality_frames, ignore_index=True),
        "variance_identity": pd.DataFrame(variance_rows),
        "spectral_identity": pd.DataFrame(spectral_rows),
        "common_mode": pd.DataFrame(common_rows),
    }.items():
        table.to_csv(output / (name + ".csv"), index=False)
    atomic_json(output / "failures.json", failures)
    atomic_json(
        output / "manifest.json",
        manifest(
            {"dataset": "eegmmidb", "recordings": sources},
            {
                "config": asdict(cfg),
                "references": REFERENCES,
                "template_not_digitization": True,
                "spectral_identity": "S(x-r)=Sx+Sr-2 Re(Sxr)",
                "window_comparison": "retained and identical shared trial sets",
                "processing_seconds": time.perf_counter() - started,
            },
            {"output": str(output.resolve()), "data_root": str(root.resolve())},
        ),
    )
    if plots:
        from soma.visualization.reference_audit import plot_reference_audit

        plot_reference_audit(output)
    report = [
        "# Reference transformation audit",
        "",
        "None retains the acquisition reference, not an absolute physical potential.",
        "Average and Fz/Pz are explicit sensor transforms, not neutral baselines.",
        "",
        "reference_accounting.csv separates shared-trial transform effects from",
        "retained-set accounting remainders. Variance and cross-spectral identities",
        "quantify reference/common-mode covariance. trial_influence.csv ranks deletion",
        "effects within conditions. Excerpts select peak-to-peak review candidates.",
        "Visible transients are not validated artifact diagnoses; no causal invariance claim.",
    ]
    (output / "report.md").write_text("\n".join(report) + "\n")
    return {
        "status": "complete" if not failures else "partial",
        "complete": len(sources),
        "failed": len(failures),
        "output": str(output),
    }
