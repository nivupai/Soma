"""Strict declarative scientific configuration, separate from machine paths."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from soma.datasets.eegbci import validate_selection
from soma.eeg.epoching import EpochConfig
from soma.eeg.motor_imagery import MotorImageryConfig
from soma.eeg.preprocessing import PreprocessingConfig
from soma.eeg.quality import QualityConfig
from soma.eeg.timefrequency import MorletConfig
from soma.signal.bursts import BurstConfig
from soma.statistics.hierarchical import ResamplingConfig


def motor_config(values: dict[str, Any]) -> MotorImageryConfig:
    values = dict(values)
    for name, constructor in (
        ("preprocessing", PreprocessingConfig),
        ("quality", QualityConfig),
        ("analysis", EpochConfig),
        ("context", EpochConfig),
        ("matched_reference", EpochConfig),
        ("morlet", MorletConfig),
    ):
        if name in values:
            section = dict(values[name])
            for coordinate in ("reference_channels", "frequencies"):
                if coordinate in section:
                    section[coordinate] = tuple(section[coordinate])
            values[name] = constructor(**section)
    if "channels" in values:
        values["channels"] = tuple(values["channels"])
    return MotorImageryConfig(**values)


@dataclass(frozen=True)
class CohortConfig:
    subjects: tuple[int, ...] = (1, 2, 3, 4, 5)
    runs: tuple[int, ...] = (4, 8, 12)
    dataset: str = "eegmmidb"
    motor: MotorImageryConfig = field(default_factory=lambda: MotorImageryConfig(plots=False))
    bursts: BurstConfig = field(default_factory=BurstConfig)
    statistics: ResamplingConfig = field(default_factory=ResamplingConfig)
    plots: bool = True
    synthetic_seed: int | None = None
    synthetic_missing: bool = False
    synthetic_artifacts: bool = False

    def __post_init__(self) -> None:
        if (
            not self.subjects
            or not self.runs
            or len(set(self.subjects)) != len(self.subjects)
            or len(set(self.runs)) != len(self.runs)
            or self.dataset != "eegmmidb"
        ):
            raise ValueError(
                "Unique nonempty subjects/runs and registered eegmmidb dataset required"
            )
        for subject in self.subjects:
            for run in self.runs:
                validate_selection(subject, run)
                if run not in (4, 8, 12):
                    raise ValueError("Unilateral imagery runs must be 4, 8, 12")


def config_from_dict(values: dict[str, Any]) -> CohortConfig:
    values = dict(values)
    for field_name in ("subjects", "runs"):
        if field_name in values:
            values[field_name] = tuple(values[field_name])
    if "motor" in values:
        values["motor"] = motor_config(values["motor"])
    if "bursts" in values:
        burst = dict(values["bursts"])
        if "strategies" in burst:
            burst["strategies"] = tuple(burst["strategies"])
        values["bursts"] = BurstConfig(**burst)
    if "statistics" in values:
        values["statistics"] = ResamplingConfig(**values["statistics"])
    return CohortConfig(**values)


def read_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Configuration must be a mapping")
    return value


def scientific_dict(cfg: CohortConfig) -> dict[str, Any]:
    result = asdict(cfg)
    result.pop("plots")
    result["motor"].pop("plots")
    # Ordered input lists do not change the scientific selection or experiment identifier.
    result["subjects"], result["runs"] = sorted(cfg.subjects), sorted(cfg.runs)
    return result
