"""Actual protocol/replay commands; data files cannot execute arbitrary programs."""

import json
from pathlib import Path
from typing import Any

import typer

from soma.protocol.binding import Snapshot, conformance, example_protocol
from soma.protocol.model import Protocol, compare_protocols, read_seal, seal, write_seal
from soma.protocol.replay import compare, plan, read_execution, run, write_execution
from soma.results.io import read_json
from soma.workflow.model import Graph
from soma.workflow.privacy import redact_export

protocol_app = typer.Typer(
    help="Versioned local scientific protocols; not independent preregistration"
)
replay_app = typer.Typer(help="Explicit bounded exact/controlled/exploratory descriptive replay")


def emit(value: Any) -> None:
    typer.echo(json.dumps(redact_export(value), indent=2, allow_nan=False))


@protocol_app.command("example")
def example(family: str, output: Path) -> None:
    p = example_protocol(family)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(p.document(), stream, indent=2)


@protocol_app.command("validate")
def validate(path: Path) -> None:
    p = Protocol.from_dict(read_json(path))
    emit(
        {
            "status": "VALID_DECLARATIONS",
            "protocol_fingerprint": p.fingerprint,
            "independent_registration_verified": False,
        }
    )


@protocol_app.command("seal")
def sealing(path: Path, output: Path) -> None:
    value = seal(Protocol.from_dict(read_json(path)))
    write_seal(value, output)
    emit(value.record()["validation_receipt"])


@protocol_app.command("compare")
def compare_protocol(left: Path, right: Path) -> None:
    emit(compare_protocols(read_seal(left).protocol, read_seal(right).protocol))


@protocol_app.command("audit")
def audit(path: Path, workflow: Path) -> None:
    result = conformance(read_seal(path).protocol, Graph.from_dict(read_json(workflow)))
    emit(result)
    if result["status"] != "CONFORMANT":
        raise typer.Exit(2)


@replay_app.command("plan")
def planning(
    protocol: Path,
    snapshot: Path,
    mode: str = "EXACT",
    reference: Path | None = None,
    cache_root: Path = Path("reports/protocol-cache"),
) -> None:
    from typing import cast

    from soma.protocol.replay import Mode

    emit(
        plan(
            read_seal(protocol),
            Snapshot.from_dict(read_json(snapshot)),
            mode=cast(Mode, mode),
            reference=read_execution(reference) if reference else None,
            cache_root=cache_root,
        )
    )


@replay_app.command("run")
def execute(
    protocol: Path,
    snapshot: Path,
    output: Path,
    sequence: int,
    mode: str = "EXACT",
    reference: Path | None = None,
    cache_root: Path = Path("reports/protocol-cache"),
    dry_run: bool = False,
) -> None:
    from typing import cast

    from soma.protocol.replay import Mode

    if dry_run:
        planning(protocol, snapshot, mode, reference, cache_root)
        return
    result = run(
        read_seal(protocol),
        Snapshot.from_dict(read_json(snapshot)),
        cache_root,
        sequence=sequence,
        mode=cast(Mode, mode),
        reference=read_execution(reference) if reference else None,
    )
    write_execution(result, output)
    r = result.record()
    emit(
        {
            "status": r["status"],
            "interpretation": r["interpretation"],
            "replay_assessment": r["replay_assessment"],
        }
    )
    if r["status"] != "COMPLETE" or r["replay_assessment"].get("authorized") is False:
        raise typer.Exit(2)


@replay_app.command("compare")
def compare_executions(left: Path, right: Path, mode: str = "EXACT") -> None:
    from typing import cast

    from soma.protocol.replay import Mode

    result = compare(read_execution(left), read_execution(right), mode=cast(Mode, mode))
    emit(result)
    if not result["authorized"]:
        raise typer.Exit(2)


@replay_app.command("drift")
def drift(left: Path, right: Path, mode: str = "CONTROLLED") -> None:
    from typing import cast

    from soma.protocol.replay import Mode

    emit(compare(read_execution(left), read_execution(right), mode=cast(Mode, mode)))
