"""Offline-by-default commands: no implicit raw preprocessing or bulk downloads."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

app = typer.Typer(help="Task-fMRI modeling with explicit preprocessing and spatial provenance")
multimodal = typer.Typer(help="Descriptive regional comparison with identity safeguards")


def emit(value: Any) -> None:
    typer.echo(json.dumps(value, default=str))


def failure(exc: Exception) -> None:
    emit({"status": "failed", "diagnostic": str(exc)})
    raise typer.Exit(1)


@app.command("inspect")
def inspect(input: Annotated[Path, typer.Option()]) -> None:
    from soma.fmri.ingestion import inspect_functional

    try:
        emit(inspect_functional(input))
    except (ValueError, OSError) as exc:
        failure(exc)


@app.command("simulate")
def simulation(output: Annotated[Path, typer.Option()], seed: int = 13042) -> None:
    from soma.fmri.laboratory import laboratory

    try:
        result = laboratory(output, seed)
        emit({"status": result["status"], "output": str(output)})
    except (ValueError, OSError, RuntimeError) as exc:
        failure(exc)


@app.command("fit")
def fitting(
    config: Annotated[Path, typer.Option()], output: Annotated[Path, typer.Option()]
) -> None:
    from soma.fmri.workflows import fit_config

    try:
        result = fit_config(config, output)
        emit(
            {
                "status": result["status"],
                "preprocessing": result["preprocessing"],
                "output": str(output),
            }
        )
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        failure(exc)


@app.command("design")
def designing(
    config: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    input_config: Path = Path("configs/fmri-firstlevel.yaml"),
) -> None:
    from soma.core.provenance import write_json
    from soma.fmri.design import build_design
    from soma.fmri.workflows import configuration, load_spec
    from soma.pipeline.derivatives import private_output

    try:
        private_output(output)
        spec = yaml.safe_load(input_config.read_text())
        spec["preparation"] = str(output.parent / (output.name + "-input-preparation"))
        run, _, _, _ = load_spec(spec)
        design, report = build_design(run, configuration(config))
        output.mkdir(parents=True, exist_ok=False)
        design.to_csv(output / "design.tsv", sep="\t", index_label="time_s")
        write_json(output / "diagnostics.json", report)
        emit({"status": "complete", "rank": report["rank"], "output": str(output)})
    except (ValueError, OSError, KeyError) as exc:
        failure(exc)


@app.command("contrasts")
def contrasts(
    config: Annotated[Path, typer.Option()], output: Annotated[Path, typer.Option()]
) -> None:
    from soma.fmri.workflows import analyze, load_spec

    try:
        request = yaml.safe_load(config.read_text())
        spec = json.loads((Path(request["fit_report"]) / "input-spec.json").read_text())
        spec["contrast"] = request["contrast"]
        spec["weights"] = request.get("weights", {request["contrast"]: 1.0})
        spec["preparation"] = str(output.parent / (output.name + "-input-preparation"))
        run, cfg, definition, allow = load_spec(spec)
        result = analyze(
            run, cfg, definition, output, allow_unvalidated_demo=allow, input_spec=spec
        )
        emit(
            {"status": result["status"], "note": "refit original inputs; no pickled model loading"}
        )
    except (ValueError, OSError, KeyError) as exc:
        failure(exc)


@app.command("retest")
def retesting(
    config: Annotated[Path, typer.Option()], output: Annotated[Path, typer.Option()]
) -> None:
    from soma.core.provenance import write_json
    from soma.fmri.retest import retest
    from soma.fmri.workflows import estimate_spec
    from soma.pipeline.derivatives import private_output

    try:
        spec = yaml.safe_load(config.read_text())
        if "sessions" not in spec or len(spec["sessions"]) != 2:
            raise ValueError(
                "Two preprocessed session specifications required; raw ds000114 is insufficient"
            )
        result = retest(*[estimate_spec(s) for s in spec["sessions"]])
        private_output(output)
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "retest.json", result)
        emit({"status": "complete", "output": str(output)})
    except (ValueError, OSError, KeyError) as exc:
        failure(exc)


@multimodal.command("compare-roi")
def comparing(
    config: Annotated[Path, typer.Option()], output: Annotated[Path, typer.Option()]
) -> None:
    from soma.core.provenance import write_json
    from soma.fmri.spatial import compare_regions
    from soma.pipeline.derivatives import private_output

    try:
        spec = yaml.safe_load(config.read_text())
        result = compare_regions(spec["EEG"], spec["fMRI"], mode=spec["mode"])
        private_output(output)
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "comparison.json", result)
        emit(
            {
                "status": "complete",
                "mode": result["mode"],
                "physiological_equivalence_claimed": False,
            }
        )
    except (ValueError, OSError, KeyError) as exc:
        failure(exc)
