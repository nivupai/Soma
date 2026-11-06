"""Interpretable QC flags, not automatic diagnoses of physiological artifacts."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.signal import periodogram


@dataclass(frozen=True)
class QualityConfig:
    channel_ptp_v: float = 500e-6
    trial_ptp_v: float = 300e-6
    excursion_v: float = 150e-6
    flat_std_v: float = 0.05e-6

    def __post_init__(self) -> None:
        if not np.isfinite(list(self.__dict__.values())).all() or min(self.__dict__.values()) <= 0:
            raise ValueError("QC thresholds must be finite positive values in volts")


DEFAULT_QUALITY = QualityConfig()


def quality_metrics(
    data: NDArray[np.float64],
    channels: tuple[str, ...],
    fs: float,
    config: QualityConfig = DEFAULT_QUALITY,
    *,
    trial: bool = False,
    line_hz: float | None = None,
) -> list[dict[str, Any]]:
    """Channel×sample input; finite subset metrics never imply repaired data."""
    if data.ndim != 2 or data.shape[0] != len(channels) or data.shape[1] < 2:
        raise ValueError("QC requires channel×sample data and matching channel coordinates")
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError("Sampling rate must be positive and finite")
    if line_hz is not None and not 1 < line_hz < fs / 2 - 1:
        raise ValueError("Line frequency ±1 Hz must be below Nyquist")
    reports = []
    for ch, values in zip(channels, data, strict=True):
        finite = np.isfinite(values)
        x = values[finite]
        flags = []
        if not finite.all():
            flags.append("nonfinite")
        ptp = float(np.ptp(x)) if x.size else None
        variance = float(np.var(x)) if x.size else None
        rms = float(np.sqrt(np.mean(x**2))) if x.size else None
        if ptp is not None and ptp > (config.trial_ptp_v if trial else config.channel_ptp_v):
            flags.append("high_peak_to_peak")
        if variance is not None and variance < config.flat_std_v**2:
            flags.append("flat")
        if x.size and np.max(np.abs(x)) > config.excursion_v:
            flags.append("high_amplitude_excursion")
        line_ratio = None
        if line_hz is not None and finite.all():
            f, p = periodogram(values, fs)
            center = np.abs(f - line_hz) <= 1
            flanks = (np.abs(f - line_hz) >= 2) & (np.abs(f - line_hz) <= 4)
            if center.any() and flanks.any() and np.mean(p[flanks]) > 0:
                line_ratio = float(np.mean(p[center]) / np.mean(p[flanks]))
        reports.append(
            {
                "channel": ch,
                "ptp_v": ptp,
                "rms_v": rms,
                "variance_v2": variance,
                "nonfinite_samples": int((~finite).sum()),
                "excursion_samples": int(np.sum(np.abs(x) > config.excursion_v)),
                "line_to_flank_density_ratio": line_ratio,
                "flags": flags,
            }
        )
    return reports
