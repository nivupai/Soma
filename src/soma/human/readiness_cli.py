"""Explicit local evidence audit commands, without shell dispatch or pipeline execution."""

from pathlib import Path
from typing import Any

import typer

from soma.human.cli import emit, registration_app
from soma.human.configuration import request
from soma.human.evidence import read_bundle, verify_bundle
from soma.human.model import Identity
from soma.human.preprocessing import PreprocessingManifest, audit_manifest
from soma.human.readiness import execution_readiness, session_audit, write_readiness
from soma.human.registration import verify_attachment
from soma.protocol.model import closed, read_seal
from soma.results.io import read_json

evidence_app = typer.Typer(help="Inspect immutable references; never publishes private documents")
preprocessing_app = typer.Typer(help="Read-only explicitly rooted preprocessing evidence audits")
sessions_app = typer.Typer(help="Explicit dataset-scoped session integrity checks")
research_app = typer.Typer(help="Read-only scientific readiness, never inferential execution")


def references(path: Path) -> dict[str, tuple[Path, str]]:
    value = read_json(path)
    if len(value) > 128:
        raise ValueError("Bounded explicitly configured evidence references required")
    result = {}
    for key, spec in value.items():
        closed(spec, {"root", "path"})
        result[key] = (Path(spec["root"]), spec["path"])
    return result


@registration_app.command("verify-attachment")
def attachment(
    seal: Path,
    identifier: str,
    file: str,
    version: str,
    root: Path,
    relative: str,
    network: bool = False,
) -> None:
    from soma.human.evidence import local_file

    path = local_file(root, relative)
    if path.stat().st_size > 1024**2:
        raise ValueError("Protocol attachment exceeds1MiB bound")
    emit(
        verify_attachment(
            read_seal(seal).protocol, identifier, file, version, path.read_bytes(), opt_in=network
        )
    )


@evidence_app.command("inspect")
def inspect(path: Path) -> None:
    bundle = read_bundle(path)
    emit(
        {
            "fingerprint": bundle.fingerprint,
            "manifest": bundle.document(),
            "authority_verified": False,
        }
    )


@evidence_app.command("verify")
def verify(path: Path, config: Path) -> None:
    emit(verify_bundle(read_bundle(path), references(config)))


@preprocessing_app.command("audit")
def preprocessing(manifest: Path, config: Path, raw: Path, derivatives: Path) -> None:
    m = PreprocessingManifest.from_dict(read_json(manifest))
    _, selections, _, _ = request(config)
    matching = [
        s for s in selections if s.identity.fingerprint == m.document()["identity_fingerprint"]
    ]
    if len(matching) != 1:
        raise ValueError("Manifest must match exactly one selected recording")
    emit(audit_manifest(m, matching[0], {"raw": raw, "derivatives": derivatives}))


@sessions_app.command("validate")
def sessions(path: Path, chronology_required: bool = False) -> None:
    value = read_json(path)
    closed(value, {"identities"})
    emit(
        session_audit(
            [Identity.from_dict(d) for d in value["identities"]],
            chronology_required=chronology_required,
        )
    )


@research_app.command("readiness")
def readiness(config: Path, output: Path | None = None) -> None:
    cfg = read_json(config)
    closed(cfg, {"request", "bundle", "references", "preprocessing", "roots"})
    protocol, selections, permission, source = request(Path(cfg["request"]))
    manifests = [PreprocessingManifest.from_dict(read_json(Path(p))) for p in cfg["preprocessing"]]
    mapped = {m.document()["identity_fingerprint"]: m for m in manifests}
    if len(mapped) != len(manifests):
        raise ValueError("Duplicate preprocessing recording")
    roots: dict[str, Path] = {k: Path(v) for k, v in cfg["roots"].items()}
    report: dict[str, Any] = execution_readiness(
        protocol,
        selections,
        permission,
        source,
        read_bundle(Path(cfg["bundle"])),
        references(Path(cfg["references"])),
        manifests=mapped,
        roots=roots,
    )
    if output is not None:
        resolved = output.resolve()
        if any(resolved.is_relative_to(s.root.resolve()) for s in selections) or any(
            resolved.is_relative_to(root.resolve()) for root in roots.values()
        ):
            raise ValueError("Readiness output cannot modify an input root")
        write_readiness(report, output)
    emit(report)
