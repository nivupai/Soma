from dataclasses import replace

import mne
import numpy as np
import pytest

from soma.eeg.epoching import EpochConfig, extract_trials, matched_rest, trial_table
from soma.eeg.events import event_table, parse_events, validate_events
from soma.eeg.preprocessing import PreprocessingConfig, preprocess
from soma.signal.event_locked import event_locked_eeg


def unfiltered(raw):
    return preprocess(raw, PreprocessingConfig(reference="none", highpass_hz=None, lowpass_hz=None))


def test_event_decode_samples_and_original_annotations():
    raw, _ = event_locked_eeg()
    events = parse_events(raw, 1, 4, "model")
    assert len(events) == 17
    assert events[1].code == "T1"
    assert events[1].label == "left hand imagery"
    assert events[1].onset_s == 4
    assert events[1].duration_s == 4
    assert events[1].sample == 640
    assert events[1].annotation_onset_s == raw.annotations.onset[1]
    assert event_table(events).shape[0] == 17
    other_run = parse_events(raw, 1, 6, "bilateral")
    assert other_run[1].label == "both fists imagery"


def test_first_sample_offset_preserved():
    raw, _ = event_locked_eeg()
    shifted = mne.io.RawArray(raw.get_data(), raw.info.copy(), first_samp=1600, verbose=False)
    shifted.set_annotations(mne.Annotations([0, 4, 8], [4, 4, 4], ["T0", "T1", "T2"]))
    events = parse_events(shifted, 1, 4, "offset")
    assert events[0].annotation_onset_s == 10
    assert events[0].onset_s == 0
    assert events[1].sample == 640


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(duration_s=0),
        dict(duration_s=-1),
        dict(duration_s=np.inf),
        dict(onset_s=-1),
        dict(onset_s=1000),
        dict(sample=1),
        dict(sample=-1),
        dict(code="T3"),
        dict(label="wrong"),
    ],
)
def test_invalid_events(kwargs):
    raw, _ = event_locked_eeg()
    events = parse_events(raw, 1, 4, "model")
    with pytest.raises(ValueError):
        validate_events((replace(events[0], **kwargs),), 160, raw.n_times)


def test_overlap_and_unknown_missing_labels():
    raw, _ = event_locked_eeg()
    events = parse_events(raw, 1, 4, "model")
    with pytest.raises(ValueError, match="nonoverlapping"):
        validate_events((events[0], replace(events[1], onset_s=3, sample=480)), 160, raw.n_times)
    with pytest.raises(ValueError):
        validate_events((), 160, raw.n_times)
    for descriptions in (["T0", "T3"], ["T0", "T1"]):
        raw.set_annotations(mne.Annotations([0, 4], [4, 4], descriptions))
        with pytest.raises(ValueError):
            parse_events(raw, 1, 4, "model")


def test_half_open_trial_boundaries_and_labels():
    raw, _ = event_locked_eeg(noise_v=0)
    p = unfiltered(raw)
    events = parse_events(raw, 1, 4, "model")
    epochs = extract_trials(p, events)
    assert epochs.data.shape == (8, 3, 320)
    first = epochs.trials[0]
    assert first.start_sample == 800
    assert first.stop_sample == 1120
    np.testing.assert_array_equal(epochs.data[0], p.data[:, 800:1120])
    assert epochs.times[0] == 1
    assert epochs.times[-1] == 3 - 1 / 160
    assert [t.event.code for t in epochs.trials] == ["T1", "T2"] * 4
    assert trial_table(epochs)["accepted"].all()


def test_outside_condition_and_edges_logged():
    raw, _ = event_locked_eeg()
    p = unfiltered(raw)
    ev = parse_events(raw, 1, 4, "model")
    epochs = extract_trials(p, ev, EpochConfig(-1, 5))
    assert not len(epochs.trials)
    assert len(epochs.log) == 8
    assert all("outside_annotation" in tr.reasons for tr in epochs.log)
    assert all("incompatible_condition" in tr.reasons for tr in epochs.log)
    edge = replace(
        ev[-1], code="T1", label="left hand imagery", duration_s=1, onset_s=67, sample=10720
    )
    result = extract_trials(p, (edge,))
    assert "recording_boundary" in result.log[0].reasons
    guarded = replace(p, edge_samples=900)
    assert "filter_transient_guard" in extract_trials(guarded, ev).log[0].reasons


def test_trial_artifact_nonfinite_and_invalid_duration():
    raw, _ = event_locked_eeg(artifacts=True)
    ev = parse_events(raw, 1, 4, "model")
    p = unfiltered(raw)
    epochs = extract_trials(p, ev)
    assert len(epochs.trials) == 7
    assert "C3:high_peak_to_peak" in epochs.log[0].reasons
    p.data[1, 800] = np.nan
    rejected = extract_trials(p, ev).log[0]
    assert "Cz:nonfinite" in rejected.reasons
    invalid = extract_trials(p, (replace(ev[1], duration_s=0),))
    assert "invalid_duration" in invalid.log[0].reasons


def test_matched_rest_is_actually_contained():
    raw, _ = event_locked_eeg()
    ev = parse_events(raw, 1, 4, "model")
    p = unfiltered(raw)
    refs = matched_rest(p, ev)
    assert len(refs.trials) == 8
    assert refs.trials[0].start_sample == 160
    assert refs.trials[0].reference_event_index == 0
    missing = matched_rest(p, tuple(e for e in ev if e.code != "T0"))
    assert len(missing.trials) == 0
    assert all("no_contained_rest_reference" in tr.reasons for tr in missing.log)
    too_long = matched_rest(p, ev, EpochConfig(-5, -1))
    assert len(too_long.trials) == 0
    with pytest.raises(ValueError):
        matched_rest(p, ev, EpochConfig(-1, 1))
    with pytest.raises(ValueError):
        EpochConfig(3, 1)


def test_recording_identity_and_sampling_contract():
    raw, _ = event_locked_eeg()
    ev = parse_events(raw, 1, 4, "model")
    for fs, n in ((0, raw.n_times), (np.nan, raw.n_times), (160, 0)):
        with pytest.raises(ValueError):
            validate_events(ev, fs, n)
    with pytest.raises(ValueError, match="one identified"):
        validate_events((ev[0], replace(ev[1], recording="other")), 160, raw.n_times)
    with pytest.raises(ValueError, match="integers"):
        validate_events((replace(ev[0], sample=0.1),), 160, raw.n_times)
