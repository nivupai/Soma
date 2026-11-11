"""Focused explicit-root benchmark commands; no shell, download or raw-result export."""

import json
from pathlib import Path
from typing import Any

import typer

from soma.eeg_benchmark.data import inventory
from soma.eeg_benchmark.protocol import benchmark_protocol, design
from soma.eeg_benchmark.report import (
    aggregate_export,
    compare,
    read_aggregate,
    save_aggregate,
    verify_execution,
)
from soma.eeg_benchmark.runner import run_benchmark
from soma.human.cli import emit
from soma.human.permissions import PermissionEvidence
from soma.protocol.model import closed, read_seal, write_seal
from soma.results.io import read_json

benchmark_app = typer.Typer(help="Focused scientific benchmarks; no clinical confirmation")
eeg_app = typer.Typer(help="Permission-aware cached EEGBCI decoding")
benchmark_app.add_typer(eeg_app, name="eeg")


def request(config: Path) -> tuple[dict[str, Any], bytes, PermissionEvidence]:
    d = read_json(config)
    closed(
        d,
        {
            "root",
            "key_file",
            "permission_file",
            "permission_source",
            "seal",
            "inventory",
            "output",
            "cache",
        },
    )
    key = bytes.fromhex(read_json(Path(d["key_file"]))["key_hex"])
    return d, key, PermissionEvidence.from_dict(read_json(Path(d["permission_file"])))


@eeg_app.command("plan")
def plan(config: Path, source_count: int = 35, target_count: int = 30) -> None:
    d, key, _ = request(config)
    p = design(source_count, target_count)
    inv = inventory(Path(d["root"]), p, key)
    destination = Path(d["inventory"])
    from soma.datasets.human_mri import safe_local_output

    safe_local_output(destination.parent)
    with destination.open("x") as stream:
        json.dump(inv, stream, indent=2)
    write_seal(benchmark_protocol(p, inv["fingerprint"]), Path(d["seal"]))
    emit(
        {
            "status": "SEALED_BEFORE_EVALUATION",
            "subjects": source_count + target_count,
            "recordings": len(inv["records"]),
            "inventory_fingerprint": inv["fingerprint"],
            "external_replication": False,
        }
    )


@eeg_app.command("run")
def execute(config: Path) -> None:
    d, key, permission = request(config)
    record = run_benchmark(
        read_seal(Path(d["seal"])),
        read_json(Path(d["inventory"])),
        Path(d["root"]),
        permission,
        Path(d["permission_source"]),
        key,
        Path(d["output"]),
        Path(d["cache"]),
    )
    emit(
        {
            "status": record["status"],
            "variants": len(record["variants"]),
            "confirmatory_claim_allowed": False,
        }
    )


@eeg_app.command("verify")
def verify(output: Path) -> None:
    emit(verify_execution(output))


@eeg_app.command("results")
def results(config: Path, output: Path | None = None) -> None:
    d, _, permission = request(config)
    aggregate = aggregate_export(
        Path(d["output"]), permission, Path(d["permission_source"]).read_bytes()
    )
    if output is not None:
        save_aggregate(aggregate, output)
    emit(aggregate)


@eeg_app.command("compare")
def comparison(left: Path, right: Path) -> None:
    emit(compare(read_aggregate(left), read_aggregate(right)))
