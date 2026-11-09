"""NeuroDSP trial-local PSD/context bank and training-only burst calibration."""

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from neurodsp.filt import filter_signal
from neurodsp.timefrequency import amp_by_time
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from soma.core.signal import Signal
from soma.decoding.covariance import TrialCovariances
from soma.decoding.data import FloatArray, TrialDataset
from soma.signal.bursts import calibrated_detector, intervals
from soma.signal.spectral import BANDS, WelchConfig, welch


@dataclass(frozen=True)
class FeatureBank:
    dataset: TrialDataset
    logpowers: FloatArray  # trials × channels × bands
    burst_contexts: FloatArray  # trials × bands × channels × (filtered, amplitude) × time
    profile: dict[str, float]
    covariances: FloatArray
    covariance_parameters: dict[str, Any]
    covariance_diagnostics: list[dict[str, float]]

    def input(self, model: str) -> FloatArray:
        if model == "motor_mu_lr":
            return self.logpowers[:, [self.dataset.channels.index(c) for c in ("C3", "C4")], 0]
        if model == "motor_bands_lda":
            return self.logpowers[
                :, [self.dataset.channels.index(c) for c in ("C3", "C4")]
            ].reshape(len(self.dataset.y), -1)
        if model == "multiband_lr":
            return self.logpowers.reshape(len(self.dataset.y), -1)
        if model == "burst_lr":
            return self.burst_contexts
        if model in ("covariance_lda", "euclidean_mdm", "riemann_mdm", "tangent_lr"):
            return self.covariances
        return self.dataset.X


def covariance_parameters(protocol: dict[str, Any]) -> dict[str, Any]:
    fixed = protocol["fixed"]
    return {
        "estimator": fixed["covariance_estimator"],
        "relative_floor": fixed["covariance_relative_floor"],
        "trace_normalize": fixed["covariance_trace_normalize"],
    }


def build_bank(
    dataset: TrialDataset, covariance_config: dict[str, Any] | None = None
) -> FeatureBank:
    start = time.perf_counter()
    powers = np.empty((*dataset.X.shape[:2], 2))
    config = WelchConfig(round(dataset.fs), round(dataset.fs) // 2)
    for t, trial in enumerate(dataset.X):
        for c, channel in enumerate(dataset.channels):
            spectrum = welch(Signal(trial[c], dataset.fs, channel), config)
            powers[t, c] = [spectrum.band_power(*band) for band in BANDS.values()]
    if np.any(powers <= 0):
        raise ValueError("Zero spectral power cannot be logged")
    psd_s = time.perf_counter() - start
    start = time.perf_counter()
    context = np.empty((len(dataset.y), 2, len(dataset.channels), 2, dataset.context.shape[-1]))
    for t, trial in enumerate(dataset.context):
        for b, band in enumerate(BANDS.values()):
            for c, signal in enumerate(trial):
                filtered = filter_signal(
                    signal,
                    dataset.fs,
                    "bandpass",
                    band,
                    n_cycles=3,
                    remove_edges=False,
                )
                context[t, b, c, 0] = filtered
                context[t, b, c, 1] = amp_by_time(
                    filtered, dataset.fs, f_range=None, remove_edges=False
                )
    if not np.isfinite(context).all():
        raise ValueError("Nonfinite NeuroDSP burst context")
    burst_seconds = time.perf_counter() - start
    start = time.perf_counter()
    params = covariance_config or {
        "estimator": "oas",
        "relative_floor": 1e-6,
        "trace_normalize": False,
    }
    covariance = TrialCovariances(**params)
    matrices = covariance.fit_transform(dataset.X)
    covariance_seconds = time.perf_counter() - start
    return FeatureBank(
        dataset,
        np.log(powers),
        context,
        {
            "psd_seconds": psd_s,
            "burst_context_seconds": burst_seconds,
            "trial_covariance_seconds": covariance_seconds,
            "bank_mib": (powers.nbytes + context.nbytes + dataset.X.nbytes + matrices.nbytes)
            / 2**20,
        },
        matrices,
        params,
        covariance.last_diagnostics_,
    )


class TrainingBursts(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    def __init__(
        self, fs: float = 160.0, low: float = 1.0, high: float = 2.0, minimum_cycles: float = 3.0
    ) -> None:
        self.fs = fs
        self.low = low
        self.high = high
        self.minimum_cycles = minimum_cycles

    def _validate(self, X: FloatArray) -> tuple[int, int]:
        if (
            X.ndim != 5
            or X.shape[1] != 2
            or X.shape[3] != 2
            or X.shape[-1] != round(4 * self.fs)
            or not np.isfinite(X).all()
            or not 0 < self.low <= self.high
            or self.minimum_cycles <= 0
        ):
            raise ValueError("Expected finite trial/band/channel/field/four-second-context tensor")
        return round(self.fs), round(3 * self.fs)

    def fit(self, X: FloatArray, y: Any = None) -> "TrainingBursts":
        a, b = self._validate(X)
        if not len(X):
            raise ValueError("No burst calibration trials")
        self.threshold_reference_ = np.median(X[:, :, :, 1, a:b], axis=(0, 3))
        if np.any(self.threshold_reference_ <= 0):
            raise ValueError("Training burst calibration has no positive amplitude")
        self.n_features_in_ = X.shape[2]
        return self

    def transform(self, X: FloatArray) -> FloatArray:
        check_is_fitted(self, "threshold_reference_")
        a, b = self._validate(X)
        if X.shape[2] != self.n_features_in_:
            raise ValueError("Burst channel count changed")
        rows = []
        for trial in X:
            row = []
            for band, limits in enumerate(BANDS.values()):
                for c in range(X.shape[2]):
                    calibration = self.threshold_reference_[band, c]
                    mask = calibrated_detector(
                        trial[band, c, 0],
                        self.fs,
                        self.low * calibration,
                        self.high * calibration,
                        float(self.minimum_cycles / np.mean(limits)),
                    )
                    observed = mask[a:b]
                    events = intervals(mask)
                    onsets = sum(a <= first < b for first, _ in events)
                    durations = [
                        (last - first) / self.fs for first, last in events if a <= first < last <= b
                    ]
                    amplitude = trial[band, c, 1, a:b][observed]
                    row.extend(
                        [
                            float(observed.mean()),
                            float(amplitude.mean()) if len(amplitude) else 0.0,
                            onsets / ((b - a) / self.fs),
                            float(np.mean(durations)) if durations else 0.0,
                        ]
                    )
            rows.append(row)
        return np.asarray(rows)
