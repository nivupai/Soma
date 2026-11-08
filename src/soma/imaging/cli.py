"""Offline-by-default MRI operations with explicit physical geometry."""

import json
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import typer

app = typer.Typer(
    help="MRI geometry, registration and anatomical candidate surfaces", no_args_is_help=True
)
experiments = typer.Typer(help="Deterministic synthetic or explicit real MRI experiments")
app.add_typer(experiments, name="experiment")


def _fail(exc: Exception) -> None:
    typer.echo(json.dumps({"status": "error", "error": str(exc)}), err=True)
    raise typer.Exit(1)


def _done(result: dict[str, Any], output: Annotated[Path, typer.Option()]) -> None:
    typer.echo(
        json.dumps(
            {
                "status": result.get("status", "complete"),
                "output": str(output),
                "summary": str(output / "summary.json"),
            }
        )
    )


@app.command("inspect")
def inspect_command(
    input: Annotated[Path, typer.Option()], frame: int | None = None, policy: str = "error"
) -> None:
    """Inspect lazy NIfTI metadata; explicit policy handles conflicting/uncoded forms."""
    from soma.imaging.nifti import load_nifti

    try:
        v = load_nifti(
            input, frame=frame, policy=cast(Literal["error", "nibabel", "qform", "sform"], policy)
        )
        typer.echo(json.dumps({"geometry": v.geometry(), "metadata": v.metadata}, indent=2))
    except Exception as exc:
        _fail(exc)


@app.command("validate")
def validate_command(
    input: Annotated[Path, typer.Option()], frame: int | None = None, policy: str = "error"
) -> None:
    """Validate header/grid metadata, physical round trips and finite voxel data."""
    from soma.imaging.nifti import load_nifti
    from soma.imaging.validation import validate_volume

    try:
        result = validate_volume(
            load_nifti(
                input,
                frame=frame,
                policy=cast(Literal["error", "nibabel", "qform", "sform"], policy),
            ),
            check_data=True,
        )
        typer.echo(json.dumps(result, indent=2))
        if not result["valid"]:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(exc)


@app.command("resample")
def resample_command(
    input: Annotated[Path, typer.Option()],
    reference: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    order: int = 1,
    labels: bool = False,
    allow_repeated: bool = False,
) -> None:
    """Pull input onto reference geometry; labels require --order 0; no source overwrite."""
    from soma.imaging.nifti import load_nifti, save_nifti
    from soma.imaging.reporting import ImagingReport
    from soma.imaging.resampling import resample

    try:
        source = load_nifti(input, kind="labels" if labels else "intensity")
        target = load_nifti(reference)
        report = ImagingReport(
            output,
            {"order": order, "reference": target.geometry(), "reference_source": target.metadata},
            source=source.metadata,
        )
        result = resample(source, target, order=order, allow_repeated=allow_repeated)
        save_nifti(result, output / "resampled.nii.gz")
        _done(
            report.finish(
                {
                    "status": "complete",
                    "geometry": result.geometry(),
                    "resampling": result.metadata["resampling"],
                }
            ),
            output,
        )
    except Exception as exc:
        _fail(exc)


@app.command("register")
def register_command(
    fixed: Annotated[Path, typer.Option()],
    moving: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    mode: str = "rigid",
    metric: str = "meansquares",
    iterations: int = 300,
) -> None:
    """Estimate fixed→moving RAS metres; completion is not anatomical validation."""
    from soma.imaging.nifti import load_nifti, save_nifti
    from soma.imaging.registration import RegistrationConfig, register
    from soma.imaging.reporting import ImagingReport

    try:
        f, m = load_nifti(fixed), load_nifti(moving)
        report = ImagingReport(
            output,
            {"mode": mode, "metric": metric, "iterations": iterations},
            source={"fixed": f.metadata, "moving": m.metadata},
        )
        result = register(
            f,
            m,
            RegistrationConfig(
                mode=cast(Literal["rigid", "affine"], mode),
                metric=cast(Literal["meansquares", "correlation", "mutual_information"], metric),
                iterations=iterations,
            ),
        )
        result.save(output / "transform")
        save_nifti(result.warp(m, f), output / "registered.nii.gz")
        _done(report.finish({"status": "complete", **result.diagnostics}), output)
    except Exception as exc:
        _fail(exc)


@app.command("surfaces")
def surfaces_command(
    mask: Annotated[Path, typer.Option()], output: Annotated[Path, typer.Option()], label: int = 1
) -> None:
    """Extract a physical RAS surface and validate topology/intersections; no BEM solver."""
    import numpy as np

    from soma.imaging.mesh_quality import mesh_quality
    from soma.imaging.nifti import load_nifti
    from soma.imaging.reporting import ImagingReport
    from soma.imaging.surfaces import extract_surface

    try:
        volume = load_nifti(mask, kind="labels")
        report = ImagingReport(output, {"label": label}, source=volume.metadata)
        mesh = extract_surface(volume, label=label)
        quality = mesh_quality(mesh)
        np.savez_compressed(
            output / "surface.npz", vertices_RAS_m=mesh.vertices.xyz, faces=mesh.faces
        )
        _done(report.finish({"status": "complete", **quality}), output)
    except Exception as exc:
        _fail(exc)


@experiments.command("synthetic")
def synthetic_command(
    output: Annotated[Path, typer.Option()],
    seed: int = 42,
    config: Path = Path("configs/mri-geometry.yaml"),
) -> None:
    """Known-transform phantoms, segmentation truth and nested-shell validation."""
    from soma.experiments.mri_geometry import synthetic_experiment

    try:
        _done(synthetic_experiment(output, seed=seed, config_path=config), output)
    except Exception as exc:
        _fail(exc)


@experiments.command("real")
def real_command(
    output: Annotated[Path, typer.Option()],
    dataset: str = "spm-auditory",
    fetch: bool = False,
    config: Path = Path("configs/mri-geometry.yaml"),
) -> None:
    """Cached structural MRI demonstration; --fetch retrieves only anatomical archive bytes."""
    from soma.experiments.mri_geometry import real_experiment

    try:
        _done(real_experiment(output, dataset=dataset, fetch=fetch, config_path=config), output)
    except Exception as exc:
        _fail(exc)


@app.command("benchmark")
def benchmark_command(
    input: Annotated[Path, typer.Option()], output: Annotated[Path, typer.Option()]
) -> None:
    """Profile real-image lazy/eager memory, transforms, resampling and geometry."""
    from soma.imaging.benchmark import benchmark

    try:
        _done(benchmark(input, output), output)
    except Exception as exc:
        _fail(exc)


references = typer.Typer(help="Official imaging references; downloads are explicit")
app.add_typer(references, name="references")


@references.command("list")
def reference_list() -> None:
    """List reference types without network access."""
    from dataclasses import asdict

    from soma.datasets.registry import REFERENCE_REGISTRY

    typer.echo(
        json.dumps({name: asdict(item) for name, item in REFERENCE_REGISTRY.items()}, indent=2)
    )


@references.command("discover")
def reference_discover(fetch: bool = False) -> None:
    from soma.datasets.references import discover

    try:
        typer.echo(json.dumps(discover(fetch=fetch), indent=2))
    except Exception as exc:
        _fail(exc)


@references.command("fetch")
def reference_fetch(dataset: str = "brainweb") -> None:
    """Explicit frozen BrainWeb or selected NKI-RS-22-11 download; never entire collection."""
    from soma.datasets.references import fetch_brainweb, fetch_mindboggle

    try:
        if dataset == "brainweb":
            value = fetch_brainweb()
        elif dataset == "mindboggle-101":
            value = fetch_mindboggle()
        else:
            raise ValueError("Supported references: brainweb, mindboggle-101")
        typer.echo(json.dumps(value))
    except Exception as exc:
        _fail(exc)


@app.command("benchmark-segmentation")
def benchmark_segmentation(
    config: Path = Path("configs/segmentation-benchmark.yaml"),
    output: Path = Path("reports/segmentation"),
) -> None:
    from soma.benchmarks.imaging_workflows import segmentation_benchmark

    try:
        _done(segmentation_benchmark(config, output), output)
    except Exception as exc:
        _fail(exc)


@app.command("benchmark-surfaces")
def benchmark_surfaces(
    config: Path = Path("configs/surface-benchmark.yaml"), output: Path = Path("reports/surfaces")
) -> None:
    from soma.benchmarks.imaging_workflows import surface_benchmark

    try:
        _done(surface_benchmark(config, output), output)
    except Exception as exc:
        _fail(exc)


@references.command("inspect")
def inspect_external(dataset: str = "sci-head") -> None:
    import json

    from soma.datasets.external_anatomy import inspect_sci

    if dataset != "sci-head":
        _fail(ValueError("Supported external inspection dataset: sci-head"))
        return
    try:
        typer.echo(json.dumps(inspect_sci(), indent=2))
    except (ValueError, OSError) as exc:
        _fail(exc)


@app.command("benchmark-tissues")
def benchmark_tissues(
    config: Path = Path("configs/tissue-benchmark.yaml"),
    output: Path = Path("reports/tissue-benchmark"),
) -> None:
    from soma.validation.cohort import cohort_benchmark

    try:
        _done(cohort_benchmark(config, output), output)
    except (ValueError, OSError) as exc:
        _fail(exc)
