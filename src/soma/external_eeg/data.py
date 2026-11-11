"""Explicit upstream MAT adapter; no downloader or automatic mirror fallback."""

from pathlib import Path
from typing import Any

import mne
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.signal import resample_poly

from soma.core.provenance import sha256
from soma.decoding.data import TrialDataset
from soma.eeg.preprocessing import PreprocessingConfig, preprocess
from soma.eeg.quality import QualityConfig, quality_metrics
from soma.external_eeg.contracts import BNCI_CHANNELS, CHANNELS, feature_contract, parameters
from soma.human.permissions import PermissionEvidence, check_permission
from soma.workflow.model import digest


def inventory(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    rows = []
    for s in range(1, 10):
        for session in ("T", "E"):
            path = root / f"A{s:02d}{session}.mat"
            available = (
                path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root)
            )
            rows.append(
                {
                    "subject": s,
                    "session": session,
                    "file": path.name,
                    "status": "AVAILABLE" if available else "MISSING",
                    "sha256": sha256(path) if available else None,
                }
            )
    return {
        "schema": "soma.external-eeg.inventory/1",
        "records": rows,
        "fingerprint": digest(rows),
        "available": sum(r["status"] == "AVAILABLE" for r in rows),
        "planned": 18,
        "format": "upstream-MAT-only; NEMAR-BIDS/GDF explicitly unsupported",
    }


def authorize(
    permission: PermissionEvidence, source: bytes, version: str, action: str = "analyze"
) -> None:
    decision = check_permission(
        permission,
        dataset="bnci2014-001",
        version=version,
        purpose="methods_research",
        action=action,
        source_content=source,
    )
    if not decision["allowed"]:
        raise ValueError("External data permission blocked: " + str(decision["reasons"]))


def bnci_record(
    path: Path,
    subject: int,
    session: str,
    expected_hash: str,
    permission: PermissionEvidence,
    source: bytes,
    version: str,
) -> tuple[TrialDataset | None, list[dict[str, Any]]]:
    authorize(permission, source, version)
    if (
        session not in ("T", "E")
        or not 1 <= subject <= 9
        or path.name != f"A{subject:02d}{session}.mat"
        or sha256(path) != expected_hash
    ):
        raise ValueError("Changed input or wrong subject/session")
    document = loadmat(path, squeeze_me=True, struct_as_record=False)
    if "data" not in document:
        raise ValueError("Missing BNCI data structure")
    frames = []
    signals = []
    decisions: list[dict[str, Any]] = []
    task_run = 0
    for raw in np.asarray(document["data"], dtype=object).reshape(-1):
        if not all(hasattr(raw, k) for k in ("X", "trial", "y", "fs", "classes")):
            raise ValueError("Incomplete BNCI structure")
        onsets = np.atleast_1d(raw.trial)
        labels = np.atleast_1d(raw.y)
        if not len(onsets):
            continue
        task_run += 1
        classes = [str(x).strip().lower() for x in np.atleast_1d(raw.classes)]
        if classes != ["left hand", "right hand", "feet", "tongue"]:
            raise ValueError("Incorrect authoritative class order; label inversion rejected")
        if (
            float(raw.fs) != 250
            or labels.shape != onsets.shape
            or not np.isin(labels, [1, 2, 3, 4]).all()
        ):
            raise ValueError("Sampling or labels mismatch")
        if not hasattr(raw, "artifacts"):
            raise ValueError("Missing source artifact flags")
        flags = np.atleast_1d(raw.artifacts)
        if flags.shape != labels.shape or not np.isin(flags, [0, 1]).all():
            raise ValueError("Invalid artifact flags")
        data = np.asarray(raw.X, float)
        if data.ndim != 2 or data.shape[1] != 25 or not np.isfinite(data).all():
            raise ValueError("Expected finite 22 EEG +3 EOG channels")
        if not np.equal(onsets, np.round(onsets)).all() or np.any(onsets < 1):
            raise ValueError("One-based integer trial starts required")
        # Documented MAT values are µV; remove common reference using all22 EEG.
        info = mne.create_info(
            BNCI_CHANNELS + ["EOG1", "EOG2", "EOG3"], 250, ["eeg"] * 22 + ["eog"] * 3
        )
        raw_record = mne.io.RawArray(data.T * 1e-6, info, verbose=False)
        try:
            processed = preprocess(
                raw_record,
                PreprocessingConfig(**parameters()["preprocessing"]),
                qc=QualityConfig(**parameters()["quality"]),
            )
        finally:
            raw_record.close()
        if set(processed.channels) != set(BNCI_CHANNELS):
            decisions.extend(
                {"run": task_run, "event": i, "status": "required_reference_channel_qc"}
                for i in range(len(labels))
            )
            continue
        eeg = resample_poly(processed.data, 16, 25, axis=1)
        eeg = eeg[[processed.channels.index(c) for c in CHANNELS]]
        for i, (onset, label, flag) in enumerate(zip(onsets, labels, flags, strict=True)):
            if label not in (1, 2):
                decisions.append({"run": task_run, "event": i, "status": "EXCLUDED_NON_BINARY"})
                continue
            start = round(((float(onset) - 1) / 250 + 3) * 160)
            stop = start + 320
            trial = eeg[:, start:stop]
            reason = "accepted"
            if flag:
                reason = "source_artifact"
            elif trial.shape != (9, 320):
                reason = "epoch_not_contained"
            else:
                flags_qc = quality_metrics(
                    trial,
                    tuple(CHANNELS),
                    160,
                    QualityConfig(**parameters()["quality"]),
                    trial=True,
                )
                reasons = sorted({f for row_qc in flags_qc for f in row_qc["flags"]})
                if reasons:
                    reason = ",".join(reasons)
            decisions.append({"run": task_run, "event": i, "status": reason})
            if reason != "accepted":
                continue
            record = f"bnci2014-001/s{subject:02}/{session}/r{task_run}"
            frames.append(
                {
                    "subject": subject,
                    "session": session,
                    "run": task_run,
                    "recording": record,
                    "event_id": i,
                    "trial_id": record + f"/t{i}",
                    "label": int(label) - 1,
                    "condition": "left" if label == 1 else "right",
                    "start_sample": start,
                    "stop_sample": stop,
                    "qc_accepted": True,
                    "preprocessing_fingerprint": digest(feature_contract()),
                }
            )
            signals.append(trial)
    if sha256(path) != expected_hash:
        raise ValueError("Input changed during preprocessing")
    if task_run != 6:
        raise ValueError("Expected six actual task runs, not inferred sessions")
    if not frames:
        return None, decisions
    X = np.asarray(signals)
    frame = pd.DataFrame(frames)
    return TrialDataset(
        X,
        frame.label.to_numpy(dtype=np.int64),
        frame,
        tuple(CHANNELS),
        160.0,
        (1.0, 3.0),
        X.copy(),
        (1.0, 3.0),
        {
            "dataset": "bnci2014-001",
            "version": version,
            "sha256": expected_hash,
            "contract": feature_contract(),
            "context": "epoch-only; no burst/context method",
        },
    ), decisions


def combine(datasets: list[TrialDataset]) -> TrialDataset:
    if not datasets:
        raise ValueError("No eligible external trials")
    d = datasets[0]
    return TrialDataset(
        np.concatenate([x.X for x in datasets]),
        np.concatenate([x.y for x in datasets]),
        pd.concat([x.metadata for x in datasets], ignore_index=True),
        d.channels,
        d.fs,
        d.interval,
        np.concatenate([x.context for x in datasets]),
        d.context_interval,
        {"dataset": "bnci2014-001", "input_fingerprints": [x.fingerprint for x in datasets]},
    )
