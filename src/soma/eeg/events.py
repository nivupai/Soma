"""Run-aware annotation durations and recording-relative sample coordinates."""

from dataclasses import asdict, dataclass
from typing import Any

import mne
import numpy as np
import pandas as pd

from soma.datasets.eegbci import event_meanings, validate_selection


@dataclass(frozen=True)
class Event:
    subject: int
    run: int
    code: str
    label: str
    onset_s: float
    duration_s: float
    sample: int
    annotation_onset_s: float
    source: str
    recording: str
    index: int

    @property
    def end_s(self) -> float:
        return self.onset_s + self.duration_s


def validate_events(events: tuple[Event, ...], fs: float, n_samples: int) -> None:
    if (
        not np.isfinite(fs)
        or fs <= 0
        or not isinstance(n_samples, (int, np.integer))
        or n_samples < 1
    ):
        raise ValueError("Event validation requires positive sampling rate and recording length")
    if not events:
        raise ValueError("No supported annotations")
    previous_end = 0.0
    identity = (events[0].subject, events[0].run, events[0].recording)
    for ev in events:
        validate_selection(ev.subject, ev.run)
        if (ev.subject, ev.run, ev.recording) != identity or not ev.recording:
            raise ValueError("Event table must describe one identified subject/run/recording")
        if not isinstance(ev.sample, (int, np.integer)):
            raise ValueError("Event sample indices must be integers")
        meanings = event_meanings(ev.run)
        if ev.code not in meanings or ev.label != meanings[ev.code]:
            raise ValueError("Unsupported event code or semantic label")
        if not np.isfinite([ev.onset_s, ev.duration_s]).all() or ev.duration_s <= 0:
            raise ValueError("Event duration must be finite and positive")
        if ev.onset_s < previous_end - 1e-8:
            raise ValueError("Events must be chronological and nonoverlapping")
        if ev.onset_s < 0 or ev.end_s > n_samples / fs + 1e-8:
            raise ValueError("Event outside recording boundaries")
        if not 0 <= ev.sample < n_samples or abs(ev.sample / fs - ev.onset_s) > 0.5 / fs + 1e-8:
            raise ValueError("Event sample does not match onset within half a sample")
        previous_end = ev.end_s


def parse_events(raw: Any, subject: int, run: int, recording: str) -> tuple[Event, ...]:
    validate_selection(subject, run)
    meanings = event_meanings(run)
    descriptions = set(raw.annotations.description)
    if descriptions - meanings.keys() or not descriptions:
        raise ValueError(f"Missing or unsupported annotations: {sorted(descriptions)}")
    if run > 2 and descriptions != meanings.keys():
        raise ValueError("Task annotation table must contain T0/T1/T2")
    mapping = {code: int(code[1:]) + 1 for code in meanings}
    samples, _ = mne.events_from_annotations(raw, event_id=mapping, verbose=False)
    if len(samples) != len(raw.annotations):
        raise ValueError("Annotation/event count mismatch")
    result = tuple(
        Event(
            subject,
            run,
            str(a["description"]),
            meanings[str(a["description"])],
            float(a["onset"] - raw.first_time),
            float(a["duration"]),
            int(s[0] - raw.first_samp),
            float(a["onset"]),
            "MNE annotations",
            recording,
            i,
        )
        for i, (a, s) in enumerate(zip(raw.annotations, samples, strict=True))
    )
    validate_events(result, float(raw.info["sfreq"]), int(raw.n_times))
    return result


def event_table(events: tuple[Event, ...]) -> pd.DataFrame:
    return pd.DataFrame([asdict(ev) for ev in events])
