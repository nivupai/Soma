"""Trial Welch matrices and edge-masked MNE Morlet power with named coordinates."""

from dataclasses import dataclass

import numpy as np
from mne.time_frequency import morlet, tfr_array_morlet
from numpy.typing import NDArray

from soma.core.signal import Signal
from soma.eeg.epoching import EpochSet
from soma.signal.spectral import BANDS, Spectrum, WelchConfig, welch


@dataclass(frozen=True)
class TrialSpectra:
    density: NDArray[np.float64]  # trial × channel × frequency, V²/Hz
    frequencies: NDArray[np.float64]
    channels: tuple[str, ...]
    config: WelchConfig

    def bands(self) -> NDArray[np.float64]:
        result = np.empty((*self.density.shape[:2], len(BANDS)))
        for t in range(len(result)):
            for c in range(len(self.channels)):
                spectrum = Spectrum(self.frequencies, self.density[t, c], {})
                result[t, c] = [spectrum.band_power(*band) for band in BANDS.values()]
        return result


def trial_spectra(epochs: EpochSet, cfg: WelchConfig | None = None) -> TrialSpectra:
    config = cfg or WelchConfig(int(round(epochs.fs)), int(round(epochs.fs)) // 2)
    if epochs.data.shape[-1] < config.nperseg:
        raise ValueError("Trials are shorter than the requested Welch segment")
    frequencies = np.asarray(np.fft.rfftfreq(config.nperseg, 1 / epochs.fs), dtype=np.float64)
    result = np.empty((*epochs.data.shape[:2], len(frequencies)))
    for t, trial in enumerate(epochs.data):
        for c, channel in enumerate(epochs.channels):
            spec = welch(Signal(trial[c], epochs.fs, channel), config)
            result[t, c] = spec.density
    return TrialSpectra(result, frequencies, epochs.channels, config)


@dataclass(frozen=True)
class MorletConfig:
    frequencies: tuple[float, ...] = tuple(float(f) for f in range(8, 31))
    n_cycles: float = 5.0


DEFAULT_MORLET = MorletConfig()


@dataclass(frozen=True)
class TimeFrequency:
    power: NDArray[np.float64]  # trial × channel × frequency × time, wavelet power V²
    frequencies: NDArray[np.float64]
    times: NDArray[np.float64]
    channels: tuple[str, ...]
    valid: NDArray[np.bool_]  # frequency × time, full discrete wavelet support
    half_support_s: NDArray[np.float64]
    config: MorletConfig

    def band_trajectories(self) -> NDArray[np.float64]:
        """Mean wavelet power over frequency centers in each band; not a PSD integral."""
        indices = [(self.frequencies >= lo) & (self.frequencies <= hi) for lo, hi in BANDS.values()]
        return np.stack([np.mean(self.power[:, :, mask, :], axis=2) for mask in indices], axis=2)

    def reference_mean(
        self, start_s: float | None = None, stop_s: float | None = None
    ) -> NDArray[np.float64]:
        mask = np.ones(self.times.shape, dtype=bool)
        if start_s is not None:
            mask &= self.times >= start_s
        if stop_s is not None:
            mask &= self.times < stop_s
        values = self.power[..., mask]
        count = np.sum(np.isfinite(values), axis=-1)
        result = np.full(values.shape[:-1], np.nan)
        np.divide(np.nansum(values, axis=-1), count, out=result, where=count > 0)
        return result


def morlet_power(epochs: EpochSet, cfg: MorletConfig = DEFAULT_MORLET) -> TimeFrequency:
    frequencies = np.asarray(cfg.frequencies, dtype=float)
    if (
        frequencies.ndim != 1
        or frequencies.size == 0
        or not np.isfinite(frequencies).all()
        or np.any(np.diff(frequencies) <= 0)
        or frequencies[0] <= 0
        or frequencies[-1] >= epochs.fs / 2
        or not np.isfinite(cfg.n_cycles)
        or cfg.n_cycles <= 0
    ):
        raise ValueError(
            "Morlet frequencies must increase inside (0, Nyquist); cycles must be positive"
        )
    if not np.isfinite(epochs.data).all():
        raise ValueError("Nonfinite input to Morlet analysis")
    wavelets = morlet(epochs.fs, frequencies, n_cycles=cfg.n_cycles, zero_mean=True)
    half = np.asarray([(len(w) - 1) // 2 for w in wavelets], dtype=int)
    n = epochs.data.shape[-1]
    if np.any(2 * half + 1 > n):
        raise ValueError("Wavelet exceeds supported epoch; supply a longer contained segment")
    sample = np.arange(n)
    valid = (sample[None, :] >= half[:, None]) & (sample[None, :] < n - half[:, None])
    shape = (*epochs.data.shape[:2], len(frequencies), n)
    power = np.empty(shape)
    if len(epochs.data):
        power = np.asarray(
            tfr_array_morlet(
                epochs.data,
                epochs.fs,
                frequencies,
                n_cycles=cfg.n_cycles,
                zero_mean=True,
                use_fft=True,
                decim=1,
                output="power",
                n_jobs=1,
                verbose=False,
            )
        )
        power = np.where(valid[None, None, :, :], power, np.nan)
    return TimeFrequency(
        power, frequencies, epochs.times, epochs.channels, valid, half / epochs.fs, cfg
    )
