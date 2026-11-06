"""Continuous NeuroDSP burst detection with explicit amplitude calibration and exposure."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from neurodsp.burst import detect_bursts_dual_threshold
from neurodsp.filt import filter_signal
from neurodsp.timefrequency import amp_by_time
from numpy.typing import NDArray

from soma.eeg.preprocessing import ProcessedRecording
from soma.signal.spectral import BANDS


@dataclass(frozen=True)
class BurstConfig:
    strategies: tuple[str, ...] = ("rest_dual", "rest_percentile")
    low_multiplier: float = 1.0
    high_multiplier: float = 2.0
    low_quantile: float = 0.75
    high_quantile: float = 0.95
    fixed_low_v: float = 3e-6
    fixed_high_v: float = 5e-6
    min_cycles: float = 3.0
    filter_cycles: float = 7.0
    hilbert_guard_s: float = 2.0
    event_bin_s: float = 0.1

    def __post_init__(self) -> None:
        if (
            not self.strategies
            or len(set(self.strategies)) != len(self.strategies)
            or set(self.strategies) - {"rest_dual", "rest_percentile", "fixed"}
        ):
            raise ValueError("Choose unique rest_dual, rest_percentile or fixed strategies")
        values = [
            self.low_multiplier,
            self.high_multiplier,
            self.fixed_low_v,
            self.fixed_high_v,
            self.min_cycles,
            self.filter_cycles,
            self.hilbert_guard_s,
            self.event_bin_s,
        ]
        if not np.isfinite(values).all() or min(values) <= 0:
            raise ValueError("Burst thresholds, cycles and guard must be finite positive")
        if not (
            self.low_multiplier <= self.high_multiplier
            and self.fixed_low_v <= self.fixed_high_v
            and 0 < self.low_quantile <= self.high_quantile < 1
        ):
            raise ValueError("Burst thresholds/quantiles must be ordered")


DEFAULT_BURSTS = BurstConfig()


def intervals(mask: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """Half-open true intervals, including runs at either boundary."""
    if mask.ndim != 1:
        raise ValueError("Burst mask must be 1D")
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return list(
        zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist(), strict=True)
    )


def calibrated_detector(
    filtered: NDArray[np.float64], fs: float, low_v: float, high_v: float, minimum_duration_s: float
) -> NDArray[np.bool_]:
    """Use genuine NeuroDSP dual-threshold logic, with thresholds specified in volts.

    NeuroDSP divides its Hilbert amplitude by the whole-input median; rescale the
    thresholds by that same median so fixed/rest calibration is not lost.
    """
    if (
        filtered.ndim != 1
        or len(filtered) < 3
        or not np.isfinite(filtered).all()
        or not np.isfinite([fs, low_v, high_v, minimum_duration_s]).all()
        or fs <= 0
        or not 0 < low_v <= high_v
        or minimum_duration_s <= 0
    ):
        raise ValueError("Invalid finite signal, sampling rate, thresholds or duration")
    median = float(np.median(amp_by_time(filtered, fs, f_range=None, remove_edges=False)))
    if median <= 0:
        return np.zeros(len(filtered), dtype=bool)
    return np.asarray(
        detect_bursts_dual_threshold(
            filtered,
            fs,
            (low_v / median, high_v / median),
            f_range=None,
            min_n_cycles=None,
            min_burst_duration=minimum_duration_s,
            avg_type="median",
            magnitude_type="amplitude",
        ),
        dtype=bool,
    )


def map_windows(
    mask: NDArray[np.bool_],
    amplitude: NDArray[np.float64],
    valid: NDArray[np.bool_],
    fs: float,
    windows: pd.DataFrame,
    identity: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Map continuous detections into accepted half-open event windows.

    Rates count real onsets, not entries of an already-active burst into a window.
    Complete-duration estimates omit left/right censored fragments. Occupancy
    and amplitude still use all valid observed burst samples.
    """
    if (
        mask.shape != amplitude.shape
        or mask.shape != valid.shape
        or mask.ndim != 1
        or not np.isfinite(fs)
        or fs <= 0
    ):
        raise ValueError("Aligned 1D burst/amplitude/valid arrays and positive fs required")
    full = intervals(mask)
    summaries, fragments = [], []
    for row in windows.to_dict("records"):
        a, b = int(row["start_sample"]), int(row["stop_sample_exclusive"])
        if not 0 <= a < b <= len(mask):
            raise ValueError("Burst observation window outside recording")
        support = valid[a:b]
        observed = mask[a:b] & support
        n_valid, n_burst = int(support.sum()), int(observed.sum())
        exposure = n_valid / fs
        durations, onsets = [], 0
        for first, last in full:
            lo, hi = max(first, a), min(last, b)
            if lo >= hi:
                continue
            # Usually one contiguous valid region; split explicitly if a caller supplies gaps.
            for rel_a, rel_b in intervals(valid[lo:hi]):
                start, stop = lo + rel_a, lo + rel_b
                left = start > first or (start == 0) or not valid[start - 1]
                right = stop < last or stop == len(mask) or not valid[stop]
                complete = not (left or right)
                if complete:
                    durations.append((stop - start) / fs)
                if start == first and not left:
                    onsets += 1
                fragments.append(
                    {
                        **identity,
                        "trial_index": int(row["index"]),
                        "condition": row["label"],
                        "onset_s": start / fs,
                        "offset_s": stop / fs,
                        "onset_relative_s": start / fs - float(row["onset_s"]),
                        "offset_relative_s": stop / fs - float(row["onset_s"]),
                        "observed_duration_s": (stop - start) / fs,
                        "mean_amplitude_v": float(np.mean(amplitude[start:stop])),
                        "left_censored": left,
                        "right_censored": right,
                        "complete": complete,
                    }
                )
        summaries.append(
            {
                **identity,
                "trial_index": int(row["index"]),
                "condition": row["label"],
                "valid_observation_s": exposure,
                "burst_observation_s": n_burst / fs,
                "occupancy": n_burst / n_valid if n_valid else np.nan,
                "onset_count": onsets,
                "rate_hz": onsets / exposure if exposure else np.nan,
                "complete_count": len(durations),
                "complete_duration_sum_s": float(sum(durations)),
                "mean_complete_duration_s": float(np.mean(durations)) if durations else np.nan,
                "amplitude_sum_v": float(amplitude[a:b][observed].sum()),
                "burst_samples": n_burst,
                "mean_burst_amplitude_v": float(amplitude[a:b][observed].mean())
                if n_burst
                else np.nan,
            }
        )
    summary_columns = [
        *identity,
        "trial_index",
        "condition",
        "valid_observation_s",
        "burst_observation_s",
        "occupancy",
        "onset_count",
        "rate_hz",
        "complete_count",
        "complete_duration_sum_s",
        "mean_complete_duration_s",
        "amplitude_sum_v",
        "burst_samples",
        "mean_burst_amplitude_v",
    ]
    return pd.DataFrame(summaries, columns=summary_columns), pd.DataFrame(fragments)


def analyze_bursts(
    processed: ProcessedRecording,
    trials: pd.DataFrame,
    subject: int,
    run: int,
    recording: str,
    cfg: BurstConfig = DEFAULT_BURSTS,
) -> dict[str, Any]:
    fs, n = processed.fs, processed.data.shape[1]
    if not np.isfinite(processed.data).all():
        raise ValueError("Burst input contains nonfinite data")
    windows = trials[trials.stage.isin(["analysis", "rest"]) & trials.accepted].copy()
    features, fragments, calibration, dynamics = [], [], [], []
    for channel, values in zip(processed.channels, processed.data, strict=True):
        for band, bounds in BANDS.items():
            if not 0 < bounds[0] < bounds[1] < fs / 2:
                raise ValueError("Burst band must be below Nyquist")
            pad = int(np.ceil(max(cfg.hilbert_guard_s, cfg.filter_cycles / bounds[0]) * fs))
            padded = np.pad(values, (pad, pad), mode="reflect")
            filtered, kernel = filter_signal(
                padded,
                fs,
                "bandpass",
                bounds,
                filter_type="fir",
                n_cycles=cfg.filter_cycles,
                remove_edges=False,
                return_filter=True,
            )
            amplitude_padded = np.asarray(
                amp_by_time(filtered, fs, f_range=None, remove_edges=False)
            )
            amplitude = amplitude_padded[pad : pad + n]
            edge = (
                processed.edge_samples + len(kernel) // 2 + int(np.ceil(cfg.hilbert_guard_s * fs))
            )
            valid = (np.arange(n) >= edge) & (np.arange(n) < n - edge)
            rest_mask = np.zeros(n, dtype=bool)
            for row in windows[windows.code == "T0"].to_dict("records"):
                rest_mask[int(row["start_sample"]) : int(row["stop_sample_exclusive"])] = True
            reference = amplitude[rest_mask & valid]
            for strategy in cfg.strategies:
                low, high = cfg.fixed_low_v, cfg.fixed_high_v
                available = bool(valid.any())
                if strategy != "fixed":
                    available &= bool(reference.size and np.median(reference) > 0)
                    if available:
                        if strategy == "rest_dual":
                            low, high = (
                                float(np.median(reference)) * x
                                for x in (cfg.low_multiplier, cfg.high_multiplier)
                            )
                        else:
                            low, high = (
                                float(np.quantile(reference, q))
                                for q in (cfg.low_quantile, cfg.high_quantile)
                            )
                identity = {
                    "subject": subject,
                    "run": run,
                    "recording": recording,
                    "channel": channel,
                    "band": band,
                    "strategy": strategy,
                }
                calibration.append(
                    {
                        **identity,
                        "available": available,
                        "low_amplitude_v": low if available else None,
                        "high_amplitude_v": high if available else None,
                        "reference_samples": int(reference.size),
                        "reference_exposure_s": reference.size / fs,
                        "edge_samples": edge,
                        "reflect_padding_samples": pad,
                        "fir_half_support_samples": len(kernel) // 2,
                        "fir_coefficients": kernel.tolist(),
                        "minimum_duration_s": cfg.min_cycles / bounds[0],
                    }
                )
                mask = (
                    calibrated_detector(
                        np.asarray(filtered), fs, low, high, cfg.min_cycles / bounds[0]
                    )[pad : pad + n]
                    if available
                    else np.zeros(n, dtype=bool)
                )
                use_valid = valid if available else np.zeros(n, dtype=bool)
                table, events = map_windows(mask, amplitude, use_valid, fs, windows, identity)
                dynamics.append(
                    event_dynamics(mask, use_valid, fs, windows, identity, cfg.event_bin_s)
                )
                features.append(table)
                fragments.append(events)
    columns = [
        "subject",
        "run",
        "recording",
        "channel",
        "band",
        "strategy",
        "trial_index",
        "condition",
        "onset_s",
        "offset_s",
        "onset_relative_s",
        "offset_relative_s",
        "observed_duration_s",
        "mean_amplitude_v",
        "left_censored",
        "right_censored",
        "complete",
    ]
    event_frames = [f for f in fragments if not f.empty]
    return {
        "features": pd.concat(features, ignore_index=True) if features else pd.DataFrame(),
        "events": pd.concat(event_frames, ignore_index=True)
        if event_frames
        else pd.DataFrame(columns=columns),
        "dynamics": pd.concat(dynamics, ignore_index=True),
        "calibration": calibration,
        "config": {**asdict(cfg), "bands_hz": BANDS},
    }


def event_dynamics(
    mask: NDArray[np.bool_],
    valid: NDArray[np.bool_],
    fs: float,
    windows: pd.DataFrame,
    identity: dict[str, Any],
    bin_s: float = 0.1,
) -> pd.DataFrame:
    """Observed occupancy in event-relative bins, retaining zero-exposure bins."""
    if not np.isfinite(bin_s) or bin_s <= 0:
        raise ValueError("Event bins must have finite positive duration")
    width = max(1, int(round(bin_s * fs)))
    rows = []
    for row in windows.to_dict("records"):
        a, b = int(row["start_sample"]), int(row["stop_sample_exclusive"])
        for start in range(a, b, width):
            stop = min(start + width, b)
            exposure = int(valid[start:stop].sum())
            observed = int((mask[start:stop] & valid[start:stop]).sum())
            rows.append(
                {
                    **identity,
                    "trial_index": int(row["index"]),
                    "condition": row["label"],
                    "bin_start_relative_s": start / fs - float(row["onset_s"]),
                    "bin_stop_relative_s": stop / fs - float(row["onset_s"]),
                    "exposure_s": exposure / fs,
                    "burst_s": observed / fs,
                    "occupancy": observed / exposure if exposure else np.nan,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            *identity,
            "trial_index",
            "condition",
            "bin_start_relative_s",
            "bin_stop_relative_s",
            "exposure_s",
            "burst_s",
            "occupancy",
        ],
    )
