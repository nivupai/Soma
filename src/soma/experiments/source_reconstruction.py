"""Exploratory template reconstruction of individual trials, not only evoked EEG."""

from collections import Counter
from pathlib import Path
from typing import Any

import mne
import numpy as np

from soma.core.provenance import sha256, write_json
from soma.datasets.eegbci import load_recording, recording_path
from soma.eeg.epoching import EpochConfig, extract_trials, trial_table
from soma.eeg.events import parse_events
from soma.eeg.preprocessing import PreprocessingConfig, preprocess
from soma.eeg.quality import QualityConfig
from soma.source.inverse import CorticalInverse
from soma.source.noise import NoiseModel
from soma.source.power import band_powers
from soma.source.template import Template
from soma.source.workflow import RunReport, sealed_config, study_forward


def reconstruct(
    output: Path,
    *,
    subject: int = 1,
    runs: tuple[int, ...] = (4, 8, 12),
    data_dir: Path = Path("data/raw"),
    template_dir: Path = Path("data/anatomy"),
    config_path: Path = Path("configs/source-modeling.yaml"),
) -> dict[str, Any]:
    config = sealed_config(config_path)
    if subject not in config["subjects"] or list(runs) != config["runs"]:
        raise ValueError("The sealed exploratory protocol requires subject 1, runs 4/8/12")
    forward = study_forward(subject, runs[0], data_dir, template_dir)
    report = RunReport(output, config, forward, config["seed"])
    condition_maps: dict[str, list[np.ndarray[Any, Any]]] = {}
    roi_rows: list[dict[str, Any]] = []
    summaries = []
    roi_masks: dict[str, np.ndarray[Any, Any]] = {}
    template = Template(template_dir)
    for hemi in ("lh", "rh"):
        path = template.root / "label" / f"{hemi}.precentral.label"
        if path.is_file():
            label = mne.read_label(path)
            roi_masks[f"{hemi}_precentral"] = np.array(
                [h == hemi and v in set(label.vertices) for h, v in forward.coordinates.identifiers]
            )
    if not roi_masks and (template.root / "label/lh.aparc.annot").exists():
        labels_roi = mne.read_labels_from_annot(
            "fsaverage",
            parc="aparc",
            regexp="^precentral-",
            subjects_dir=template_dir,
            verbose=False,
        )
        for label in labels_roi:
            vertices_roi = set(label.vertices)
            roi_masks[label.name] = np.array(
                [h == label.hemi and v in vertices_roi for h, v in forward.coordinates.identifiers]
            )
    for run in runs:
        raw, raw_metadata = load_recording(data_dir, subject, run)
        events = parse_events(raw, subject, run, str(recording_path(data_dir, subject, run)))
        # Replace only this workflow's montage; historical EEG APIs remain unchanged.
        raw.set_montage(mne.channels.make_standard_montage("fsaverage_1005"))
        processed = preprocess(
            raw,
            PreprocessingConfig(**config["preprocessing"]),
            qc=QualityConfig(**config["quality"]),
        )
        epoch = extract_trials(
            processed,
            events,
            EpochConfig(*config["epoch"]),
            codes=("T0", "T1", "T2"),
            qc=QualityConfig(**config["quality"]),
        )
        if tuple(processed.channels) != tuple(forward.info["ch_names"]):
            raise ValueError("Preprocessing changed channel order")
        labels = np.array([t.event.code for t in epoch.trials])
        counts = dict(Counter(labels.tolist()))
        if any(counts.get(code, 0) < 2 for code in ("T0", "T1", "T2")):
            raise ValueError(f"Insufficient accepted trials: {counts}")
        trial_table(epoch).to_csv(output / f"run-{run:02d}-trials.csv", index=False)
        info = forward.info.copy()
        rest = mne.EpochsArray(
            epoch.data[labels == "T0"],
            info,
            tmin=epoch.times[0],
            baseline=None,
            proj=True,
            verbose=False,
        )
        covariance = mne.compute_covariance(
            rest,
            method="shrunk",
            method_params={"shrunk": {"shrinkage": [config["noise"]["shrinkage"]]}},
            rank={"eeg": len(info["ch_names"]) - 1},
            verbose=False,
        )
        # MNE returns a covariance with its projection represented in metadata;
        # numerical checks use the explicitly projected sensor covariance.
        c = forward.projector @ covariance.data @ forward.projector
        noise = NoiseModel(
            c,
            tuple(info["ch_names"]),
            forward.projector,
            "same_run_T0_background_not_instrument_noise",
        )
        covariance.save(output / f"run-{run:02d}-cov.fif", overwrite=False, verbose=False)
        mne_epochs = mne.EpochsArray(
            epoch.data, info, tmin=epoch.times[0], baseline=None, proj=True, verbose=False
        )
        run_summary: dict[str, Any] = {
            "run": run,
            "accepted": counts,
            "proposed": len(epoch.log),
            "noise": noise.diagnostics(),
            "raw": raw_metadata,
            "edf_sha256": sha256(recording_path(data_dir, subject, run)),
            "preprocessing": processed.summary,
            "methods": {},
        }
        arrays: dict[str, Any] = {
            "labels": labels,
            "covariance": c,
            "event_indices": [t.event.index for t in epoch.trials],
        }
        for method in config["inverse"]["methods"]:
            inv = CorticalInverse(
                forward,
                covariance,
                method=method,
                lambda2=config["inverse"]["lambda2"],
                depth=config["inverse"]["depth"],
            )
            powers: dict[str, list[np.ndarray[Any, Any]]] = {"mu": [], "beta": []}
            mean_source = np.zeros((len(forward.coordinates.identifiers), epoch.data.shape[-1]))
            residuals = []
            for trial_index, stc in enumerate(inv.epochs(mne_epochs)):
                forward.require_vertices(stc.vertices)
                mean_source += stc.data / len(epoch.trials)
                bp = band_powers(stc.data, epoch.fs)
                for band, values in bp.items():
                    powers[band].append(values)
                    for roi, mask in roi_masks.items():
                        if mask.any():
                            roi_rows.append(
                                {
                                    "run": run,
                                    "method": method,
                                    "band": band,
                                    "condition": str(labels[trial_index]),
                                    "event_index": epoch.trials[trial_index].event.index,
                                    "roi": roi,
                                    "mean_vertex_power": float(values[mask].mean()),
                                    "units": "(A m)^2" if method == "MNE" else "dimensionless^2",
                                }
                            )
                if method == "MNE":
                    y = epoch.data[trial_index]
                    residuals.append(
                        float(np.linalg.norm(forward.matrix @ stc.data - y) / np.linalg.norm(y))
                    )
            evoked = mne.EvokedArray(epoch.data.mean(axis=0), info, tmin=epoch.times[0], nave=1)
            evoked_source = inv.apply(evoked).data
            evoked_power = band_powers(evoked_source, epoch.fs)
            method_summary: dict[str, Any] = {
                "units": inv.units,
                "nave": 1,
                "evoked_comparison_pool": "all accepted T0/T1/T2 trials, equal trial weight",
                "evoked_linearity_relative_error": float(
                    np.linalg.norm(evoked_source - mean_source) / np.linalg.norm(mean_source)
                ),
                "mean_physical_sensor_residual_relative": float(np.mean(residuals))
                if residuals
                else None,
                "evoked_to_trial_mean_power_ratio": {},
            }
            for band, trial_values in powers.items():
                power = np.stack(trial_values)
                arrays[f"{method}_{band}_trial_power"] = power
                arrays[f"{method}_{band}_evoked_power"] = evoked_power[band]
                means = {code: power[labels == code].mean(axis=0) for code in ("T0", "T1", "T2")}
                floor = config["source_power"]["minimum_rest_power"][method]
                for code in ("T1", "T2"):
                    key = f"{method}_{band}_{code}_log_ratio_to_rest"
                    condition_maps.setdefault(key, []).append(
                        np.log(np.maximum(means[code], floor) / np.maximum(means["T0"], floor))
                    )
                method_summary["evoked_to_trial_mean_power_ratio"][band] = float(
                    evoked_power[band].sum() / power.mean(axis=0).sum()
                )
            run_summary["methods"][method] = method_summary
        np.savez_compressed(output / f"run-{run:02d}-source-power.npz", **arrays)
        write_json(output / f"run-{run:02d}-summary.json", run_summary)
        summaries.append(run_summary)
        raw.close()
    import pandas as pd

    pd.DataFrame(roi_rows).to_csv(output / "template-roi-trial-power.csv", index=False)
    maps: dict[str, Any] = {key: np.mean(value, axis=0) for key, value in condition_maps.items()}
    np.savez_compressed(output / "equal-run-mean-maps.npz", **maps)
    from soma.visualization.source import power_figure

    power_figure(output, forward, maps)
    return report.finish(
        {
            "status": "complete",
            "subject": subject,
            "runs": summaries,
            "roi_names": list(roi_masks),
            "roi_assets_sha256": {
                str(p): sha256(p) for p in (template.root / "label").glob("?h.aparc.annot")
            },
            "interpretation": (
                "template exploratory trialwise induced power; "
                "no true anatomical localization or population inference"
            ),
        }
    )
