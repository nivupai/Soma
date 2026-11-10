"""Read-only artifact inspection and explicitly requested exclusive migration output."""

import json
from pathlib import Path

import typer

from soma.results.compatibility import compare_results
from soma.results.contracts import canonical, create_result, validate_result
from soma.results.io import inspect_result, load_result, save_result, verify_provenance
from soma.results.legacy import migrate_legacy

app = typer.Typer(help="Versioned scientific artifacts; format validity is not scientific validity")


def emit(value: object) -> None:
    typer.echo(json.dumps(value, indent=2, allow_nan=False))


@app.command("inspect")
def inspect(path: Path) -> None:
    emit(inspect_result(path))


@app.command("validate")
def validate(path: Path) -> None:
    value, arrays = load_result(path)
    emit(validate_result(value, arrays))


@app.command("compare")
def compare(left: Path, right: Path) -> None:
    a, _ = load_result(left)
    b, _ = load_result(right)
    result = compare_results(a, b)
    emit(result)
    if not result["compatible"]:
        raise typer.Exit(2)


@app.command("migrate")
def migrate(
    path: Path,
    source_format: str = typer.Option(...),
    channel: str | None = None,
    output: Path | None = None,
) -> None:
    value, arrays, receipt = migrate_legacy(path, source_format=source_format, channel=channel)
    # No output means dry-run. Historical sources are never overwritten.
    if output is not None:
        save_result(value, arrays, output)
    emit(receipt)


@app.command("verify-provenance")
def provenance(path: Path, input_root: Path | None = None) -> None:
    emit(verify_provenance(path, input_root=input_root))


@app.command("verify-reproducibility")
def reproducibility(output: Path) -> None:
    from soma.results.reproducibility import run_suite

    if output.exists():
        raise typer.BadParameter("Output must be new")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = run_suite()
    result = create_result(
        "experiment.manifest",
        {
            "computation": "soma.synthetic-reproducibility-v1",
            "inputs": {},
            "environment": {
                k: report[k]
                for k in [
                    "platform",
                    "architecture",
                    "python",
                    "dependencies",
                    "numerical_backends",
                ]
            },
            "assumptions": ["deterministic synthetic generators; independent mathematical oracles"],
            "validation": {c["case"]: c["passed"] for c in report["cases"]},
            "limitations": [
                "numerical equivalence is not statistical/anatomical/clinical validity"
            ],
        },
        values=report,
        interpretation_state="VALIDATED_NUMERICAL",
        provenance={"source": "controlled synthetic benchmark; no medical inputs"},
        method={"id": "soma.synthetic-reproducibility", "version": "1"},
        parameters={"GLM_seed": 17042},
        units={},
        dataset_identity="synthetic-suite-v1",
        subject_identity=None,
        spatial_reference=None,
        temporal_reference=None,
        statistical_estimand="numerical error against declared references",
    )
    with output.open("xb") as stream:
        stream.write(canonical(result) + b"\n")
    emit(result)
