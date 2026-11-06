import numpy as np
import pandas as pd
import pytest

from soma.signal.bursts import BurstConfig, calibrated_detector, intervals, map_windows


@pytest.mark.parametrize(
    "mask,expected",
    [
        ([], []),
        ([False, False], []),
        ([True, True], [(0, 2)]),
        ([False, True, False, True], [(1, 2), (3, 4)]),
    ],
)
def test_true_intervals_half_open(mask, expected):
    assert intervals(np.array(mask, dtype=bool)) == expected


def test_exposure_and_censoring_common_denominators():
    fs = 10
    mask = np.zeros(100, dtype=bool)
    mask[10:40] = True
    mask[50:60] = True
    valid = np.ones(100, dtype=bool)
    amplitude = np.ones(100) * 10e-6
    windows = pd.DataFrame(
        [
            dict(
                index=3,
                label="left hand imagery",
                onset_s=1.0,
                start_sample=20,
                stop_sample_exclusive=70,
            )
        ]
    )
    summary, events = map_windows(mask, amplitude, valid, fs, windows, {"channel": "C3"})
    row = summary.iloc[0]
    assert row.valid_observation_s == 5
    assert row.occupancy == 0.6
    assert row.onset_count == 1  # the existing burst entering the window is not a new onset
    assert row.rate_hz == 0.2
    assert row.mean_complete_duration_s == 1
    assert events.iloc[0].left_censored
    assert not events.iloc[1].left_censored
    assert events.iloc[0].onset_relative_s == 1


def test_empty_detection_vs_no_valid_exposure():
    windows = pd.DataFrame(
        [dict(index=0, label="rest", onset_s=0.0, start_sample=0, stop_sample_exclusive=50)]
    )
    mask = np.zeros(50, dtype=bool)
    summary, events = map_windows(mask, np.ones(50), np.ones(50, dtype=bool), 10, windows, {})
    assert summary.iloc[0].occupancy == summary.iloc[0].rate_hz == 0
    assert np.isnan(summary.iloc[0].mean_complete_duration_s)
    assert events.empty
    unavailable, _ = map_windows(mask, np.ones(50), np.zeros(50, dtype=bool), 10, windows, {})
    assert np.isnan(unavailable.iloc[0].occupancy)
    assert np.isnan(unavailable.iloc[0].rate_hz)


def test_validity_gap_censors_both_fragments():
    valid = np.ones(100, dtype=bool)
    valid[40:60] = False
    windows = pd.DataFrame(
        [dict(index=0, label="rest", onset_s=0.0, start_sample=10, stop_sample_exclusive=90)]
    )
    mask = np.zeros(100, dtype=bool)
    mask[20:80] = True
    summary, events = map_windows(mask, np.ones(100), valid, 10, windows, {})
    assert summary.iloc[0].valid_observation_s == 6
    assert summary.iloc[0].complete_count == 0
    assert len(events) == 2 and not events.complete.any()


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(strategies=()),
        dict(strategies=("unknown",)),
        dict(low_multiplier=3, high_multiplier=2),
        dict(low_quantile=0.99, high_quantile=0.9),
        dict(min_cycles=0),
        dict(fixed_low_v=0),
        dict(filter_cycles=np.nan),
    ],
)
def test_burst_configuration_invalid(kwargs):
    with pytest.raises(ValueError):
        BurstConfig(**kwargs)


def test_zero_signal_and_invalid_detector_inputs():
    assert not calibrated_detector(np.zeros(100), 100, 1, 2, 0.1).any()
    for x, fs, lo, hi, duration in (
        (np.ones(10), 0, 1, 2, 0.1),
        (np.full(10, np.nan), 100, 1, 2, 0.1),
        (np.ones(10), 100, 2, 1, 0.1),
        (np.ones(10), 100, 1, 2, 0),
    ):
        with pytest.raises(ValueError):
            calibrated_detector(x, fs, lo, hi, duration)


def test_event_relative_bins_keep_exposure_and_missing_bins():
    from soma.signal.bursts import event_dynamics

    mask = np.zeros(100, dtype=bool)
    mask[20:30] = True
    valid = np.ones(100, dtype=bool)
    valid[20:25] = False
    windows = pd.DataFrame(
        [
            dict(
                index=2,
                label="left hand imagery",
                onset_s=1,
                start_sample=20,
                stop_sample_exclusive=40,
            )
        ]
    )
    frame = event_dynamics(mask, valid, 10, windows, {}, bin_s=0.5)
    np.testing.assert_allclose(frame.bin_start_relative_s, [1, 1.5, 2, 2.5])
    assert np.isnan(frame.occupancy.iloc[0])
    assert frame.occupancy.iloc[1] == 1
    assert frame.exposure_s.sum() == 1.5
