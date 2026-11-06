"""Command-line entry points. Downloads require an explicit fetch command."""

import json
from pathlib import Path
from typing import Annotated

import typer

from soma.datasets.eegbci import fetch, load_recording
from soma.datasets.registry import REGISTRY
from soma.eeg.analysis import analyze_recording
from soma.signal.experiments import synthetic_spectrum

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


if __name__ == "__main__":
    app()
