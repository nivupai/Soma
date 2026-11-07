"""Batched NeuroDSP Welch spectra; trial power precedes all averaging."""

import numpy as np
from neurodsp.spectral import compute_spectrum_welch
from numpy.typing import NDArray
from scipy.integrate import trapezoid


def band_powers(data: NDArray[np.float64], sfreq: float) -> dict[str, NDArray[np.float64]]:
    if not np.isfinite(sfreq) or sfreq <= 60:
        raise ValueError("Sampling frequency must put 30 Hz strictly below Nyquist")
    if data.ndim != 2 or not np.isfinite(data).all() or data.shape[1] < int(sfreq):
        raise ValueError("Finite source by time data with at least one second required")
    frequencies, spectrum = compute_spectrum_welch(
        data, sfreq, nperseg=int(sfreq), noverlap=int(sfreq / 2), fast_len=False
    )
    result = {}
    for name, lo, hi in (("mu", 8, 13), ("beta", 13, 30)):
        # Interpolate both exact band boundaries, including noninteger-Hz grids.
        mask = (frequencies > lo) & (frequencies < hi)
        edges = []
        for edge in (lo, hi):
            right = int(np.searchsorted(frequencies, edge))
            weight = (edge - frequencies[right - 1]) / (frequencies[right] - frequencies[right - 1])
            edges.append((1 - weight) * spectrum[:, right - 1] + weight * spectrum[:, right])
        values = np.column_stack([edges[0], spectrum[:, mask], edges[1]])
        result[name] = np.asarray(
            trapezoid(values, np.r_[lo, frequencies[mask], hi], axis=1), dtype=float
        )
    return result
