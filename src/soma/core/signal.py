"""One-dimensional sampled signals, independent of MNE."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class Signal:
    """Real samples (n,), fs in Hz, t[i] = t0 + i/fs seconds.

    EEG uses volts. Arrays are borrowed without copying when already float64;
    callers must not mutate them while an analysis is running. No interpolation,
    resampling or omission of nonfinite values is implicit.
    """

    values: NDArray[np.float64]
    fs: float
    channel: str = "synthetic"
    unit: str = "V"
    t0: float = 0.0

    def __post_init__(self) -> None:
        if np.iscomplexobj(self.values):
            raise ValueError("Signal must be real-valued")
        data = np.asarray(self.values, dtype=np.float64)
        if data.ndim != 1 or data.size < 2:
            raise ValueError("Signal must be one-dimensional with at least two samples")
        if not np.isfinite(data).all():
            raise ValueError("Signal contains NaN or infinite values")
        if not np.isfinite(self.fs) or self.fs <= 0 or not np.isfinite(self.t0):
            raise ValueError("fs must be finite and positive; t0 must be finite")
        object.__setattr__(self, "values", data)

    @property
    def times(self) -> NDArray[np.float64]:
        return self.t0 + np.arange(self.values.size) / self.fs
