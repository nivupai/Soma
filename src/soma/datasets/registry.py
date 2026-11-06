"""Small factual registry; loader implementations remain in dataset adapters."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from soma.datasets.eegbci import SOURCE, load_recording


@dataclass(frozen=True)
class Dataset:
    identifier: str
    modality: str
    source: str
    citation: str
    license: str
    sampling_hz: float
    eeg_channels: int
    subjects: str
    runs: str
    loader: Callable[..., Any]


REGISTRY = {
    "eegmmidb": Dataset(
        "eegmmidb",
        "EEG",
        SOURCE,
        "Schalk (2009), doi:10.13026/C28G6P; Schalk et al. (2004), BCI2000, "
        "IEEE TBME 51(6):1034–1043. Cite PhysioNet as requested at source.",
        "Open Data Commons Attribution License v1.0 (ODC-By 1.0)",
        160.0,
        64,
        "1–109",
        "1–14; meanings depend on run",
        load_recording,
    )
}
