import mne
import numpy as np
import pytest

from soma.eeg.geometry import assign_geometry
from soma.eeg.preprocessing import (
    PreprocessingConfig,
    design_filter,
    preprocess,
    rereference,
    select_eeg,
)
from soma.eeg.quality import QualityConfig, quality_metrics
from soma.signal.event_locked import event_locked_eeg


def test_average_reference_and_raw_immutable():
    raw, _ = event_locked_eeg()
    data = raw.get_data().copy()
    annotations = raw.annotations.copy()
    result = preprocess(raw)
    np.testing.assert_array_equal(raw.get_data(), data)
    np.testing.assert_array_equal(raw.annotations.onset, annotations.onset)
    np.testing.assert_allclose(result.data.mean(axis=0), 0, atol=1e-16)
    assert result.summary["units"] == "V"
    assert result.edge_samples > 160
    assert result.summary["filter"]["single_pass_order"] == 8
    assert result.summary["filter"]["effective_order"] == 16
    assert np.isfinite(result.data).all()


def test_reference_and_dc_stages():
    x = np.array([[1.0, 3, 7], [2.0, 5, 8]])
    np.testing.assert_allclose(rereference(x, "average").sum(axis=0), 0)
    assert not np.shares_memory(rereference(x, "none"), x)
    with pytest.raises(ValueError):
        rereference(x, "unknown")
    raw, _ = event_locked_eeg()
    raw._data += 3e-5
    p = preprocess(
        raw,
        PreprocessingConfig(reference="none", highpass_hz=None, lowpass_hz=None, remove_dc=True),
    )
    np.testing.assert_allclose(p.data.mean(axis=1), 0, atol=1e-18)
    assert p.edge_samples == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(highpass_hz=0),
        dict(lowpass_hz=80),
        dict(highpass_hz=50, lowpass_hz=40),
        dict(highpass_hz=np.nan),
        dict(phase="invalid"),
        dict(order=0),
        dict(order=1.2),
        dict(transient_tolerance=0),
        dict(notch_hz=60),
        dict(notch_hz=90, notch_justification="observed 60 Hz peak"),
        dict(notch_hz=60, notch_q=0, notch_justification="observed 60 Hz peak"),
    ],
)
def test_filter_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        design_filter(160, PreprocessingConfig(**kwargs))


def test_notch_is_opt_in_and_response_recorded():
    sos, report = design_filter(
        160,
        PreprocessingConfig(
            notch_hz=60, notch_justification="unfiltered line/flank PSD ratio > 10"
        ),
    )
    assert len(sos) == 5
    f = np.asarray(report["response_frequency_hz"])
    gain = np.asarray(report["effective_amplitude_gain"])
    assert gain[np.argmin(np.abs(f - 60))] < 1e-5
    assert report["transition_crossings_hz_by_db"]["-40"]


def test_channel_selection_and_nonfinite_and_short():
    raw, _ = event_locked_eeg()
    assert select_eeg(raw) == ("C3", "Cz", "C4")
    for channels in (("missing",), ("C3", "C3"), ()):
        with pytest.raises(ValueError):
            select_eeg(raw, channels)
    raw.info["bads"] = ["C3"]
    with pytest.raises(ValueError, match="marked bads"):
        select_eeg(raw)
    raw.info["bads"] = []
    raw._data[0, 0] = np.nan
    with pytest.raises(ValueError, match="Nonfinite"):
        preprocess(raw)
    raw, _ = event_locked_eeg()
    with pytest.raises(ValueError, match="too short"):
        preprocess(raw.copy().crop(tmax=2))


def test_quality_is_interpretable():
    x = np.array([[0.0, 0.0, 0.0], [0, 1e-3, np.nan]])
    q = quality_metrics(x, ("flat", "spike"), 160)
    assert q[0]["flags"] == ["flat"]
    assert q[1]["nonfinite_samples"] == 1
    assert "high_peak_to_peak" in q[1]["flags"]
    assert q[1]["excursion_samples"] == 1
    assert q[1]["rms_v"] == pytest.approx(1e-3 / np.sqrt(2))
    with pytest.raises(ValueError):
        QualityConfig(trial_ptp_v=-1)
    with pytest.raises(ValueError):
        quality_metrics(x, ("flat",), 160)
    with pytest.raises(ValueError):
        quality_metrics(x, ("a", "b"), 160, line_hz=80)


def test_line_indicator_on_known_contamination():
    fs = 160
    t = np.arange(3200) / fs
    rng = np.random.default_rng(3)
    x = np.sin(2 * np.pi * 60 * t) + rng.normal(0, 0.1, len(t))
    q = quality_metrics(x[None], ("C3",), fs, line_hz=60)
    assert q[0]["line_to_flank_density_ratio"] > 100


def test_geometry_matches_and_does_not_mutate():
    raw, _ = event_locked_eeg()
    copy, metadata = assign_geometry(raw)
    assert raw.get_montage() is None
    assert copy.get_montage() is not None
    assert metadata["template"] is True
    assert metadata["units"] == "m"
    xyz = np.array(list(metadata["positions"].values()))
    assert np.isfinite(xyz).all()
    assert np.all(np.linalg.norm(xyz, axis=1) < 0.2)
    assert metadata["positions"]["C3"][0] < metadata["positions"]["C4"][0]
    with pytest.raises(ValueError, match="provenance"):
        assign_geometry(raw, copy.get_montage())
    _, supplied = assign_geometry(raw, copy.get_montage(), provenance="explicit test digitization")
    assert supplied["template"] is False


def test_geometry_rejects_unmatched_and_missing_motor_channels():
    raw, _ = event_locked_eeg()
    raw.rename_channels({"Cz": "unexpected"})
    with pytest.raises(ValueError, match="requires C3"):
        assign_geometry(raw)
    raw, _ = event_locked_eeg()
    extra = mne.io.RawArray(
        np.zeros((1, raw.n_times)), mne.create_info(["unexpected"], 160, "eeg"), verbose=False
    )
    raw.add_channels([extra])
    with pytest.raises(ValueError, match="Unmatched"):
        assign_geometry(raw)
