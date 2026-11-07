"""Identified raw trial tensors and explicitly trial-local cached representations."""

import hashlib
import json
import shutil
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from soma.core.provenance import sha256
from soma.datasets.eegbci import load_recording, recording_path
from soma.decoding.config import digest, identity
from soma.eeg.epoching import EpochConfig, extract_trials, trial_table
from soma.eeg.events import parse_events
from soma.eeg.geometry import assign_geometry
from soma.eeg.preprocessing import PreprocessingConfig, ProcessedRecording, preprocess
from soma.eeg.quality import QualityConfig
from soma.simulations.calibration import atomic_json

FloatArray = NDArray[np.float64]
REQUIRED = (
    "subject",
    "run",
    "recording",
    "event_id",
    "trial_id",
    "label",
    "start_sample",
    "stop_sample",
    "qc_accepted",
    "preprocessing_fingerprint",
)


@dataclass(frozen=True)
class TrialDataset:
    X: FloatArray
    y: NDArray[np.int64]
    metadata: pd.DataFrame
    channels: tuple[str, ...]
    fs: float
    interval: tuple[float, float]
    context: FloatArray
    context_interval: tuple[float, float]
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        validate_tensor(self.X)
        n, c, t = self.X.shape
        if (
            self.y.shape != (n,)
            or self.y.dtype.kind not in "iu"
            or not np.isin(self.y, [0, 1]).all()
            or not set(REQUIRED) <= set(self.metadata.columns)
            or len(self.metadata) != n
        ):
            raise ValueError(
                "Trial labels/required provenance identifiers are missing or misaligned"
            )
        if (
            len(self.channels) != c
            or len(set(self.channels)) != c
            or not np.isfinite(self.fs)
            or self.fs <= 0
            or t != round((self.interval[1] - self.interval[0]) * self.fs)
        ):
            raise ValueError("Channel ordering, sampling frequency or sample length mismatch")
        if (
            self.context.shape
            != (n, c, round((self.context_interval[1] - self.context_interval[0]) * self.fs))
            or not np.isfinite(self.context).all()
        ):
            raise ValueError("Invalid aligned context tensor")
        if (
            self.metadata.trial_id.duplicated().any()
            or self.metadata[list(REQUIRED)].isna().any().any()
            or self.metadata.preprocessing_fingerprint.nunique() != 1
            or not self.metadata.qc_accepted.all()
            or not np.array_equal(self.metadata.label.to_numpy(), self.y)
        ):
            raise ValueError("Duplicate trials, missing provenance, failed QC or label mismatch")
        if not np.all((self.metadata.stop_sample - self.metadata.start_sample).to_numpy() == t):
            raise ValueError("Metadata window lengths disagree with the canonical tensor")
        for _, rows in self.metadata.groupby(["subject", "run", "recording"]):
            ordered = rows.sort_values("start_sample")
            if np.any(ordered.start_sample.to_numpy()[1:] < ordered.stop_sample.to_numpy()[:-1]):
                raise ValueError("Repeated/overlapping event windows cannot be independent trials")

    def subset(self, indices: NDArray[np.int64]) -> "TrialDataset":
        return TrialDataset(
            self.X[indices],
            self.y[indices],
            self.metadata.iloc[indices].reset_index(drop=True),
            self.channels,
            self.fs,
            self.interval,
            self.context[indices],
            self.context_interval,
            self.provenance,
        )

    @property
    def fingerprint(self) -> str:
        return digest(
            {
                "sources": _stable_provenance(self.provenance),
                "channels": self.channels,
                "fs": self.fs,
                "trials": self.metadata[list(REQUIRED)].to_dict("records"),
                "labels": self.y.tolist(),
                "X_sha256": hashlib.sha256(self.X.tobytes()).hexdigest(),
                "context_sha256": hashlib.sha256(self.context.tobytes()).hexdigest(),
            }
        )


def _stable_provenance(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _stable_provenance(v) for k, v in value.items() if k != "cache_hit"}
    if isinstance(value, list):
        return [_stable_provenance(v) for v in value]
    return value


def validate_tensor(X: FloatArray) -> FloatArray:
    if np.iscomplexobj(X):
        raise ValueError("Complex trial tensors are not supported")
    data = np.asarray(X, dtype=float)
    if data.ndim != 3 or not len(data) or data.shape[1] < 2 or data.shape[2] < 2:
        raise ValueError("Expected nonempty trial × channel × sample tensor")
    if not np.isfinite(data).all():
        raise ValueError("Nonfinite trial tensor")
    return data


def _record(
    root: Path, subject: int, run: int, protocol: dict[str, Any]
) -> tuple[dict[str, FloatArray], pd.DataFrame, dict[str, Any]]:
    raw, source = load_recording(root, subject, run)
    try:
        geometry_raw, geometry = assign_geometry(raw)
        geometry_raw.close()
        full = preprocess(
            raw,
            PreprocessingConfig(**protocol["preprocessing"]),
            qc=QualityConfig(**protocol["quality"]),
        )
        if full.fs != protocol["fs_hz"]:
            raise ValueError("Unexpected sampling; no implicit resampling")
        channels = tuple(protocol["channels"])
        indices = [full.channels.index(ch) for ch in channels]
        selected = ProcessedRecording(
            full.data[indices], channels, full.fs, full.edge_samples, full.summary
        )
        events = parse_events(raw, subject, run, source["file_identifier"])
        qc = QualityConfig(**protocol["quality"])
        analysis = extract_trials(selected, events, EpochConfig(*protocol["epoch"]), qc=qc)
        # Context must be contained, but QC applies only to the primary analysis interval.
        contexts = extract_trials(
            selected,
            events,
            EpochConfig(*protocol["context"]),
            qc=QualityConfig(1e9, 1e9, 1e9, 1e-30),
        )
        contexts_by_id = {t.event.index: i for i, t in enumerate(contexts.trials)}
        keep = [i for i, t in enumerate(analysis.trials) if t.event.index in contexts_by_id]
        if not keep:
            raise ValueError("No accepted trials with contained context")
        fingerprint = digest(
            {
                "preprocessing": protocol["preprocessing"],
                "channels": channels,
                "quality": protocol["quality"],
                "epoch": protocol["epoch"],
            }
        )
        rows = []
        for i in keep:
            t = analysis.trials[i]
            rows.append(
                dict(
                    subject=subject,
                    run=run,
                    recording=t.event.recording,
                    event_id=t.event.index,
                    trial_id=f"S{subject:03d}R{run:02d}E{t.event.index:03d}",
                    label=protocol["labels"][t.event.code],
                    start_sample=t.start_sample,
                    stop_sample=t.stop_sample,
                    qc_accepted=True,
                    preprocessing_fingerprint=fingerprint,
                )
            )
        proposals = trial_table(analysis)
        proposals["has_context"] = proposals["index"].isin(contexts_by_id)
        meta = {
            "source": source,
            "preprocessing": full.summary,
            "geometry": geometry,
            "proposals": proposals.to_dict("records"),
            "n_accepted": len(keep),
            "channel_order": channels,
            "fs_hz": full.fs,
        }
        return (
            {
                "X": analysis.data[keep],
                "context": contexts.data[
                    [contexts_by_id[analysis.trials[i].event.index] for i in keep]
                ],
            },
            pd.DataFrame(rows),
            meta,
        )
    finally:
        raw.close()


def load_trials(
    root: Path,
    subjects: tuple[int, ...],
    protocol: dict[str, Any],
    cache: Path = Path("data/derived/decoding-trials"),
    *,
    heldout: bool = False,
    frozen_config: Path | None = None,
) -> tuple[TrialDataset, list[dict[str, Any]]]:
    if heldout:
        from soma.decoding.config import read_protocol

        if frozen_config is None:
            raise ValueError("Held-out data requires a separately sealed frozen configuration")
        frozen, _ = read_protocol(frozen_config)
        if (
            "selected_parameters" not in frozen
            or frozen["software"] != identity()
            or digest(frozen["protocol"]) != digest(protocol)
        ):
            raise ValueError("Invalid held-out freeze/code identity")
    elif set(subjects) & set(range(36, 66)):
        raise ValueError("Reserved held-out subjects cannot enter development")
    allowed = protocol["heldout_subjects"] if heldout else protocol["development_subjects"]
    if not subjects or len(set(subjects)) != len(subjects) or not set(subjects) <= set(allowed):
        raise ValueError("Subjects outside the permitted development/held-out cohort")
    software = identity()
    tensors, contexts, frames, records = [], [], [], []
    cache.mkdir(parents=True, exist_ok=True)
    for subject in sorted(subjects):
        for run in protocol["runs"]:
            row: dict[str, Any] = {"subject": subject, "run": run, "status": "failed"}
            try:
                source_hash = sha256(recording_path(root, subject, run))
                key = digest(
                    {
                        "edf_sha256": source_hash,
                        "subject": subject,
                        "run": run,
                        "protocol": protocol,
                        "software": software,
                    }
                )
                folder = cache / key
                if folder.exists():
                    receipt = json.loads((folder / "receipt.json").read_text())
                    if receipt.get("identity") != key or set(receipt.get("files", {})) != {
                        "arrays.npz",
                        "trials.csv",
                        "metadata.json",
                    }:
                        raise ValueError("Decoding trial cache identity/schema mismatch")
                    for name, expected in receipt["files"].items():
                        if Path(name).name != name or sha256(folder / name) != expected:
                            raise ValueError("Corrupt decoding trial cache")
                    with np.load(folder / "arrays.npz", allow_pickle=False) as archive:
                        arrays = {name: archive[name].copy() for name in ("X", "context")}
                    frame = pd.read_csv(folder / "trials.csv")
                    metadata = json.loads((folder / "metadata.json").read_text())
                    hit = True
                else:
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        arrays, frame, metadata = _record(root, subject, run, protocol)
                    metadata["warnings"] = [str(w.message) for w in caught]
                    staging = Path(tempfile.mkdtemp(prefix=key + ".building-", dir=cache))
                    np.savez_compressed(
                        staging / "arrays.npz", X=arrays["X"], context=arrays["context"]
                    )
                    frame.to_csv(staging / "trials.csv", index=False)
                    atomic_json(staging / "metadata.json", metadata)
                    atomic_json(
                        staging / "receipt.json",
                        {
                            "identity": key,
                            "files": {p.name: sha256(p) for p in staging.iterdir() if p.is_file()},
                        },
                    )
                    try:
                        staging.rename(folder)
                    except OSError:
                        if not folder.is_dir():
                            raise
                        concurrent = json.loads((folder / "receipt.json").read_text())
                        if concurrent.get("identity") != key or set(
                            concurrent.get("files", {})
                        ) != {"arrays.npz", "trials.csv", "metadata.json"}:
                            raise ValueError(
                                "Concurrent decoding cache identity mismatch"
                            ) from None
                        for name, expected in concurrent["files"].items():
                            if Path(name).name != name or sha256(folder / name) != expected:
                                raise ValueError("Corrupt concurrently published cache") from None
                        shutil.rmtree(staging)
                    hit = False
                if (
                    tuple(metadata["channel_order"]) != tuple(protocol["channels"])
                    or metadata["fs_hz"] != protocol["fs_hz"]
                ):
                    raise ValueError("Cached channel order or sampling mismatch")
                TrialDataset(
                    arrays["X"],
                    frame.label.to_numpy(dtype=np.int64),
                    frame,
                    tuple(protocol["channels"]),
                    protocol["fs_hz"],
                    tuple(protocol["epoch"]),
                    arrays["context"],
                    tuple(protocol["context"]),
                    {},
                )
                tensors.append(arrays["X"])
                contexts.append(arrays["context"])
                frames.append(frame)
                row.update(
                    status="complete",
                    edf_sha256=source_hash,
                    cache_key=key,
                    cache_hit=hit,
                    n_accepted=len(frame),
                    n_proposed=len(metadata["proposals"]),
                    warnings=metadata["warnings"],
                )
            except Exception as exc:
                row.update(error_type=type(exc).__name__, error=str(exc))
            records.append(row)
    if not tensors:
        raise ValueError(f"No usable recordings: {records}")
    dataset = TrialDataset(
        np.concatenate(tensors),
        np.concatenate([f.label.to_numpy(dtype=np.int64) for f in frames]),
        pd.concat(frames, ignore_index=True),
        tuple(protocol["channels"]),
        protocol["fs_hz"],
        tuple(protocol["epoch"]),
        np.concatenate(contexts),
        tuple(protocol["context"]),
        {"records": records, "software": software, "protocol_sha256": digest(protocol)},
    )
    return dataset, records


def combine_trials(datasets: tuple[TrialDataset, ...]) -> TrialDataset:
    if not datasets:
        raise ValueError("No trial datasets to combine")
    first = datasets[0]
    for other in datasets[1:]:
        if (
            other.channels != first.channels
            or other.fs != first.fs
            or other.interval != first.interval
            or other.context_interval != first.context_interval
            or set(other.metadata.preprocessing_fingerprint)
            != set(first.metadata.preprocessing_fingerprint)
        ):
            raise ValueError(
                "Incompatible channel order, sampling, interval or reference fingerprint"
            )
    return TrialDataset(
        np.concatenate([d.X for d in datasets]),
        np.concatenate([d.y for d in datasets]),
        pd.concat([d.metadata for d in datasets], ignore_index=True),
        first.channels,
        first.fs,
        first.interval,
        np.concatenate([d.context for d in datasets]),
        first.context_interval,
        {"components": [d.provenance for d in datasets]},
    )
