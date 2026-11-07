"""Explicit, offline-by-default source-modeling command group."""

import json
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    help=("Template and participant EEG source modeling; anatomy fetch is explicit"),
    no_args_is_help=True,
)


def _echo_result(result: dict[str, object], output: Path) -> None:
    typer.echo(
        json.dumps(
            {
                "status": result.get("status", "complete"),
                "output": str(output),
                "summary": str(output / "summary.json"),
                "runtime_s": result.get("runtime_s", result.get("wall_s")),
            }
        )
    )


def _fail(exc: Exception) -> None:
    typer.echo(json.dumps({"status": "error", "error": str(exc)}), err=True)
    raise typer.Exit(1)


@app.command("inspect-template")
def inspect_template(template_dir: Path = Path("data/anatomy"), fetch: bool = False) -> None:
    """Inspect cached fsaverage hashes, or explicitly fetch large public assets."""
    from soma.source.template import Template

    try:
        template = Template(template_dir)
        typer.echo(json.dumps(template.fetch() if fetch else template.inspect(), indent=2))
    except Exception as exc:
        _fail(exc)


@app.command("forward")
def forward_command(
    subject: int = 1,
    run: int = 4,
    output: Path = Path("reports/source-forward"),
    data_dir: Path = Path("data/raw"),
    template_dir: Path = Path("data/anatomy"),
) -> None:
    """Compute/read an fsaverage EEG BEM forward; cached EDF and anatomy required."""
    from soma.source.workflow import RunReport, sealed_config, study_forward
    from soma.visualization.source import forward_figures

    try:
        config = sealed_config(Path("configs/source-modeling.yaml"))
        forward = study_forward(subject, run, data_dir, template_dir)
        report = RunReport(output, config, forward)
        forward_figures(output, forward)
        _echo_result(
            report.finish({"status": "complete", "diagnostics": forward.diagnostics()}), output
        )
    except Exception as exc:
        _fail(exc)


@app.command("simulate")
def simulate_command(
    config: Path = Path("configs/source-simulation.yaml"),
    output: Path = Path("reports/source-simulation"),
) -> None:
    """Run sealed cortical simulations with independent covariance training."""
    from soma.experiments.source_simulation import simulate

    try:
        _echo_result(simulate(config, output), output)
    except Exception as exc:
        _fail(exc)


@app.command("inverse")
def inverse_command(
    subject: int = 1,
    runs: Annotated[
        list[int] | None, typer.Option(help="Repeat: --runs 4 --runs 8 --runs 12")
    ] = None,
    output: Path = Path("reports/source-inverse"),
    data_dir: Path = Path("data/raw"),
    template_dir: Path = Path("data/anatomy"),
) -> None:
    """Reconstruct subject 1 runs 4/8/12; trial-wise MNE/dSPM oscillatory power."""
    from soma.experiments.source_reconstruction import reconstruct

    try:
        result = reconstruct(
            output,
            subject=subject,
            runs=tuple(runs or [4, 8, 12]),
            data_dir=data_dir,
            template_dir=template_dir,
        )
        _echo_result(result, output)
    except Exception as exc:
        _fail(exc)


@app.command("resolution")
def resolution_command(
    config: Path = Path("configs/source-resolution.yaml"),
    output: Path = Path("reports/source-resolution"),
) -> None:
    """Compute selected signed PSFs/CTFs and white-mesh geodesic diagnostics."""
    from soma.experiments.source_resolution import analyze_resolution

    try:
        _echo_result(analyze_resolution(config, output), output)
    except Exception as exc:
        _fail(exc)


@app.command("benchmark")
def benchmark_command(output: Path = Path("reports/source-benchmark")) -> None:
    """Time an uncached BEM forward and export independent numerical benchmarks."""
    from soma.source.benchmark import benchmark

    try:
        result = benchmark(output)
        typer.echo(
            json.dumps(
                {"output": str(output), "fresh_forward_s": result["fresh_bem_forward_runtime_s"]}
            )
        )
    except Exception as exc:
        _fail(exc)


@app.command("build-individual")
def individual_command(
    config: Path = Path("configs/individual-source.yaml"),
    output: Path = Path("reports/individual-source"),
    meg_fallback: bool = False,
) -> None:
    """Matched MRI/EEG conditional research workflow; explicit MEG fallback is
    separately labeled."""
    try:
        if meg_fallback:
            from soma.source.meg_matched import build_meg_fallback

            value = build_meg_fallback(config, output)
        else:
            from soma.anatomy.workflow import build_individual_workflow

            value = build_individual_workflow(config, output)
        _echo_result(value, output)
    except Exception as exc:
        _fail(exc)


@app.command("uncertainty")
def uncertainty_command(
    config: Path = Path("configs/source-uncertainty.yaml"),
    output: Path = Path("reports/source-uncertainty"),
) -> None:
    """Recompute matched forwards for geometry/conductivity changes; fixed inverse policy."""
    from soma.anatomy.uncertainty import uncertainty_workflow

    try:
        _echo_result(uncertainty_workflow(config, output), output)
    except Exception as exc:
        _fail(exc)
