"""Run-preserving motor imagery experiment orchestration and saved artifacts."""

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from soma.core.provenance import manifest, output_directory, sha256, write_json
from soma.datasets.eegbci import load_recording, recording_path
from soma.eeg.epoching import EpochConfig, EpochSet, extract_trials, matched_rest, trial_table
from soma.eeg.erd import PowerCoordinates, lateralization, power_change
from soma.eeg.events import event_table, parse_events
from soma.eeg.geometry import assign_geometry
from soma.eeg.preprocessing import PreprocessingConfig, ProcessedRecording, preprocess
from soma.eeg.quality import QualityConfig
from soma.eeg.timefrequency import (
    MorletConfig,
    TimeFrequency,
    TrialSpectra,
    morlet_power,
    trial_spectra,
)
from soma.signal.event_locked import event_locked_eeg
from soma.signal.spectral import BANDS


@dataclass(frozen=True)
class MotorImageryConfig:
    preprocessing: PreprocessingConfig = PreprocessingConfig()
    quality: QualityConfig = QualityConfig()
    analysis: EpochConfig = EpochConfig(1, 3)
    context: EpochConfig = EpochConfig(0, 4)
    matched_reference: EpochConfig = EpochConfig(-3, -1)
    baseline: str = "condition_rest"
    minimum_rest_s: float = 2.0
    minimum_band_reference_v2: float = 1e-20
    minimum_wavelet_reference_v2: float = 1e-20
    morlet: MorletConfig = MorletConfig()
    channels: tuple[str, ...] = ("C3", "Cz", "C4")
    plots: bool = True

    def __post_init__(self) -> None:
        if self.baseline not in {"none", "condition_rest", "matched_rest"}:
            raise ValueError("baseline must be none, condition_rest or matched_rest")
        if not np.isfinite(self.minimum_rest_s) or self.minimum_rest_s <= 0:
            raise ValueError("minimum_rest_s must be positive")
        if (
            not self.channels
            or len(set(self.channels)) != len(self.channels)
            or not np.isfinite(
                [self.minimum_band_reference_v2, self.minimum_wavelet_reference_v2]
            ).all()
            or min(self.minimum_band_reference_v2, self.minimum_wavelet_reference_v2) < 0
        ):
            raise ValueError("Channels must be unique; reference floors finite and nonnegative")


DEFAULT_MOTOR_IMAGERY = MotorImageryConfig()


def _select(processed: ProcessedRecording, channels: tuple[str, ...]) -> ProcessedRecording:
    if not set(channels) <= set(processed.channels):
        raise ValueError(f"Missing selected channels: {set(channels) - set(processed.channels)}")
    indices = [processed.channels.index(ch) for ch in channels]
    return ProcessedRecording(
        processed.data[indices], channels, processed.fs, processed.edge_samples, processed.summary
    )


def _mean(values: NDArray[np.float64], axis: int) -> NDArray[np.float64]:
    count = np.sum(np.isfinite(values), axis=axis)
    result = np.full(count.shape, np.nan)
    np.divide(np.nansum(values, axis=axis), count, out=result, where=count > 0)
    return result


def _reference(
    target: EpochSet, reference: EpochSet, values: NDArray[np.float64], baseline: str
) -> NDArray[np.float64]:
    """Reference values T×C×F: preserve channel/frequency order, map matched trial ids."""
    result = np.full((len(target.trials), *values.shape[1:]), np.nan)
    if baseline == "condition_rest" and len(values):
        result[:] = _mean(values, 0)
    elif baseline == "matched_rest":
        lookup = {trial.event.index: i for i, trial in enumerate(reference.trials)}
        for i, trial in enumerate(target.trials):
            if trial.event.index in lookup:
                result[i] = values[lookup[trial.event.index]]
    return result


def analyze_run(
    raw: Any, subject: int, run: int, identity: str, cfg: MotorImageryConfig = DEFAULT_MOTOR_IMAGERY
) -> dict[str, Any]:
    started = perf_counter()
    if run not in (4, 8, 12):
        raise ValueError("Motor imagery workflow supports unilateral imagery runs 4, 8, 12 only")
    geometry_raw, geometry = assign_geometry(raw)
    events = parse_events(geometry_raw, subject, run, identity)
    processed_all = preprocess(geometry_raw, cfg.preprocessing, qc=cfg.quality)
    preprocessing_seconds = perf_counter() - started
    processed = _select(processed_all, cfg.channels)
    epochs = extract_trials(processed, events, cfg.analysis, qc=cfg.quality)
    rest = extract_trials(processed, events, cfg.analysis, codes=("T0",), qc=cfg.quality)
    context = extract_trials(processed, events, cfg.context, qc=cfg.quality)
    rest_context = extract_trials(processed, events, cfg.context, codes=("T0",), qc=cfg.quality)
    matched = matched_rest(
        processed, events, cfg.matched_reference, cfg.minimum_rest_s, cfg.quality
    )
    spectra = trial_spectra(epochs)
    rest_spectra = trial_spectra(rest)
    matched_spectra = trial_spectra(matched)
    tfr_started = perf_counter()
    tfr = morlet_power(context, cfg.morlet)
    rest_tfr = morlet_power(rest_context, cfg.morlet)
    matched_tfr = morlet_power(matched, cfg.morlet)
    tfr_seconds = perf_counter() - tfr_started
    reference_epochs = rest if cfg.baseline == "condition_rest" else matched
    reference_spectra = rest_spectra if cfg.baseline == "condition_rest" else matched_spectra
    reference_context = rest_context if cfg.baseline == "condition_rest" else matched
    reference_tfr = rest_tfr if cfg.baseline == "condition_rest" else matched_tfr

    # Minimum rest applies to entire annotation AND sampled interval, not just a label.
    # Rejected reference windows remain in the log; masking below never fabricates a reference.
    def eligible(ref: EpochSet) -> NDArray[np.bool_]:
        return np.asarray(
            [
                tr.event.duration_s >= cfg.minimum_rest_s
                and (tr.stop_sample - tr.start_sample) / ref.fs >= cfg.minimum_rest_s
                for tr in ref.trials
            ],
            dtype=bool,
        )

    reference_bands = reference_spectra.bands()
    reference_bands[~eligible(reference_epochs)] = np.nan
    band_reference = _reference(epochs, reference_epochs, reference_bands, cfg.baseline)
    band_coordinates = PowerCoordinates(epochs.channels, tuple(BANDS))
    bands = spectra.bands()
    change = power_change(
        bands, band_reference, band_coordinates, band_coordinates, cfg.minimum_band_reference_v2
    )
    reference_values = reference_tfr.reference_mean(
        cfg.analysis.start_s if cfg.baseline == "condition_rest" else None,
        cfg.analysis.stop_s if cfg.baseline == "condition_rest" else None,
    )
    reference_values[~eligible(reference_context)] = np.nan
    tfr_reference = _reference(context, reference_context, reference_values, cfg.baseline)
    coordinates = PowerCoordinates(context.channels, tuple(tfr.frequencies))
    tfr_change = power_change(
        tfr.power,
        np.broadcast_to(tfr_reference[..., None], tfr.power.shape),
        coordinates,
        coordinates,
        cfg.minimum_wavelet_reference_v2,
    )
    features: list[dict[str, Any]] = []
    for ep, psd, kind in ((epochs, spectra, "imagery"), (rest, rest_spectra, "rest")):
        values = psd.bands()
        for t, trial in enumerate(ep.trials):
            for c, channel in enumerate(ep.channels):
                for b, band in enumerate(BANDS):
                    features.append(
                        {
                            "subject": subject,
                            "run": run,
                            "recording": identity,
                            "trial_index": trial.event.index,
                            "condition": trial.event.label,
                            "kind": kind,
                            "channel": channel,
                            "band": band,
                            "absolute_power_v2": float(values[t, c, b]),
                            "reference_power_v2": float(band_reference[t, c, b])
                            if kind == "imagery"
                            else np.nan,
                            "erd_percent": float(change.percent[t, c, b])
                            if kind == "imagery"
                            else np.nan,
                            "log_power_ratio": float(change.log_ratio[t, c, b])
                            if kind == "imagery"
                            else np.nan,
                            "power_difference_v2": float(change.difference[t, c, b])
                            if kind == "imagery"
                            else np.nan,
                            "baseline": cfg.baseline,
                        }
                    )
    columns = [
        "subject",
        "run",
        "recording",
        "trial_index",
        "condition",
        "kind",
        "channel",
        "band",
        "absolute_power_v2",
        "reference_power_v2",
        "erd_percent",
        "log_power_ratio",
        "power_difference_v2",
        "baseline",
    ]
    feature_table = pd.DataFrame(features, columns=columns)
    group = ["subject", "run", "recording", "condition", "channel", "band", "baseline"]
    summary = (
        feature_table.groupby(group, sort=False)
        .agg(
            n_trials=("absolute_power_v2", "size"),
            n_normalized=("erd_percent", "count"),
            mean_power_v2=("absolute_power_v2", "mean"),
            sd_power_v2=("absolute_power_v2", "std"),
            mean_erd_percent=("erd_percent", "mean"),
            mean_log_ratio=("log_power_ratio", "mean"),
            mean_difference_v2=("power_difference_v2", "mean"),
        )
        .reset_index()
    )
    laterality = []
    if {"C3", "C4"} <= set(epochs.channels):
        li = lateralization(
            bands[:, epochs.channels.index("C3")], bands[:, epochs.channels.index("C4")]
        )
        for t, trial in enumerate(epochs.trials):
            for b, band in enumerate(BANDS):
                laterality.append(
                    {
                        "subject": subject,
                        "run": run,
                        "recording": identity,
                        "trial_index": trial.event.index,
                        "condition": trial.event.label,
                        "band": band,
                        "c4_minus_c3_over_sum": float(li[t, b]),
                    }
                )
    tables = [
        (epochs, "analysis"),
        (rest, "rest"),
        (context, "timefrequency"),
        (rest_context, "rest_timefrequency"),
        (matched, "matched_reference"),
    ]
    counts = {
        stage: {
            "proposed": len(ep.log),
            "accepted": len(ep.trials),
            "rejected": len(ep.log) - len(ep.trials),
        }
        for ep, stage in tables
    }
    return {
        "events": event_table(events),
        "trials": pd.concat([trial_table(ep, stage) for ep, stage in tables], ignore_index=True),
        "quality": {
            "thresholds": asdict(cfg.quality),
            "trial_counts": counts,
            "channel_before": processed_all.summary["quality_before"],
            "channel_after": processed_all.summary["quality_after"],
            "trial_details": {stage: [asdict(t) for t in ep.log] for ep, stage in tables},
            "interpretation": "threshold flags, not confirmed artifact diagnoses",
            "reference_strategy": cfg.baseline,
            "reference_minimum_rest_s": cfg.minimum_rest_s,
            "reference_eligibility": {
                stage: [
                    {
                        "event_index": tr.event.index,
                        "rest_event_index": tr.reference_event_index,
                        "eligible_duration": bool(ok),
                        "reason": ""
                        if ok
                        else "reference interval or annotation below minimum duration",
                    }
                    for tr, ok in zip(ep.trials, eligible(ep), strict=True)
                ]
                for ep, stage in ((reference_epochs, "band"), (reference_context, "wavelet"))
            },
            "normalization_availability": {
                "band_valid_cells": int(change.valid.sum()),
                "wavelet_valid_cells": int(tfr_change.valid.sum()),
                "absolute_imagery_trials": len(epochs.trials),
                "trials_with_any_valid_band_reference": int(
                    np.any(change.valid, axis=(1, 2)).sum()
                ),
            },
        },
        "preprocessing": processed_all.summary,
        "geometry": geometry,
        "features": feature_table,
        "summary": summary,
        "lateralization": pd.DataFrame(
            laterality,
            columns=[
                "subject",
                "run",
                "recording",
                "trial_index",
                "condition",
                "band",
                "c4_minus_c3_over_sum",
            ],
        ),
        "epochs": epochs,
        "rest": rest,
        "context": context,
        "spectra": spectra,
        "rest_spectra": rest_spectra,
        "tfr": tfr,
        "rest_tfr": rest_tfr,
        "tfr_change": tfr_change,
        "band_change": change,
        "band_reference": band_reference,
        "wavelet_reference": tfr_reference,
        "processed": processed,
        "profile": {
            "core_seconds": perf_counter() - started,
            "preprocessing_seconds": preprocessing_seconds,
            "tfr_seconds": tfr_seconds,
            "continuous_selected_array_mib": processed.data.nbytes / 2**20,
            "continuous_reference_array_mib": processed_all.data.nbytes / 2**20,
            "morlet_power_arrays_mib": (
                tfr.power.nbytes + rest_tfr.power.nbytes + matched_tfr.power.nbytes
            )
            / 2**20,
        },
    }


def _save_arrays(folder: Path, result: dict[str, Any]) -> None:
    spectra: TrialSpectra = result["spectra"]
    tfr: TimeFrequency = result["tfr"]
    epochs: EpochSet = result["epochs"]
    context: EpochSet = result["context"]
    np.savez(
        folder / "spectra.npz",
        density=spectra.density,
        frequencies=spectra.frequencies,
        channels=np.asarray(spectra.channels),
        trial_indices=np.asarray([t.event.index for t in epochs.trials]),
        conditions=np.asarray([t.event.label for t in epochs.trials]),
        rest_density=result["rest_spectra"].density,
        rest_trial_indices=np.asarray([t.event.index for t in result["rest"].trials]),
        band_reference_v2=result["band_reference"],
    )
    condition_names = ("left hand imagery", "right hand imagery")
    masks = [
        np.asarray([t.event.label == name for t in context.trials], dtype=bool)
        for name in condition_names
    ]
    aggregate = np.stack([_mean(tfr.power[mask], 0) for mask in masks])
    np.savez(
        folder / "timefrequency.npz",
        power=tfr.power,
        condition_names=np.asarray(condition_names),
        condition_trial_counts=np.asarray([mask.sum() for mask in masks]),
        condition_mean_power=aggregate,
        band_names=np.asarray(list(BANDS)),
        reference_wavelet_power=result["wavelet_reference"],
        frequencies=tfr.frequencies,
        times=tfr.times,
        channels=np.asarray(tfr.channels),
        valid=tfr.valid,
        half_support_s=tfr.half_support_s,
        trial_indices=np.asarray([t.event.index for t in context.trials]),
        conditions=np.asarray([t.event.label for t in context.trials]),
        band_wavelet_power=tfr.band_trajectories(),
        erd_percent=result["tfr_change"].percent,
        log_ratio=result["tfr_change"].log_ratio,
        power_difference=result["tfr_change"].difference,
        normalization_valid=result["tfr_change"].valid,
    )


def motor_imagery(
    root: Path,
    subject: int,
    runs: list[int],
    output: Path,
    cfg: MotorImageryConfig = DEFAULT_MOTOR_IMAGERY,
    *,
    synthetic_seed: int | None = None,
    synthetic_artifacts: bool = False,
) -> dict[str, Any]:
    if not runs or len(set(runs)) != len(runs) or any(run not in (4, 8, 12) for run in runs):
        raise ValueError("Explicit unique imagery runs 4, 8, 12 are required")
    if synthetic_seed is not None and runs != [4]:
        raise ValueError("Synthetic laboratory models run 4 only")
    output_directory(output)
    results, sources, truth = {}, [], None
    for run in runs:
        if synthetic_seed is None:
            raw, source = load_recording(root, subject, run)
            source["sha256"] = sha256(recording_path(root, subject, run))
        else:
            raw, truth = event_locked_eeg(synthetic_seed, artifacts=synthetic_artifacts)
            source = {
                "dataset": "synthetic-event-locked",
                "file_identifier": "soma-event-lab-v1",
                "subject": subject,
                "run": run,
                "truth": truth,
            }
        try:
            results[run] = analyze_run(raw, subject, run, str(source["file_identifier"]), cfg)
        finally:
            raw.close()
        sources.append(source)
        folder = output / f"run-{run:02d}"
        folder.mkdir()
        _save_arrays(folder, results[run])
    for key, filename in (
        ("events", "events.csv"),
        ("trials", "trials.csv"),
        ("features", "spectral_features.csv"),
        ("summary", "condition_summary.csv"),
        ("lateralization", "lateralization.csv"),
    ):
        pd.concat([r[key] for r in results.values()], ignore_index=True).to_csv(
            output / filename, index=False
        )
    for key in ("quality", "preprocessing", "geometry"):
        write_json(output / f"{key}.json", {str(run): r[key] for run, r in results.items()})
    parameters = {
        **asdict(cfg),
        "selected_channels": list(cfg.channels),
        "sampling_hz_by_run": {str(run): r["epochs"].fs for run, r in results.items()},
        "welch_by_run": {str(run): asdict(r["spectra"].config) for run, r in results.items()},
        "band_definitions_hz": BANDS,
        "window_convention": "half-open, rounded sample offsets",
        "morlet_units": "V^2, MNE wavelet normalization; not PSD density",
        "minimum_reference_policy": "mask at/below explicit floor; no epsilon",
        "template_geometry": True,
    }
    result = manifest(
        {"recordings": sources, "dataset": sources[0]["dataset"]},
        parameters,
        {"data_root": str(root.resolve()), "output": str(output.resolve())},
        synthetic_seed,
    )
    write_json(output / "manifest.json", result)
    if truth is not None:
        write_json(output / "synthetic_truth.json", truth)
    if cfg.plots:
        from soma.visualization.motor_imagery import plot_motor_imagery

        plot_motor_imagery(results, output)
    lines = [
        "# Motor imagery dynamics",
        "",
        f"Subject {subject}; runs {runs}; baseline: {cfg.baseline}.",
        "",
        "Standard/template electrode coordinates are not measured subject digitization.",
        "",
        "Analysis parameters and versions are in manifest.json; full filter response and "
        "coefficients are in preprocessing.json. All thresholds are QC flags, not diagnoses.",
        "",
    ]
    for run, r in results.items():
        lines += [
            f"## Run {run}",
            "",
            f"Events by label: {r['events'].groupby('label').size().to_dict()}",
            "",
            f"Reference: {cfg.preprocessing.reference}; "
            f"selected analysis channels: {cfg.channels}. "
            f"Analysis window: {asdict(cfg.analysis)}; context: {asdict(cfg.context)}.",
            "",
            f"Filter: {asdict(cfg.preprocessing)}. Boundary guard: "
            f"{r['preprocessing']['filter']['edge_samples']} samples.",
            "",
            f"Trial counts by stage: {r['quality']['trial_counts']}",
            "",
            f"Normalization availability: {r['quality']['normalization_availability']}",
            "",
            "```csv\n" + r["summary"].to_csv(index=False) + "```",
            "",
        ]
    lines += [
        "Absolute Welch powers are V². ERD is percent change; log ratios use natural log. "
        "Negative ERD denotes suppression. Condition-rest uses separate accepted T0 windows "
        "within each run, not an invented pre-cue baseline. Missing references remain unavailable.",
        "",
        f"Morlet cycles: {cfg.morlet.n_cycles}; frequency centers (Hz): {cfg.morlet.frequencies}. "
        "Full discrete support masking and no decimation. "
        "Band trajectories are means of wavelet powers, not PSD integrals. "
        "See run-specific NPZ files for trial/channel/frequency/time arrays and masks.",
        "",
        "Lateralization is (C4−C3)/(C4+C3) of absolute power: positive means lower C3 power. "
        "It can reflect baseline asymmetry, reference choice, or artifacts, not just imagery.",
        "",
        "Single-subject exploratory summaries have no population inference, significance, "
        "decoding accuracy, or confirmed physiological lateralization claim. No ICA, source "
        "localization or MRI analysis was performed.",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n")
    return result
