"""Bounded, unit-bearing scientific contracts; no filesystem paths on the wire."""

from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class State(StrEnum):
    VALIDATED_NUMERICAL = "VALIDATED_NUMERICAL"
    DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"
    EXPLORATORY = "EXPLORATORY"
    INDETERMINATE = "INDETERMINATE"
    INVALID = "INVALID"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


T = TypeVar("T")


class Result(Strict, Generic[T]):
    dataset_id: str
    state: State
    synthetic: bool
    warnings: list[str]
    provenance: dict[str, Any]
    data: T


class Dataset(Strict):
    id: str
    label: str
    kind: str
    synthetic: bool
    state: State
    available: bool
    subjects: list[str] = []
    sessions: list[str] = []
    runs: list[str] = []


class Catalog(Strict):
    datasets: list[Dataset]
    version: str
    inference_policy: str


class EEGMeta(Strict):
    channels: list[str]
    fs_hz: float
    duration_s: float
    units: str = "V"
    reference: str
    events: list[dict[str, Any]]
    quality: list[str]


class EEGWindow(Strict):
    times_s: list[float]
    channels: list[str]
    values_V: list[list[float]]
    lower_V: list[list[float]]
    upper_V: list[list[float]]
    fs_hz: float
    display_only: bool = True
    start_sample: int
    stop_sample: int


class EEGAnalysis(Strict):
    channel: str
    frequencies_hz: list[float]
    density_V2_Hz: list[float]
    band_power_V2: dict[str, float]
    tf_times_s: list[float]
    tf_frequencies_hz: list[float]
    tf_power_V2: list[list[float]]
    bursts_s: list[list[float]]
    n_analysis_samples: int
    edge_guard_s: float


class VolumeMeta(Strict):
    shape: list[int]
    affine_mm: list[list[float]]
    spacing_mm: list[float]
    orientation: list[str]
    frame: str
    units: str
    intensity_range: list[float]
    oblique: bool
    labels: dict[str, str]
    transforms: list[dict[str, Any]] = []


class Slice(Strict):
    plane: str
    index: int
    width: int
    height: int
    values: list[list[float]]
    labels: list[list[int]] | None
    voxel: list[int]
    world_mm: list[float]
    label: int | None
    pixel_to_world_mm: list[list[float]]
    horizontal_labels: list[str]
    vertical_labels: list[str]
    stride: int
    overlay_units: str | None = None


class MeshData(Strict):
    vertices_mm: list[list[float]]
    faces: list[list[int]]
    values: list[float]
    points_mm: list[list[float]]
    electrode_points_mm: list[list[float]]
    frame: str
    units: str
    layers: list[str]
    qc: list[str]
    render_geometry: str
    diagnostics: dict[str, Any]


class SourceSeries(Strict):
    source_index: int
    times_s: list[float]
    values: list[float]
    units: str
    point_mm: list[float] | None
    point_spread: list[float] | None
    diagnostics: dict[str, Any] = {}


class Artifact(Strict):
    schema_name: str | None = None
    schema_version: str | None = None
    validation_status: str = "LEGACY_UNVERSIONED"
    migration_status: str = "NOT_APPLIED"
    result_envelope: dict[str, Any] | None = None
    state: State
    id: str
    title: str
    metrics: dict[str, Any]
    parameters: dict[str, Any]
    compatibility: dict[str, str]
    checksums: dict[str, str]
    figures: list[str]
    warnings: list[str]


class CompareRequest(Strict):
    ids: list[str] = Field(min_length=2, max_length=4)


class JobRequest(Strict):
    dataset_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    channel: str = Field(max_length=40)
    start_s: float = Field(ge=0, le=86400)
    duration_s: float = Field(ge=2, le=30)
    kind: str = Field(default="eeg-analysis", pattern=r"^eeg-analysis$")


class Job(Strict):
    id: str
    status: str
    progress: float
    error: str | None = None
    result: Result[EEGAnalysis] | None = None
    manifest: dict[str, Any] | None = None


class Comparison(Strict):
    compatible: bool
    artifacts: list[Artifact]


class QCReport(Strict):
    state: State
    human_preprocessing: State
    human_retest: State
    clinical_validity: bool
    warnings: list[str]
    inference_policy: str
