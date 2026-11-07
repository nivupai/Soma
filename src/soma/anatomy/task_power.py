"""Short audiovisual epochs: explicitly limited-resolution trialwise Welch power."""

from typing import Any

import numpy as np
from neurodsp.spectral import compute_spectrum_welch
from scipy.integrate import trapezoid


def short_epoch_band_power(
    data: Any, fs: float, band: tuple[float, float] = (8.0, 13.0)
) -> np.ndarray[Any, Any]:
    x = np.asarray(data, dtype=float)
    if (
        x.ndim != 2
        or x.shape[1] < 16
        or not np.isfinite(x).all()
        or not 0 < band[0] < band[1] < fs / 2
    ):
        raise ValueError("Finite source×time epochs and a supported band below Nyquist required")
    segment = min(int(fs), x.shape[1])
    frequencies, spectrum = compute_spectrum_welch(
        x, fs, nperseg=segment, noverlap=segment // 2, fast_len=False
    )
    edges = []
    for edge in band:
        right = int(np.searchsorted(frequencies, edge))
        weight = (edge - frequencies[right - 1]) / (frequencies[right] - frequencies[right - 1])
        edges.append((1 - weight) * spectrum[:, right - 1] + weight * spectrum[:, right])
    mask = (frequencies > band[0]) & (frequencies < band[1])
    return np.asarray(
        trapezoid(
            np.column_stack([edges[0], spectrum[:, mask], edges[1]]),
            np.r_[band[0], frequencies[mask], band[1]],
            axis=1,
        ),
        dtype=float,
    )
