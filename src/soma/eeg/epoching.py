"""Half-open trial windows with an explicit log for every proposed extraction."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from soma.eeg.events import Event
from soma.eeg.preprocessing import ProcessedRecording
from soma.eeg.quality import DEFAULT_QUALITY, QualityConfig, quality_metrics


@dataclass(frozen=True)
class EpochConfig:
    start_s: float = 1.0
    stop_s: float = 3.0
    require_containment: bool = True

    def __post_init__(self) -> None:
        if not np.isfinite([self.start_s, self.stop_s]).all() or self.start_s >= self.stop_s:
            raise ValueError("Epoch start must precede stop, both finite seconds")


DEFAULT_EPOCH = EpochConfig()
DEFAULT_MATCHED = EpochConfig(-3, -1)


@dataclass(frozen=True)
class Trial:
    event: Event
    start_sample: int
    stop_sample: int
    accepted: bool
    reasons: tuple[str, ...]
    quality: tuple[dict[str, Any], ...]
    reference_event_index: int | None = None


@dataclass(frozen=True)
class EpochSet:
    data: NDArray[np.float64]  # trial × channel × sample, accepted trials only
    channels: tuple[str, ...]
    fs: float
    times: NDArray[np.float64]  # seconds relative to cue
    trials: tuple[Trial, ...]  # aligned to data
    log: tuple[Trial, ...]  # every proposal, including rejected trials


def _extract(
    processed: ProcessedRecording,
    events: tuple[Event, ...],
    cfg: EpochConfig,
    codes: tuple[str, ...],
    qc: QualityConfig,
    matched: bool,
    min_rest_s: float,
) -> EpochSet:
    fs = processed.fs
    offsets = np.rint(np.asarray([cfg.start_s, cfg.stop_s]) * fs).astype(int)
    length = int(offsets[1] - offsets[0])
    if length < 2:
        raise ValueError("Epoch must contain at least two samples")
    accepted, log, arrays = [], [], []
    for ev in events:
        if ev.code not in codes:
            continue
        start, stop = ev.sample + int(offsets[0]), ev.sample + int(offsets[1])
        reasons = []
        reference = None
        start_s, stop_s = start / fs, stop / fs
        if ev.duration_s <= 0 or not np.isfinite(ev.duration_s):
            reasons.append("invalid_duration")
        if start < 0 or stop > processed.data.shape[1]:
            reasons.append("recording_boundary")
        if (
            start < processed.edge_samples
            or stop > processed.data.shape[1] - processed.edge_samples
        ):
            reasons.append("filter_transient_guard")
        if matched:
            candidates = [
                r
                for r in events
                if r.code == "T0"
                and r.duration_s >= min_rest_s
                and r.onset_s <= start_s + 1e-8
                and r.end_s >= stop_s - 1e-8
                and stop_s <= ev.onset_s
            ]
            if len(candidates) != 1 or (stop - start) / fs < min_rest_s:
                reasons.append("no_contained_rest_reference")
            else:
                reference = candidates[0].index
        else:
            if cfg.require_containment and not (
                ev.onset_s <= start_s + 1e-8 and stop_s <= ev.end_s + 1e-8
            ):
                reasons.append("outside_annotation")
            if any(
                other.index != ev.index
                and other.code != ev.code
                and other.onset_s < stop_s - 1e-8
                and other.end_s > start_s + 1e-8
                for other in events
            ):
                reasons.append("incompatible_condition")
        metrics: tuple[dict[str, Any], ...] = ()
        if 0 <= start < stop <= processed.data.shape[1]:
            segment = processed.data[:, start:stop]
            metrics = tuple(quality_metrics(segment, processed.channels, fs, qc, trial=True))
            for row in metrics:
                reasons.extend(f"{row['channel']}:{flag}" for flag in row["flags"])
        trial = Trial(ev, start, stop, not reasons, tuple(reasons), metrics, reference)
        log.append(trial)
        if trial.accepted:
            accepted.append(trial)
            arrays.append(processed.data[:, start:stop])
    data = np.stack(arrays) if arrays else np.empty((0, len(processed.channels), length))
    return EpochSet(
        data,
        processed.channels,
        fs,
        np.arange(length) / fs + offsets[0] / fs,
        tuple(accepted),
        tuple(log),
    )


def extract_trials(
    processed: ProcessedRecording,
    events: tuple[Event, ...],
    cfg: EpochConfig = DEFAULT_EPOCH,
    codes: tuple[str, ...] = ("T1", "T2"),
    qc: QualityConfig = DEFAULT_QUALITY,
) -> EpochSet:
    return _extract(processed, events, cfg, codes, qc, False, 0.0)


def matched_rest(
    processed: ProcessedRecording,
    events: tuple[Event, ...],
    cfg: EpochConfig = DEFAULT_MATCHED,
    min_rest_s: float = 2.0,
    qc: QualityConfig = DEFAULT_QUALITY,
) -> EpochSet:
    """Propose pre-cue windows only within a single actual T0 annotation."""
    if cfg.stop_s > 0 or not np.isfinite(min_rest_s) or min_rest_s <= 0:
        raise ValueError(
            "Matched references must be pre-cue; minimum rest duration must be positive"
        )
    return _extract(processed, events, cfg, ("T1", "T2"), qc, True, min_rest_s)


def trial_table(epochs: EpochSet, stage: str = "analysis") -> pd.DataFrame:
    rows = []
    for trial in epochs.log:
        rows.append(
            {
                **asdict(trial.event),
                "start_sample": trial.start_sample,
                "stop_sample_exclusive": trial.stop_sample,
                "accepted": trial.accepted,
                "rejection_reasons": ";".join(trial.reasons),
                "stage": stage,
                "reference_event_index": trial.reference_event_index,
            }
        )
    return pd.DataFrame(rows)
