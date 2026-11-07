"""Explicit participant anatomy commands: no implicit real-data fetching."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer

app = typer.Typer(
    help="Matched participant anatomy, coregistration and conditional BEM readiness",
    no_args_is_help=True,
)
experiments = typer.Typer(help="Offline known-truth anatomical experiments")
app.add_typer(experiments, name="experiment")


def failure(exc: Exception) -> None:
    typer.echo(json.dumps({"status": "error", "error": str(exc)}), err=True)
    raise typer.Exit(1)


def result(value: dict[str, Any], output: Path) -> None:
    typer.echo(
        json.dumps(
            {
                "status": value.get("status"),
                "output": str(output),
                "summary": str(output / "summary.json"),
            }
        )
    )


@app.command("inspect")
def inspect_anatomy(
    dataset: str = "mne-sample",
    fetch: bool = False,
    discover: bool = False,
    subject: str = "sample",
    modality: str = "eeg",
) -> None:
    """Inspect cached sample assets; --fetch downloads. ds000117 --discover fetches
    metadata only."""
    try:
        if dataset == "mne-sample":
            from soma.datasets.matched import SampleAssets

            assets = SampleAssets(subject=subject)
            if fetch:
                assets.fetch()
            typer.echo(json.dumps(assets.inspect(modality=modality), indent=2))
        elif dataset == "ds000117":
            from soma.datasets.openneuro import discover_ds000117, selected_inventory

            cache = Path("data/raw/ds000117/metadata/discovery.json")
            if not cache.exists() and not discover:
                raise FileNotFoundError("Use --discover for explicit ds000117 metadata discovery")
            data = discover_ds000117(refresh=discover)
            if subject == "sample":
                typer.echo(json.dumps({k: v for k, v in data.items() if k != "files"}, indent=2))
            else:
                typer.echo(json.dumps(selected_inventory(data, subject), indent=2))
        else:
            raise ValueError("Supported anatomy datasets: mne-sample, ds000117")
    except Exception as exc:
        failure(exc)


@app.command("fetch-selected")
def fetch_selected_command(
    subject: str,
    files: Annotated[
        list[str], typer.Option(help="Exact BIDS participant-relative path; repeat explicitly")
    ],
    maximum_MiB: int = 1024,
) -> None:
    """Explicit selected-subject ds000117 files, bounded bytes; no automatic full dataset."""
    from soma.datasets.openneuro import fetch_selected

    try:
        typer.echo(
            json.dumps(
                fetch_selected(subject, files, maximum_bytes=maximum_MiB * 1024**2), indent=2
            )
        )
    except Exception as exc:
        failure(exc)


@app.command("coregister")
def coregister_command(
    config: Path = Path("configs/coregistration.yaml"), output: Path = Path("reports/coreg")
) -> None:
    """Compare primary sample transform with SVD-derived fiducials and labeled headshape ICP."""
    from soma.anatomy.workflow import coregister_workflow

    try:
        result(coregister_workflow(config, output), output)
    except Exception as exc:
        failure(exc)


@app.command("validate-bem")
def validate_bem_command(
    config: Path = Path("configs/bem.yaml"), output: Path = Path("reports/bem-validation")
) -> None:
    """Write PASS/FAIL/INDETERMINATE per condition; never clinical certification."""
    from soma.anatomy.workflow import validate_bem_workflow

    try:
        result(validate_bem_workflow(config, output), output)
    except Exception as exc:
        failure(exc)


@app.command("watershed")
def watershed_command(subject: str, subjects_dir: Path) -> None:
    """Explicit optional MNE/FreeSurfer boundary generation, never overwrites existing products."""
    from soma.anatomy.surfaces import generate_watershed

    try:
        typer.echo(json.dumps(generate_watershed(subject, subjects_dir)))
    except Exception as exc:
        failure(exc)


@experiments.command("synthetic")
def synthetic_command(
    seed: int = 42,
    output: Path = Path("reports/anatomical-synthetic"),
    config: Path = Path("configs/source-uncertainty.yaml"),
) -> None:
    """Known rigid/sphere truth, independent analytical reference and Jacobian/MC comparison."""
    from soma.experiments.anatomical_synthetic import run_synthetic

    try:
        result(run_synthetic(output, seed=seed, config_path=config), output)
    except Exception as exc:
        failure(exc)


@app.command("audit-evidence")
def audit_evidence_command(
    config: Path = Path("configs/anatomical-evidence.yaml"),
    output: Path = Path("reports/anatomical-audit"),
) -> None:
    """Categorical anatomical evidence; unavailable truth remains INDETERMINATE."""
    from soma.reliability.workflows import evidence_study

    try:
        result(evidence_study(config, output), output)
    except Exception as exc:
        failure(exc)


@app.command("repair-audit")
def repair_audit_command(
    config: Path = Path("configs/mesh-repair.yaml"), output: Path = Path("reports/repair")
) -> None:
    from soma.benchmarks.imaging_workflows import repair_audit

    try:
        result(repair_audit(config, output), output)
    except Exception as exc:
        failure(exc)
