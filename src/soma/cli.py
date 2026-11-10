"""Command-line entry points. Downloads require an explicit fetch command."""

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from soma.anatomy.cli import app as anatomy_app
from soma.datasets.eegbci import fetch, load_recording
from soma.datasets.registry import REGISTRY
from soma.eeg.analysis import analyze_recording
from soma.fmri.cli import app as fmri_app
from soma.fmri.cli import multimodal as multimodal_app
from soma.human.cli import data_app, human_app, registration_app
from soma.imaging.cli import app as mri_app
from soma.protocol.cli import protocol_app, replay_app
from soma.results.cli import app as results_app
from soma.signal.experiments import synthetic_spectrum
from soma.source.cli import app as source_app
from soma.workflow.cli import app as workflow_app

if TYPE_CHECKING:
    from soma.eeg.motor_imagery import MotorImageryConfig

app = typer.Typer(help="Soma scientific computing foundation", no_args_is_help=True)
datasets = typer.Typer(help="List metadata or fetch explicitly selected recordings")
eeg = typer.Typer(help="Inspect cached EEG and produce descriptive analyses")
experiments = typer.Typer(help="Reproducible signal laboratories")
app.add_typer(data_app, name="data")
app.add_typer(registration_app, name="registration")
app.add_typer(human_app, name="human-pilot")
app.add_typer(results_app, name="results")
app.add_typer(protocol_app, name="protocol")
app.add_typer(replay_app, name="replay")
app.add_typer(workflow_app, name="workflow")
app.add_typer(source_app, name="source")
app.add_typer(mri_app, name="mri")
app.add_typer(fmri_app, name="fmri")
app.add_typer(multimodal_app, name="multimodal")
app.add_typer(anatomy_app, name="anatomy")
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


stats = typer.Typer(help="Subject-level inference, influence and simulation calibration")
app.add_typer(stats, name="stats")


def _subject_selection(value: str | None, expand_all: bool = False) -> tuple[int, ...] | None:
    if value is None:
        return None
    if value == "all":
        if not expand_all:
            raise ValueError("Selecting all subjects requires --expand-all")
        return tuple(range(1, 110))
    if ":" in value:
        start, stop = map(int, value.split(":"))
        result = tuple(range(start, stop + 1))
    else:
        result = tuple(map(int, value.split(",")))
    if not result or len(set(result)) != len(result) or min(result) < 1 or max(result) > 109:
        raise ValueError("Subjects must be unique IDs in 1..109")
    if len(result) == 109 and not expand_all:
        raise ValueError("Selecting all subjects requires --expand-all")
    return result


@eeg.command("replicate")
def eeg_replicate(
    subjects: str | None = None,
    runs: Annotated[list[int] | None, typer.Option()] = None,
    config: Path = Path("configs/replication.yaml"),
    output: Path = Path("reports/m4-replication"),
    data_dir: DataDir = Path("data/raw"),
    cache_dir: Path = Path("data/derived/cohort-cache"),
    resume: bool = False,
    sensitivity: bool = False,
    expand_all: bool = False,
    fetch_data: Annotated[bool, typer.Option("--fetch")] = False,
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Run the sealed protocol; subject ranges are inclusive, e.g. 6:35."""
    from soma.experiments.replication import load_protocol, replicate, replication_sensitivity

    try:
        selected = _subject_selection(subjects, expand_all)
        protocol, _ = load_protocol(config)
        if fetch_data:
            fetch(
                data_dir,
                list(selected or protocol["cohort"]["subjects"]),
                runs or protocol["cohort"]["runs"],
            )
        runner = replication_sensitivity if sensitivity else replicate
        result = runner(
            data_dir,
            output,
            config,
            subjects=selected,
            runs=tuple(runs) if runs else None,
            cache_root=cache_dir,
            resume=resume,
            plots=not no_plots,
        )
        typer.echo(json.dumps(result))
        if result["status"] == "failed":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _structured_fail(exc)


@stats.command("calibrate")
def stats_calibrate(
    config: Path = Path("configs/calibration.yaml"),
    output: Path = Path("reports/m4-calibration"),
    workers: int = 1,
    resume: bool = False,
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Calibrate interval coverage with deterministic independent simulated datasets."""
    from soma.experiments.config import read_config
    from soma.simulations.calibration import CalibrationConfig, calibrate

    try:
        values = read_config(config)
        for key in ("scenarios", "subject_counts", "methods"):
            if key in values:
                values[key] = tuple(values[key])
        typer.echo(
            json.dumps(
                calibrate(
                    output,
                    CalibrationConfig(**values),
                    workers=workers,
                    resume=resume,
                    plots=not no_plots,
                )
            )
        )
    except Exception as exc:
        _structured_fail(exc)


@eeg.command("audit-reference")
def eeg_audit_reference(
    subjects: str = "1:5",
    runs: Annotated[list[int] | None, typer.Option()] = None,
    output: Path = Path("reports/m4-reference-audit"),
    data_dir: DataDir = Path("data/raw"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Audit cached reference covariance, shared trials, PSD and artifact examples."""
    from soma.eeg.reference_audit import audit_reference

    try:
        selected = _subject_selection(subjects)
        assert selected is not None
        typer.echo(
            json.dumps(
                audit_reference(
                    data_dir, output, selected, tuple(runs or (4, 8, 12)), plots=not no_plots
                )
            )
        )
    except Exception as exc:
        _structured_fail(exc)


@stats.command("influence")
def stats_influence(
    input_path: Annotated[Path, typer.Option("--input")],
    output: Path = Path("reports/m4-influence"),
    minimum_paired_runs: int | None = None,
) -> None:
    """Recompute subject/run influence and distinct weighting targets from saved tables."""
    from soma.statistics.robustness import run_influence

    try:
        typer.echo(json.dumps(run_influence(input_path, output, minimum_paired_runs)))
    except Exception as exc:
        _structured_fail(exc)


decode = typer.Typer(help="Leakage-auditable motor-imagery decoding and covariance geometry")
app.add_typer(decode, name="decode")


def _decode_development(
    mode: str,
    subjects: str,
    runs: list[int] | None,
    config: Path,
    output: Path,
    data_dir: Path,
    cache_dir: Path,
    no_plots: bool,
) -> None:
    from soma.decoding.workflows import run_development

    try:
        selected = _subject_selection(subjects)
        if selected is None or (runs is not None and sorted(runs) != [4, 8, 12]):
            raise ValueError("Decoding requires explicit development subjects and runs 4/8/12")
        result = run_development(
            data_dir, selected, config, output, mode, cache=cache_dir, plots=not no_plots
        )
        typer.echo(json.dumps(result))
        if result["status"] != "complete":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _structured_fail(exc)


@decode.command("within-subject")
def decode_within(
    subjects: str = "1:35",
    runs: Annotated[list[int] | None, typer.Option()] = None,
    config: Path = Path("configs/decoding.yaml"),
    output: Path = Path("reports/decoding-within"),
    data_dir: DataDir = Path("data/raw"),
    cache_dir: Path = Path("data/derived/decoding-trials"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Train on two runs; test each remaining run; never random trial CV."""
    _decode_development(
        "within-subject", subjects, runs, config, output, data_dir, cache_dir, no_plots
    )


@decode.command("cross-subject")
def decode_cross(
    subjects: str = "1:35",
    runs: Annotated[list[int] | None, typer.Option()] = None,
    config: Path = Path("configs/decoding.yaml"),
    output: Path = Path("reports/decoding-cross"),
    data_dir: DataDir = Path("data/raw"),
    cache_dir: Path = Path("data/derived/decoding-trials"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Nested subject-disjoint GroupKFold with training-only model selection."""
    _decode_development(
        "cross-subject", subjects, runs, config, output, data_dir, cache_dir, no_plots
    )


@decode.command("adaptation")
def decode_adaptation(
    subjects: str = "1:35",
    config: Path = Path("configs/decoding.yaml"),
    output: Path = Path("reports/decoding-adaptation"),
    data_dir: DataDir = Path("data/raw"),
    cache_dir: Path = Path("data/derived/decoding-trials"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Supply 0/4/8 labeled run-4 trials; evaluate only runs 8/12."""
    _decode_development("adaptation", subjects, None, config, output, data_dir, cache_dir, no_plots)


@decode.command("synthetic")
def decode_synthetic(
    seed: int = 42,
    config: Path = Path("configs/decoding.yaml"),
    output: Path = Path("reports/decoding-synthetic"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Known oscillatory mixtures and independent-label null; no network."""
    from soma.decoding.workflows import synthetic_workflow

    try:
        typer.echo(json.dumps(synthetic_workflow(config, output, seed, plots=not no_plots)))
    except Exception as exc:
        _structured_fail(exc)


@decode.command("development-suite")
def decode_suite(
    config: Path = Path("configs/decoding.yaml"),
    output: Path = Path("reports/m5-development"),
    data_dir: DataDir = Path("data/raw"),
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Run all development modes and 19 full nested permutation nulls, sharing trial features."""
    from soma.decoding.workflows import development_suite

    try:
        result = development_suite(data_dir, config, output, plots=not no_plots)
        typer.echo(json.dumps(result))
        if result["status"] != "complete":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _structured_fail(exc)


@decode.command("freeze-heldout")
def decode_freeze(
    verification: Annotated[Path, typer.Option(help="Passing current-code verification receipt")],
    config: Path = Path("configs/decoding.yaml"),
    development: Path = Path("reports/m5-development"),
    output: Path = Path("configs/decoding-frozen.yaml"),
    data_dir: DataDir = Path("data/raw"),
) -> None:
    """Seal development-only model choices before accessing prospective subjects."""
    from soma.decoding.workflows import freeze_heldout

    try:
        typer.echo(json.dumps(freeze_heldout(data_dir, config, development, output, verification)))
    except Exception as exc:
        _structured_fail(exc)


@decode.command("evaluate-heldout")
def decode_heldout(
    config: Annotated[
        Path, typer.Option(help="Separately frozen protocol and selected parameters")
    ],
    subjects: str = "36:65",
    output: Path = Path("reports/decoding-heldout"),
    data_dir: DataDir = Path("data/raw"),
    fetch_data: Annotated[bool, typer.Option("--fetch")] = False,
    no_plots: Annotated[bool, typer.Option("--no-plots")] = False,
) -> None:
    """Explicit prospective evaluation; validates freeze before any held-out fetch/read."""
    from soma.decoding.workflows import evaluate_heldout

    try:
        selected = _subject_selection(subjects)
        if selected is None:
            raise ValueError("Explicit prospective subjects required")
        result = evaluate_heldout(
            data_dir, config, selected, output, fetch_data=fetch_data, plots=not no_plots
        )
        typer.echo(json.dumps(result))
        if result["status"] != "complete":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _structured_fail(exc)


@decode.command("benchmark")
def decode_benchmark(
    output: Path = Path("reports/decoding-benchmark"),
    config: Path = Path("configs/decoding.yaml"),
    seed: int = 42,
) -> None:
    """Measure synthetic feature, matrix, CSP, geometry and nested evaluation stages."""
    from soma.decoding.benchmark import benchmark

    try:
        typer.echo(json.dumps(benchmark(output, config, seed)))
    except Exception as exc:
        _structured_fail(exc)


if __name__ == "__main__":
    app()


@experiments.command("anatomical-holdout")
def anatomical_holdout(
    config: Path = Path("configs/anatomical-holdout.yaml"), output: Path = Path("reports/holdout")
) -> None:
    from soma.validation.cohort import cohort_benchmark

    try:
        result = cohort_benchmark(config, output)
        typer.echo(json.dumps({"status": result["status"], "output": str(output)}, indent=2))
    except (ValueError, OSError) as exc:
        fail(exc)
