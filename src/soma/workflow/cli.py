"""Explicit allowlisted workflows; inspection/navigation never execute stages."""

import json
from pathlib import Path
from typing import Any

import typer

from soma.results.io import read_json
from soma.workflow.examples import example
from soma.workflow.model import Graph, WorkflowError, invalidation
from soma.workflow.operations import builtins
from soma.workflow.privacy import redact_export
from soma.workflow.runtime import Executor

app = typer.Typer(help="Inspect, execute and verify explicit bounded scientific workflows")


def read_graph(path: Path) -> Graph:
    value = read_json(path)
    graph = Graph.from_dict(
        value["graph"] if value.get("schema") == "soma.workflow.run/1" else value
    )
    builtins().validate(graph)
    return graph


def emit(value: Any) -> None:
    typer.echo(json.dumps(redact_export(value), allow_nan=False, indent=2))


@app.command("example")
def make_example(family: str, output: Path) -> None:
    graph = example(family)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(graph.to_dict(), stream, indent=2)


@app.command("inspect")
def inspect(path: Path) -> None:
    emit(read_graph(path).to_dict())


@app.command("validate")
def validate(path: Path) -> None:
    graph = read_graph(path)
    emit(
        {
            "status": "VALID",
            "stages": [s.id for s in graph.order()],
            "scientific_validity": "NOT_ESTABLISHED",
        }
    )


@app.command("plan")
def plan(path: Path, cache_root: Path = Path("reports/workflow-cache")) -> None:
    emit(Executor(builtins(), cache_root).plan(read_graph(path)))


@app.command("run")
def run(
    path: Path,
    cache_root: Path = Path("reports/workflow-cache"),
    record: Path | None = None,
    input_root: Path | None = None,
    dry_run: bool = False,
) -> None:
    graph = read_graph(path)
    executor = Executor(builtins(), cache_root)
    if record is not None and record.resolve() == path.resolve():
        raise WorkflowError("Run journal cannot overwrite workflow source")
    result = (
        executor.plan(graph)
        if dry_run
        else executor.run(graph, input_root=input_root, record=record)
    )
    emit(result)
    if result.get("status") in {"FAILED", "CANCELLED"}:
        raise typer.Exit(2)


@app.command("resume")
def resume(
    path: Path,
    cache_root: Path = Path("reports/workflow-cache"),
    record: Path | None = None,
    input_root: Path | None = None,
    dry_run: bool = False,
) -> None:
    run(path, cache_root, record, input_root, dry_run)


@app.command("explain-cache")
def explain(
    path: Path, cache_root: Path = Path("reports/workflow-cache"), previous: Path | None = None
) -> None:
    graph = read_graph(path)
    result = Executor(builtins(), cache_root).plan(graph)
    if previous is not None:
        result["invalidation"] = invalidation(read_graph(previous), graph)
    emit(result)


@app.command("lineage")
def lineage(path: Path, node: str, downstream: bool = False) -> None:
    graph = read_graph(path)
    found = graph.lineage(node, downstream=downstream)
    found["declarations"] = graph.to_dict()
    emit(found)


@app.command("verify")
def verify(path: Path, cache_root: Path = Path("reports/workflow-cache")) -> None:
    result = Executor(builtins(), cache_root).plan(read_graph(path))
    emit(result)
    if any(s["status"] != "VERIFIED_HIT" for s in result["stages"]):
        raise typer.Exit(2)
