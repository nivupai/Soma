"""EEG uses volts, seconds and Hz; no implicit unit conversions or downloads."""

from pathlib import Path
from typing import Any

from soma.core.signal import Signal as Signal
from soma.datasets.eegbci import load_recording as load_recording
from soma.eeg.epoching import EpochConfig as EpochConfig
from soma.eeg.epoching import EpochSet as EpochSet
from soma.eeg.epoching import extract_trials as extract_trials
from soma.eeg.epoching import trial_table as trial_table
from soma.eeg.events import Event as Event
from soma.eeg.events import event_table as event_table
from soma.eeg.events import parse_events as parse_events
from soma.eeg.timefrequency import MorletConfig as MorletConfig
from soma.eeg.timefrequency import morlet_power as morlet_power
from soma.eeg.timefrequency import trial_spectra as trial_spectra
from soma.signal.bursts import calibrated_detector as calibrated_detector
from soma.signal.bursts import intervals as intervals
from soma.signal.spectral import BANDS as BANDS
from soma.signal.spectral import Spectrum as Spectrum
from soma.signal.spectral import WelchConfig as WelchConfig
from soma.signal.spectral import welch as welch


def eeg_spectrum(signal: Signal, config: WelchConfig | None = None) -> Spectrum:
    """Strict EEG convenience boundary; existing general-unit welch stays compatible."""
    if signal.unit != "V":
        raise ValueError("EEG spectrum requires volts (V); convert explicitly")
    return welch(signal, config)


def recording_metadata(root: Path, subject: int, run: int) -> dict[str, Any]:
    """Cached EEGBCI metadata and trial events, closing the lazy recording handle."""
    raw, metadata = load_recording(root, subject, run)
    try:
        return {
            **metadata,
            "events": event_table(parse_events(raw, subject, run, f"{subject}:{run}")).to_dict(
                "records"
            ),
        }
    finally:
        raw.close()
