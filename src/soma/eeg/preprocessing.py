"""Explicit continuous preprocessing with measured filter response and edge guard."""

from dataclasses import asdict, dataclass
from typing import Any

import mne
import numpy as np
from numpy.typing import NDArray
from scipy.signal import butter, iirnotch, sosfilt, sosfiltfilt, sosfreqz, tf2sos

from soma.eeg.quality import DEFAULT_QUALITY, QualityConfig, quality_metrics


@dataclass(frozen=True)
class PreprocessingConfig:
    reference: str = "average"
    highpass_hz: float | None = 1.0
    lowpass_hz: float | None = 40.0
    order: int = 4
    phase: str = "zero"
    notch_hz: float | None = None
    notch_q: float = 30.0
    notch_justification: str | None = None
    remove_dc: bool = False
    transient_tolerance: float = 1e-4
    reference_channels: tuple[str, ...] = ()


DEFAULT_PREPROCESSING = PreprocessingConfig()


@dataclass(frozen=True)
class ProcessedRecording:
    data: NDArray[np.float64]
    channels: tuple[str, ...]
    fs: float
    edge_samples: int
    summary: dict[str, Any]


def select_eeg(raw: Any, channels: tuple[str, ...] | None = None) -> tuple[str, ...]:
    names = tuple(raw.ch_names[i] for i in mne.pick_types(raw.info, eeg=True, exclude=[]))
    selected = names if channels is None else channels
    if not selected or len(set(selected)) != len(selected) or not set(selected) <= set(names):
        raise ValueError("Select unique, available EEG channels")
    if set(selected) & set(raw.info["bads"]):
        raise ValueError("Selected channels include marked bads; explicitly select usable channels")
    return selected


def rereference(
    data: NDArray[np.float64], reference: str, indices: tuple[int, ...] | None = None
) -> NDArray[np.float64]:
    if reference == "none":
        return data.copy()
    if reference == "channels":
        if (
            not indices
            or len(set(indices)) != len(indices)
            or any(i < 0 or i >= data.shape[0] for i in indices)
        ):
            raise ValueError("Explicit reference requires unique available EEG channel indices")
        return np.asarray(
            data - np.mean(data[list(indices)], axis=0, keepdims=True), dtype=np.float64
        )
    if reference != "average" or data.shape[0] < 2:
        raise ValueError("Reference must be none, or average with at least two EEG channels")
    return np.asarray(data - np.mean(data, axis=0, keepdims=True), dtype=np.float64)


def design_filter(
    fs: float, cfg: PreprocessingConfig
) -> tuple[NDArray[np.float64], dict[str, Any]]:
    if not np.isfinite(fs) or fs <= 0 or cfg.phase not in {"zero", "causal"}:
        raise ValueError("Invalid sampling frequency or phase (zero/causal)")
    if not isinstance(cfg.order, int) or not 1 <= cfg.order <= 12:
        raise ValueError("Butterworth order must be an integer from 1 to 12")
    if not 0 < cfg.transient_tolerance < 1:
        raise ValueError("Transient tolerance must lie between zero and one")
    cutoffs = [f for f in (cfg.highpass_hz, cfg.lowpass_hz) if f is not None]
    if any(not np.isfinite(f) or not 0 < f < fs / 2 for f in cutoffs):
        raise ValueError("Filter cutoffs must be finite and strictly inside (0, Nyquist)")
    if len(cutoffs) == 2 and cutoffs[0] >= cutoffs[1]:
        raise ValueError("High-pass must be below low-pass")
    sections = []
    if cutoffs:
        kind = (
            "bandpass"
            if len(cutoffs) == 2
            else ("highpass" if cfg.highpass_hz is not None else "lowpass")
        )
        sections.append(
            butter(
                cfg.order,
                cutoffs if len(cutoffs) == 2 else cutoffs[0],
                btype=kind,
                fs=fs,
                output="sos",
            )
        )
    if cfg.notch_hz is not None:
        if not cfg.notch_justification or not cfg.notch_justification.strip():
            raise ValueError("Notch requires an observed-contamination justification")
        if not np.isfinite([cfg.notch_hz, cfg.notch_q]).all() or not (
            0 < cfg.notch_hz < fs / 2 and cfg.notch_q > 0
        ):
            raise ValueError("Notch frequency must be below Nyquist; Q must be positive")
        b, a = iirnotch(cfg.notch_hz, cfg.notch_q, fs=fs)
        sections.append(tf2sos(b, a))
    if not sections:
        return np.empty((0, 6)), {"enabled": False, "edge_samples": 0}
    sos = np.concatenate(sections)
    # Probe up to 120 seconds; fail if decay cannot be established, never clip silently.
    impulse = np.zeros(int(np.ceil(120 * fs)))
    impulse[0] = 1
    response = sosfilt(sos, impulse)
    tail = np.cumsum(np.abs(response)[::-1])[::-1]
    threshold = cfg.transient_tolerance * tail[0]
    candidates = np.flatnonzero(tail < threshold)
    if candidates.size == 0 or candidates[0] >= impulse.size // 2:
        raise ValueError("Filter transient not resolved within 60 s; revise design")
    edge = max(int(candidates[0]), 3 * (2 * len(sos) + 1))
    f, h = sosfreqz(sos, worN=8192, fs=fs)
    gain = np.abs(h) ** (2 if cfg.phase == "zero" else 1)
    phase = np.zeros_like(f) if cfg.phase == "zero" else np.unwrap(np.angle(h))
    group_delay = -np.gradient(phase, 2 * np.pi * f)
    db = 20 * np.log10(np.maximum(gain, np.finfo(float).tiny))
    crossings = np.flatnonzero(np.diff(db >= -3))
    transitions = {
        str(level): f[np.flatnonzero(np.diff(db >= level))].tolist() for level in (-3, -6, -20, -40)
    }
    return np.asarray(sos), {
        "enabled": True,
        "family": "Butterworth plus optional IIR notch",
        "sos": sos.tolist(),
        "single_pass_order": 2 * len(sos),
        "effective_order": 2 * len(sos) * (2 if cfg.phase == "zero" else 1),
        "phase": "zero-phase forward-backward"
        if cfg.phase == "zero"
        else "causal, nonlinear phase",
        "padding": "odd reflection" if cfg.phase == "zero" else "zero initial state",
        "padlen_samples": edge if cfg.phase == "zero" else 0,
        "edge_samples": edge,
        "edge_seconds": edge / fs,
        "edge_rule": (
            "single-pass impulse absolute-tail fraction below transient_tolerance; guard both ends"
        ),
        "response_frequency_hz": f.tolist(),
        "effective_amplitude_gain": gain.tolist(),
        "effective_phase_radians": phase.tolist(),
        "group_delay_s": group_delay.tolist(),
        "effective_minus3db_crossings_hz": f[crossings].tolist(),
        "transition_crossings_hz_by_db": transitions,
    }


def preprocess(
    raw: Any,
    cfg: PreprocessingConfig = DEFAULT_PREPROCESSING,
    channels: tuple[str, ...] | None = None,
    qc: QualityConfig = DEFAULT_QUALITY,
) -> ProcessedRecording:
    names = select_eeg(raw, channels)
    fs = float(raw.info["sfreq"])
    data = np.asarray(raw.get_data(picks=list(names)), dtype=np.float64)
    before = quality_metrics(data, names, fs, qc, line_hz=cfg.notch_hz)
    if not np.isfinite(data).all():
        raise ValueError("Nonfinite EEG samples: inspect quality_metrics before preprocessing")
    if cfg.reference_channels and cfg.reference != "channels":
        raise ValueError("reference_channels requires reference=channels")
    if not set(cfg.reference_channels) <= set(names):
        raise ValueError("Reference channel is unavailable in selected EEG")
    indices = tuple(names.index(ch) for ch in cfg.reference_channels)
    data = rereference(data, cfg.reference, indices)
    if cfg.remove_dc:
        data -= np.mean(data, axis=1, keepdims=True)
    sos, characteristics = design_filter(fs, cfg)
    edge = int(characteristics["edge_samples"])
    if sos.size:
        if data.shape[1] <= 2 * edge + 2:
            raise ValueError("Recording too short for filter transient guards")
        data = (
            sosfiltfilt(sos, data, axis=-1, padtype="odd", padlen=edge)
            if cfg.phase == "zero"
            else sosfilt(sos, data, axis=-1)
        )
    if not np.isfinite(data).all():
        raise ValueError("Filtering produced nonfinite data")
    return ProcessedRecording(
        np.asarray(data),
        names,
        fs,
        edge,
        {
            "config": asdict(cfg),
            "channels": list(names),
            "units": "V",
            "fs_hz": fs,
            "reference_channels": (
                list(names) if cfg.reference == "average" else list(cfg.reference_channels)
            ),
            "filter": characteristics,
            "quality_before": before,
            "quality_after": quality_metrics(data, names, fs, qc, line_hz=cfg.notch_hz),
            "raw_mutated": False,
            "ica": False,
            "channel_policy": "QC flags reported; no automatic channel exclusion or interpolation",
        },
    )
