"""Command-line entry points. Downloads require an explicit fetch command."""

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from soma.datasets.eegbci import fetch, load_recording
from soma.datasets.registry import REGISTRY
from soma.eeg.analysis import analyze_recording
from soma.signal.experiments import synthetic_spectrum

if TYPE_CHECKING:
    from soma.eeg.motor_imagery import MotorImageryConfig

app = typer.Typer(help="Soma scientific computing foundation", no_args_is_help=True)
datasets = typer.Typer(help="List metadata or fetch explicitly selected recordings")
eeg = typer.Typer(help="Inspect cached EEG and produce descriptive analyses")
experiments = typer.Typer(help="Reproducible signal laboratories")
app.add_typer(datasets, name="datasets")
app.add_typer(eeg, name="eeg")
app.add_typer(experiments, name="experiments")
DataDir = Annotated[Path, typer.Option(help="Raw dataset root", envvar="SOMA_DATA_DIR")]


def fail(exc: Exception) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(1)


@datasets.command("list")
def list_datasets() -> None:
    """List registered datasets, sampling metadata, citations and licenses."""
    for item in REGISTRY.values():
        typer.echo(
            f"{item.identifier}: {item.modality}, {item.eeg_channels} channels, "
            f"{item.sampling_hz:g} Hz\n{item.source}\n{item.license}\n{item.citation}"
        )


@datasets.command("fetch")
def fetch_dataset(
    identifier: str,
    subjects: Annotated[list[int], typer.Option(help="Subject; repeat for multiple")],
    runs: Annotated[list[int], typer.Option(help="Run; repeat for multiple")],
    data_dir: DataDir = Path("data/raw"),
) -> None:
    """Download only selected subjects × runs. Existing cached files are reused."""
    try:
        if identifier not in REGISTRY:
            raise ValueError(f"Unknown dataset {identifier!r}")
        for path in fetch(data_dir, subjects, runs):
            typer.echo(str(path))
    except Exception as exc:
        fail(exc)


@eeg.command("inspect")
def inspect_eeg(subject: int = 1, run: int = 4, data_dir: DataDir = Path("data/raw")) -> None:
    """Validate a cached EDF and print sensor and event metadata; never downloads."""
    try:
        raw, metadata = load_recording(data_dir, subject, run)
        typer.echo(json.dumps(metadata, indent=2))
        raw.close()
    except Exception as exc:
        fail(exc)


@eeg.command("analyze")
def analyze_eeg(
    subject: int = 1,
    run: int = 4,
    data_dir: DataDir = Path("data/raw"),
    output: Path = Path("reports/eeg-s001-r04"),
) -> None:
    """Save whole-record motor-channel PSD, band powers, figures and provenance."""
    try:
        analyze_recording(data_dir, subject, run, output)
        typer.echo(f"Saved analysis to {output}")
    except Exception as exc:
        fail(exc)


@experiments.command("synthetic-spectrum")
def run_synthetic(output: Path = Path("reports/synthetic-spectrum"), seed: int = 42) -> None:
    """Generate six deterministic signals and save spectral benchmarks."""
    try:
        synthetic_spectrum(output, seed)
        typer.echo(f"Saved experiment to {output}")
    except Exception as exc:
        fail(exc)


def _motor_config(
    path: Path | None,
    baseline: str | None,
    reference: str | None,
    no_plots: bool,
    synthetic: bool = False,
) -> "MotorImageryConfig":
    from soma.eeg.epoching import EpochConfig
    from soma.eeg.motor_imagery import MotorImageryConfig
    from soma.eeg.preprocessing import PreprocessingConfig
    from soma.eeg.quality import QualityConfig
    from soma.eeg.timefrequency import MorletConfig

    values = {} if path is None else json.loads(path.read_text())
    for name, constructor in (
        ("preprocessing", PreprocessingConfig),
        ("quality", QualityConfig),
        ("analysis", EpochConfig),
        ("context", EpochConfig),
        ("matched_reference", EpochConfig),
        ("morlet", MorletConfig),
    ):
        if name in values:
            if name == "morlet" and "frequencies" in values[name]:
                values[name]["frequencies"] = tuple(values[name]["frequencies"])
            values[name] = constructor(**values[name])
    if "channels" in values:
        values["channels"] = tuple(values["channels"])
    if synthetic and "preprocessing" not in values:
        values["preprocessing"] = PreprocessingConfig(reference="none")
    cfg = MotorImageryConfig(**values)
    if baseline is not None:
        cfg = replace(cfg, baseline=baseline)
    if reference is not None:
        cfg = replace(cfg, preprocessing=replace(cfg.preprocessing, reference=reference))
    return replace(cfg, plots=False) if no_plots else cfg


@eeg.command("motor-imagery")
def run_motor_imagery(
    runs: Annotated[list[int], typer.Option(help="Imagery run; repeat for 4, 8, 12")],
    subject: int = 1,
    data_dir: DataDir = Path("data/raw"),
    output: Path = Path("reports/motor-imagery-s1"),
    config: Annotated[Path | None, typer.Option(help="Scientific settings JSON")] = None,
    baseline: Annotated[str | None, typer.Option(help="none, condition_rest, matched_rest")] = None,
    reference: Annotated[str | None, typer.Option(help="none or average")] = None,
    no_plots: Annotated[bool, typer.Option("--no-plots", help="Skip figure exports")] = False,
) -> None:
    """Analyze cached unilateral imagery runs with explicit QC and rest references."""
    from soma.eeg.motor_imagery import motor_imagery

    try:
        cfg = _motor_config(config, baseline, reference, no_plots)
        motor_imagery(data_dir, subject, runs, output, cfg)
        typer.echo(f"Saved motor imagery analysis to {output}")
    except Exception as exc:
        fail(exc)


@experiments.command("event-locked")
def run_event_locked(
    output: Path = Path("reports/event-locked"),
    seed: int = 42,
    artifacts: bool = False,
    config: Path | None = None,
    no_plots: Annotated[bool, typer.Option("--no-plots", help="Skip figure exports")] = False,
) -> None:
    """Run the motor imagery pipeline on known synthetic suppression; reference=none."""
    from soma.eeg.motor_imagery import motor_imagery

    try:
        cfg = _motor_config(config, None, None, no_plots, synthetic=True)
        motor_imagery(
            Path("data/raw"),
            1,
            [4],
            output,
            cfg,
            synthetic_seed=seed,
            synthetic_artifacts=artifacts,
        )
        typer.echo(f"Saved event-locked laboratory to {output}")
    except Exception as exc:
        fail(exc)


def _structured_fail(exc: Exception) -> None:
    typer.echo(
        json.dumps({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}),
        err=True,
    )
    raise typer.Exit(1)


@eeg.command("cohort")
def eeg_cohort(
    subjects: Annotated[list[int], typer.Option(help="Repeat --subjects for each participant")],
    runs: Annotated[list[int], typer.Option(help="Repeat --runs for 4, 8, 12")],
    output: Path = Path("reports/cohort"),
    data_dir: DataDir = Path("data/raw"),
    config: Path | None = None,
    cache_dir: Path = Path("data/derived/cohort-cache"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Analyze explicitly selected cached subjects/runs; report partial completion as JSON."""
    from soma.experiments.cohort import run_cohort
    from soma.experiments.config import CohortConfig, config_from_dict, read_config

    try:
        cfg = config_from_dict(read_config(config)) if config else CohortConfig()
        cfg = replace(
            cfg, subjects=tuple(subjects), runs=tuple(runs), plots=False if no_plots else cfg.plots
        )
        result = run_cohort(data_dir, output, cfg, cache_dir)
        typer.echo(json.dumps(result))
        if not result["complete"]:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _structured_fail(exc)


@eeg.command("sensitivity")
def eeg_sensitivity(
    config: Annotated[Path, typer.Option(help="Predefined sensitivity design YAML/JSON")],
    output: Path = Path("reports/sensitivity"),
    data_dir: DataDir = Path("data/raw"),
    cache_dir: Path = Path("data/derived/cohort-cache"),
) -> None:
    """Run a predefined one-factor-at-a-time design from YAML/JSON; never downloads."""
    from soma.experiments.config import read_config
    from soma.experiments.sensitivity import run_sensitivity

    try:
        result = run_sensitivity(data_dir, output, read_config(config), cache_dir)
        typer.echo(json.dumps(result))
        if result.get("status") == "failed":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _structured_fail(exc)


@eeg.command("bursts")
def eeg_bursts(
    runs: Annotated[list[int], typer.Option(help="Repeat --runs for each imagery recording")],
    subject: int = 1,
    output: Path = Path("reports/bursts"),
    data_dir: DataDir = Path("data/raw"),
    cache_dir: Path = Path("data/derived/cohort-cache"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Continuous mu/beta bursts plus spectral comparisons; same cohort cache and provenance."""
    from soma.experiments.cohort import run_cohort
    from soma.experiments.config import CohortConfig

    try:
        result = run_cohort(
            data_dir,
            output,
            CohortConfig(subjects=(subject,), runs=tuple(runs), plots=not no_plots),
            cache_dir,
        )
        typer.echo(json.dumps(result))
        if not result["complete"]:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _structured_fail(exc)


@experiments.command("cohort-synthetic")
def synthetic_cohort(
    output: Path = Path("reports/cohort-synthetic"),
    seed: int = 42,
    missing: bool = False,
    artifacts: bool = False,
    cache_dir: Path = Path("data/derived/cohort-cache"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Five subjects × three runs with seeded individual effects, noise and known bursts."""
    from soma.experiments.cohort import run_cohort
    from soma.experiments.config import CohortConfig

    try:
        cfg = CohortConfig(
            synthetic_seed=seed,
            synthetic_missing=missing,
            synthetic_artifacts=artifacts,
            plots=not no_plots,
        )
        result = run_cohort(Path("data/raw"), output, cfg, cache_dir)
        typer.echo(json.dumps(result))
        if not result["complete"]:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _structured_fail(exc)


@experiments.command("benchmark")
def run_benchmark(output: Path = Path("reports/benchmark"), seed: int = 42) -> None:
    """Measure run/TFR/memory costs, cold/warm cache and a three-variant sensitivity sweep."""
    from soma.experiments.benchmark import benchmark

    try:
        typer.echo(json.dumps(benchmark(output, seed)))
    except Exception as exc:
        _structured_fail(exc)


@experiments.command("uncertainty-validation")
def run_coverage(
    output: Path = Path("reports/uncertainty-validation"),
    seed: int = 42,
    repetitions: int = 200,
    n_subjects: int = 40,
    n_bootstrap: int = 1000,
) -> None:
    """Repeated subject simulations to measure percentile-bootstrap coverage."""
    from soma.experiments.benchmark import uncertainty_validation

    try:
        typer.echo(
            json.dumps(uncertainty_validation(output, seed, repetitions, n_subjects, n_bootstrap))
        )
    except Exception as exc:
        _structured_fail(exc)


if __name__ == "__main__":
    app()
