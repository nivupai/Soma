"""Opt-in M25 commands, using private requests and existing permission evidence."""

import json
from pathlib import Path
from typing import Any

from soma.human.cli import emit
from soma.human.evidence import read_bundle
from soma.human.permissions import PermissionEvidence
from soma.model_archive.archive import inspect_archive
from soma.protocol.model import read_seal, write_seal
from soma.results.io import read_json

from .acquisition import acquire, acquisition_template, gate, snapshot, validate_manifest
from .validation import (
    M24_RELEASE,
    execute,
    inspect_validation,
    read_validation,
    runtime_request,
    seal_validation,
)


def access(q: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        PermissionEvidence.from_dict(read_json(Path(q["permission"])))
        if q.get("permission")
        else None,
        Path(q["notice"]).read_bytes() if q.get("notice") else None,
        read_bundle(Path(q["bundle"])) if q.get("bundle") else None,
        {k: (Path(v["root"]), v["relative"]) for k, v in read_json(Path(q["references"])).items()}
        if q.get("references")
        else None,
    )


def acquisition_manifest(output: Path, dataset: str = "bnci2014-001") -> None:
    from soma.datasets.human_mri import safe_local_output

    safe_local_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(acquisition_template(dataset), stream, indent=2)
    emit({"status": "BLOCKED_UNTIL_VERIFIED_MANIFEST_AND_APPROVAL", "downloaded": 0})


def acquisition_run(request: Path) -> None:
    q = read_json(request)
    sealed = read_seal(Path(q["seal"]))
    v = inspect_validation(sealed)
    m = read_json(Path(q["manifest"]))
    fp = validate_manifest(m)
    if (
        v["dataset"] != m["dataset"]
        or sealed.protocol.document()["optional_metadata"]["manifest_fingerprint"] != fp
    ):
        raise ValueError("Acquisition/protocol manifest mismatch")
    p, n, b, refs = access(q)
    result = acquire(
        m, sealed.protocol.fingerprint, Path(q["root"]), Path(q["output"]), p, n, b, refs
    )
    emit(
        {
            "status": "SNAPSHOT_VERIFIED",
            "downloaded_files": result["downloaded_files"],
            "snapshot_fingerprint": result["snapshot_fingerprint"],
        }
    )


def snapshot_check(request: Path) -> None:
    q = read_json(request)
    m = read_json(Path(q["manifest"]))
    sealed = read_seal(Path(q["seal"]))
    p, n, b, refs = access(q)
    ready = gate(m, sealed.protocol.fingerprint, p, n, b, refs, acquisition=False)
    if ready["status"] != "READY":
        raise ValueError("Snapshot use is not authorized")
    emit(snapshot(Path(q["root"]), m))


def validation_plan(request: Path) -> None:
    q = read_json(request)
    m = read_json(Path(q["manifest"]))
    fp = validate_manifest(m, complete=False)
    release = inspect_archive(Path(q["archive"]), M24_RELEASE)
    sealed = seal_validation(fp, release["id"], m["dataset"], q.get("mode", "HARMONIZED_FROZEN"))
    write_seal(sealed, Path(q["seal"]))
    emit(
        {
            "status": "SEALED_BEFORE_EXTERNAL_OUTCOMES",
            "protocol_fingerprint": sealed.protocol.fingerprint,
            "scientific_compatibility": inspect_validation(sealed)["compatible"],
            "human_execution": "BLOCKED",
        }
    )


def validation_run(request: Path) -> None:
    import sys

    q = read_json(request)
    p, n, b, refs = access(q)
    d = execute(
        read_seal(Path(q["seal"])),
        read_json(Path(q["manifest"])),
        Path(q["root"]),
        Path(q["archive"]),
        Path(q.get("runtime_python", sys.executable)),
        Path(q["output"]),
        p,
        n,
        b,
        refs,
    )
    emit(
        {
            "status": d["status"],
            "human_external_trials": d["human_external_trials"],
            "blockers": d["blockers"],
            "performance": d["performance"],
        }
    )


def validation_verify(receipt: Path) -> None:
    d = read_validation(receipt)
    emit(
        {
            "status": "VERIFIED_AGGREGATE_INTEGRITY",
            "scientific_status": d["status"],
            "independent_replication": False,
        }
    )


def domain_shift(receipt: Path) -> None:
    emit(read_validation(receipt)["domain_shift"])


def verify_source_runtime(
    runtime_python: Path, archive: Path, permission: Path, notice: Path, output: Path
) -> dict[str, Any]:
    inspect_archive(archive, M24_RELEASE)
    result = runtime_request(
        runtime_python,
        {
            "operation": "verify-source",
            "archive": str(archive.resolve()),
            "release_id": M24_RELEASE,
            "permission": str(permission.resolve()),
            "notice": str(notice.resolve()),
        },
        output,
    )
    return {**result["envelope"]["payload"]["values"], "worker_sha256": result["worker_sha256"]}


def runtime_check(request: Path) -> None:
    q = read_json(request)
    emit(
        verify_source_runtime(
            Path(q["runtime_python"]),
            Path(q["archive"]),
            Path(q["permission"]),
            Path(q["notice"]),
            Path(q["output"]),
        )
    )
