"""Seeded signal laboratory; amplitudes are in volts."""

import numpy as np

from soma.core.signal import Signal

KINDS = ("sine10", "sine20", "combined", "noisy", "modulated", "burst")


def synthetic(kind: str, fs: float = 160.0, duration: float = 20.0, seed: int = 42) -> Signal:
    if kind not in KINDS:
        raise ValueError(f"Unknown signal {kind!r}; choose from {KINDS}")
    if not np.isfinite([fs, duration]).all() or fs <= 40 or duration <= 0:
        raise ValueError("fs must exceed 40 Hz (20 Hz below Nyquist); duration must be positive")
    n = int(round(fs * duration))
    if n < 2:
        raise ValueError("Duration must contain at least two samples")
    t = np.arange(n) / fs
    a = 1e-5
    s10 = a * np.sin(2 * np.pi * 10 * t)
    noise = np.random.default_rng(seed).normal(0, 0.3 * a, n)
    if kind == "sine10":
        values = s10
    elif kind == "sine20":
        values = a * np.sin(2 * np.pi * 20 * t)
    elif kind == "combined":
        values = s10 + a * np.sin(2 * np.pi * 20 * t)
    elif kind == "noisy":
        values = s10 + noise
    elif kind == "modulated":
        values = (1 + 0.5 * np.sin(2 * np.pi * 0.5 * t)) * s10
    else:
        values = noise + s10 * ((t >= 0.4 * duration) & (t < 0.6 * duration))
    return Signal(values, fs, channel=kind)
