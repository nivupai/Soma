"""NeuroDSP Welch density estimates and frequency-integrated absolute power."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from neurodsp.spectral import compute_spectrum_welch
from numpy.typing import NDArray
from scipy.integrate import trapezoid

from soma.core.signal import Signal

BANDS = {"mu": (8.0, 13.0), "beta": (13.0, 30.0)}


@dataclass(frozen=True)
class WelchConfig:
    nperseg: int = 320
    noverlap: int = 160
    window: str = "hann"
    average: str = "mean"


@dataclass(frozen=True)
class Spectrum:
    frequencies: NDArray[np.float64]
    density: NDArray[np.float64]
    metadata: dict[str, Any]

    @property
    def peak_frequency(self) -> float:
        return float(self.frequencies[np.argmax(self.density)])

    def band_power(self, low: float, high: float) -> float:
        """Trapezoidal integral with linearly interpolated band boundaries."""
        f, p = self.frequencies, self.density
        if not np.isfinite([low, high]).all() or not f[0] <= low < high <= f[-1]:
            raise ValueError("Band must be finite, ordered and inside the PSD frequency range")
        interior = (f > low) & (f < high)
        x = np.r_[low, f[interior], high]
        y = np.r_[np.interp(low, f, p), p[interior], np.interp(high, f, p)]
        return float(trapezoid(y, x))


def welch(signal: Signal, config: WelchConfig | None = None) -> Spectrum:
    """One-sided density; NeuroDSP uses SciPy spectrogram with constant detrend.

    Reject clipped segment sizes. Disable NeuroDSP fast_len so the requested
    segment length is preserved. Density units are signal.unit squared / Hz.
    """
    cfg = config or WelchConfig()
    if not isinstance(cfg.nperseg, int) or not 2 <= cfg.nperseg <= signal.values.size:
        raise ValueError("nperseg must be an integer in [2, number of samples]")
    if not isinstance(cfg.noverlap, int) or not 0 <= cfg.noverlap < cfg.nperseg:
        raise ValueError("noverlap must be an integer in [0, nperseg)")
    if cfg.average not in {"mean", "median"}:
        raise ValueError("average must be mean or median")
    # Recheck borrowed samples in case the caller has mutated the source array.
    if not np.isfinite(signal.values).all():
        raise ValueError("Signal contains NaN or infinite values")
    f, p = compute_spectrum_welch(
        signal.values,
        signal.fs,
        avg_type=cfg.average,
        window=cfg.window,
        nperseg=cfg.nperseg,
        noverlap=cfg.noverlap,
        nfft=None,
        fast_len=False,
    )
    return Spectrum(
        np.asarray(f),
        np.asarray(p),
        {
            **asdict(cfg),
            "fs_hz": signal.fs,
            "channel": signal.channel,
            "units": f"{signal.unit}^2/Hz",
            "scaling": "density",
            "sidedness": "one-sided",
            "detrend": "constant",
            "median_bias_correction": False,
            "nfft": None,
            "fast_len": False,
            "n_samples": int(signal.values.size),
            "segments": 1 + (signal.values.size - cfg.nperseg) // (cfg.nperseg - cfg.noverlap),
            "bin_spacing_hz": signal.fs / cfg.nperseg,
            "segment_resolution_hz": signal.fs / cfg.nperseg,
        },
    )
