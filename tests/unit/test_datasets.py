from pathlib import Path

import mne
import numpy as np
import pytest

from soma.datasets import eegbci


def fixture_raw(fs=160, count=64, descriptions=("T0", "T1", "T2")):
    names = ["C3..", "Cz..", "C4.."] + [f"X{i}.." for i in range(count - 3)]
    raw = mne.io.RawArray(np.zeros((count, 640)), mne.create_info(names, fs, "eeg"), verbose=False)
    raw.set_annotations(
        mne.Annotations([0, 1, 2][: len(descriptions)], [0.5] * len(descriptions), descriptions)
    )
    return raw


def test_loader_standardizes_events_without_data_change(tmp_path, monkeypatch):
    path = eegbci.recording_path(tmp_path, 1, 4)
    path.parent.mkdir(parents=True)
    path.touch()
    raw = fixture_raw()
    original = raw.get_data().copy()
    monkeypatch.setattr(mne.io, "read_raw_edf", lambda *a, **kw: raw)
    result, metadata = eegbci.load_recording(tmp_path, 1, 4)
    assert result is raw
    assert raw.ch_names[:3] == ["C3", "Cz", "C4"]
    np.testing.assert_array_equal(raw.get_data(), original)
    assert metadata["event_meanings"]["T1"] == "left hand imagery"
    assert [event[0] for event in metadata["events"]] == [0, 160, 320]
    assert metadata["event_id"] == {"T0": 1, "T1": 2, "T2": 3}


@pytest.mark.parametrize(
    "fs,count,descriptions",
    [
        (100, 64, ("T0", "T1", "T2")),
        (160, 63, ("T0", "T1", "T2")),
        (160, 64, ("T0", "T3")),
        (160, 64, ("T0",)),
    ],
)
def test_validation_failures(tmp_path, monkeypatch, fs, count, descriptions):
    path = eegbci.recording_path(tmp_path, 1, 4)
    path.parent.mkdir(parents=True)
    path.touch()
    monkeypatch.setattr(
        mne.io, "read_raw_edf", lambda *a, **kw: fixture_raw(fs, count, descriptions)
    )
    with pytest.raises(ValueError):
        eegbci.load_recording(tmp_path, 1, 4)


def test_fetch_exact_selection(tmp_path, monkeypatch):
    calls = []

    def fake(subject, runs, **kwargs):
        calls.append((subject, runs, kwargs))
        return [str(tmp_path / f"{subject}-{run}.edf") for run in runs]

    monkeypatch.setattr(eegbci.eegbci, "load_data", fake)
    paths = eegbci.fetch(tmp_path, [1, 2, 1], [4, 4])
    assert len(paths) == 2
    assert [(s, r) for s, r, _ in calls] == [(1, [4]), (2, [4])]
    assert all(not kwargs["update_path"] for _, _, kwargs in calls)


@pytest.mark.parametrize("subject,run", [(0, 4), (110, 4), (1, 0), (1, 15)])
def test_invalid_selection(subject, run):
    with pytest.raises(ValueError):
        eegbci.recording_path(Path("."), subject, run)


def test_missing_and_run_semantics(tmp_path):
    with pytest.raises(FileNotFoundError, match="datasets fetch"):
        eegbci.load_recording(tmp_path, 1, 4)
    assert eegbci.event_meanings(6)["T1"] == "both fists imagery"
    assert eegbci.event_meanings(3)["T1"] == "left hand movement"
    assert eegbci.event_meanings(1)["T0"] == "eyes-open baseline"
