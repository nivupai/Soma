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


# Imaging references have no EEG sample rate or channel/run contract. Extend the
# registry with a separate typed collection rather than inventing those fields.
@dataclass(frozen=True)
class ReferenceDataset:
    identifier: str
    modality: str
    source: str
    reference: str
    license: str


REFERENCE_REGISTRY = {
    "brainweb": ReferenceDataset(
        "brainweb",
        "simulated MRI",
        "https://brainweb.bic.mni.mcgill.ca/",
        "provided discrete tissue labels / fuzzy memberships",
        "official citation request; record exact downloaded terms",
    ),
    "mindboggle-101": ReferenceDataset(
        "mindboggle-101",
        "T1 MRI",
        "https://mindboggle.info/data.html",
        "manual DKT cortical parcellation",
        "CC BY 4.0 current author release; separate assets have separate terms",
    ),
}

REFERENCE_REGISTRY.update(
    {
        "sci-head": ReferenceDataset(
            "sci-head",
            "T1/T2 MRI and FEM materials",
            "https://sci.utah.edu/sci-head-model/",
            "Seg3D computational eight-tissue model; evidence gaps explicit",
            "public institutional resource; attribution and NIH acknowledgment requested",
        ),
        "mrbrains13": ReferenceDataset(
            "mrbrains13",
            "T1/T1-IR/FLAIR",
            "https://mrbrains13.isi.uu.nl/",
            "authorized local training tissue labels only",
            "registration and dataset access conditions apply; no automatic fetch",
        ),
        "ibsr-v2": ReferenceDataset(
            "ibsr-v2",
            "T1 MRI",
            "https://www.nitrc.org/projects/ibsr/",
            "CMA manually guided expert tissue labels",
            (
                "release 2316 notice and original CMA "
                "research restrictions; authorized local ingestion"
            ),
        ),
    }
)
