"""Explicit local data governance and opt-in public registration metadata."""

import json
from pathlib import Path

import typer

from soma.human.configuration import request
from soma.human.model import Identity
from soma.human.permissions import PermissionEvidence, check_permission
from soma.human.registration import inspect_registration, verify_registration
from soma.human.workflow import plan, run
from soma.protocol.model import read_seal
from soma.results.io import read_json
from soma.workflow.privacy import redact_export

data_app = typer.Typer(help="Inspect configured local dataset identity and use evidence")
registration_app = typer.Typer(
    help="Read-only optional registration evidence; never registers a study"
)
human_app = typer.Typer(help="Permission-aware human descriptive pilot planning")


def emit(value: object) -> None:
    typer.echo(json.dumps(redact_export(value), indent=2, allow_nan=False))


@data_app.command("inspect")
def inspect(config: Path) -> None:
    _, selections, _, _ = request(config)
    emit(
        [
            {
                "identity": s.identity.document(),
                "identity_fingerprint": s.identity.fingerprint,
                "facts": s.facts(),
            }
            for s in selections
        ]
    )


@data_app.command("validate-identity")
def validate_identity(path: Path) -> None:
    value = Identity.from_dict(read_json(path))
    emit(
        {
            "status": "VALID_DECLARATIONS",
            "fingerprint": value.fingerprint,
            "human_identity_biometrically_verified": False,
        }
    )


@data_app.command("permissions")
def permissions(
    path: Path,
    source: Path,
    dataset: str,
    version: str,
    purpose: str = "methods_research",
    action: str = "analyze",
) -> None:
    emit(
        check_permission(
            PermissionEvidence.from_dict(read_json(path)),
            dataset=dataset,
            version=version,
            purpose=purpose,
            action=action,
            source_content=source.read_bytes(),
        )
    )


@data_app.command("protocol-check")
@human_app.command("plan")
def planning(config: Path) -> None:
    protocol, selections, permission, source = request(config)
    emit(plan(protocol, selections, permission, source))


@human_app.command("run")
def execute(config: Path, output: Path, cache: Path, sequence: int) -> None:
    protocol, selections, permission, source = request(config)
    record = run(
        protocol, selections, permission, source, cache=cache, output=output, sequence=sequence
    )
    emit({"status": record["status"], "interpretation": record["interpretation"]})
    if record["status"] != "COMPLETE":
        raise typer.Exit(2)


@registration_app.command("inspect")
def registration_inspect(path: Path, seal: Path) -> None:
    emit(inspect_registration(read_json(path), read_seal(seal).protocol))


@registration_app.command("verify")
def registration_verify(seal: Path, identifier: str, network: bool = False) -> None:
    emit(verify_registration(read_seal(seal).protocol, identifier, opt_in=network))
