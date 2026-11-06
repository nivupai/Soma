"""Explicit-selection PhysioNet EEGBCI adapter, with no signal preprocessing."""

from pathlib import Path
from typing import Any

import mne
import numpy as np
from mne.datasets import eegbci

SOURCE = "https://physionet.org/content/eegmmidb/1.0.0/"


def event_meanings(run: int) -> dict[str, str]:
    if run in (1, 2):
        return {"T0": "eyes-open baseline" if run == 1 else "eyes-closed baseline"}
    if run in (3, 7, 11):
        task, first, second = "movement", "left hand", "right hand"
    elif run in (4, 8, 12):
        task, first, second = "imagery", "left hand", "right hand"
    elif run in (5, 9, 13):
        task, first, second = "movement", "both fists", "both feet"
    elif run in (6, 10, 14):
        task, first, second = "imagery", "both fists", "both feet"
    else:
        raise ValueError("Unsupported EEGBCI run: expected an integer from 1 to 14")
    return {"T0": "rest", "T1": f"{first} {task}", "T2": f"{second} {task}"}


def validate_selection(subject: int, run: int) -> None:
    if not isinstance(subject, int) or not 1 <= subject <= 109:
        raise ValueError("EEGBCI subject must be an integer from 1 to 109")
    if not isinstance(run, int):
        raise ValueError("EEGBCI run must be an integer from 1 to 14")
    event_meanings(run)


def recording_path(root: Path, subject: int, run: int) -> Path:
    validate_selection(subject, run)
    return (
        root
        / "MNE-eegbci-data"
        / "files"
        / "eegmmidb"
        / "1.0.0"
        / (f"S{subject:03d}")
        / f"S{subject:03d}R{run:02d}.edf"
    )


def fetch(root: Path, subjects: list[int], runs: list[int]) -> list[Path]:
    """Download exactly the requested Cartesian product; never update MNE config."""
    if not subjects or not runs:
        raise ValueError("Explicit nonempty subjects and runs are required")
    for subject in subjects:
        for run in runs:
            validate_selection(subject, run)
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for subject in dict.fromkeys(subjects):
        paths.extend(
            Path(p)
            for p in eegbci.load_data(
                subject,
                list(dict.fromkeys(runs)),
                path=str(root.resolve()),
                update_path=False,
                verbose=False,
            )
        )
    return paths


def load_recording(root: Path, subject: int, run: int) -> tuple[Any, dict[str, Any]]:
    """Open one cached EDF lazily; normalize labels only. Values stay in MNE volts."""
    path = recording_path(root, subject, run)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing EDF: {path}. Run soma datasets fetch eegmmidb "
            f"--subjects {subject} --runs {run} --data-dir {root}"
        )
    raw = mne.io.read_raw_edf(path, preload=False, verbose=False)
    original_names = list(raw.ch_names)
    eegbci.standardize(raw)
    fs = float(raw.info["sfreq"])
    eeg_count = len(mne.pick_types(raw.info, eeg=True, exclude=[]))
    if not np.isclose(fs, 160.0, rtol=0, atol=1e-9) or eeg_count != 64:
        raise ValueError(
            f"EEGBCI validation failed: expected 64 EEG at 160 Hz; got {eeg_count}, {fs}"
        )
    meanings = event_meanings(run)
    observed = set(raw.annotations.description)
    unexpected = observed - meanings.keys()
    if unexpected or not observed:
        raise ValueError(f"Unexpected/empty annotations for run {run}: {sorted(observed)}")
    if run > 2 and observed != meanings.keys():
        raise ValueError(
            f"Missing task annotations: expected {sorted(meanings)}, got {sorted(observed)}"
        )
    mapping = {code: int(code[1:]) + 1 for code in meanings}
    events, _ = mne.events_from_annotations(raw, event_id=mapping, verbose=False)
    metadata = {
        "dataset": "eegmmidb",
        "dataset_version": "1.0.0",
        "source": SOURCE,
        "file_identifier": path.name,
        "subject": subject,
        "run": run,
        "sfreq_hz": fs,
        "n_eeg_channels": eeg_count,
        "n_samples": int(raw.n_times),
        "channel_names": raw.ch_names,
        "original_channel_names": original_names,
        "event_meanings": meanings,
        "event_id": mapping,
        "events": events.tolist(),
        "annotations": [
            {
                "onset_s": float(a["onset"]),
                "duration_s": float(a["duration"]),
                "description": a["description"],
            }
            for a in raw.annotations
        ],
        "voltage_unit": "V",
        "sensor_locations": "not assigned; EDF channel labels only",
        "processing": [
            "MNE EDF physical unit conversion to SI",
            "EEGBCI channel label standardization",
        ],
    }
    return raw, metadata
